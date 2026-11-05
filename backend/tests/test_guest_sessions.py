import hashlib
import unittest
from unittest.mock import patch
from uuid import UUID

from fastapi import HTTPException

from app import main, progress


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, guest_session=None):
        self.guest_session = guest_session
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        if "INSERT INTO students" in query:
            return FakeResult({"id": 31})
        if "SELECT student_id, library_key FROM guest_sessions" in query:
            return FakeResult(self.guest_session)
        return FakeResult(None)


class FakePool:
    def __init__(self, connection):
        self.fake_connection = connection

    def connection(self):
        return self.fake_connection


class GuestSessionTests(unittest.TestCase):
    def test_creates_session_with_only_token_hash_stored(self):
        connection = FakeConnection()
        with patch.object(progress, "pool", FakePool(connection)):
            session = progress.create_guest_session()

        self.assertEqual(session["id"], 31)
        self.assertEqual(len(session["guest_session"]), 43)
        library_key = UUID(session["library_key"])
        self.assertIsInstance(library_key, UUID)

        insert = next(
            call for call in connection.calls if "INSERT INTO guest_sessions" in call[0]
        )
        stored_hash, stored_student_id, stored_library_key = insert[1]
        self.assertEqual(
            stored_hash,
            hashlib.sha256(session["guest_session"].encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(stored_hash, session["guest_session"])
        self.assertEqual(stored_student_id, 31)
        self.assertEqual(stored_library_key, library_key)

    def test_retrieves_session_by_hash_without_exposing_raw_token(self):
        token = "random-guest-session-token"
        library_key = UUID("12345678-1234-5678-1234-567812345678")
        connection = FakeConnection(
            {"student_id": 31, "library_key": library_key}
        )
        with patch.object(progress, "pool", FakePool(connection)):
            session = progress.get_guest_session(token)

        self.assertEqual(session, {"id": 31, "library_key": str(library_key)})
        self.assertEqual(
            connection.calls[0][1],
            (hashlib.sha256(token.encode("utf-8")).hexdigest(),),
        )

    def test_unknown_guest_session_is_not_created_or_replaced(self):
        connection = FakeConnection()
        with patch.object(progress, "pool", FakePool(connection)):
            session = progress.get_guest_session("unknown-token")

        self.assertIsNone(session)
        self.assertEqual(len(connection.calls), 1)

    def test_guest_token_authenticates_only_its_student_profile(self):
        with patch.object(
            main.progress,
            "get_guest_session",
            return_value={"id": 31, "library_key": "key"},
        ):
            student_id = main.authenticated_student_id(
                authorization=None,
                guest_session="valid-token",
            )

        self.assertEqual(student_id, 31)
        main._require_student_owner(31, student_id)
        with self.assertRaises(HTTPException) as raised:
            main._require_student_owner(32, student_id)
        self.assertEqual(raised.exception.status_code, 403)

    def test_unknown_guest_token_is_rejected(self):
        with (
            patch.object(main.progress, "get_guest_session", return_value=None),
            self.assertRaises(HTTPException) as raised,
        ):
            main.authenticated_student_id(
                authorization=None,
                guest_session="unknown-token",
            )

        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
