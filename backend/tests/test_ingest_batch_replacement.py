import asyncio
import base64
import hashlib
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from Crypto.Cipher import AES
from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class IngestBatchReplacementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self.uploads_dir = Path(self.tmp.name) / "uploads"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_logs_dir = os.environ.get("LOGS_DIR")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_content_encryption_key = os.environ.get("CONTENT_ENCRYPTION_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["UPLOADS_DIR"] = str(self.uploads_dir)
        os.environ["LOGS_DIR"] = str(Path(self.tmp.name) / "logs")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"

        import database
        import auth
        import deployment_config
        import ingest_db
        import ingest

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.deployment_config = importlib.reload(deployment_config)
        self.ingest_db = importlib.reload(ingest_db)
        self.ingest = importlib.reload(ingest)
        self.database.init_schema()
        self.ingest.JOBS = self.ingest._load_jobs_from_db()

        self.original_scheduler = self.ingest.schedule_document_processing
        self.ingest.schedule_document_processing = lambda *_args, **_kwargs: None
        self.original_chunk_deleter = self.ingest.delete_document_chunks
        self.deleted_chunk_job_ids = []
        self.ingest.delete_document_chunks = self.record_chunk_delete

        app = FastAPI()
        app.include_router(self.ingest.router)
        app.include_router(self.deployment_config.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        app.dependency_overrides[self.deployment_config.auth.require_admin] = lambda: {
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
        self._restore_env("LOGS_DIR", self._orig_logs_dir)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("CONTENT_ENCRYPTION_KEY", self._orig_content_encryption_key)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    async def record_chunk_delete(self, job_id: str) -> int:
        self.deleted_chunk_job_ids.append(job_id)
        return 3

    def upload_text(self, filename: str, content: str = "operator knowledge"):
        return self.client.post(
            "/ingest/upload",
            files={"file": (filename, content.encode("utf-8"), "text/plain")},
        )

    def test_upload_allows_plaintext_active_content_without_key_by_default(self) -> None:
        os.environ.pop("CONTENT_ENCRYPTION_KEY", None)

        upload = self.upload_text("Handbook.md", "operator knowledge")

        self.assertEqual(upload.status_code, 200)
        job = self.ingest.JOBS[upload.json()["job_id"]]
        artifact_path = Path(job["file_path"])
        self.assertEqual(artifact_path.read_bytes(), b"operator knowledge")

    def test_upload_stores_encrypted_artifact_when_content_key_configured(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"

        upload = self.upload_text("Handbook.md", "operator knowledge")

        self.assertEqual(upload.status_code, 200)
        job = self.ingest.JOBS[upload.json()["job_id"]]
        artifact_path = Path(job["file_path"])
        self.assertTrue(artifact_path.exists())
        self.assertNotEqual(artifact_path.read_bytes(), b"operator knowledge")
        self.assertTrue(artifact_path.read_bytes().startswith(b"enclave-artifact::v1::"))

    def test_legacy_artifact_ciphertext_is_not_supported(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        import content_artifacts

        nonce = b"1" * 12
        legacy_key = hashlib.sha256(b"test-content-key").digest()
        cipher = AES.new(legacy_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(b"operator knowledge")
        legacy_artifact = (
            b"sanctum-artifact::v1::"
            + base64.b64encode(nonce + tag + ciphertext)
        )

        self.assertFalse(content_artifacts.is_encrypted_artifact(legacy_artifact))
        self.assertNotEqual(content_artifacts.decrypt_bytes(legacy_artifact), b"operator knowledge")

    def test_upload_allows_plaintext_artifact_when_operator_disables_encryption(self) -> None:
        self.database.update_setting_with_audit(
            "DOCUMENT_ARTIFACT_ENCRYPTION",
            "disabled",
            changed_by="admin-pubkey",
        )

        upload = self.upload_text("Handbook.md", "operator knowledge")

        self.assertEqual(upload.status_code, 200)
        job = self.ingest.JOBS[upload.json()["job_id"]]
        artifact_path = Path(job["file_path"])
        self.assertEqual(artifact_path.read_bytes(), b"operator knowledge")

    def test_processing_persists_retrieval_chunk_text_encrypted_and_delete_removes_it(self) -> None:
        async def fake_store_chunk(*_args, **_kwargs):
            return {"qdrant": {"points_inserted": 1}}

        original_store_chunk = self.ingest.store_chunk
        self.ingest.store_chunk = fake_store_chunk
        try:
            upload = self.upload_text("Handbook.md", "operator knowledge for retrieval")
            self.assertEqual(upload.status_code, 200)
            job_id = upload.json()["job_id"]
            artifact_path = Path(self.ingest.JOBS[job_id]["file_path"])

            asyncio.run(self.ingest.process_document(job_id, artifact_path, sample_percent=100.0))

            chunk_id = self.ingest.generate_chunk_id(job_id, 0)
            chunk = self.client.get(f"/ingest/chunk/{chunk_id}")
            self.assertEqual(chunk.status_code, 200)
            self.assertEqual(chunk.json()["text"], "operator knowledge for retrieval")

            raw_rows = self.ingest_db.list_retrieval_chunks(job_id)
            self.assertEqual(len(raw_rows), 1)
            self.assertNotIn("operator knowledge", raw_rows[0]["encrypted_text"])

            response = self.client.delete(f"/ingest/jobs/{job_id}")
            self.assertEqual(response.status_code, 200)
            actions = {result["action"]: result for result in response.json()["deletion"]["results"]}
            self.assertEqual(actions["delete_retrieval_chunk_text"]["status"], "succeeded")
            self.assertEqual(self.ingest_db.list_retrieval_chunks(job_id), [])
        finally:
            self.ingest.store_chunk = original_store_chunk

    def test_processing_persists_plaintext_retrieval_chunk_text_without_key_by_default(self) -> None:
        self.database.update_setting_with_audit(
            "DOCUMENT_ARTIFACT_ENCRYPTION",
            "disabled",
            changed_by="admin-pubkey",
        )
        os.environ.pop("CONTENT_ENCRYPTION_KEY", None)

        async def fake_store_chunk(*_args, **_kwargs):
            return {"qdrant": {"points_inserted": 1}}

        original_store_chunk = self.ingest.store_chunk
        self.ingest.store_chunk = fake_store_chunk
        try:
            upload = self.upload_text("Handbook.md", "plaintext artifact and retrieval")
            self.assertEqual(upload.status_code, 200)
            job_id = upload.json()["job_id"]
            artifact_path = Path(self.ingest.JOBS[job_id]["file_path"])
            self.assertEqual(artifact_path.read_text(encoding="utf-8"), "plaintext artifact and retrieval")

            asyncio.run(self.ingest.process_document(job_id, artifact_path, sample_percent=100.0))

            job = self.ingest.JOBS[job_id]
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["processed_chunks"], 1)
            self.assertEqual(job["failed_chunks"], 0)
            raw_rows = self.ingest_db.list_retrieval_chunks(job_id)
            self.assertEqual(raw_rows[0]["encrypted_text"], "plaintext artifact and retrieval")
        finally:
            self.ingest.store_chunk = original_store_chunk

    def test_upload_requires_content_key_when_encryption_required(self) -> None:
        self.database.update_setting_with_audit(
            "DOCUMENT_ARTIFACT_ENCRYPTION",
            "required",
            changed_by="admin-pubkey",
        )
        os.environ.pop("CONTENT_ENCRYPTION_KEY", None)

        upload = self.upload_text("Handbook.md", "plaintext artifact but protected retrieval")
        self.assertEqual(upload.status_code, 503)
        self.assertIn("Content Encryption Key", upload.json()["detail"])
        self.assertEqual(self.ingest.JOBS, {})

    def test_startup_ignores_legacy_json_job_state(self) -> None:
        logs_dir = Path(os.environ["LOGS_DIR"])
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "jobs_state.json").write_text(
            json.dumps({
                "legacy-job": {
                    "filename": "Legacy.md",
                    "file_path": "/uploads/Legacy.md",
                    "ontology_id": "general",
                    "status": "completed",
                    "total_chunks": 1,
                    "processed_chunks": 1,
                }
            }),
            encoding="utf-8",
        )
        self.ingest.JOBS = {}

        asyncio.run(self.ingest.load_jobs_and_resume())

        self.assertEqual(self.ingest.JOBS, {})
        self.assertEqual(self.ingest_db.list_jobs(), [])

    def complete_job(self, job_id: str) -> None:
        """Mark a job completed for state-machine tests; does not exercise process_document."""
        job = self.ingest.JOBS[job_id]
        job["status"] = "completed"
        job["total_chunks"] = 1
        job["processed_chunks"] = 1
        self.ingest._sync_job_to_db(job_id)

    def audit_entries(self, table_name: str) -> list[dict]:
        response = self.client.get(f"/admin/deployment/audit-log?table_name={table_name}")
        self.assertEqual(response.status_code, 200)
        return response.json()["entries"]

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

        entries = self.audit_entries("document_actions")
        actions = {entry["config_key"]: json.loads(entry["new_value"]) for entry in entries}
        self.assertEqual(actions[f"document:{old_job_id}:queue"]["action"], "upload_document")
        self.assertEqual(actions[f"document:{replacement['job_id']}:queue"]["action"], "replace_document")
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=document_actions")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

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

        actions = {entry["config_key"]: json.loads(entry["new_value"]) for entry in self.audit_entries("document_actions")}
        self.assertEqual(actions[f"document:{new_job_id}:promote_replacement"]["action"], "promote_replacement")

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

    def test_batch_upload_preserves_safe_relative_paths_and_rejects_traversal(self) -> None:
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

    def test_admin_delete_document_removes_access_artifact_and_retrieval_entries(self) -> None:
        upload = self.upload_text("Handbook.md")
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        self.complete_job(job_id)

        defaults_response = self.client.put(
            f"/ingest/admin/documents/{job_id}/defaults",
            json={"is_available": True, "is_default_active": True, "display_order": 4},
        )
        self.assertEqual(defaults_response.status_code, 200)
        defaults_entries = self.audit_entries("document_defaults")
        self.assertEqual(defaults_entries[0]["config_key"], job_id)
        self.assertEqual(defaults_entries[0]["changed_by"], "admin-pubkey")
        file_path = Path(self.ingest.JOBS[job_id]["file_path"])
        self.assertTrue(file_path.exists())

        response = self.client.delete(f"/ingest/jobs/{job_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "deleted")
        self.assertEqual(body["deletion"]["status"], "succeeded")
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["delete_retrieval_index"]["status"], "succeeded")
        self.assertEqual(actions["delete_retrieval_chunk_text"]["status"], "succeeded")
        self.assertEqual(actions["delete_uploaded_document_artifact"]["status"], "succeeded")
        self.assertEqual(actions["delete_document_metadata"]["status"], "succeeded")
        self.assertEqual(actions["delete_runtime_document_state"]["status"], "succeeded")

        self.assertEqual(self.deleted_chunk_job_ids, [job_id])
        self.assertFalse(file_path.exists())
        self.assertNotIn(job_id, self.ingest.JOBS)
        self.assertNotIn(
            job_id,
            {doc["job_id"] for doc in self.client.get("/ingest/admin/documents/defaults").json()["documents"]},
        )

        deletion_entries = self.audit_entries("data_deletion")
        self.assertEqual(len(deletion_entries), 1)
        deletion_event = json.loads(deletion_entries[0]["new_value"])
        self.assertEqual(deletion_entries[0]["config_key"], f"document:{job_id}:delete")
        self.assertEqual(deletion_event["workflow"], "delete_document")
        self.assertEqual(deletion_event["status"], "succeeded")
        self.assertEqual(deletion_event["counts"]["succeeded"], 5)
        self.assertIn(
            f"document:{job_id}:delete",
            {entry["config_key"] for entry in self.audit_entries("document_actions")},
        )
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=data_deletion")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_admin_delete_document_is_safe_to_repeat(self) -> None:
        upload = self.upload_text("Handbook.md")
        job_id = upload.json()["job_id"]
        self.complete_job(job_id)

        first = self.client.delete(f"/ingest/jobs/{job_id}")
        self.assertEqual(first.status_code, 200)

        second = self.client.delete(f"/ingest/jobs/{job_id}")

        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertEqual(body["status"], "deleted")
        self.assertEqual(body["deletion"]["status"], "succeeded")
        self.assertEqual(body["deletion"]["counts"]["skipped"], 5)
        self.assertEqual(
            {result["status"] for result in body["deletion"]["results"]},
            {"skipped"},
        )

        entries = self.audit_entries("data_deletion")
        idempotent_entry = next(
            entry for entry in entries
            if json.loads(entry["new_value"])["counts"]["skipped"] == 5
        )
        idempotent_event = json.loads(idempotent_entry["new_value"])
        self.assertEqual(idempotent_entry["config_key"], f"document:{job_id}:delete")
        self.assertEqual(idempotent_event["status"], "succeeded")
        self.assertEqual(idempotent_event["counts"]["skipped"], 5)

    def test_admin_delete_document_rejects_artifact_path_outside_uploads_root(self) -> None:
        upload = self.upload_text("Handbook.md")
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        self.complete_job(job_id)
        outside_file = Path(self.tmp.name) / "outside.txt"
        outside_file.write_text("do not delete")
        self.ingest.JOBS[job_id]["file_path"] = str(outside_file)
        with self.ingest_db.get_cursor() as cursor:
            cursor.execute("UPDATE ingest_jobs SET file_path = ? WHERE job_id = ?", (str(outside_file), job_id))

        response = self.client.delete(f"/ingest/jobs/{job_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(body["deletion"]["status"], "partial_failure")
        self.assertFalse(body["deletion"]["retryable"])
        self.assertEqual(actions["delete_uploaded_document_artifact"]["status"], "failed")
        self.assertFalse(actions["delete_uploaded_document_artifact"]["retryable"])
        self.assertTrue(outside_file.exists())
        self.assertIsNotNone(self.ingest_db.get_job(job_id))
        self.assertEqual(actions["delete_document_metadata"]["status"], "skipped")

    def test_delete_document_requires_admin(self) -> None:
        app = FastAPI()
        app.include_router(self.ingest.router)
        client = TestClient(app)

        response = client.delete("/ingest/jobs/not-a-real-job")

        self.assertIn(response.status_code, (401, 403))

    def test_admin_cleanup_removes_failed_ingestion_artifacts(self) -> None:
        upload = self.upload_text("Broken.md")
        job_id = upload.json()["job_id"]
        job = self.ingest.JOBS[job_id]
        job["status"] = "failed"
        job["error"] = "Extraction failed"
        self.ingest._sync_job_to_db(job_id)
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id=f"{job_id}_chunk_0000",
            job_id=job_id,
            chunk_index=0,
            source_file="Broken.md",
            text="failed job retrieval text",
        )
        file_path = Path(job["file_path"])
        self.assertTrue(file_path.exists())

        response = self.client.post("/ingest/admin/documents/artifacts/cleanup")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertEqual(body["cleaned_jobs"], 1)
        self.assertEqual(body["eligible_jobs"][0]["reason"], "failed_ingestion")
        self.assertFalse(file_path.exists())
        self.assertNotIn(job_id, self.ingest.JOBS)
        actions = {result["action"]: result for result in body["eligible_jobs"][0]["deletion"]["results"]}
        self.assertEqual(actions["delete_retrieval_chunk_text"]["status"], "succeeded")
        self.assertEqual(self.ingest_db.list_retrieval_chunks(job_id), [])

        entries = self.audit_entries("data_deletion")
        self.assertEqual(entries[0]["config_key"], f"document:{job_id}:cleanup")
        cleanup_event = json.loads(entries[0]["new_value"])
        self.assertEqual(cleanup_event["workflow"], "cleanup_document_artifacts:failed_ingestion")
        self.assertEqual(cleanup_event["status"], "succeeded")

    def test_admin_cleanup_removes_superseded_replacement_artifacts_without_current_document(self) -> None:
        first = self.upload_text("Handbook.md")
        old_job_id = first.json()["job_id"]
        self.complete_job(old_job_id)
        old_file_path = Path(self.ingest.JOBS[old_job_id]["file_path"])

        second = self.upload_text("Handbook.md", "updated knowledge")
        new_job_id = second.json()["job_id"]
        self.complete_job(new_job_id)
        asyncio.run(self.ingest.promote_replacement(new_job_id))

        response = self.client.post("/ingest/admin/documents/artifacts/cleanup")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertEqual(body["cleaned_jobs"], 1)
        self.assertEqual(body["eligible_jobs"][0]["job_id"], old_job_id)
        self.assertEqual(body["eligible_jobs"][0]["reason"], "superseded_document")
        self.assertNotIn(old_job_id, self.ingest.JOBS)
        self.assertFalse(old_file_path.exists())
        jobs_by_id = {
            job["job_id"]: job
            for job in self.client.get("/ingest/jobs").json()["jobs"]
        }
        self.assertIn(new_job_id, jobs_by_id)
        self.assertTrue(jobs_by_id[new_job_id]["is_current"])

    def test_admin_cleanup_preserves_current_document_during_pending_replacement(self) -> None:
        first = self.upload_text("Handbook.md")
        old_job_id = first.json()["job_id"]
        self.complete_job(old_job_id)

        second = self.upload_text("Handbook.md", "updated knowledge")
        new_job_id = second.json()["job_id"]

        response = self.client.post("/ingest/admin/documents/artifacts/cleanup")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["cleaned_jobs"], 0)
        jobs_by_id = {
            job["job_id"]: job
            for job in self.client.get("/ingest/jobs").json()["jobs"]
        }
        self.assertIn(old_job_id, jobs_by_id)
        self.assertIn(new_job_id, jobs_by_id)
        self.assertTrue(jobs_by_id[old_job_id]["is_current"])
        self.assertFalse(jobs_by_id[new_job_id]["is_current"])


if __name__ == "__main__":
    unittest.main()
