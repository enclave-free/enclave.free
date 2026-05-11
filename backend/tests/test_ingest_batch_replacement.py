import asyncio
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


class IngestBatchReplacementTest(unittest.TestCase):
    def setUp(self) -> None:
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
        import ingest_db
        import ingest

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.ingest_db = importlib.reload(ingest_db)
        self.ingest = importlib.reload(ingest)
        self.database.init_schema()
        self.ingest.JOBS = self.ingest._load_jobs_from_db()

        self.original_scheduler = self.ingest.schedule_document_processing
        self.ingest.schedule_document_processing = lambda *_args, **_kwargs: None
        self.original_chunk_deleter = self.ingest.delete_document_chunks
        self.ingest.delete_document_chunks = self.noop_chunk_delete

        app = FastAPI()
        app.include_router(self.ingest.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.ingest.schedule_document_processing = self.original_scheduler
        self.ingest.delete_document_chunks = self.original_chunk_deleter
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    async def noop_chunk_delete(self, _job_id: str) -> int:
        return 0

    def upload_text(self, filename: str, content: str = "operator knowledge"):
        return self.client.post(
            "/ingest/upload",
            files={"file": (filename, content.encode("utf-8"), "text/plain")},
        )

    def complete_job(self, job_id: str) -> None:
        """Mark a job completed for state-machine tests; does not exercise process_document."""
        job = self.ingest.JOBS[job_id]
        job["status"] = "completed"
        job["total_chunks"] = 1
        job["processed_chunks"] = 1
        self.ingest._sync_job_to_db(job_id)

    def test_single_upload_replacement_keeps_old_document_current_while_pending(self):
        first = self.upload_text("Handbook.md")
        self.assertEqual(first.status_code, 200)
        old_job_id = first.json()["job_id"]
        self.complete_job(old_job_id)

        second = self.upload_text("Handbook.md", "updated knowledge")
        self.assertEqual(second.status_code, 200)
        replacement = second.json()

        self.assertEqual(replacement["replacement_for_job_id"], old_job_id)
        self.assertEqual(replacement["replacement_for_filename"], "Handbook.md")

        jobs = self.client.get("/ingest/jobs").json()["jobs"]
        old_job = next(job for job in jobs if job["job_id"] == old_job_id)
        new_job = next(job for job in jobs if job["job_id"] == replacement["job_id"])
        self.assertTrue(old_job["is_current"])
        self.assertFalse(new_job["is_current"])
        self.assertEqual(new_job["replacement_for_job_id"], old_job_id)

    def test_successful_replacement_transfers_access_and_retires_old_document(self):
        first = self.upload_text("Handbook.md")
        old_job_id = first.json()["job_id"]
        self.complete_job(old_job_id)
        defaults_response = self.client.put(
            f"/ingest/admin/documents/{old_job_id}/defaults",
            json={"is_available": False, "is_default_active": False, "display_order": 7},
        )
        self.assertEqual(defaults_response.status_code, 200)

        second = self.upload_text("Handbook.md", "updated knowledge")
        new_job_id = second.json()["job_id"]
        self.complete_job(new_job_id)
        asyncio.run(self.ingest.promote_replacement(new_job_id))

        jobs = self.client.get("/ingest/jobs").json()["jobs"]
        jobs_by_id = {job["job_id"]: job for job in jobs}
        job_ids = set(jobs_by_id)
        self.assertIn(new_job_id, job_ids)
        self.assertIn(old_job_id, job_ids)
        self.assertTrue(jobs_by_id[new_job_id]["is_current"])
        self.assertFalse(jobs_by_id[old_job_id]["is_current"])
        self.assertEqual(jobs_by_id[old_job_id]["replaced_by_job_id"], new_job_id)

        defaults = self.client.get("/ingest/admin/documents/defaults").json()["documents"]
        new_defaults = next(doc for doc in defaults if doc["job_id"] == new_job_id)
        self.assertFalse(new_defaults["is_available"])
        self.assertFalse(new_defaults["is_default_active"])
        self.assertEqual(new_defaults["display_order"], 7)

    def test_batch_upload_partial_success_and_same_batch_duplicate_rejection(self):
        response = self.client.post(
            "/ingest/upload/batch",
            files=[
                ("files", ("Policies/Handbook.md", b"one", "text/markdown")),
                ("files", ("Policies/Handbook.md", b"two", "text/markdown")),
                ("files", ("Logo.png", b"png", "image/png")),
                ("files", ("FAQ.txt", b"faq", "text/plain")),
            ],
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["filename"] for item in body["accepted"]], ["Handbook.md", "FAQ.txt"])
        self.assertEqual(len(body["rejected"]), 2)
        reasons = [item["reason"] for item in body["rejected"]]
        self.assertIn("Duplicate document name in this batch", reasons)
        self.assertTrue(any("Unsupported file type" in reason for reason in reasons))

    def test_batch_upload_preserves_safe_relative_paths_and_rejects_traversal(self):
        response = self.client.post(
            "/ingest/upload/batch",
            data={"relative_paths": ["Policies/HR/Handbook.md", "../secrets.md"]},
            files=[
                ("files", ("Handbook.md", b"handbook", "text/markdown")),
                ("files", ("secrets.md", b"secret", "text/markdown")),
            ],
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["accepted"][0]["filename"], "Policies/HR/Handbook.md")
        self.assertEqual(body["rejected"][0]["filename"], "secrets.md")
        self.assertIn("cannot contain '..'", body["rejected"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
