"""Index authorized NCERT-style PDFs from subject folders into shared course knowledge.

Run from backend/: python -m app.ingest_shared data
"""
import argparse
import hashlib
import pathlib
import re

from . import db, ingest
from .embeddings import embed_docs

NCERT_BOOK = re.compile(r"^([kl])e(mh|ph|ch|bo)\d", re.IGNORECASE)
NCERT_CHAPTER = re.compile(r"^([kl])e(mh|ph|ch|bo)(\d)(\d{2})", re.IGNORECASE)
SUBJECTS = {"mh": "maths", "ph": "physics", "ch": "chemistry", "bo": "biology"}
MIN_CHUNK_CHARS = 80
SECTION_MARKER = re.compile(
    r"(?i)^\s*(?:chapter|unit)\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s*$"
)
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def classify(path: pathlib.Path) -> tuple[str, str] | None:
    match = NCERT_BOOK.match(path.stem)
    if not match:
        return None
    grade = "XI" if match.group(1).lower() == "k" else "XII"
    subject = SUBJECTS[match.group(2).lower()]
    return subject, grade


def chapter_metadata(path: pathlib.Path, subject: str) -> tuple[int | None, str]:
    match = NCERT_CHAPTER.match(path.stem)
    if not match:
        return None, ""
    chapter_no = int(match.group(4))
    if subject == "chemistry" and int(match.group(3)) > 1:
        chapter_no += 6 * (int(match.group(3)) - 1)

    text = "\n".join(page_text for _, page_text in zip(range(3), _read_first_pages(path)))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        marker = SECTION_MARKER.match(line)
        if not marker:
            continue
        marker_number = marker.group(1).lower()
        chapter_no = NUMBER_WORDS.get(marker_number, int(marker_number) if marker_number.isdigit() else chapter_no)
        title_lines = []
        for candidate in lines[index + 1:index + 5]:
            if (
                re.match(r"(?i)^(after studying|learning objectives|contents|exercise|summary)\b", candidate)
                or re.match(r"^\d+(?:\.\d+)+\b", candidate)
                or re.fullmatch(r"[\W\d_]+", candidate)
            ):
                break
            title_lines.append(candidate)
            if candidate.endswith((".", "!", "?")):
                break
        title = re.sub(r"\s+", " ", " ".join(title_lines)).strip(" .:-")
        title = re.sub(r"(?i)^(?:strUctUre|classifiCation)\b", lambda m: m.group(0).title(), title)
        if title:
            return chapter_no, title[:160]

    return chapter_no, f"Chapter {chapter_no}"


def _read_first_pages(path: pathlib.Path):
    from pypdf import PdfReader

    yield from (
        page.extract_text() or ""
        for page in PdfReader(str(path)).pages[:3]
    )


def index_file(path: pathlib.Path, root: pathlib.Path) -> tuple[str, int]:
    classification = classify(path)
    if classification is None:
        return "unclassified", 0
    subject, grade = classification
    chapter_no, title = chapter_metadata(path, subject)
    source = path.relative_to(root).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    with db.pool.connection() as conn:
        same_source = conn.execute(
            """SELECT id, content_hash FROM course_documents
               WHERE subject = %s AND grade = %s AND source = %s""",
            (subject, grade, source),
        ).fetchone()
        if same_source and same_source["content_hash"] == digest:
            conn.execute(
                """UPDATE course_documents SET chapter_no = %s, title = %s WHERE id = %s""",
                (chapter_no, title, same_source["id"]),
            )
            return "unchanged", 0
        duplicate = conn.execute(
            """SELECT source FROM course_documents
               WHERE subject = %s AND grade = %s AND content_hash = %s
                 AND source <> %s""",
            (subject, grade, digest, source),
        ).fetchone()
        if duplicate:
            return f"duplicate of {duplicate['source']}", 0

    page_chunks = [
        (page, chunk)
        for page, text in ingest.read_pages(path)
        for chunk in ingest.split_text(text)
        if len(chunk) >= MIN_CHUNK_CHARS
    ]
    if not page_chunks:
        raise ValueError(f"No selectable text extracted from {source}; scanned PDFs need OCR.")
    vectors = embed_docs([chunk for _, chunk in page_chunks])

    with db.pool.connection() as conn:
        document = conn.execute(
            """INSERT INTO course_documents (subject, grade, source, title, chapter_no, content_hash)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (subject, grade, source) DO UPDATE
               SET content_hash = EXCLUDED.content_hash, title = EXCLUDED.title,
                   chapter_no = EXCLUDED.chapter_no
               RETURNING id""",
            (subject, grade, source, title, chapter_no, digest),
        ).fetchone()
        document_id = document["id"]
        conn.execute("DELETE FROM course_document_chunks WHERE document_id = %s", (document_id,))
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO course_document_chunks (document_id, page, content, embedding)
                   VALUES (%s, %s, %s, %s)""",
                (
                    (document_id, page, content, vector)
                    for (page, content), vector in zip(page_chunks, vectors)
                ),
            )
    return "indexed", len(page_chunks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=pathlib.Path, help="Root folder containing subject folders")
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        raise SystemExit(f"Data directory not found: {root}")

    db.init_db()
    counts = {"indexed": 0, "unchanged": 0, "duplicates": 0, "unclassified": 0, "failed": 0}
    try:
        for path in sorted(root.rglob("*.pdf")):
            try:
                status, chunks = index_file(path, root)
                if status == "indexed":
                    counts["indexed"] += 1
                    print(f"Indexed {path.relative_to(root)} ({chunks} chunks)")
                elif status == "unchanged":
                    counts["unchanged"] += 1
                elif status.startswith("duplicate of "):
                    counts["duplicates"] += 1
                    print(f"Skipped duplicate {path.relative_to(root)}: {status}")
                else:
                    counts["unclassified"] += 1
                    print(f"Skipped unclassified filename: {path.relative_to(root)}")
            except Exception as exc:
                counts["failed"] += 1
                print(f"Failed {path.relative_to(root)}: {exc}")
    finally:
        db.pool.close()

    print(
        "Summary: "
        + ", ".join(f"{key}={value}" for key, value in counts.items())
    )
    if counts["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
