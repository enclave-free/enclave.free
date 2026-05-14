import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from httpx import Response
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class RetentionExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer,
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "sanctum.db"
        self.uploads_dir = Path(self.tmp.name) / "uploads"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["UPLOADS_DIR"] = str(self.uploads_dir)
        os.environ["SECRET_KEY"] = "test-secret"

        import database
        import auth
        import deployment_config
        import ingest
        import lifecycle
        import query
        import main

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.deployment_config = importlib.reload(deployment_config)
        self.ingest = importlib.reload(ingest)
        self.lifecycle = importlib.reload(lifecycle)
        self.query = importlib.reload(query)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.ingest.JOBS = self.ingest._load_jobs_from_db()

        self.original_scheduler = self.ingest.schedule_document_processing
        self.ingest.schedule_document_processing = lambda *_args, **_kwargs: None
        self.original_chunk_deleter = self.ingest.delete_document_chunks
        self.deleted_chunk_job_ids: list[str] = []
        self.ingest.delete_document_chunks = self.record_chunk_delete

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
        self.main.app.dependency_overrides[self.lifecycle.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        self.ingest.schedule_document_processing = self.original_scheduler
        self.ingest.delete_document_chunks = self.original_chunk_deleter
        self.query._sessions.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
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

    async def record_chunk_delete(self, job_id: str) -> int:
        self.deleted_chunk_job_ids.append(job_id)
        return 2

    def upload_text(self, filename: str, content: str = "operator knowledge") -> Response:
        return self.client.post(
            "/ingest/upload",
            files={"file": (filename, content.encode("utf-8"), "text/plain")},
        )

    def mark_failed_job_stale(self, job_id: str) -> Path:
        job = self.ingest.JOBS[job_id]
        job["status"] = "failed"
        job["error"] = "Extraction failed"
        stale = (datetime.utcnow() - timedelta(days=10)).isoformat()
        job["updated_at"] = stale
        self.ingest._sync_job_to_db(job_id)
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE ingest_jobs SET updated_at = ? WHERE job_id = ?",
                (stale, job_id),
            )
        return Path(job["file_path"])

    def audit_entries(self, table_name: str) -> list[dict]:
        response = self.client.get(f"/admin/deployment/audit-log?table_name={table_name}")
        self.assertEqual(response.status_code, 200)
        return response.json()["entries"]

    def test_retention_deletes_stale_conversations_and_failed_document_artifacts(self) -> None:
        stale_session_id = "stale-session"
        recent_session_id = "recent-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "1",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
        }
        self.query._sessions[recent_session_id] = {
            "id": recent_session_id,
            "owner_type": "user",
            "owner_id": "1",
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
        }
        upload = self.upload_text("Broken.md")
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        artifact_path = self.mark_failed_job_stale(job_id)

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertIn(stale_session_id, body["retained"]["stale_conversations"])
        self.assertNotIn(stale_session_id, self.query._sessions)
        self.assertIn(recent_session_id, self.query._sessions)
        self.assertFalse(artifact_path.exists())
        self.assertIsNone(self.ingest.ingest_db.get_job(job_id))
        self.assertIn(job_id, self.deleted_chunk_job_ids)
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["retention_delete_stale_conversation"]["status"], "succeeded")
        self.assertEqual(actions["delete_document_metadata"]["status"], "succeeded")

        entries = self.audit_entries("data_deletion")
        retention_event = json.loads(entries[0]["new_value"])
        self.assertEqual(retention_event["workflow"], "run_retention")
        self.assertEqual(retention_event["status"], "succeeded")
        self.assertEqual(entries[0]["changed_by"], "admin-pubkey")
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=data_deletion")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_retention_is_safe_to_repeat_when_nothing_is_eligible(self) -> None:
        first = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )
        second = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertEqual(body["deletion"]["counts"]["skipped"], 1)
        self.assertEqual(body["deletion"]["results"][0]["action"], "run_retention")

    def test_retention_reports_partial_failure_for_retryable_document_cleanup(self) -> None:
        upload = self.upload_text("Broken.md")
        job_id = upload.json()["job_id"]
        self.mark_failed_job_stale(job_id)

        async def fail_chunk_delete(_job_id: str) -> int:
            raise RuntimeError("qdrant unavailable")

        self.ingest.delete_document_chunks = fail_chunk_delete

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "partial_failure")
        self.assertTrue(body["deletion"]["retryable"])
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["delete_retrieval_index"]["status"], "failed")
        self.assertTrue(actions["delete_retrieval_index"]["retryable"])
        self.assertEqual(actions["delete_document_metadata"]["status"], "skipped")
        self.assertIsNotNone(self.ingest.ingest_db.get_job(job_id))
        self.assertIn(job_id, self.ingest.JOBS)

    def test_retention_requires_admin(self) -> None:
        self.main.app.dependency_overrides.clear()

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
