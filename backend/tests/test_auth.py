import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt

from app import auth, progress


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, existing_student=None):
        self.existing_student = existing_student
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        if "SELECT student_id FROM auth_users" in query:
            return FakeResult(
                {"student_id": self.existing_student}
                if self.existing_student is not None
                else None
            )
        if "INSERT INTO students" in query:
            return FakeResult({"id": 31})
        return FakeResult(None)


class FakePool:
    def __init__(self, connection):
        self.fake_connection = connection

    def connection(self):
        return self.fake_connection


class SupabaseTokenTests(unittest.TestCase):
    def setUp(self):
        self.user_id = str(uuid4())
        self.issuer = "https://project.supabase.co/auth/v1"
        self.secret = "test-only-signing-secret-that-is-long-enough"
        self.token = jwt.encode(
            {
                "sub": self.user_id,
                "iss": self.issuer,
                "aud": "authenticated",
                "exp": int(time.time()) + 60,
            },
            self.secret,
            algorithm="HS256",
        )

    def test_verifies_signed_supabase_identity(self):
        with (
            patch.object(auth.settings, "supabase_url", "https://project.supabase.co"),
            patch.object(auth.settings, "supabase_jwt_secret", self.secret),
        ):
            result = auth.verify_access_token(self.token)

        self.assertEqual(result, self.user_id)

    def test_rejects_tampered_token(self):
        with (
            patch.object(auth.settings, "supabase_url", "https://project.supabase.co"),
            patch.object(auth.settings, "supabase_jwt_secret", self.secret),
            self.assertRaises(auth.InvalidAccessToken),
        ):
            auth.verify_access_token(self.token + "tampered")

    def test_rejects_unconfigured_supabase_project(self):
        with (
            patch.object(auth.settings, "supabase_url", ""),
            self.assertRaises(auth.AuthServiceUnavailable),
        ):
            auth.verify_access_token(self.token)

    def test_existing_auth_identity_reuses_its_student_profile(self):
        connection = FakeConnection(existing_student=31)
        with patch.object(progress, "pool", FakePool(connection)):
            student_id = progress.ensure_authenticated_student(self.user_id)

        self.assertEqual(student_id, 31)
        self.assertEqual(len(connection.calls), 2)

    def test_new_auth_identity_gets_a_separate_profile_and_library_key(self):
        connection = FakeConnection()
        with patch.object(progress, "pool", FakePool(connection)):
            student_id = progress.ensure_authenticated_student(self.user_id)

        self.assertEqual(student_id, 31)
        insert = next(call for call in connection.calls if "INSERT INTO auth_users" in call[0])
        self.assertEqual(insert[1][0], UUID(self.user_id))
        self.assertEqual(insert[1][1], 31)
        self.assertIsInstance(insert[1][2], UUID)


if __name__ == "__main__":
    unittest.main()
