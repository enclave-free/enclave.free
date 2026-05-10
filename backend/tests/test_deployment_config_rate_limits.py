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


class DeploymentConfigRateLimitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "sanctum.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"

        import auth
        import database
        import deployment_config

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.deployment_config = importlib.reload(deployment_config)
        self.database.init_schema()
        self.deployment_config._sync_env_to_db()

        app = FastAPI()
        app.include_router(self.deployment_config.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_rate_limit_config_rejects_non_positive_and_non_integer_values(self) -> None:
        for value in ("0", "-1", "abc"):
            with self.subTest(value=value):
                response = self.client.put(
                    "/admin/deployment/config/RATE_LIMIT_CHAT_PER_MINUTE",
                    json={"value": value},
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["detail"], "RATE_LIMIT_CHAT_PER_MINUTE must be a positive integer")

    def test_rate_limit_config_persists_positive_integer_values(self) -> None:
        response = self.client.put(
            "/admin/deployment/config/RATE_LIMIT_CHAT_PER_MINUTE",
            json={"value": "42"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["key"], "RATE_LIMIT_CHAT_PER_MINUTE")
        self.assertEqual(response.json()["value"], "42")


if __name__ == "__main__":
    unittest.main()
