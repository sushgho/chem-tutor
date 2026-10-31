"""Load textbook / notes into the vector store.

Usage (from backend/):
  python -m app.ingest data/ncert_xi_ch1.pdf --grade XI --unit 1
  python -m app.ingest data/my_notes.md --grade XII --unit 3 --topic XII-03-04

Each chunk is tagged with grade, unit, page and (automatically) the closest topic
inside that unit unless --topic is given.
"""
import argparse
import logging
import pathlib
import re

from pypdf import PdfReader
from pypdf.errors import LimitReachedError

from . import db
from .embeddings import embed_docs, similarity

CHUNK_CHARS = 900
OVERLAP = 150
logger = logging.getLogger(__name__)


def read_pages(path: pathlib.Path):
    """Yield (page_number, text)."""
    if path.suffix.lower() == ".pdf":
        for i, page in enumerate(PdfReader(str(path)).pages, start=1):
            try:
                text = page.extract_text() or ""
            except LimitReachedError as exc:
                logger.warning("Skipped text extraction for %s page %d: %s", path, i, exc)
                continue
            yield i, text
    else:
        yield None, path.read_text(encoding="utf-8")


def split_text(text: str):
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 1 <= CHUNK_CHARS:
            buf = f"{buf}\n{p}".strip()
            continue
        if buf:
            yield buf
        while len(p) > CHUNK_CHARS:  # very long paragraph
            yield p[:CHUNK_CHARS]
            p = p[CHUNK_CHARS - OVERLAP:]
        buf = p
    if buf:
        yield buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--grade", required=True, choices=["XI", "XII"])
    ap.add_argument("--unit", type=int, help="unit number from the syllabus")
    ap.add_argument("--topic", help="force a topic id, e.g. XI-01-04")
    ap.add_argument("--source", help="display name, defaults to the file name")
    args = ap.parse_args()

    db.init_db()
    path = pathlib.Path(args.file)
    source = args.source or path.name

    with db.pool.connection() as c:
        q = "SELECT id, title FROM topics WHERE grade = %s"
        params = [args.grade]
        if args.unit:
            q += " AND unit_no = %s"
            params.append(args.unit)
        topics = c.execute(q + " ORDER BY ord", params).fetchall()
    if not topics:
        raise SystemExit("No topics found for that grade/unit.")
    topic_vecs = embed_docs([t["title"] for t in topics])

    rows = []
    for page, text in read_pages(path):
        for chunk in split_text(text):
            if len(chunk) < 80:
                continue
            rows.append((page, chunk))
    if not rows:
        raise SystemExit("No text extracted (scanned PDF? run OCR first).")

    vecs = embed_docs([r[1] for r in rows])
    with db.pool.connection() as c:
        for (page, chunk), vec in zip(rows, vecs):
            topic_id = args.topic or max(
                zip(topics, topic_vecs),
                key=lambda item: similarity(item[1], vec),
            )[0]["id"]
            c.execute(
                """INSERT INTO chunks (grade, unit_no, topic_id, source, page, content, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (args.grade, args.unit or int(topic_id.split("-")[1]),
                 topic_id, source, page, chunk, vec),
            )
    print(f"Ingested {len(rows)} chunks from {source}")


if __name__ == "__main__":
    main()
