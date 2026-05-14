import importlib
import json
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


class UserDeletionLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "sanctum.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        self.addCleanup(self._restore_sentence_transformers)
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import database
        import auth
        import deployment_config
        import query
        import main

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.deployment_config = importlib.reload(deployment_config)
        self.query = importlib.reload(query)
        self.main = importlib.reload(main)
        self.database.init_schema()

        self.user_id = self.database.create_user(pubkey="a" * 64)
        self.memory_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers deletion receipts.",
            source_kind="conversation",
            source_conversation_id="query-session-1",
            author_actor="sage",
        )
        self.query._sessions["query-session-1"] = {
            "id": "query-session-1",
            "owner_type": "user",
            "owner_id": str(self.user_id),
            "messages": [],
        }

        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.auth.require_admin_or_user] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.deployment_config.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        self.query._sessions.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_sentence_transformers()
        self.tmp.cleanup()

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

    def audit_entries(self, table_name: str) -> list[dict]:
        response = self.client.get(f"/admin/deployment/audit-log?table_name={table_name}")
        self.assertEqual(response.status_code, 200)
        return response.json()["entries"]

    def test_user_deletion_removes_profile_memory_and_conversations(self) -> None:
        response = self.client.delete(f"/users/{self.user_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["deletion"]["status"], "succeeded")
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["delete_user_memory"]["status"], "succeeded")
        self.assertEqual(actions["delete_user_memory"]["count"], 1)
        self.assertEqual(actions["delete_conversations"]["status"], "succeeded")
        self.assertEqual(actions["delete_user_profile"]["status"], "succeeded")
        self.assertEqual(actions["delete_user_approval"]["status"], "succeeded")

        self.assertIsNone(self.database.get_user(self.user_id))
        self.assertIsNone(self.database.get_user_memory(self.memory_id))
        self.assertNotIn("query-session-1", self.query._sessions)
        users = self.client.get("/admin/users").json()["users"]
        self.assertNotIn(self.user_id, {user["id"] for user in users})

        entries = self.audit_entries("data_deletion")
        self.assertEqual(len(entries), 1)
        event = json.loads(entries[0]["new_value"])
        self.assertEqual(entries[0]["config_key"], f"user:{self.user_id}:delete")
        self.assertEqual(entries[0]["changed_by"], "admin-pubkey")
        self.assertEqual(event["workflow"], "delete_user")
        self.assertEqual(event["status"], "succeeded")
        self.assertEqual(event["counts"]["succeeded"], 4)
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=data_deletion")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_user_deletion_is_safe_to_repeat(self) -> None:
        first = self.client.delete(f"/users/{self.user_id}")
        self.assertEqual(first.status_code, 200)

        second = self.client.delete(f"/users/{self.user_id}")

        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["deletion"]["status"], "succeeded")
        self.assertEqual({result["status"] for result in body["deletion"]["results"]}, {"skipped"})

        entries = self.audit_entries("data_deletion")
        idempotent_entry = next(
            entry for entry in entries
            if json.loads(entry["new_value"])["counts"]["skipped"] == 4
        )
        idempotent_event = json.loads(idempotent_entry["new_value"])
        self.assertEqual(idempotent_entry["config_key"], f"user:{self.user_id}:delete")
        self.assertEqual(idempotent_event["workflow"], "delete_user")
        self.assertEqual(idempotent_event["counts"]["skipped"], 4)

    def test_repeat_deletion_reports_late_conversation_cleanup(self) -> None:
        first = self.client.delete(f"/users/{self.user_id}")
        self.assertEqual(first.status_code, 200)
        self.query._sessions["late-session"] = {
            "id": "late-session",
            "owner_type": "user",
            "owner_id": str(self.user_id),
            "messages": [],
        }

        second = self.client.delete(f"/users/{self.user_id}")

        self.assertEqual(second.status_code, 200)
        actions = {result["action"]: result for result in second.json()["deletion"]["results"]}
        self.assertEqual(actions["delete_conversations"]["status"], "succeeded")
        self.assertEqual(actions["delete_conversations"]["count"], 1)
        self.assertNotIn("late-session", self.query._sessions)

    def test_admin_subject_binding_cleanup_is_not_reported_as_conversation_deletion(self) -> None:
        self.query._sessions.clear()
        self.main.admin_conversation_states["admin-session"] = {
            "subject_user_id": self.user_id,
            "pending_user_memory_change": {"action": "create"},
        }

        response = self.client.delete(f"/users/{self.user_id}")

        self.assertEqual(response.status_code, 200)
        actions = {result["action"]: result for result in response.json()["deletion"]["results"]}
        self.assertEqual(actions["delete_conversations"]["status"], "skipped")
        self.assertNotIn("subject_user_id", self.main.admin_conversation_states["admin-session"])
        self.assertNotIn("pending_user_memory_change", self.main.admin_conversation_states["admin-session"])

    def test_user_deletion_requires_authentication(self) -> None:
        self.main.app.dependency_overrides.clear()

        response = self.client.delete(f"/users/{self.user_id}")

        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
