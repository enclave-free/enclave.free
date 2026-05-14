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

    def test_lifecycle_registry_discloses_unsupported_deployment_surfaces(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            {data_class["key"] for data_class in body["data_classes"]},
            {
                "user_profiles",
                "user_memory",
                "document_library",
                "retrieval_index",
                "uploaded_document_artifacts",
                "sage_session_memory",
                "audit_log",
            },
        )
        surfaces = {surface["key"]: surface for surface in body["deployment_surfaces"]}
        for key in {
            "docker_logs",
            "gateway_logs",
            "sqlite_wal",
            "postgres_wal",
            "host_backups",
            "host_snapshots",
            "provider_traces",
        }:
            self.assertIn(key, surfaces)
            self.assertEqual(surfaces[key]["status"], "unsupported")
            self.assertFalse(surfaces[key]["acknowledged"])

    def test_admin_can_acknowledge_unsupported_deployment_surface(self) -> None:
        response = self.client.put("/admin/lifecycle/deployment-surfaces/docker_logs/acknowledgement")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deployment_surface"]["acknowledged"])

        status = self.client.get("/admin/lifecycle/status")
        surfaces = {surface["key"]: surface for surface in status.json()["deployment_surfaces"]}
        self.assertTrue(surfaces["docker_logs"]["acknowledged"])
        self.assertFalse(surfaces["gateway_logs"]["acknowledged"])

    def test_admin_can_configure_instance_wide_retention_policy(self) -> None:
        defaults = self.client.get("/admin/lifecycle/retention-policy")

        self.assertEqual(defaults.status_code, 200)
        policies = {policy["lifecycle_data_class"]: policy for policy in defaults.json()["policies"]}
        self.assertFalse(policies["user_memory"]["enabled"])
        self.assertFalse(policies["user_memory"]["schedule_enabled"])

        update = self.client.put(
            "/admin/lifecycle/retention-policy/user_memory",
            json={
                "enabled": True,
                "retention_days": 90,
                "schedule_enabled": True,
            },
        )

        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["policy"]["lifecycle_data_class"], "user_memory")
        self.assertTrue(update.json()["policy"]["enabled"])
        self.assertEqual(update.json()["policy"]["retention_days"], 90)
        self.assertTrue(update.json()["policy"]["schedule_enabled"])

        status = self.client.get("/admin/lifecycle/status").json()
        data_classes = {data_class["key"]: data_class for data_class in status["data_classes"]}
        self.assertEqual(data_classes["user_memory"]["retention_policy"]["retention_days"], 90)
        self.assertTrue(data_classes["user_memory"]["retention_policy"]["schedule_enabled"])

    def test_retention_policy_only_exposes_implemented_data_classes(self) -> None:
        defaults = self.client.get("/admin/lifecycle/retention-policy")

        self.assertEqual(defaults.status_code, 200)
        self.assertEqual(
            {policy["lifecycle_data_class"] for policy in defaults.json()["policies"]},
            {"user_memory", "sage_session_memory", "uploaded_document_artifacts"},
        )

        unsupported = self.client.put(
            "/admin/lifecycle/retention-policy/audit_log",
            json={
                "enabled": True,
                "retention_days": 365,
                "schedule_enabled": False,
            },
        )

        self.assertEqual(unsupported.status_code, 404)
        status = self.client.get("/admin/lifecycle/status").json()
        data_classes = {data_class["key"]: data_class for data_class in status["data_classes"]}
        self.assertNotIn("retention_policy", data_classes["audit_log"])
        self.assertIn("retention_policy", data_classes["user_memory"])

    def test_admin_can_preview_policy_backed_retention_without_deleting_data(self) -> None:
        stale_session_id = "policy-preview-stale-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "1",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
        }
        upload = self.upload_text("Preview Broken.md")
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        artifact_path = self.mark_failed_job_stale(job_id)
        for lifecycle_data_class in ("sage_session_memory", "uploaded_document_artifacts"):
            self.client.put(
                f"/admin/lifecycle/retention-policy/{lifecycle_data_class}",
                json={
                    "enabled": True,
                    "retention_days": 7,
                    "schedule_enabled": False,
                },
            )

        response = self.client.post("/admin/lifecycle/retention/preview", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "preview")
        self.assertEqual(body["eligible"]["sage_session_memory"]["count"], 1)
        self.assertEqual(body["eligible"]["uploaded_document_artifacts"]["count"], 1)
        self.assertIn(stale_session_id, self.query._sessions)
        self.assertTrue(artifact_path.exists())
        self.assertIsNotNone(self.ingest.ingest_db.get_job(job_id))

    def test_policy_backed_retention_deletes_stale_user_memory(self) -> None:
        subject_user_id = self.database.create_user()
        memory_id = self.database.create_user_memory(
            subject_user_id=subject_user_id,
            kind="preference",
            content="Likes old onboarding hints",
            source_kind="test",
            author_actor="admin-pubkey",
        )
        stale = (datetime.utcnow() - timedelta(days=10)).isoformat()
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE user_memories SET created_at = ?, updated_at = ? WHERE id = ?",
                (stale, stale, memory_id),
            )
        self.client.put(
            "/admin/lifecycle/retention-policy/user_memory",
            json={
                "enabled": True,
                "retention_days": 7,
                "schedule_enabled": False,
            },
        )

        preview = self.client.post("/admin/lifecycle/retention/preview", json={})

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["eligible"]["user_memory"]["count"], 1)

        response = self.client.post("/admin/lifecycle/retention/run", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(memory_id, body["retained"]["user_memory"])
        stored_memory = self.database.get_user_memory(memory_id)
        self.assertEqual(stored_memory["status"], "deleted")
        self.assertEqual(stored_memory["deleted_by_actor"], "admin-pubkey")
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["retention_delete_stale_user_memory"]["status"], "succeeded")

    def test_user_memory_retention_pages_all_eligible_records(self) -> None:
        subject_user_id = self.database.create_user()
        memory_ids = [
            self.database.create_user_memory(
                subject_user_id=subject_user_id,
                kind="preference",
                content=f"Old memory {index}",
                source_kind="test",
                author_actor="admin-pubkey",
            )
            for index in range(1005)
        ]
        stale = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE user_memories SET created_at = ?, updated_at = ? WHERE subject_user_id = ?",
                (stale, stale, subject_user_id),
            )
        self.client.put(
            "/admin/lifecycle/retention-policy/user_memory",
            json={
                "enabled": True,
                "retention_days": 7,
                "schedule_enabled": False,
            },
        )

        preview = self.client.post("/admin/lifecycle/retention/preview", json={})
        response = self.client.post("/admin/lifecycle/retention/run", json={})

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["eligible"]["user_memory"]["count"], len(memory_ids))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["retained"]["user_memory"]), len(memory_ids))
        self.assertTrue(all(
            self.database.get_user_memory(memory_id)["status"] == "deleted"
            for memory_id in memory_ids
        ))

    def test_policy_backed_retention_run_skips_disabled_classes(self) -> None:
        stale_session_id = "policy-run-stale-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "1",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
        }
        upload = self.upload_text("Disabled Artifact.md")
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        artifact_path = self.mark_failed_job_stale(job_id)
        self.client.put(
            "/admin/lifecycle/retention-policy/sage_session_memory",
            json={
                "enabled": True,
                "retention_days": 7,
                "schedule_enabled": False,
            },
        )

        response = self.client.post("/admin/lifecycle/retention/run", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertIn(stale_session_id, body["retained"]["stale_conversations"])
        self.assertNotIn(stale_session_id, self.query._sessions)
        self.assertEqual(body["retained"]["document_artifacts"], [])
        self.assertTrue(artifact_path.exists())
        self.assertIsNotNone(self.ingest.ingest_db.get_job(job_id))
        retention_event = json.loads(self.audit_entries("data_deletion")[0]["new_value"])
        self.assertEqual(retention_event["workflow"], "run_retention")

    def test_scheduled_retention_uses_opted_in_policies_and_bounded_retry(self) -> None:
        stale_session_id = "scheduled-retry-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "agent_runtime": "sage",
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
        }
        self.client.put(
            "/admin/lifecycle/retention-policy/sage_session_memory",
            json={
                "enabled": True,
                "retention_days": 7,
                "schedule_enabled": True,
            },
        )
        attempts = {"count": 0}

        async def eventually_delete_session_memory(_payload: dict) -> dict:
            attempts["count"] += 1
            if attempts["count"] < 3:
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

        self.lifecycle.post_sage_session_memory_delete = eventually_delete_session_memory

        response = self.client.post("/admin/lifecycle/retention/scheduled-run")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(len(body["deletion"]["attempts"]), 3)
        self.assertEqual(body["deletion"]["attempts"][0]["deletion"]["status"], "failed")
        self.assertEqual(body["deletion"]["attempts"][2]["deletion"]["status"], "succeeded")
        self.assertNotIn(stale_session_id, self.query._sessions)
        self.assertEqual(self.client.get("/admin/lifecycle/deletion-tombstones").json()["tombstones"], [])
        retention_event = json.loads(self.audit_entries("data_deletion")[0]["new_value"])
        self.assertEqual(retention_event["workflow"], "scheduled_retention")
        self.assertEqual(len(retention_event["attempts"]), 3)

    def test_scheduled_retention_is_noop_without_schedule_enabled_policies(self) -> None:
        stale_session_id = "scheduled-no-opt-in-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
        }

        response = self.client.post("/admin/lifecycle/retention/scheduled-run")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "skipped")
        self.assertIn(stale_session_id, self.query._sessions)
        self.assertEqual(body["retained"]["stale_conversations"], [])

    def test_user_memory_retention_uses_database_timestamp_ordering(self) -> None:
        subject_user_id = self.database.create_user()
        stale_memory_id = self.database.create_user_memory(
            subject_user_id=subject_user_id,
            kind="preference",
            content="Likes older material",
            source_kind="test",
            author_actor="admin-pubkey",
        )
        future_memory_id = self.database.create_user_memory(
            subject_user_id=subject_user_id,
            kind="preference",
            content="Likes future material",
            source_kind="test",
            author_actor="admin-pubkey",
        )
        stale = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_day = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        future = f"{cutoff_day} 23:59:59"
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE user_memories SET created_at = ?, updated_at = ? WHERE id = ?",
                (stale, stale, stale_memory_id),
            )
            cursor.execute(
                "UPDATE user_memories SET created_at = ?, updated_at = ? WHERE id = ?",
                (future, future, future_memory_id),
            )
        self.client.put(
            "/admin/lifecycle/retention-policy/user_memory",
            json={
                "enabled": True,
                "retention_days": 7,
                "schedule_enabled": False,
            },
        )

        response = self.client.post("/admin/lifecycle/retention/preview", json={})

        self.assertEqual(response.status_code, 200)
        memory_ids = response.json()["eligible"]["user_memory"]["memory_ids"]
        self.assertIn(stale_memory_id, memory_ids)
        self.assertNotIn(future_memory_id, memory_ids)

    def test_retention_records_tombstone_creation_failure_without_aborting(self) -> None:
        stale_session_id = "tombstone-write-fails-session"
        self.query._sessions[stale_session_id] = {
            "id": stale_session_id,
            "owner_type": "user",
            "owner_id": "42",
            "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
            "messages": [],
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

        def fail_tombstone_create(**_kwargs) -> None:
            raise RuntimeError("sqlite unavailable")

        self.lifecycle.delete_session_memory_for_conversation = fail_session_memory_deletion
        self.lifecycle.create_session_memory_tombstone = fail_tombstone_create

        response = self.client.post(
            "/admin/lifecycle/retention/run",
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "partial_failure")
        self.assertNotIn(stale_session_id, self.query._sessions)
        actions = {result["action"]: result for result in body["deletion"]["results"]}
        self.assertEqual(actions["create_session_memory_tombstone"]["status"], "failed")
        retention_event = json.loads(self.audit_entries("data_deletion")[0]["new_value"])
        audit_actions = {result["action"]: result for result in retention_event["results"]}
        self.assertEqual(audit_actions["create_session_memory_tombstone"]["status"], "failed")

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
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
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
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
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
        self.assertEqual(len(refreshed["deletion"]["attempts"]), 2)
        self.assertEqual(refreshed["deletion"]["attempts"][0]["deletion"]["status"], "failed")
        self.assertEqual(refreshed["deletion"]["attempts"][1]["deletion"]["status"], "succeeded")
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
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
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
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=data_deletion")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_conversation_delete_backfills_agent_runtime_before_lifecycle_delete(self) -> None:
        session_id = "runtime-backfill-session"
        self.query._sessions[session_id] = {
            "id": session_id,
            "owner_type": "user",
            "owner_id": "42",
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
        }
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "id": 42,
            "approved": True,
        }
        calls: list[dict] = []

        async def record_sage_delete(payload: dict) -> dict:
            calls.append(payload)
            return {
                "status": "succeeded",
                "retryable": False,
                "counts": {"succeeded": 1, "skipped": 0, "failed": 0},
                "results": [
                    {
                        "target_kind": "session_memory",
                        "target_id": session_id,
                        "action": "delete_session_memory",
                        "status": "succeeded",
                        "retryable": False,
                    }
                ],
            }

        self.lifecycle.post_sage_session_memory_delete = record_sage_delete

        response = self.client.delete(f"/query/session/{session_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [{"conversation_id": session_id}])

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
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
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
            json={"stale_conversation_days": 7, "document_artifact_days": 7},
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
