import unittest
from unittest.mock import patch

from app import course_materials


class FakeResult:
    def fetchall(self):
        return [
            {
                "id": 1,
                "content": "Relevant textbook excerpt",
                "source": "biology.pdf",
                "page": 2,
                "dist": 0.91,
                "keyword_match": True,
            },
            {
                "id": 2,
                "content": "Unmatched vector candidate",
                "source": "biology.pdf",
                "page": 3,
                "dist": 0.25,
                "keyword_match": False,
            },
        ]


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args, **_kwargs):
        return FakeResult()


class FakePool:
    def connection(self):
        return FakeConnection()


class CourseMaterialRetrievalTests(unittest.TestCase):
    def test_keyword_mode_keeps_text_matches_and_ignores_vector_only_candidates(self):
        with (
            patch.object(course_materials, "pool", FakePool()),
            patch.object(course_materials, "embed_query", return_value=[]),
            patch.object(course_materials.settings, "embedding_mode", "keyword"),
        ):
            chunks = course_materials.retrieve("biology", "XI", "cell structure")

        self.assertEqual([chunk.id for chunk in chunks], [1])

    def test_semantic_mode_keeps_cosine_distance_cutoff(self):
        with (
            patch.object(course_materials, "pool", FakePool()),
            patch.object(course_materials, "embed_query", return_value=[]),
            patch.object(course_materials.settings, "embedding_mode", "sentence-transformers"),
            patch.object(course_materials.settings, "max_dist", 0.6),
        ):
            chunks = course_materials.retrieve("biology", "XI", "cell structure")

        self.assertEqual([chunk.id for chunk in chunks], [2])


class CourseChapterCatalogTests(unittest.TestCase):
    def test_class_xi_uses_clean_subject_chapter_titles(self):
        rows = [
            {"chapter_no": 1, "title": "SETS Georg Cantor"},
            {"chapter_no": 2, "title": "Chapter 2"},
        ]
        with patch.object(course_materials.pool, "connection") as connection:
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = rows
            chapters = course_materials.list_chapters("maths", "XI")

        self.assertEqual(chapters, [
            {"chapter_no": 1, "title": "Sets"},
            {"chapter_no": 2, "title": "Relations and Functions"},
        ])

    def test_class_xii_keeps_titles_from_its_indexed_material(self):
        rows = [{"chapter_no": 1, "title": "Electric Charges and Fields"}]
        with patch.object(course_materials.pool, "connection") as connection:
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = rows
            chapters = course_materials.list_chapters("physics", "XII")

        self.assertEqual(chapters, rows)


if __name__ == "__main__":
    unittest.main()
