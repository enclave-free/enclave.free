from __future__ import annotations

import importlib
import os
import sys
import tempfile
import threading
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from coincurve import PrivateKey


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class InternalSessionLogsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_internal_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        self._orig_store_module = sys.modules.get("store")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["INTERNAL_AGENT_TOKEN"] = "test-internal-token"
        store_stub = types.ModuleType("store")
        store_stub.embed_texts = lambda texts: [[0.0] for _ in texts]
        store_stub.COLLECTION_NAME = "test"
        store_stub.QDRANT_HOST = "localhost"
        store_stub.QDRANT_PORT = 6333
        sys.modules["store"] = store_stub

        import database
        import internal_agent
        import session_logs

        self.database = importlib.reload(database)
        self.session_logs = importlib.reload(session_logs)
        self.internal_agent = importlib.reload(internal_agent)
        self.database.init_schema()

        app = FastAPI()
        app.include_router(self.internal_agent.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        if self._orig_sqlite_path is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = self._orig_sqlite_path
        if self._orig_internal_token is None:
            os.environ.pop("INTERNAL_AGENT_TOKEN", None)
        else:
            os.environ["INTERNAL_AGENT_TOKEN"] = self._orig_internal_token
        if self._orig_store_module is None:
            sys.modules.pop("store", None)
        else:
            sys.modules["store"] = self._orig_store_module
        self.tmp.cleanup()

    def _headers(self) -> dict[str, str]:
        return {"x-internal-agent-token": "test-internal-token"}

    def _session_log_count(self) -> int:
        with self.database.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM session_logs")
            return int(cursor.fetchone()["count"])

    def test_internal_user_session_logs_reject_non_user_actor(self) -> None:
        response = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {"id": 1, "type": "admin", "approved": True},
                "turns": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ],
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._session_log_count(), 0)

    def test_internal_failed_transcript_save_removes_metadata_row(self) -> None:
        user_id = self.database.create_user()

        response = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {"id": user_id, "type": "user", "approved": True},
                "turns": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ],
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("No admin configured", response.json()["detail"])
        self.assertEqual(self._session_log_count(), 0)

    def test_reserved_looking_email_does_not_suppress_normal_user_log(self) -> None:
        admin_key = PrivateKey()
        self.database.add_admin(admin_key.public_key.format(compressed=True)[1:].hex())
        user_id = self.database.create_user(
            pubkey=PrivateKey().public_key.format(compressed=True)[1:].hex(),
            email="test-user+ordinary@enclave.test",
            name="Ordinary User",
        )

        response = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {
                    "id": user_id,
                    "type": "user",
                    "approved": True,
                    "email": "test-user+ordinary@enclave.test",
                },
                "turns": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["status"], "skipped")
        self.assertEqual(self._session_log_count(), 1)

    def test_instance_derived_test_user_skips_ambient_log(self) -> None:
        import impersonation

        admin_key = PrivateKey()
        admin_pubkey = admin_key.public_key.format(compressed=True)[1:].hex()
        self.database.add_admin(admin_pubkey)
        user_type_id = self.database.create_user_type("Student")
        user_id = self.database.create_user(
            pubkey=impersonation.derive_test_user_pubkey(
                admin_pubkey,
                user_type_id,
            ),
            email=f"test-user+type{user_type_id}@enclave.test",
            name="Test User",
            user_type_id=user_type_id,
        )

        response = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {
                    "id": user_id,
                    "type": "user",
                    "approved": True,
                    "email": f"test-user+type{user_type_id}@enclave.test",
                    "user_type_id": user_type_id,
                },
                "turns": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "skipped")
        self.assertEqual(response.json()["log_id"], "")
        self.assertEqual(self._session_log_count(), 0)

    def test_internal_user_session_log_updates_existing_sage_session_record(self) -> None:
        admin_key = PrivateKey()
        self.database.add_admin(admin_key.public_key.format(compressed=True)[1:].hex())
        user_id = self.database.create_user()

        first = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {"id": user_id, "type": "user", "approved": True},
                "sage_session_id": "sage-session-1",
                "turns": [
                    {"role": "user", "content": "first question"},
                    {"role": "assistant", "content": "first answer"},
                ],
            },
        )
        second = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {"id": user_id, "type": "user", "approved": True},
                "sage_session_id": "sage-session-1",
                "turns": [
                    {"role": "user", "content": "first question"},
                    {"role": "assistant", "content": "first answer"},
                    {"role": "user", "content": "second question"},
                    {"role": "assistant", "content": "second answer"},
                ],
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self._session_log_count(), 1)
        self.assertEqual(second.json()["log_id"], first.json()["log_id"])
        self.assertEqual(second.json()["turn_count"], 4)
        stale = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {"id": user_id, "type": "user", "approved": True},
                "sage_session_id": "sage-session-1",
                "turns": [
                    {"role": "user", "content": "first question"},
                    {"role": "assistant", "content": "first answer"},
                ],
            },
        )
        self.assertEqual(stale.status_code, 200)
        self.assertEqual(stale.json()["log_id"], first.json()["log_id"])
        self.assertEqual(stale.json()["turn_count"], 4)
        with self.database.get_cursor() as cursor:
            cursor.execute("SELECT transcript_ciphertext, turn_count FROM session_logs")
            row = cursor.fetchone()
            ciphertext = row["transcript_ciphertext"]
            turn_count = row["turn_count"]
        self.assertIsNotNone(ciphertext)
        self.assertNotIn("second answer", ciphertext)
        self.assertEqual(turn_count, 4)

    def test_internal_user_session_log_reuse_is_concurrent_idempotent(self) -> None:
        admin_key = PrivateKey()
        self.database.add_admin(admin_key.public_key.format(compressed=True)[1:].hex())
        user_id = self.database.create_user()
        barrier = threading.Barrier(2)

        def post_session(content: str):
            barrier.wait(timeout=5)
            return self.client.post(
                "/internal/agent/session-logs",
                headers=self._headers(),
                json={
                    "actor": {"id": user_id, "type": "user", "approved": True},
                    "sage_session_id": "sage-session-concurrent",
                    "turns": [
                        {"role": "user", "content": content},
                        {"role": "assistant", "content": f"answer to {content}"},
                    ],
                },
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(
                    post_session,
                    ["first concurrent turn", "second concurrent turn"],
                )
            )

        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(self._session_log_count(), 1)
        self.assertEqual(responses[0].json()["log_id"], responses[1].json()["log_id"])

    def test_internal_user_session_log_reuse_is_scoped_to_subject_user(self) -> None:
        admin_key = PrivateKey()
        self.database.add_admin(admin_key.public_key.format(compressed=True)[1:].hex())
        first_user_id = self.database.create_user()
        second_user_id = self.database.create_user()

        first = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {"id": first_user_id, "type": "user", "approved": True},
                "sage_session_id": "shared-sage-session",
                "turns": [
                    {"role": "user", "content": "first user question"},
                    {"role": "assistant", "content": "first user answer"},
                ],
            },
        )
        second = self.client.post(
            "/internal/agent/session-logs",
            headers=self._headers(),
            json={
                "actor": {"id": second_user_id, "type": "user", "approved": True},
                "sage_session_id": "shared-sage-session",
                "turns": [
                    {"role": "user", "content": "second user question"},
                    {"role": "assistant", "content": "second user answer"},
                ],
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(second.json()["log_id"], first.json()["log_id"])
        self.assertEqual(self._session_log_count(), 2)


if __name__ == "__main__":
    unittest.main()
