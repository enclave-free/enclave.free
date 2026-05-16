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


class AgentRuntimeRouteTombstonesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer,
        )
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import auth
        import database
        import main
        import query

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.query = importlib.reload(query)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "id": 1,
            "email": "user@example.test",
            "user_type_id": None,
        }
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.query.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "id": 1,
            "email": "user@example.test",
            "user_type_id": None,
        }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        if self._orig_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._orig_sentence_transformers
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def assert_tombstone(self, response) -> None:
        self.assertEqual(response.status_code, 410)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "sage_route_required")
        self.assertIn("Sage owns this public Agent Runtime route", body["detail"]["message"])

    def test_python_llm_chat_route_is_tombstoned(self) -> None:
        response = self.client.post("/llm/chat", json={"message": "hello"})

        self.assert_tombstone(response)

    def test_python_llm_chat_stream_route_is_tombstoned(self) -> None:
        response = self.client.post("/llm/chat/stream", json={"message": "hello"})

        self.assert_tombstone(response)

    def test_python_session_defaults_route_is_tombstoned(self) -> None:
        response = self.client.get("/session-defaults")

        self.assert_tombstone(response)

    def test_python_query_route_is_tombstoned(self) -> None:
        response = self.client.post("/query", json={"question": "hello"})

        self.assert_tombstone(response)

    def test_python_query_stream_route_is_tombstoned(self) -> None:
        response = self.client.post("/query/stream", json={"question": "hello"})

        self.assert_tombstone(response)

    def test_python_query_session_get_route_is_tombstoned(self) -> None:
        response = self.client.get("/query/session/test-session")

        self.assert_tombstone(response)

    def test_python_query_session_delete_route_is_tombstoned(self) -> None:
        response = self.client.delete("/query/session/test-session")

        self.assert_tombstone(response)

    def test_python_admin_tools_execute_route_is_tombstoned(self) -> None:
        response = self.client.post(
            "/admin/tools/execute",
            json={"tool_id": "db-query", "query": "SELECT 1"},
        )

        self.assert_tombstone(response)
