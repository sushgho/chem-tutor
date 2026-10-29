import unittest
from pathlib import Path

from app.ingest_shared import classify


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


if __name__ == "__main__":
    unittest.main()
