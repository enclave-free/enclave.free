import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class MagicLinkEnumerationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import auth
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.database.add_admin("a" * 64)
        self.database.mark_instance_setup_complete()
        self.database.create_user(email="known@example.com", name="Known User")
        self.sent_to: list[str] = []
        self.auth.send_magic_link_email = self._record_magic_link
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_sentence_transformers()
        self.tmp.cleanup()

    def _record_magic_link(self, to_email: str, token: str) -> bool:
        self.assertTrue(token)
        self.sent_to.append(to_email)
        return True

    def _restore_sentence_transformers(self) -> None:
        if self._orig_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._orig_sentence_transformers

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_magic_link_request_response_does_not_enumerate_known_addresses(self) -> None:
        known = self.client.post(
            "/auth/magic-link",
            json={"email": "known@example.com", "name": "Known User"},
        )
        unknown = self.client.post(
            "/auth/magic-link",
            json={"email": "new-person@example.com", "name": "New Person"},
        )

        expected_body = {
            "success": True,
            "message": "If this address can sign in, we'll send a magic link.",
        }
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.json(), expected_body)
        self.assertEqual(unknown.json(), expected_body)
        self.assertEqual(self.sent_to, ["known@example.com", "new-person@example.com"])

    def test_magic_link_email_uses_instance_name_by_default(self) -> None:
        self.database.update_settings({"instance_name": "FreeThem"})

        message = self.auth.build_magic_link_email("known@example.com", "token-123")
        html = message.get_payload()[0].get_payload()

        self.assertEqual(message["Subject"], "Sign in to FreeThem")
        self.assertIn("Sign in to FreeThem", html)
        self.assertIn("token-123", html)

    def test_magic_link_email_uses_public_email_display_name_override(self) -> None:
        self.database.update_settings({
            "instance_name": "FreeThem",
            "public_email_display_name": "World Liberty Congress",
        })

        message = self.auth.build_magic_link_email("known@example.com", "token-123")
        html = message.get_payload()[0].get_payload()

        self.assertEqual(message["Subject"], "Sign in to World Liberty Congress")
        self.assertIn("Sign in to World Liberty Congress", html)
        self.assertNotIn("Sign in to FreeThem", html)


if __name__ == "__main__":
    unittest.main()
