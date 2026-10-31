import unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch

from pypdf.errors import LimitReachedError

from app import ingest
from app.ingest_shared import chapter_metadata, classify, index_file


class SharedIngestTests(unittest.TestCase):
    def test_classifies_ncert_filename_by_subject_and_class(self):
        examples = {
            "kebo101.pdf": ("biology", "XI"),
            "kemh112.pdf": ("maths", "XI"),
            "keph201.pdf": ("physics", "XI"),
            "kech207.pdf": ("chemistry", "XI"),
            "lebo101.pdf": ("biology", "XII"),
            "lemh112.pdf": ("maths", "XII"),
            "leph201.pdf": ("physics", "XII"),
            "lech207.pdf": ("chemistry", "XII"),
        }
        for filename, expected in examples.items():
            with self.subTest(filename=filename):
                self.assertEqual(classify(Path(filename)), expected)

    def test_leaves_unknown_filenames_unclassified(self):
        self.assertIsNone(classify(Path("desm_s_Chemistry.pdf")))
        self.assertIsNone(classify(Path("chemistry_notes.pdf")))

    def test_extracts_a_chapter_title_from_textbook_front_matter(self):
        with patch("app.ingest_shared._read_first_pages", return_value=[
            "CHAPTER ONE\nUNITS AND MEASUREMENT\n1.1 INTRODUCTION"
        ]):
            self.assertEqual(chapter_metadata(Path("keph101.pdf"), "physics"), (1, "UNITS AND MEASUREMENT"))

    def test_falls_back_to_the_chapter_number_when_heading_is_missing(self):
        with patch("app.ingest_shared._read_first_pages", return_value=["Foreword and contents"]):
            self.assertEqual(chapter_metadata(Path("kemh102.pdf"), "maths"), (2, "Chapter 2"))

    def test_supplementary_files_without_chapter_numbers_are_not_catalogued(self):
        self.assertEqual(chapter_metadata(Path("kemh1an.pdf"), "maths"), (None, ""))

    def test_inserts_chunks_with_a_psycopg_cursor(self):
        connection = Mock()
        connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value=None)),
            Mock(fetchone=Mock(return_value=None)),
            Mock(fetchone=Mock(return_value={"id": 42})),
            Mock(),
        ]
        cursor = Mock()
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection.cursor.return_value = cursor_context
        pool_context = MagicMock()
        pool_context.__enter__.return_value = connection

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "kebo101.pdf"
            source.write_bytes(b"test PDF")
            with (
                patch("app.ingest_shared.db.pool.connection", return_value=pool_context),
                patch("app.ingest_shared.ingest.read_pages", return_value=[(1, "a" * 100)]),
                patch("app.ingest_shared.embed_docs", return_value=[[0.1, 0.2]]),
                patch("app.ingest_shared.chapter_metadata", return_value=(1, "The Living World")),
            ):
                result = index_file(source, root)

        self.assertEqual(result, ("indexed", 1))
        inserted_rows = list(cursor.executemany.call_args.args[1])
        self.assertEqual(inserted_rows, [(42, 1, "a" * 100, [0.1, 0.2])])

    def test_pdf_reader_skips_pages_over_pypdf_parsing_limit(self):
        pages = [Mock(), Mock(), Mock()]
        pages[0].extract_text.return_value = "first page"
        pages[1].extract_text.side_effect = LimitReachedError("stream limit")
        pages[2].extract_text.return_value = "last page"
        reader = Mock(pages=pages)

        with patch("app.ingest.PdfReader", return_value=reader), self.assertLogs(
            "app.ingest", level="WARNING"
        ):
            extracted = list(ingest.read_pages(Path("book.pdf")))

        self.assertEqual(extracted, [(1, "first page"), (3, "last page")])

    def test_text_splitting_removes_nul_bytes(self):
        self.assertEqual(list(ingest.split_text("chapter\x00 text")), ["chapter text"])


if __name__ == "__main__":
    unittest.main()
