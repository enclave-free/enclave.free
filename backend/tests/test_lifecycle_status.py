import importlib
import json
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
        import database
        import lifecycle

        self.previous_sqlite_path = os.environ.get("SQLITE_PATH")
        self.db_path = Path(self.temp_dir.name) / "sanctum.db"
        os.environ["SQLITE_PATH"] = str(self.db_path)

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.lifecycle = importlib.reload(lifecycle)
        self.database.init_schema()

        app = FastAPI()
        app.include_router(self.lifecycle.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        if self.previous_sqlite_path is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = self.previous_sqlite_path
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

    def test_lifecycle_status_summarizes_deletion_tombstones(self) -> None:
        self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id="conversation-1",
            former_subject_ref="deleted_user:42",
            status="incomplete",
            source="retention_execution",
            workflow="run_retention",
            deletion={
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [],
            },
        )
        self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id="conversation-2",
            former_subject_ref="deleted_user:43",
            status="completed",
            source="retry",
            workflow="retry_deletion_tombstone",
            deletion={
                "status": "succeeded",
                "retryable": False,
                "counts": {"succeeded": 1, "skipped": 0, "failed": 0},
                "results": [],
            },
        )

        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["deletion_tombstones"]["total"], 2)
        self.assertEqual(body["deletion_tombstones"]["incomplete"], 1)
        self.assertEqual(body["deletion_tombstones"]["completed"], 1)
        self.assertEqual(
            body["deletion_tombstones"]["by_class"]["sage_session_memory"]["incomplete"],
            1,
        )
        serialized = json.dumps(body["deletion_tombstones"])
        self.assertNotIn("deleted_user", serialized)
        self.assertNotIn("conversation-", serialized)

    def test_incomplete_deletion_tombstones_are_idempotent_per_conversation(self) -> None:
        first_id = self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id="conversation-1",
            former_subject_ref="deleted_user:42",
            status="incomplete",
            source="retention_execution",
            workflow="run_retention",
            deletion={
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [],
            },
        )
        second_id = self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id="conversation-1",
            former_subject_ref="deleted_user:42",
            status="incomplete",
            source="retention_execution",
            workflow="run_retention",
            deletion={
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [],
            },
        )

        tombstones = self.database.list_deletion_tombstones()

        self.assertEqual(first_id, second_id)
        self.assertEqual(len(tombstones), 1)

    def test_lifecycle_status_requires_admin_authentication(self) -> None:
        app = FastAPI()
        app.include_router(self.lifecycle.router)
        client = TestClient(app)

        response = client.get("/admin/lifecycle/status")

        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
