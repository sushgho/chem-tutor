import re
from io import BytesIO
from pathlib import PurePath
from typing import BinaryIO
from uuid import UUID

from fastapi import HTTPException
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from . import rag
from .config import settings
from .db import pool
from .embeddings import embed_docs, embed_query

SUBJECTS = {"maths", "physics", "chemistry", "biology"}
MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_TEXT_CHARS = 300_000
MAX_PDF_PAGES = 100
MAX_CHUNKS = 300
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 160


class DocumentError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _chunks(text: str, page: int | None) -> list[tuple[str, int | None]]:
    result = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + CHUNK_SIZE // 2, end)
            if boundary > start:
                end = boundary
        excerpt = text[start:end].strip()
        if excerpt:
            result.append((excerpt, page))
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return result


def _extract(filename: str, data: bytes) -> list[tuple[str, int | None]]:
    extension = PurePath(filename).suffix.lower()
    if extension == ".txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentError("Text files must use UTF-8 encoding.") from exc
        text = re.sub(r"\x00", "", text).strip()
        if len(text) > MAX_TEXT_CHARS:
            raise DocumentError("This document is too long. Keep extracted text under 300,000 characters.", 413)
        return _chunks(text, None)

    if extension != ".pdf":
        raise DocumentError("Upload a PDF or UTF-8 text file.")
    if not data.startswith(b"%PDF-"):
        raise DocumentError("The uploaded file is not a valid PDF.")

    try:
        reader = PdfReader(BytesIO(data))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentError(f"PDFs may contain up to {MAX_PDF_PAGES} pages.", 413)
        extracted = []
        total_chars = 0
        for page_number, pdf_page in enumerate(reader.pages, start=1):
            text = (pdf_page.extract_text() or "").strip()
            total_chars += len(text)
            if total_chars > MAX_TEXT_CHARS:
                raise DocumentError("This document is too long. Keep extracted text under 300,000 characters.", 413)
            extracted.extend(_chunks(text, page_number))
    except DocumentError:
        raise
    except (FileNotDecryptedError, PdfReadError, ValueError, OSError) as exc:
        raise DocumentError("The PDF could not be read. Please upload a valid, unprotected PDF.") from exc

    if not extracted:
        raise DocumentError("No selectable text was found. Scanned PDFs need OCR before uploading.", 422)
    return extracted


def validate_library_key(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(400, "Invalid study-library key.") from exc


def create_document(
    student_id: int,
    library_key: UUID,
    subject: str,
    filename: str,
    file: BinaryIO,
) -> dict:
    if subject not in SUBJECTS:
        raise DocumentError("Choose Maths, Physics, Chemistry, or Biology.")
    safe_name = PurePath(filename.replace("\\", "/")).name[:200]
    if not safe_name or safe_name in (".", ".."):
        raise DocumentError("The uploaded file needs a valid filename.")
    data = file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise DocumentError("Files must be 12 MB or smaller.", 413)
    if not data:
        raise DocumentError("The uploaded file is empty.")
    excerpts = _extract(safe_name, data)
    if not excerpts:
        raise DocumentError("No readable study text was found in the document.", 422)
    if len(excerpts) > MAX_CHUNKS:
        raise DocumentError(f"This document has too much text. Limit it to {MAX_CHUNKS} text sections.", 413)

    vectors = embed_docs([text for text, _ in excerpts])
    with pool.connection() as conn:
        if not conn.execute("SELECT 1 FROM students WHERE id = %s", (student_id,)).fetchone():
            raise DocumentError("The study profile was not found. Reload the app and try again.", 404)
        document = conn.execute(
            """INSERT INTO student_documents (student_id, library_key, subject, filename)
               VALUES (%s, %s, %s, %s) RETURNING id, filename, subject, created_at""",
            (student_id, library_key, subject, safe_name),
        ).fetchone()
        for (content, page), embedding in zip(excerpts, vectors):
            conn.execute(
                """INSERT INTO student_document_chunks
                   (document_id, student_id, library_key, subject, page, content, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (document["id"], student_id, library_key, subject, page, content, embedding),
            )
    return {**document, "chunks": len(excerpts)}


def list_documents(student_id: int, library_key: UUID, subject: str) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT id, filename, subject, created_at
               FROM student_documents
               WHERE student_id = %s AND library_key = %s AND subject = %s
               ORDER BY created_at DESC, id DESC""",
            (student_id, library_key, subject),
        ).fetchall()
    return rows


def delete_document(student_id: int, library_key: UUID, document_id: int) -> bool:
    with pool.connection() as conn:
        row = conn.execute(
            """DELETE FROM student_documents
               WHERE id = %s AND student_id = %s AND library_key = %s RETURNING id""",
            (document_id, student_id, library_key),
        ).fetchone()
    return row is not None


def retrieve(
    student_id: int,
    library_key: UUID,
    subject: str,
    query: str,
    limit: int = 5,
) -> list[rag.Chunk]:
    qv = embed_query(query)
    with pool.connection() as conn:
        rows = conn.execute(
            """WITH v AS (
                   SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(qv)s) AS r
                   FROM student_document_chunks
                   WHERE student_id = %(student_id)s AND library_key = %(library_key)s
                     AND subject = %(subject)s
                   ORDER BY embedding <=> %(qv)s LIMIT 30
               ),
               f AS (
                   SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS r
                   FROM student_document_chunks, websearch_to_tsquery('english', %(query)s) q
                   WHERE student_id = %(student_id)s AND library_key = %(library_key)s
                     AND subject = %(subject)s AND tsv @@ q
                   ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 30
               )
               SELECT c.id, c.content, d.filename AS source, c.page,
                      c.embedding <=> %(qv)s AS dist,
                      COALESCE(1.0 / (60 + v.r), 0) + COALESCE(1.0 / (60 + f.r), 0) AS score
               FROM student_document_chunks c
               JOIN student_documents d ON d.id = c.document_id
               LEFT JOIN v ON v.id = c.id
               LEFT JOIN f ON f.id = c.id
               WHERE (v.id IS NOT NULL OR f.id IS NOT NULL)
                 AND c.student_id = %(student_id)s AND c.library_key = %(library_key)s
                 AND c.subject = %(subject)s
               ORDER BY score DESC
               LIMIT %(limit)s""",
            {
                "qv": qv,
                "query": query,
                "student_id": student_id,
                "library_key": library_key,
                "subject": subject,
                "limit": limit,
            },
        ).fetchall()
    return [
        rag.Chunk(
            row["id"],
            row["content"],
            row["source"],
            row["page"],
            None,
            float(row["dist"]),
        )
        for row in rows
        if float(row["dist"]) <= settings.max_dist
    ]


def retrieve_all(
    student_id: int,
    library_key: UUID,
    subject: str,
    limit: int = 12,
) -> list[rag.Chunk]:
    with pool.connection() as conn:
        rows = conn.execute(
            """WITH ranked AS (
                   SELECT c.id, c.content, d.filename AS source, c.page, d.created_at,
                          ROW_NUMBER() OVER (
                              PARTITION BY d.id ORDER BY c.page NULLS FIRST, c.id
                          ) AS position,
                          COUNT(*) OVER (PARTITION BY d.id) AS document_chunks
                   FROM student_document_chunks c
                   JOIN student_documents d ON d.id = c.document_id
                   WHERE c.student_id = %s AND c.library_key = %s AND c.subject = %s
               )
               SELECT id, content, source, page
               FROM ranked
               WHERE position IN (1, GREATEST(1, (document_chunks + 1) / 2), document_chunks)
               ORDER BY created_at DESC, page NULLS FIRST, id
               LIMIT %s""",
            (student_id, library_key, subject, limit),
        ).fetchall()
    return [
        rag.Chunk(row["id"], row["content"], row["source"], row["page"], None, 0.0)
        for row in rows
    ]
