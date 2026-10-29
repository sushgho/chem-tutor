import unittest
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from app import main


LIBRARY_KEY = "0b4baf2c-e52c-4acd-8d75-9cce2f9f0c63"


class StudyApiTests(unittest.TestCase):
    def setUp(self):
        self.init_db = patch.object(main.db, "init_db")
        self.close_pool = patch.object(main.db.pool, "close")
        self.init_db.start()
        self.close_pool.start()
        self.addCleanup(self.init_db.stop)
        self.addCleanup(self.close_pool.stop)
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()
        self.addCleanup(self.client_context.__exit__, None, None, None)

    def test_document_library_requires_opaque_key(self):
        response = self.client.get("/students/8/documents?subject=biology")
        self.assertEqual(response.status_code, 422)

        with patch.object(main.documents, "list_documents", return_value=[]) as list_documents:
            response = self.client.get(
                "/students/8/documents?subject=biology",
                headers={"X-Study-Library-Key": LIBRARY_KEY},
            )
        self.assertEqual(response.status_code, 200)
        list_documents.assert_called_once_with(8, UUID(LIBRARY_KEY), "biology")

    def test_upload_endpoint_accepts_supported_file_and_library_key(self):
        saved = {"id": 9, "filename": "notes.txt", "subject": "biology", "chunks": 1}
        with patch.object(main.documents, "create_document", return_value=saved) as create:
            response = self.client.post(
                "/students/8/documents",
                data={"subject": "biology"},
                files={"file": ("notes.txt", b"Cell structure", "text/plain")},
                headers={"X-Study-Library-Key": LIBRARY_KEY},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), saved)
        self.assertEqual(create.call_args.args[:3], (8, UUID(LIBRARY_KEY), "biology"))

    def test_study_chat_streams_for_non_chemistry_subject(self):
        request = {
            "student_id": 8,
            "subject": "biology",
            "grade": "XII",
            "question": "Explain photosynthesis",
            "mode": "chat",
            "history": [],
        }
        with (
            patch.object(main.documents, "retrieve", return_value=[]) as retrieve,
            patch.object(main.progress, "log_message"),
            patch.object(main.llm, "stream_answer", return_value=iter(["Photosynthesis uses light."])),
        ):
            response = self.client.post(
                "/study/chat",
                json=request,
                headers={"X-Study-Library-Key": LIBRARY_KEY},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Photosynthesis uses light.")
        retrieve.assert_called_once_with(8, UUID(LIBRARY_KEY), "biology", "Explain photosynthesis")


if __name__ == "__main__":
    unittest.main()
