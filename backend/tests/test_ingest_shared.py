import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch

from app.ingest_shared import classify, index_file


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
            ):
                result = index_file(source, root)

        self.assertEqual(result, ("indexed", 1))
        inserted_rows = list(cursor.executemany.call_args.args[1])
        self.assertEqual(inserted_rows, [(42, 1, "a" * 100, [0.1, 0.2])])


if __name__ == "__main__":
    unittest.main()
