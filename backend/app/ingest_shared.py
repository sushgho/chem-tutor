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
SUBJECTS = {"mh": "maths", "ph": "physics", "ch": "chemistry", "bo": "biology"}
MIN_CHUNK_CHARS = 80


def classify(path: pathlib.Path) -> tuple[str, str] | None:
    match = NCERT_BOOK.match(path.stem)
    if not match:
        return None
    grade = "XI" if match.group(1).lower() == "k" else "XII"
    subject = SUBJECTS[match.group(2).lower()]
    return subject, grade


def index_file(path: pathlib.Path, root: pathlib.Path) -> tuple[str, int]:
    classification = classify(path)
    if classification is None:
        return "unclassified", 0
    subject, grade = classification
    source = path.relative_to(root).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    with db.pool.connection() as conn:
        same_source = conn.execute(
            """SELECT id, content_hash FROM course_documents
               WHERE subject = %s AND grade = %s AND source = %s""",
            (subject, grade, source),
        ).fetchone()
        if same_source and same_source["content_hash"] == digest:
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
            """INSERT INTO course_documents (subject, grade, source, content_hash)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (subject, grade, source) DO UPDATE
               SET content_hash = EXCLUDED.content_hash
               RETURNING id""",
            (subject, grade, source, digest),
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
