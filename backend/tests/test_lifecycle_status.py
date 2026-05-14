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


class LifecycleStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["UPLOADS_DIR"] = str(Path(self.temp_dir.name) / "uploads")

        import auth
        import lifecycle

        self.auth = importlib.reload(auth)
        self.lifecycle = importlib.reload(lifecycle)

        app = FastAPI()
        app.include_router(self.lifecycle.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.previous_uploads_dir is None:
            os.environ.pop("UPLOADS_DIR", None)
        else:
            os.environ["UPLOADS_DIR"] = self.previous_uploads_dir
        self.temp_dir.cleanup()

    def test_admin_can_inspect_instance_data_lifecycle_status(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        classes_by_key = {
            data_class["key"]: data_class
            for data_class in body["data_classes"]
        }

        for key in (
            "user_profiles",
            "document_library",
            "retrieval_index",
            "uploaded_document_artifacts",
            "sage_session_memory",
            "audit_log",
        ):
            self.assertIn(key, classes_by_key)

        session_memory = classes_by_key["sage_session_memory"]
        self.assertEqual(session_memory["owner"], "Sage")
        self.assertIn("Postgres", session_memory["storage_targets"])
        self.assertEqual(session_memory["deletion"]["status"], "complete")
        self.assertEqual(session_memory["retention"]["status"], "partial")
        self.assertIn(
            "stale active Conversation",
            session_memory["retention"]["summary"],
        )

    def test_lifecycle_status_requires_admin_authentication(self) -> None:
        app = FastAPI()
        app.include_router(self.lifecycle.router)
        client = TestClient(app)

        response = client.get("/admin/lifecycle/status")

        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
