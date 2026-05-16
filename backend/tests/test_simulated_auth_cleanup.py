import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SimulatedAuthCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_simulate_user = os.environ.get("SIMULATE_USER_AUTH")
        self._orig_simulate_admin = os.environ.get("SIMULATE_ADMIN_AUTH")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        os.environ["SIMULATE_USER_AUTH"] = "true"
        os.environ["SIMULATE_ADMIN_AUTH"] = "true"

        import auth
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.database.update_deployment_config("SIMULATE_USER_AUTH", "true", "test")
        self.database.update_deployment_config("SIMULATE_ADMIN_AUTH", "true", "test")
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("SIMULATE_USER_AUTH", self._orig_simulate_user)
        self._restore_env("SIMULATE_ADMIN_AUTH", self._orig_simulate_admin)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_public_config_does_not_expose_simulated_auth_flags(self) -> None:
        response = self.client.get("/config/public")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn("simulated_auth", data)
        self.assertNotIn("simulate_admin_auth", data)
        self.assertNotIn("simulate_user_auth", data)
        self.assertNotIn("simulated_auth_enabled", data)

    def test_dev_session_endpoint_is_absent_even_when_stale_flags_are_enabled(self) -> None:
        response = self.client.post(
            "/auth/dev-session",
            json={"email": "user@example.test", "name": "User"},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
