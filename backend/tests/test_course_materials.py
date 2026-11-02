from io import BytesIO
import unittest
from unittest.mock import patch

from app import course_materials
from app.rag import Chunk, sources_payload


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

    def test_shared_results_include_original_pdf_page_urls(self):
        with (
            patch.object(course_materials, "pool", FakePool()),
            patch.object(course_materials, "embed_query", return_value=[]),
            patch.object(course_materials.settings, "embedding_mode", "keyword"),
        ):
            chunks = course_materials.retrieve("biology", "XI", "cell structure")

        self.assertEqual(
            chunks[0].image_url,
            "/study/page-image?subject=biology&grade=XI&source=biology.pdf&page=2",
        )


class SharedPdfPageTests(unittest.TestCase):
    def setUp(self):
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        output = BytesIO()
        writer.write(output)
        self.pdf_data = output.getvalue()

    def test_renders_the_requested_pdf_page_as_png(self):
        with patch.object(course_materials.pool, "connection") as connection:
            connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = {
                "pdf_data": self.pdf_data,
            }
            image = course_materials.get_pdf_page("biology", "XI", "Biology/book.pdf", 1)

        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_rejects_a_page_outside_the_pdf(self):
        with (
            patch.object(course_materials.pool, "connection") as connection,
            self.assertRaisesRegex(ValueError, "outside this document"),
        ):
            connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = {
                "pdf_data": self.pdf_data,
            }
            course_materials.get_pdf_page("biology", "XI", "Biology/book.pdf", 2)


class SourcePayloadTests(unittest.TestCase):
    def test_includes_page_image_link_only_when_available(self):
        chunk = Chunk(1, "Excerpt", "Biology/book.pdf", 2, None, 0.1, "/study/page-image?page=2")

        self.assertEqual(
            sources_payload([chunk]),
            [{
                "n": 1,
                "source": "Biology/book.pdf",
                "page": 2,
                "topic": None,
                "image_url": "/study/page-image?page=2",
            }],
        )


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

    def test_lists_numbered_topics_for_the_selected_chapter(self):
        rows = [
            {
                "document_id": 1,
                "content": (
                    "1.1 INTRODUCTION\n1.2 THE INTER\n"
                    "1.2 THE INTERNATIONAL SYSTEM OF\nUNITS\n1.2.1 Base quantities\n"
                    "1.3 Dimensions of physical\nquantities\n"
                    "1.4 Union of sets Let A and B be any two sets.\n"
                    "EXERCISE 1.1\n1.1 Fill in the blanks\n1.3 Significant figures\n"
                    "EXERCISES\n1.4 This is a question, not a topic"
                ),
            },
            {"document_id": 1, "content": "1.1 Introduction to measurement\n2.1 A different chapter"},
        ]
        with patch.object(course_materials.pool, "connection") as connection:
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = rows
            topics = course_materials.list_topics("physics", "XI", 1)

        self.assertEqual(topics, [
            {"section_no": "1.1", "title": "INTRODUCTION"},
            {"section_no": "1.2", "title": "THE INTERNATIONAL SYSTEM OF UNITS"},
            {"section_no": "1.2.1", "title": "Base quantities"},
            {"section_no": "1.3", "title": "Dimensions of physical quantities"},
            {"section_no": "1.4", "title": "Union of sets"},
        ])


if __name__ == "__main__":
    unittest.main()
