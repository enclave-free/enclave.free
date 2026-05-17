from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from httpx import Response


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class AgentRuntimeRoutesAbsentTest(unittest.TestCase):
    def setUp(self) -> None:
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

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def assert_absent(self, response: Response) -> None:
        self.assertEqual(response.status_code, 404)

    def test_python_llm_chat_route_is_absent(self) -> None:
        self.assert_absent(self.client.post("/llm/chat", json={"message": "hello"}))

    def test_python_llm_chat_stream_route_is_absent(self) -> None:
        self.assert_absent(self.client.post("/llm/chat/stream", json={"message": "hello"}))

    def test_python_session_defaults_route_is_absent(self) -> None:
        self.assert_absent(self.client.get("/session-defaults"))

    def test_python_query_route_is_absent(self) -> None:
        self.assert_absent(self.client.post("/query", json={"question": "hello"}))

    def test_python_query_stream_route_is_absent(self) -> None:
        self.assert_absent(self.client.post("/query/stream", json={"question": "hello"}))

    def test_python_query_session_get_route_is_absent(self) -> None:
        self.assert_absent(self.client.get("/query/session/test-session"))

    def test_python_query_session_delete_route_is_absent(self) -> None:
        self.assert_absent(self.client.delete("/query/session/test-session"))

    def test_python_admin_tools_execute_route_is_absent(self) -> None:
        self.assert_absent(self.client.post(
            "/admin/tools/execute",
            json={"tool_id": "db-query", "query": "SELECT 1"},
        ))


if __name__ == "__main__":
    unittest.main()
