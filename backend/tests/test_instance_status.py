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


class InstanceStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import database
        import inference_repair
        import main

        self.database = importlib.reload(database)
        self.inference_repair = importlib.reload(inference_repair)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self.database._deployment_secret_key = None
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

    def test_instance_status_reports_degraded_protected_inference(self) -> None:
        self.inference_repair.mark_startup_verification_unavailable(
            status="missing",
            reason="LLM_API_KEY not configured",
        )

        response = self.client.get("/instance/status")

        self.assertEqual(response.status_code, 200)
        protected = response.json()["protected_inference"]
        self.assertEqual(protected["mode"], "degraded_admin_repair")
        self.assertFalse(protected["protected_inference_available"])
        self.assertEqual(protected["reason"], "LLM_API_KEY not configured")


if __name__ == "__main__":
    unittest.main()
