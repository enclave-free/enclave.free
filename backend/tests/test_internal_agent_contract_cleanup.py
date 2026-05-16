import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class InternalAgentContractCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_internal_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["INTERNAL_AGENT_TOKEN"] = "test-internal-token"

        import database
        import internal_agent

        self.database = importlib.reload(database)
        self.internal_agent = importlib.reload(internal_agent)
        self.database.init_schema()

        app = FastAPI()
        app.include_router(self.internal_agent.router)
        self.client = TestClient(app)
        self.headers = {"X-Internal-Agent-Token": "test-internal-token"}

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("INTERNAL_AGENT_TOKEN", self._orig_internal_token)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def assert_compatibility_tombstone(self, response) -> None:
        self.assertEqual(response.status_code, 410)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "internal_contract_removed")
        self.assertIn("not part of the active Sage-to-Python contract", body["detail"]["message"])

    def test_internal_session_defaults_compatibility_endpoint_is_tombstoned(self) -> None:
        response = self.client.get("/internal/agent/session-defaults", headers=self.headers)

        self.assert_compatibility_tombstone(response)

    def test_internal_ai_config_effective_compatibility_endpoint_is_tombstoned(self) -> None:
        response = self.client.get("/internal/agent/ai-config/effective", headers=self.headers)

        self.assert_compatibility_tombstone(response)

    def test_internal_health_remains_available(self) -> None:
        response = self.client.get("/internal/agent/health", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})


if __name__ == "__main__":
    unittest.main()
