from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import types
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from httpx import Response
from fastapi import HTTPException
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
        self.db_path = Path(self.tmp.name) / "enclave.db"
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
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "sage_session_memory": {
                    "lifecycle_data_class": "sage_session_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": False,
                },
                "uploaded_document_artifacts": {
                    "lifecycle_data_class": "uploaded_document_artifacts",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": False,
                },
                "user_memory": {
                    "lifecycle_data_class": "user_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": False,
                },
            }, sort_keys=True),
        )

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

    def mark_job_stale(self, job_id: str, *, status: str) -> Path:
        job = self.ingest.JOBS[job_id]
        job["status"] = status
        stale = (datetime.utcnow() - timedelta(days=10)).isoformat()
        job["updated_at"] = stale
        self.ingest._sync_job_to_db(job_id)
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE ingest_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (status, stale, job_id),
            )
        return Path(job["file_path"])

    def audit_entries(self, table_name: str) -> list[dict]:
        response = self.client.get(f"/admin/deployment/audit-log?table_name={table_name}")
        self.assertEqual(response.status_code, 200)
        return response.json()["entries"]

    def create_stale_user_memory(self, *, content: str = "Prefers private retention cleanup.") -> int:
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (pubkey, approved) VALUES (?, ?)",
                (uuid.uuid4().hex + uuid.uuid4().hex, 1),
            )
            user_id = int(cursor.lastrowid)
        memory_id = self.database.create_user_memory(
            subject_user_id=user_id,
            kind="preference",
            content=content,
            source_kind="ambient",
            source_conversation_id="memory-source-conversation",
            author_actor="sage:ambient_capture",
        )
        stale = (datetime.utcnow() - timedelta(days=10)).isoformat()
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE user_memories SET created_at = ?, updated_at = ? WHERE id = ?",
                (stale, stale, memory_id),
            )
        return memory_id

    def test_retention_only_targets_expirable_or_superseded_user_memory(self) -> None:
        durable_id = self.create_stale_user_memory(content="Durable memory must survive retention.")
        expirable_id = self.create_stale_user_memory(content="Expirable memory can be retained.")
        with self.database.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_memories
                SET source_kind = 'admin-confirmed',
                    author_actor = 'admin',
                    retention_class = 'durable'
                WHERE id = ?
                """,
                (durable_id,),
            )

        preview = self.client.post(
            "/admin/lifecycle/retention/preview",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertEqual(preview.status_code, 200)
        preview_body = preview.json()
        self.assertEqual(preview_body["counts"]["user_memories"], 1)
        self.assertEqual(preview_body["eligible"]["user_memories"], [expirable_id])
        self.assertNotIn("Durable memory", json.dumps(preview_body))
        self.assertNotIn("Expirable memory", json.dumps(preview_body))

        run = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(run.status_code, 200)
        run_body = run.json()
        self.assertEqual(run_body["retained"]["user_memories"], [expirable_id])
        self.assertEqual(self.database.get_user_memory(expirable_id)["status"], "deleted")
        self.assertEqual(self.database.get_user_memory(durable_id)["status"], "active")
        self.assertNotIn("Durable memory", json.dumps(run_body))
        self.assertNotIn("Expirable memory", json.dumps(run_body))

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
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
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
        self.assertIn("run_record", body)
        self.assertEqual(body["run_record"]["trigger"], "manual")
        self.assertEqual(body["run_record"]["actor"], "admin-pubkey")
        entries = self.audit_entries("data_deletion")
        retention_event = json.loads(entries[0]["new_value"])
        self.assertEqual(retention_event["workflow"], "run_retention")
        self.assertEqual(retention_event["status"], "succeeded")
        self.assertEqual(entries[0]["changed_by"], "admin-pubkey")
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=data_deletion")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_scheduled_retention_cleans_abandoned_and_orphaned_artifacts_but_keeps_current_documents(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "uploaded_document_artifacts": {
                    "lifecycle_data_class": "uploaded_document_artifacts",
                    "enabled": True,
                    "retention_window_days": 0,
                    "scheduled_enforcement_enabled": True,
                },
            }, sort_keys=True),
        )
        abandoned_upload = self.upload_text("Abandoned.md")
        abandoned_job_id = abandoned_upload.json()["job_id"]
        abandoned_path = self.mark_job_stale(abandoned_job_id, status="processing")
        current_upload = self.upload_text("Current.md")
        current_job_id = current_upload.json()["job_id"]
        current_path = Path(self.ingest.JOBS[current_job_id]["file_path"])
        self.ingest.JOBS[current_job_id]["status"] = "completed"
        self.ingest._sync_job_to_db(current_job_id)
        active_processing_upload = self.upload_text("ActiveProcessing.md")
        active_processing_job_id = active_processing_upload.json()["job_id"]
        active_processing_path = Path(self.ingest.JOBS[active_processing_job_id]["file_path"])
        self.ingest.JOBS[active_processing_job_id]["status"] = "processing"
        self.ingest._sync_job_to_db(active_processing_job_id)
        orphan_path = self.uploads_dir / "orphaned-upload.md"
        orphan_path.write_text("orphaned uploaded document body must not appear in lifecycle evidence", encoding="utf-8")
        stale_mtime = (datetime.utcnow() - timedelta(days=10)).timestamp()
        os.utime(orphan_path, (stale_mtime, stale_mtime))
        external_target = Path(self.tmp.name) / "external-target.md"
        external_target.write_text("external symlink target must not be managed by retention", encoding="utf-8")
        symlink_path = self.uploads_dir / "external-link.md"
        symlink_path.symlink_to(external_target)

        response = self.client.post("/admin/lifecycle/retention/scheduled/run", json={"retry_limit": 0})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        retained_artifacts = body["retention"]["retained"]["document_artifacts"]
        reasons = {artifact["reason"] for artifact in retained_artifacts}
        self.assertIn("abandoned_ingestion", reasons)
        self.assertIn("orphaned_uploaded_artifact", reasons)
        self.assertFalse(abandoned_path.exists())
        self.assertFalse(orphan_path.exists())
        self.assertTrue(symlink_path.exists())
        self.assertTrue(external_target.exists())
        self.assertTrue(current_path.exists())
        self.assertTrue(active_processing_path.exists())
        self.assertIsNotNone(self.ingest.ingest_db.get_job(current_job_id))
        self.assertIsNotNone(self.ingest.ingest_db.get_job(active_processing_job_id))
        self.assertNotIn("orphaned uploaded document body", json.dumps(body))

    def test_scheduled_retention_creates_metadata_only_run_record(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "user_memory": {
                    "lifecycle_data_class": "user_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": True,
                },
            }, sort_keys=True),
        )
        memory_id = self.create_stale_user_memory(content="Run record must not expose this memory.")
        response = self.client.post(
            "/admin/lifecycle/retention/scheduled/run",
            json={"retry_limit": 0},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertIn("run_record", body)
        self.assertEqual(body["run_record"]["trigger"], "manual")
        self.assertEqual(body["run_record"]["actor"], "admin-pubkey")

        history = self.client.get("/admin/lifecycle/retention-runs")
        self.assertEqual(history.status_code, 200)
        runs = history.json()["runs"]
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run["id"], body["run_record"]["id"])
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["trigger"], "manual")
        self.assertEqual(run["actor"], "admin-pubkey")
        self.assertIn("user_memory", run["counts"]["by_class"])
        self.assertEqual(run["counts"]["by_class"]["user_memory"]["succeeded"], 1)
        self.assertNotIn("Run record must not expose this memory", json.dumps(run))
        detail = self.client.get(f"/admin/lifecycle/retention-runs/{run['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["run"]["id"], run["id"])
        self.assertNotIn("Run record must not expose this memory", json.dumps(detail.json()))
        self.assertEqual(self.database.get_user_memory(memory_id)["status"], "deleted")

    def test_scheduled_session_memory_failure_creates_sanitized_run_record_and_tombstone(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "sage_session_memory": {
                    "lifecycle_data_class": "sage_session_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": True,
                },
            }, sort_keys=True),
        )
        session_id = "scheduled-session-failure"
        self.query._sessions[session_id] = {
            "id": session_id,
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "Scheduled retention must never keep this conversation text.",
                    "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat(),
                },
            ],
        }

        async def fail_session_memory_deletion(_session: dict) -> dict:
            return {
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": session_id,
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "target_unavailable",
                    }
                ],
            }

        self.lifecycle.delete_session_memory_for_conversation = fail_session_memory_deletion

        response = self.client.post("/admin/lifecycle/retention/scheduled/run", json={"retry_limit": 0})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "partial_failure")
        self.assertEqual(body["run_record"]["status"], "partial_failure")
        self.assertEqual(body["run_record"]["counts"]["by_class"]["sage_session_memory"]["failed"], 1)
        self.assertNotIn("Scheduled retention must never keep this conversation text", json.dumps(body))
        tombstones = self.client.get("/admin/lifecycle/deletion-tombstones")
        self.assertEqual(tombstones.status_code, 200)
        self.assertEqual(tombstones.json()["tombstones"][0]["conversation_id"], session_id)
        self.assertNotIn(
            "Scheduled retention must never keep this conversation text",
            json.dumps(tombstones.json()),
        )

    def test_lifecycle_status_reports_scheduler_observation(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "user_memory": {
                    "lifecycle_data_class": "user_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": True,
                },
            }, sort_keys=True),
        )

        before = self.client.get("/admin/lifecycle/status")
        self.assertEqual(before.status_code, 200)
        before_scheduler = before.json()["retention_scheduler"]
        self.assertEqual(before_scheduler["observation"]["status"], "never_observed")
        self.assertEqual(before_scheduler["observation"]["enabled_classes"], ["user_memory"])

        original_token = os.environ.get("RETENTION_AUTOMATION_TOKEN")
        os.environ["RETENTION_AUTOMATION_TOKEN"] = "retention-token"
        try:
            run = self.client.post(
                "/admin/lifecycle/retention/scheduled/automation/run",
                json={"retry_limit": 0},
                headers={"X-Retention-Automation-Token": "retention-token"},
            )
        finally:
            self._restore_env("RETENTION_AUTOMATION_TOKEN", original_token)
        self.assertEqual(run.status_code, 200)

        after = self.client.get("/admin/lifecycle/status")
        self.assertEqual(after.status_code, 200)
        observation = after.json()["retention_scheduler"]["observation"]
        self.assertEqual(observation["status"], "healthy")
        self.assertEqual(observation["last_run"]["trigger"], "machine")
        self.assertEqual(observation["last_run"]["actor"], "machine:scheduled-retention")

    def test_manual_and_machine_scheduled_runs_share_evidence_shape(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "user_memory": {
                    "lifecycle_data_class": "user_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": True,
                },
            }, sort_keys=True),
        )

        manual = self.client.post(
            "/admin/lifecycle/retention/scheduled/run",
            json={"retry_limit": 0},
        )
        self.assertEqual(manual.status_code, 200)

        original_token = os.environ.get("RETENTION_AUTOMATION_TOKEN")
        os.environ["RETENTION_AUTOMATION_TOKEN"] = "retention-token"
        try:
            machine = self.client.post(
                "/admin/lifecycle/retention/scheduled/automation/run",
                json={"retry_limit": 0},
                headers={"X-Retention-Automation-Token": "retention-token"},
            )
        finally:
            self._restore_env("RETENTION_AUTOMATION_TOKEN", original_token)
        self.assertEqual(machine.status_code, 200)

        history = self.client.get("/admin/lifecycle/retention-runs")
        self.assertEqual(history.status_code, 200)
        runs = history.json()["runs"]
        self.assertEqual(len(runs), 2)
        machine_run, manual_run = runs
        self.assertEqual(machine_run["trigger"], "machine")
        self.assertEqual(machine_run["actor"], "machine:scheduled-retention")
        self.assertEqual(manual_run["trigger"], "manual")
        self.assertEqual(manual_run["actor"], "admin-pubkey")
        for run in (manual_run, machine_run):
            self.assertIn("policy_snapshot", run)
            self.assertIn("counts", run)
            self.assertIn("results", run)
            self.assertIsNotNone(run["audit_log_id"])
            self.assertIsNotNone(run["audit_entry_hash"])

    def test_retention_preview_reports_eligible_counts_without_deleting(self) -> None:
        stale_session_id = "preview-stale-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "1",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
        }
        upload = self.upload_text("Preview.md")
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        artifact_path = self.mark_failed_job_stale(job_id)

        response = self.client.post(
            "/admin/lifecycle/retention/preview",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "preview")
        self.assertFalse(body["destructive"])
        self.assertEqual(body["counts"]["stale_conversations"], 1)
        self.assertEqual(body["counts"]["document_artifacts"], 1)
        self.assertIn(stale_session_id, self.query._sessions)
        self.assertTrue(artifact_path.exists())
        self.assertIsNotNone(self.ingest.ingest_db.get_job(job_id))

    def test_retention_preview_reports_stale_user_memory_without_exposing_content(self) -> None:
        memory_id = self.create_stale_user_memory(content="Raw memory content must not appear in preview.")

        response = self.client.post(
            "/admin/lifecycle/retention/preview",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "preview")
        self.assertEqual(body["counts"]["user_memories"], 1)
        self.assertEqual(body["eligible"]["user_memories"], [memory_id])
        self.assertEqual(self.database.get_user_memory(memory_id)["status"], "active")
        self.assertNotIn("Raw memory content", json.dumps(body))

    def test_retention_run_soft_deletes_stale_user_memory_with_sanitized_audit(self) -> None:
        memory_id = self.create_stale_user_memory(content="Raw memory content must not appear in audit.")

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(memory_id, body["retained"]["user_memories"])
        memory = self.database.get_user_memory(memory_id)
        self.assertEqual(memory["status"], "deleted")
        self.assertEqual(memory["deleted_by_actor"], "retention:admin-pubkey")
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["retention_delete_user_memory"]["status"], "succeeded")
        self.assertNotIn("Raw memory content", json.dumps(body))

        entries = self.audit_entries("data_deletion")
        retention_event = json.loads(entries[0]["new_value"])
        self.assertEqual(retention_event["workflow"], "run_retention")
        self.assertNotIn("Raw memory content", json.dumps(retention_event))

    def test_manual_retention_run_requires_fresh_preview_or_current_count_confirmation(self) -> None:
        memory_id = self.create_stale_user_memory(content="Preview freshness memory stays private.")

        blocked = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(self.database.get_user_memory(memory_id)["status"], "active")
        self.assertIn("preview", blocked.json()["detail"]["message"].lower())
        self.assertNotIn("Preview freshness memory", json.dumps(blocked.json()))

        preview = self.client.post(
            "/admin/lifecycle/retention/preview",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )
        self.assertEqual(preview.status_code, 200)
        preview_token = preview.json()["preview_token"]

        run = self.client.post(
            "/admin/lifecycle/retention/run",
            json={
                "stale_conversation_days": 7,
                "document_artifact_days": 7,
                "preview_token": preview_token,
            },
        )

        self.assertEqual(run.status_code, 200)
        self.assertIn(memory_id, run.json()["retained"]["user_memories"])
        self.assertEqual(self.database.get_user_memory(memory_id)["status"], "deleted")

    def test_audit_log_retention_compacts_sensitive_detail_without_full_deletion(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "audit_log": {
                    "lifecycle_data_class": "audit_log",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": False,
                },
            }, sort_keys=True),
        )
        self.database.log_config_audit_event(
            table_name="deployment_config",
            config_key="LLM_API_KEY",
            old_value="old-secret-value",
            new_value='{"value": "new-secret-value"}',
            changed_by="admin-pubkey",
        )
        self.database.log_config_audit_event(
            table_name="data_deletion",
            config_key="retention:evidence",
            old_value=None,
            new_value=json.dumps({
                "workflow": "run_retention",
                "status": "succeeded",
                "results": [{"action": "retention_delete_user_memory", "target_id": "12"}],
            }),
            changed_by="admin-pubkey",
        )
        stale = (datetime.utcnow() - timedelta(days=10)).isoformat()
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE config_audit_log SET changed_at = ? WHERE table_name IN (?, ?)",
                (stale, "deployment_config", "data_deletion"),
            )

        preview = self.client.post(
            "/admin/lifecycle/retention/preview",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["counts"]["audit_log_entries"], 1)
        self.assertEqual(len(preview.json()["eligible"]["audit_log_entries"]), 1)

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["retention_compact_audit_log"]["status"], "succeeded")
        self.assertEqual(actions["retention_compact_audit_log"]["target_id"], "1")

        deployment_entries = self.audit_entries("deployment_config")
        compacted = deployment_entries[0]
        self.assertIn("redacted_by_audit_log_retention", compacted["old_value"])
        self.assertIn("redacted_by_audit_log_retention", compacted["new_value"])
        self.assertNotIn("old-secret-value", json.dumps(deployment_entries))
        self.assertNotIn("new-secret-value", json.dumps(deployment_entries))

        lifecycle_entries = self.audit_entries("data_deletion")
        self.assertIn("retention_delete_user_memory", json.dumps(lifecycle_entries))
        verify = self.client.get("/admin/deployment/audit-log/verify")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

        full_delete = self.client.delete("/admin/deployment/audit-log")
        self.assertEqual(full_delete.status_code, 405)

    def test_scheduled_retention_reports_incomplete_when_retry_remains_incomplete(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "sage_session_memory": {
                    "lifecycle_data_class": "sage_session_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": True,
                },
            }, sort_keys=True),
        )
        self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id="still-incomplete-session",
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

        async def fail_session_memory_delete(_session: dict) -> dict:
            return {
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": "still-incomplete-session",
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "target_unavailable",
                    }
                ],
            }

        self.lifecycle.delete_session_memory_for_conversation = fail_session_memory_delete

        response = self.client.post("/admin/lifecycle/retention/scheduled/run", json={"retry_limit": 3})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "incomplete")
        self.assertEqual(body["retry_results"][0]["status"], "incomplete")

    def test_disabled_retention_policy_skips_execution_without_deleting_candidates(self) -> None:
        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "sage_session_memory": {
                    "lifecycle_data_class": "sage_session_memory",
                    "enabled": False,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": False,
                },
                "uploaded_document_artifacts": {
                    "lifecycle_data_class": "uploaded_document_artifacts",
                    "enabled": False,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": False,
                },
                "user_memory": {
                    "lifecycle_data_class": "user_memory",
                    "enabled": False,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": False,
                },
            }, sort_keys=True),
        )
        stale_session_id = "disabled-policy-stale-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "1",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
        }
        upload = self.upload_text("DisabledPolicy.md")
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        artifact_path = self.mark_failed_job_stale(job_id)
        memory_id = self.create_stale_user_memory()

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(stale_session_id, self.query._sessions)
        self.assertTrue(artifact_path.exists())
        self.assertIsNotNone(self.ingest.ingest_db.get_job(job_id))
        actions = {result["target_id"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["sage_session_memory"]["action"], "retention_skip_disabled_policy")
        self.assertEqual(actions["uploaded_document_artifacts"]["action"], "retention_skip_disabled_policy")
        self.assertEqual(actions["user_memory"]["action"], "retention_skip_disabled_policy")
        self.assertEqual(self.database.get_user_memory(memory_id)["status"], "active")

    def test_scheduled_retention_requires_opt_in_and_retries_incomplete_tombstones(self) -> None:
        skipped = self.client.post("/admin/lifecycle/retention/scheduled/run", json={"retry_limit": 3})
        self.assertEqual(skipped.status_code, 200)
        self.assertEqual(skipped.json()["status"], "skipped")
        self.assertEqual(skipped.json()["enabled_classes"], [])

        self.database.update_setting(
            "lifecycle_retention_policies",
            json.dumps({
                "sage_session_memory": {
                    "lifecycle_data_class": "sage_session_memory",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": True,
                },
                "uploaded_document_artifacts": {
                    "lifecycle_data_class": "uploaded_document_artifacts",
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": True,
                },
            }, sort_keys=True),
        )
        tombstone_id = self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id="scheduled-retry-session",
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
        self.lifecycle.delete_session_memory_for_conversation = lambda _session: self._successful_session_memory_delete()

        response = self.client.post("/admin/lifecycle/retention/scheduled/run", json={"retry_limit": 3})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("sage_session_memory", body["enabled_classes"])
        self.assertEqual(body["retry_results"][0]["tombstone_id"], tombstone_id)
        self.assertEqual(body["retry_results"][0]["status"], "completed")

    async def _successful_session_memory_delete(self) -> dict:
        return {
            "status": "succeeded",
            "retryable": False,
            "counts": {"succeeded": 1, "skipped": 0, "failed": 0},
            "results": [
                {
                    "target_kind": "session_memory",
                    "target_id": "scheduled-retry-session",
                    "action": "delete_session_memory",
                    "status": "succeeded",
                    "retryable": False,
                    "detail": "Deleted Session Memory.",
                }
            ],
        }

    def test_retention_creates_metadata_only_tombstone_when_session_memory_deletion_fails(self) -> None:
        stale_session_id = "stale-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "Sensitive conversation text must not survive in lifecycle evidence.",
                    "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat(),
                },
            ],
        }

        async def fail_session_memory_deletion(_session: dict) -> dict:
            return {
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": stale_session_id,
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "target_unavailable",
                    }
                ],
            }

        self.lifecycle.delete_session_memory_for_conversation = fail_session_memory_deletion

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "partial_failure")
        self.assertNotIn(stale_session_id, self.query._sessions)

        tombstones = self.client.get("/admin/lifecycle/deletion-tombstones")
        self.assertEqual(tombstones.status_code, 200)
        items = tombstones.json()["tombstones"]
        self.assertEqual(len(items), 1)
        tombstone = items[0]
        self.assertEqual(tombstone["status"], "incomplete")
        self.assertEqual(tombstone["conversation_id"], stale_session_id)
        self.assertEqual(tombstone["former_subject_ref"], "deleted_user:42")
        self.assertEqual(tombstone["source"], "retention_execution")
        serialized = json.dumps(tombstone)
        self.assertIn("target_unavailable", serialized)
        self.assertNotIn("Sensitive conversation text", serialized)

    def test_admin_can_retry_incomplete_session_memory_tombstone(self) -> None:
        stale_session_id = "retry-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "Retry must not reveal this message.",
                    "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat(),
                },
            ],
        }
        attempts = {"count": 0}

        async def flaky_session_memory_deletion(_session: dict) -> dict:
            attempts["count"] += 1
            if attempts["count"] == 1:
                return {
                    "status": "failed",
                    "retryable": True,
                    "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                    "results": [
                        {
                            "target_kind": "session_memory",
                            "target_id": stale_session_id,
                            "action": "delete_session_memory",
                            "status": "failed",
                            "retryable": True,
                            "detail": "target_unavailable",
                        }
                    ],
                }
            return {
                "status": "succeeded",
                "retryable": False,
                "counts": {"succeeded": 1, "skipped": 0, "failed": 0},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": stale_session_id,
                        "action": "delete_session_memory",
                        "status": "succeeded",
                        "retryable": False,
                        "detail": "Deleted Sage Session Memory.",
                    }
                ],
            }

        self.lifecycle.delete_session_memory_for_conversation = flaky_session_memory_deletion
        retention = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )
        self.assertEqual(retention.status_code, 200)
        tombstone = self.client.get("/admin/lifecycle/deletion-tombstones").json()["tombstones"][0]

        retry = self.client.post(f"/admin/lifecycle/deletion-tombstones/{tombstone['id']}/retry")

        self.assertEqual(retry.status_code, 200)
        body = retry.json()
        self.assertEqual(body["tombstone"]["status"], "completed")
        self.assertEqual(body["tombstone"]["retry_count"], 1)
        self.assertEqual(body["deletion"]["status"], "succeeded")
        refreshed = self.client.get("/admin/lifecycle/deletion-tombstones").json()["tombstones"][0]
        self.assertEqual(refreshed["status"], "completed")
        self.assertEqual(refreshed["retry_count"], 1)
        serialized = json.dumps(refreshed)
        self.assertNotIn("Retry must not reveal this message", serialized)
        entries = self.audit_entries("data_deletion")
        retry_event = next(
            json.loads(entry["new_value"])
            for entry in entries
            if json.loads(entry["new_value"])["workflow"] == "retry_deletion_tombstone"
        )
        self.assertEqual(retry_event["status"], "succeeded")

        repeat_retry = self.client.post(f"/admin/lifecycle/deletion-tombstones/{tombstone['id']}/retry")

        self.assertEqual(repeat_retry.status_code, 409)
        repeat_body = repeat_retry.json()["detail"]
        self.assertEqual(repeat_body["tombstone"]["status"], "completed")
        self.assertEqual(repeat_body["tombstone"]["retry_count"], 1)
        retry_events = [
            json.loads(entry["new_value"])
            for entry in self.audit_entries("data_deletion")
            if json.loads(entry["new_value"])["workflow"] == "retry_deletion_tombstone"
        ]
        self.assertEqual(len(retry_events), 1)

    def test_deletion_tombstone_status_filter_rejects_unknown_values(self) -> None:
        response = self.client.get("/admin/lifecycle/deletion-tombstones?status=done")

        self.assertEqual(response.status_code, 400)

    def test_retention_uses_sage_lifecycle_contract_and_sanitizes_failures(self) -> None:
        stale_session_id = "sage-backed-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "agent_runtime": "sage",
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "Do not persist this Sage-backed message.",
                    "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat(),
                },
            ],
        }
        calls: list[dict] = []

        async def fake_sage_delete(payload: dict) -> dict:
            calls.append(payload)
            return {
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": stale_session_id,
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "postgres://sage:secret@postgres:5432/sage connection refused",
                    }
                ],
            }

        self.lifecycle.post_sage_session_memory_delete = fake_sage_delete

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "partial_failure")
        self.assertEqual(calls, [{"conversation_id": stale_session_id}])
        tombstone = self.client.get("/admin/lifecycle/deletion-tombstones").json()["tombstones"][0]
        serialized = json.dumps(tombstone)
        self.assertIn("target_unavailable", serialized)
        self.assertNotIn("postgres://", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("Do not persist this Sage-backed message", serialized)

    def test_user_conversation_delete_uses_shared_session_memory_lifecycle(self) -> None:
        session_id = "user-delete-session"
        self.query._sessions[session_id] = {
            "id": session_id,
            "agent_runtime": "sage",
            "owner_type": "user",
            "owner_id": "42",
            "created_at": datetime.utcnow().isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "User-deleted content must not appear in tombstones.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                {
                    "id": "msg_trace_delete",
                    "role": "assistant",
                    "content": "Assistant trace-bearing content must not appear in tombstones.",
                    "timestamp": datetime.utcnow().isoformat(),
                    "trace": {
                        "visibility": "summary",
                        "reasoning": {
                            "summary": "Sensitive trace summary must be deleted with the conversation.",
                        },
                        "tools": [
                            {
                                "id": "db-query",
                                "name": "Database",
                                "status": "success",
                                "execution": "server",
                                "input_summary": "SELECT email FROM users WHERE email = '[redacted]'",
                                "output_summary": "Database results were redacted from the trace.",
                                "warnings": ["raw_results_redacted"],
                            }
                        ],
                        "retrieval": [],
                        "suppressed": False,
                    },
                }
            ],
        }
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "id": 42,
            "approved": True,
        }

        async def fail_sage_delete(payload: dict) -> dict:
            self.assertEqual(payload, {"conversation_id": session_id})
            return {
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": session_id,
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "Sage unavailable",
                    }
                ],
            }

        self.lifecycle.post_sage_session_memory_delete = fail_sage_delete

        response = self.client.delete(f"/query/session/{session_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "deleted")
        self.assertEqual(body["deletion"]["status"], "partial_failure")
        self.assertNotIn(session_id, self.query._sessions)
        get_deleted = self.client.get(f"/query/session/{session_id}")
        self.assertEqual(get_deleted.status_code, 404)
        def _require_admin_override():
            raise HTTPException(status_code=403, detail="Admin access required")

        self.main.app.dependency_overrides[self.lifecycle.auth.require_admin] = _require_admin_override
        hidden_tombstones = self.client.get("/admin/lifecycle/deletion-tombstones")
        self.assertEqual(hidden_tombstones.status_code, 403)
        hidden_retry = self.client.post("/admin/lifecycle/deletion-tombstones/1/retry")
        self.assertEqual(hidden_retry.status_code, 403)
        self.main.app.dependency_overrides[self.lifecycle.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        tombstone = self.client.get("/admin/lifecycle/deletion-tombstones").json()["tombstones"][0]
        self.assertEqual(tombstone["conversation_id"], session_id)
        self.assertEqual(tombstone["source"], "user_conversation_delete")
        serialized = json.dumps(tombstone)
        self.assertIn("target_unavailable", serialized)
        self.assertNotIn("User-deleted content", serialized)
        self.assertNotIn("Assistant trace-bearing content", serialized)
        self.assertNotIn("Sensitive trace summary", serialized)
        self.assertNotIn("raw_results_redacted", serialized)
        entries = self.audit_entries("data_deletion")
        event = next(
            json.loads(entry["new_value"])
            for entry in entries
            if json.loads(entry["new_value"])["workflow"] == "delete_conversation"
        )
        self.assertEqual(event["status"], "partial_failure")
        event_json = json.dumps(event)
        self.assertIn("target_unavailable", event_json)
        self.assertNotIn("User-deleted content", event_json)
        self.assertNotIn("Assistant trace-bearing content", event_json)
        self.assertNotIn("Sensitive trace summary", event_json)
        self.assertNotIn("raw_results_redacted", event_json)
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=data_deletion")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_admin_conversation_delete_uses_shared_session_memory_lifecycle(self) -> None:
        session_id = "admin-delete-session"
        self.query._sessions[session_id] = {
            "id": session_id,
            "agent_runtime": "sage",
            "owner_type": "admin",
            "owner_id": "1",
            "created_at": datetime.utcnow().isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "Admin-deleted content must not appear in lifecycle evidence.",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }

        async def fail_sage_delete(payload: dict) -> dict:
            self.assertEqual(payload, {"conversation_id": session_id})
            return {
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": session_id,
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "Sage unavailable",
                    }
                ],
            }

        self.lifecycle.post_sage_session_memory_delete = fail_sage_delete

        response = self.client.delete(f"/query/session/{session_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "deleted")
        self.assertEqual(body["deletion"]["status"], "partial_failure")
        self.assertNotIn(session_id, self.query._sessions)
        tombstone = self.client.get("/admin/lifecycle/deletion-tombstones").json()["tombstones"][0]
        self.assertEqual(tombstone["conversation_id"], session_id)
        self.assertEqual(tombstone["source"], "admin_conversation_delete")
        self.assertEqual(tombstone["former_subject_ref"], "admin:1")
        serialized = json.dumps(tombstone)
        self.assertIn("target_unavailable", serialized)
        self.assertNotIn("Admin-deleted content", serialized)
        entries = self.audit_entries("data_deletion")
        event = next(
            json.loads(entry["new_value"])
            for entry in entries
            if json.loads(entry["new_value"])["workflow"] == "delete_conversation"
        )
        self.assertEqual(event["status"], "partial_failure")
        self.assertEqual(entries[0]["changed_by"], "admin-pubkey")
        self.assertNotIn("Admin-deleted content", json.dumps(event))

    def test_repeat_conversation_delete_returns_deletion_summary_and_audit(self) -> None:
        session_id = "already-deleted-session"
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "id": 42,
            "approved": True,
        }

        response = self.client.delete(f"/query/session/{session_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "deleted")
        self.assertEqual(body["deletion"]["status"], "succeeded")
        self.assertEqual(body["deletion"]["results"][0]["status"], "skipped")
        entries = self.audit_entries("data_deletion")
        event = next(
            json.loads(entry["new_value"])
            for entry in entries
            if json.loads(entry["new_value"])["workflow"] == "delete_conversation"
        )
        self.assertEqual(event["status"], "succeeded")
        self.assertEqual(event["results"][0]["action"], "delete_session_record")

    def test_retention_is_safe_to_repeat_when_nothing_is_eligible(self) -> None:
        first = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )
        second = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertEqual(body["deletion"]["counts"]["skipped"], 1)
        self.assertEqual(body["deletion"]["results"][0]["action"], "run_retention")

    def test_retention_rechecks_conversation_activity_before_deleting_candidate(self) -> None:
        first_session_id = "first-stale-session"
        revived_session_id = "revived-stale-session"
        stale_created = (datetime.utcnow() - timedelta(days=10)).isoformat()
        revived_session = None
        for session_id in (first_session_id, revived_session_id):
            session = {
                "id": session_id,
                "owner_type": "user",
                "owner_id": "42",
                "created_at": stale_created,
                "messages": [],
            }
            self.query._sessions[session_id] = session
            if session_id == revived_session_id:
                revived_session = session

        async def revive_second_session(_session: dict) -> dict:
            revived_session["messages"].append({
                "role": "assistant",
                "content": "This activity should keep the Conversation active.",
                "timestamp": datetime.utcnow().isoformat(),
            })
            return {
                "status": "succeeded",
                "retryable": False,
                "counts": {"succeeded": 1, "skipped": 0, "failed": 0},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": first_session_id,
                        "action": "delete_session_memory",
                        "status": "succeeded",
                        "retryable": False,
                        "detail": "Deleted Sage Session Memory.",
                    }
                ],
            }

        self.lifecycle.delete_session_memory_for_conversation = revive_second_session

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(first_session_id, body["retained"]["stale_conversations"])
        self.assertIn(revived_session_id, body["retained"]["skipped_conversations"])
        self.assertNotIn(first_session_id, self.query._sessions)
        self.assertIn(revived_session_id, self.query._sessions)
        actions = {result["target_id"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions[revived_session_id]["status"], "skipped")
        self.assertEqual(actions[revived_session_id]["action"], "retention_skip_active_conversation")

    def test_retention_skips_conversations_with_incomplete_deletion_tombstones(self) -> None:
        tombstoned_session_id = "tombstoned-stale-session"
        self.query._sessions[tombstoned_session_id] = {
            "id": tombstoned_session_id,
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "This tombstoned Conversation must not be deleted again.",
                    "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat(),
                }
            ],
        }
        self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id=tombstoned_session_id,
            former_subject_ref="deleted_user:42",
            status="incomplete",
            source="user_conversation_delete",
            workflow="delete_conversation",
            deletion={
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": tombstoned_session_id,
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "target_unavailable",
                    }
                ],
            },
        )

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(tombstoned_session_id, self.query._sessions)
        self.assertNotIn(tombstoned_session_id, body["retained"]["stale_conversations"])
        self.assertIn(tombstoned_session_id, body["retained"]["skipped_conversations"])
        actions = {result["target_id"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions[tombstoned_session_id]["status"], "skipped")
        self.assertEqual(actions[tombstoned_session_id]["action"], "retention_skip_tombstoned_conversation")

    def test_retention_reports_partial_failure_for_retryable_document_cleanup(self) -> None:
        upload = self.upload_text("Broken.md")
        job_id = upload.json()["job_id"]
        self.mark_failed_job_stale(job_id)

        async def fail_chunk_delete(_job_id: str) -> int:
            raise RuntimeError("qdrant unavailable")

        self.ingest.delete_document_chunks = fail_chunk_delete

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
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

    def test_end_to_end_lifecycle_completion_smoke(self) -> None:
        registry = self.client.get("/admin/lifecycle/status")
        self.assertEqual(registry.status_code, 200)
        registry_body = registry.json()
        self.assertEqual(registry_body["secure_erase"]["status"], "unsupported")
        self.assertTrue(registry_body["unsupported_deployment_surfaces"])
        self.assertIn(
            "user_memory",
            {data_class["key"] for data_class in registry_body["data_classes"]},
        )

        for data_class_key in ("user_memory", "audit_log", "sage_session_memory"):
            policy = self.client.put(
                f"/admin/lifecycle/retention-policies/{data_class_key}",
                json={
                    "enabled": True,
                    "retention_window_days": 7,
                    "scheduled_enforcement_enabled": data_class_key == "sage_session_memory",
                },
            )
            self.assertEqual(policy.status_code, 200)
            self.assertTrue(policy.json()["policy"]["enabled"])

        memory_id = self.create_stale_user_memory(content="Smoke memory content must stay private.")
        preview = self.client.post(
            "/admin/lifecycle/retention/preview",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["counts"]["user_memories"], 1)
        self.assertNotIn("Smoke memory content", json.dumps(preview.json()))

        run = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7, "confirm_current_counts": True},
        )
        self.assertEqual(run.status_code, 200)
        self.assertIn(memory_id, run.json()["retained"]["user_memories"])
        self.assertEqual(self.database.get_user_memory(memory_id)["status"], "deleted")

        tombstone_id = self.database.create_deletion_tombstone(
            lifecycle_data_class="sage_session_memory",
            conversation_id="smoke-retry-session",
            former_subject_ref="deleted_user:99",
            status="incomplete",
            source="retention_execution",
            workflow="run_retention",
            deletion={
                "status": "failed",
                "retryable": True,
                "counts": {"succeeded": 0, "skipped": 0, "failed": 1},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": "smoke-retry-session",
                        "action": "delete_session_memory",
                        "status": "failed",
                        "retryable": True,
                        "detail": "target_unavailable",
                    }
                ],
            },
        )
        self.lifecycle.delete_session_memory_for_conversation = lambda _session: self._successful_session_memory_delete()
        scheduled = self.client.post("/admin/lifecycle/retention/scheduled/run", json={"retry_limit": 3})
        self.assertEqual(scheduled.status_code, 200)
        scheduled_body = scheduled.json()
        self.assertIn("sage_session_memory", scheduled_body["enabled_classes"])
        self.assertEqual(scheduled_body["retry_results"][0]["tombstone_id"], tombstone_id)
        self.assertEqual(scheduled_body["retry_results"][0]["status"], "completed")

        tombstones = self.client.get("/admin/lifecycle/deletion-tombstones")
        self.assertEqual(tombstones.status_code, 200)
        serialized_tombstones = json.dumps(tombstones.json())
        self.assertIn("smoke-retry-session", serialized_tombstones)
        self.assertNotIn("Smoke memory content", serialized_tombstones)

        audit_entries = self.audit_entries("data_deletion")
        audit_payload = json.dumps(audit_entries)
        self.assertIn("run_retention", audit_payload)
        self.assertIn("retry_deletion_tombstone", audit_payload)
        self.assertNotIn("Smoke memory content", audit_payload)
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=data_deletion")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

        def deny_admin():
            raise HTTPException(status_code=403, detail="Admin access required")

        self.main.app.dependency_overrides[self.lifecycle.auth.require_admin] = deny_admin
        self.main.app.dependency_overrides[self.deployment_config.auth.require_admin] = deny_admin
        self.assertEqual(self.client.get("/admin/lifecycle/status").status_code, 403)
        self.assertEqual(self.client.get("/admin/lifecycle/deletion-tombstones").status_code, 403)
        self.assertEqual(self.client.get("/admin/deployment/audit-log?table_name=data_deletion").status_code, 403)


if __name__ == "__main__":
    unittest.main()
