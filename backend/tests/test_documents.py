import io
import unittest
from unittest.mock import patch
from uuid import UUID

from fastapi import HTTPException
from pypdf import PdfWriter

from app import documents
from app.documents import DocumentError, _chunks, _extract, validate_library_key


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.calls.append((query, params))
        if query.lstrip().startswith("SELECT 1"):
            return FakeResult({"exists": 1})
        if "INSERT INTO student_documents" in query:
            return FakeResult({
                "id": 7,
                "filename": params[3],
                "subject": params[2],
                "created_at": "now",
            })
        return FakeResult(None)


class FakePool:
    def __init__(self, connection):
        self.fake_connection = connection

    def connection(self):
        return self.fake_connection


class DocumentParsingTests(unittest.TestCase):
    def test_extracts_utf8_text(self):
        self.assertEqual(
            _extract("notes.txt", b"\xef\xbb\xbfNewton's second law: F = ma."),
            [("Newton's second law: F = ma.", None)],
        )

    def test_splits_long_text_with_overlap(self):
        text = "word " * 500
        chunks = _chunks(text, 3)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(page == 3 and len(part) <= 1200 for part, page in chunks))
        self.assertIn(chunks[0][0][-40:], chunks[1][0])

    def test_rejects_non_utf8_text(self):
        with self.assertRaisesRegex(DocumentError, "UTF-8"):
            _extract("notes.txt", b"\xff")

    def test_rejects_unsupported_file_type(self):
        with self.assertRaisesRegex(DocumentError, "PDF or UTF-8"):
            _extract("notes.docx", b"text")

    def test_parses_pdf_and_reports_scanned_content(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        stream = io.BytesIO()
        writer.write(stream)
        with self.assertRaisesRegex(DocumentError, "No selectable text"):
            _extract("scanned.pdf", stream.getvalue())

    def test_validates_random_library_key(self):
        key = "0b4baf2c-e52c-4acd-8d75-9cce2f9f0c63"
        self.assertEqual(str(validate_library_key(key)), key)
        with self.assertRaises(HTTPException) as raised:
            validate_library_key("not-a-key")
        self.assertEqual(raised.exception.detail, "Invalid study-library key.")

    def test_upload_indexes_chunks_under_the_browser_library_key(self):
        connection = FakeConnection()
        key = UUID("0b4baf2c-e52c-4acd-8d75-9cce2f9f0c63")
        with (
            patch.object(documents, "pool", FakePool(connection)),
            patch.object(documents, "embed_docs", return_value=[[0.0] * 384]),
        ):
            result = documents.create_document(
                12,
                key,
                "physics",
                "C:\\study\\notes.txt",
                io.BytesIO(b"Newton's second law: F = ma."),
            )

        self.assertEqual(result["chunks"], 1)
        document_values = connection.calls[1][1]
        chunk_values = connection.calls[2][1]
        self.assertEqual(document_values, (12, key, "physics", "notes.txt"))
        self.assertEqual(chunk_values[1:4], (12, key, "physics"))


if __name__ == "__main__":
    unittest.main()
