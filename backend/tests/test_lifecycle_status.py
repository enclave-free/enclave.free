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
        self.previous_content_encryption_key = os.environ.get("CONTENT_ENCRYPTION_KEY")
        self.previous_artifact_encryption = os.environ.get("DOCUMENT_ARTIFACT_ENCRYPTION")
        self.previous_retention_automation_token = os.environ.get("RETENTION_AUTOMATION_TOKEN")
        os.environ["UPLOADS_DIR"] = str(Path(self.temp_dir.name) / "uploads")
        os.environ.pop("CONTENT_ENCRYPTION_KEY", None)
        os.environ.pop("DOCUMENT_ARTIFACT_ENCRYPTION", None)

        import auth
        import database
        import lifecycle

        self.previous_sqlite_path = os.environ.get("SQLITE_PATH")
        self.db_path = Path(self.temp_dir.name) / "enclave.db"
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
        if self.previous_content_encryption_key is None:
            os.environ.pop("CONTENT_ENCRYPTION_KEY", None)
        else:
            os.environ["CONTENT_ENCRYPTION_KEY"] = self.previous_content_encryption_key
        if self.previous_artifact_encryption is None:
            os.environ.pop("DOCUMENT_ARTIFACT_ENCRYPTION", None)
        else:
            os.environ["DOCUMENT_ARTIFACT_ENCRYPTION"] = self.previous_artifact_encryption
        if self.previous_retention_automation_token is None:
            os.environ.pop("RETENTION_AUTOMATION_TOKEN", None)
        else:
            os.environ["RETENTION_AUTOMATION_TOKEN"] = self.previous_retention_automation_token
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
            "user_memory",
            "document_library",
            "retrieval_index",
            "uploaded_document_artifacts",
            "sage_session_memory",
            "inference_verification_records",
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

        inference_records = classes_by_key["inference_verification_records"]
        self.assertEqual(inference_records["owner"], "Enclave Control Plane")
        self.assertIn("SQLite", inference_records["storage_targets"])
        self.assertEqual(inference_records["deletion"]["status"], "not_started")
        self.assertEqual(inference_records["retention"]["status"], "indefinite")
        self.assertIn("indefinitely", inference_records["retention"]["summary"])
        self.assertEqual(inference_records["audit"]["status"], "partial")

    def test_new_instance_reports_conservative_scheduled_retention_defaults(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        classes_by_key = {
            data_class["key"]: data_class
            for data_class in body["data_classes"]
        }

        expected_defaults = {
            "sage_session_memory": 90,
            "user_memory": 180,
            "uploaded_document_artifacts": 30,
            "audit_log": 180,
        }
        for key, expected_days in expected_defaults.items():
            policy = classes_by_key[key]["retention_policy"]
            self.assertTrue(policy["enabled"], key)
            self.assertTrue(policy["scheduled_enforcement_enabled"], key)
            self.assertEqual(policy["retention_window_days"], expected_days, key)

        self.assertEqual(
            body["scheduled_retention"]["enabled_classes"],
            sorted(expected_defaults),
        )
        self.assertEqual(
            body["retention_scheduler"]["observation"]["status"],
            "never_observed",
        )

    def test_lifecycle_status_exposes_conversation_retention_semantics(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        session_memory = next(
            data_class
            for data_class in response.json()["data_classes"]
            if data_class["key"] == "sage_session_memory"
        )

        semantics = session_memory["retention_semantics"]
        self.assertEqual(semantics["lifecycle_unit"], "conversation")
        self.assertEqual(semantics["policy_scope"], "instance")
        self.assertEqual(semantics["activity_basis"], "human_or_sage_turn")
        self.assertFalse(semantics["view_refreshes_activity"])
        self.assertEqual(semantics["ordinary_history_after_retention"], "removed")
        self.assertEqual(semantics["lifecycle_evidence_visibility"], "admin_metadata_only")

    def test_lifecycle_status_reports_active_storage_scope_and_confidentiality_posture(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["lifecycle_scope"]["key"], "active_storage_lifecycle")
        self.assertIn("active product storage", body["lifecycle_scope"]["summary"])
        self.assertIn("Deployment Surfaces", body["lifecycle_scope"]["excludes"])

        scheduler = body["retention_scheduler"]
        self.assertEqual(scheduler["status"], "external_or_manual")
        self.assertIn("Scheduled Retention Policy", scheduler["summary"])

        classes_by_key = {
            data_class["key"]: data_class
            for data_class in body["data_classes"]
        }
        for data_class in classes_by_key.values():
            self.assertIn("confidentiality", data_class)
            self.assertIn(data_class["confidentiality"]["status"], {
                "encrypted",
                "mixed",
                "partial",
                "plaintext_by_operator_choice",
                "not_configured",
                "unsupported",
            })

        artifacts = classes_by_key["uploaded_document_artifacts"]["confidentiality"]
        self.assertEqual(artifacts["status"], "not_configured")
        self.assertIn("Content Encryption Key", artifacts["summary"])
        retrieval = classes_by_key["retrieval_index"]["confidentiality"]
        self.assertEqual(retrieval["status"], "encrypted")
        self.assertIn("Qdrant", retrieval["summary"])
        self.assertIn("minimized", retrieval["summary"])
        self.assertNotIn("Confidentiality Migration", retrieval["summary"])
        self.assertNotIn("migration lands", retrieval["summary"])

    def test_lifecycle_status_exposes_evidence_retention_boundaries(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        classes_by_key = {
            data_class["key"]: data_class
            for data_class in response.json()["data_classes"]
        }
        inference_records = classes_by_key["inference_verification_records"]
        self.assertEqual(inference_records["retention"]["status"], "indefinite")
        self.assertIn("separate evidence-retention policy", inference_records["retention"]["summary"])
        self.assertEqual(inference_records["evidence_retention"]["ordinary_conversation_policy_applies"], False)

        run_records = classes_by_key["retention_run_records"]
        self.assertEqual(run_records["retention"]["status"], "indefinite")
        self.assertIn("metadata-only lifecycle evidence", run_records["retention"]["summary"])
        self.assertEqual(run_records["evidence_retention"]["ordinary_conversation_policy_applies"], False)

    def test_lifecycle_status_exposes_deployment_surface_retention_boundaries(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        categories = {
            category["category"]: category
            for category in body["unsupported_deployment_surface_categories"]
        }
        expected_categories = {
            "runtime_logs",
            "database_internals",
            "backups_snapshots",
            "browser_held_copies",
            "copied_exports",
            "provider_traces",
        }

        self.assertEqual(expected_categories, set(categories))
        for key in expected_categories:
            with self.subTest(key=key):
                policy = categories[key]["operator_retention_policy"]
                self.assertEqual(policy["owner"], "operator")
                self.assertIn("not_lifecycle_data_class", policy["acknowledgement_effect"])
                self.assertIn("Secure Erase", policy["secure_erase_boundary"])

        historical = body["historical_session_log_retention"]
        self.assertEqual(historical["status"], "operator_responsibility")
        self.assertIn("active Session Memory deletion", historical["summary"])
        self.assertFalse(historical["secure_erase_claimed"])

    def test_lifecycle_status_reports_mixed_when_required_artifacts_include_legacy_plaintext(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        artifact_path = Path(os.environ["UPLOADS_DIR"]) / "Legacy.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("legacy plaintext artifact", encoding="utf-8")

        import ingest_db

        ingest_db.create_job(
            job_id="legacy-job",
            filename="Legacy.md",
            file_path=str(artifact_path),
            ontology_id="default",
        )
        ingest_db.update_job_status("legacy-job", "completed", total_chunks=1, processed_chunks=1)

        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["artifact_encryption"]["status"], "mixed")
        self.assertIn("legacy plaintext", body["artifact_encryption"]["summary"])
        classes_by_key = {
            data_class["key"]: data_class
            for data_class in body["data_classes"]
        }
        artifacts = classes_by_key["uploaded_document_artifacts"]["confidentiality"]
        self.assertEqual(artifacts["status"], "mixed")
        self.assertNotIn("Secure Erase", artifacts["summary"])

    def test_lifecycle_status_reports_current_retrieval_posture_when_qdrant_payload_text_remains(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        classes_by_key = {
            data_class["key"]: data_class
            for data_class in response.json()["data_classes"]
        }
        retrieval = classes_by_key["retrieval_index"]["confidentiality"]
        self.assertEqual(retrieval["status"], "encrypted")
        self.assertIn("minimized", retrieval["summary"])
        self.assertNotIn("legacy plaintext", retrieval["summary"])
        self.assertNotIn("Secure Erase", retrieval["summary"])

    def test_lifecycle_status_exposes_active_content_encryption_evidence_terms(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"

        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        active_content = body["active_content_encryption"]
        self.assertEqual(active_content["artifact_encryption_posture"]["status"], "encrypted")
        self.assertIn("Artifact Encryption Posture", active_content["artifact_encryption_posture"]["summary"])
        self.assertEqual(active_content["retrieval_content_posture"]["status"], "encrypted")
        self.assertIn("Retrieval Content Posture", active_content["retrieval_content_posture"]["summary"])
        self.assertIn("Confidentiality Migration", active_content["confidentiality_migration"]["summary"])
        self.assertFalse(active_content["secure_erase"]["claimed"])

    def test_confidentiality_migration_preview_ignores_legacy_qdrant_payloads(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        artifact_path = Path(os.environ["UPLOADS_DIR"]) / "Legacy.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("legacy plaintext artifact", encoding="utf-8")

        import ingest_db

        ingest_db.create_job("legacy-job", "Legacy.md", str(artifact_path), "default")
        ingest_db.update_job_status("legacy-job", "completed", total_chunks=1, processed_chunks=1)
        response = self.client.get("/admin/lifecycle/confidentiality-migration/preview")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ready")
        self.assertEqual(len(body["artifacts"]), 1)
        self.assertEqual(body["retrieval_payloads"], [])
        self.assertTrue(body["support_removal_ready"])
        self.assertFalse(body["secure_erase_claimed"])
        self.assertNotIn("Secure Erase", body["summary"].replace("No Secure Erase claim is made.", ""))

    def test_confidentiality_migration_execute_ignores_legacy_qdrant_payloads(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        artifact_path = Path(os.environ["UPLOADS_DIR"]) / "Legacy.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("legacy plaintext artifact", encoding="utf-8")

        import content_artifacts
        import ingest_db

        ingest_db.create_job("legacy-job", "Legacy.md", str(artifact_path), "default")
        ingest_db.update_job_status("legacy-job", "completed", total_chunks=1, processed_chunks=1)
        response = self.client.post("/admin/lifecycle/confidentiality-migration/execute")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertTrue(content_artifacts.is_encrypted_artifact(artifact_path.read_bytes()))
        self.assertIsNone(ingest_db.get_retrieval_chunk("chunk-1"))
        self.assertFalse(body["secure_erase_claimed"])

    def test_confidentiality_migration_reports_partial_failure_without_secure_erase_claim(self) -> None:
        os.environ.pop("CONTENT_ENCRYPTION_KEY", None)
        artifact_path = Path(os.environ["UPLOADS_DIR"]) / "Legacy.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("legacy plaintext artifact", encoding="utf-8")

        import ingest_db

        ingest_db.create_job("legacy-job", "Legacy.md", str(artifact_path), "default")
        ingest_db.update_job_status("legacy-job", "completed", total_chunks=1, processed_chunks=1)
        response = self.client.post("/admin/lifecycle/confidentiality-migration/execute")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        skipped = [result for result in body["results"] if result["status"] == "skipped"]
        self.assertEqual(skipped[0]["reason"], "content_encryption_key_not_configured")
        self.assertFalse(body["secure_erase_claimed"])
        self.assertEqual(artifact_path.read_text(encoding="utf-8"), "legacy plaintext artifact")

    def test_confidentiality_migration_is_idempotent_when_no_legacy_storage_remains(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        preview = self.client.get("/admin/lifecycle/confidentiality-migration/preview")
        first = self.client.post("/admin/lifecycle/confidentiality-migration/execute")
        second = self.client.post("/admin/lifecycle/confidentiality-migration/execute")

        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()["support_removal_ready"])
        self.assertFalse(preview.json()["secure_erase_claimed"])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["results"], [])
        self.assertEqual(second.json()["results"], [])

    def test_deployment_automation_can_run_scheduled_retention_without_admin_session(self) -> None:
        os.environ["RETENTION_AUTOMATION_TOKEN"] = "automation-secret"

        response = self.client.post(
            "/admin/lifecycle/retention/scheduled/automation/run",
            headers={"X-Retention-Automation-Token": "automation-secret"},
            json={"retry_limit": 0},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "succeeded")
        self.assertEqual(
            response.json()["enabled_classes"],
            ["audit_log", "sage_session_memory", "uploaded_document_artifacts", "user_memory"],
        )
        audit_entries = self.database.get_config_audit_log(limit=1, table_name="data_deletion")
        self.assertEqual(audit_entries[0]["changed_by"], "machine:scheduled-retention")

    def test_deployment_automation_rejects_missing_or_wrong_token(self) -> None:
        os.environ["RETENTION_AUTOMATION_TOKEN"] = "automation-secret"

        missing = self.client.post(
            "/admin/lifecycle/retention/scheduled/automation/run",
            json={"retry_limit": 0},
        )
        wrong = self.client.post(
            "/admin/lifecycle/retention/scheduled/automation/run",
            headers={"X-Retention-Automation-Token": "wrong"},
            json={"retry_limit": 0},
        )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_lifecycle_status_includes_conservative_default_retention_policy_for_enforced_classes(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        enforceable = {
            "sage_session_memory",
            "uploaded_document_artifacts",
            "user_memory",
            "audit_log",
        }

        for data_class in body["data_classes"]:
            if data_class["key"] in enforceable:
                policy = data_class["retention_policy"]
                self.assertEqual(policy["lifecycle_data_class"], data_class["key"])
                self.assertTrue(policy["enabled"])
                self.assertGreater(policy["retention_window_days"], 0)
                self.assertTrue(policy["scheduled_enforcement_enabled"])
            else:
                self.assertNotIn("retention_policy", data_class)

    def test_admin_can_update_retention_policy_for_lifecycle_data_class(self) -> None:
        update = self.client.put(
            "/admin/lifecycle/retention-policies/sage_session_memory",
            json={
                "enabled": True,
                "retention_window_days": 45,
                "scheduled_enforcement_enabled": True,
            },
        )

        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["policy"]["lifecycle_data_class"], "sage_session_memory")
        self.assertTrue(update.json()["policy"]["enabled"])

        response = self.client.get("/admin/lifecycle/status")
        classes_by_key = {
            data_class["key"]: data_class
            for data_class in response.json()["data_classes"]
        }
        policy = classes_by_key["sage_session_memory"]["retention_policy"]
        self.assertTrue(policy["enabled"])
        self.assertEqual(policy["retention_window_days"], 45)
        self.assertTrue(policy["scheduled_enforcement_enabled"])
        self.assertTrue(classes_by_key["user_memory"]["retention_policy"]["enabled"])

        audit_entries = self.database.get_config_audit_log(limit=10, table_name="instance_settings")
        self.assertEqual(audit_entries[0]["config_key"], "lifecycle_retention_policies")
        self.assertEqual(audit_entries[0]["changed_by"], "admin-pubkey")

    def test_retention_policy_update_validates_window_and_requires_admin(self) -> None:
        invalid = self.client.put(
            "/admin/lifecycle/retention-policies/sage_session_memory",
            json={
                "enabled": True,
                "retention_window_days": 0,
                "scheduled_enforcement_enabled": False,
            },
        )
        self.assertEqual(invalid.status_code, 422)

        app = FastAPI()
        app.include_router(self.lifecycle.router)
        client = TestClient(app)
        unauthenticated = client.put(
            "/admin/lifecycle/retention-policies/sage_session_memory",
            json={
                "enabled": True,
                "retention_window_days": 30,
                "scheduled_enforcement_enabled": False,
            },
        )
        self.assertIn(unauthenticated.status_code, (401, 403))

        unsupported = self.client.put(
            "/admin/lifecycle/retention-policies/user_profiles",
            json={
                "enabled": True,
                "retention_window_days": 30,
                "scheduled_enforcement_enabled": False,
            },
        )
        self.assertEqual(unsupported.status_code, 404)

    def test_audit_coverage_inventory_has_no_missing_supported_mutations(self) -> None:
        response = self.client.get("/admin/lifecycle/audit-coverage")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["summary"]["guardrail_passed"])
        self.assertEqual(body["summary"]["missing"], 0)
        statuses = {item["status"] for item in body["items"]}
        self.assertIn("audited", statuses)
        self.assertIn("documented_exception", statuses)

    def test_lifecycle_status_discloses_unacknowledged_unsupported_deployment_surfaces(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        surfaces = {
            surface["key"]: surface
            for surface in body["unsupported_deployment_surfaces"]
        }

        for key in (
            "docker_logs",
            "gateway_logs",
            "host_backups",
            "host_snapshots",
            "sqlite_wal",
            "postgres_wal",
            "provider_traces",
        ):
            self.assertIn(key, surfaces)
            self.assertEqual(surfaces[key]["status"], "unsupported")
            self.assertFalse(surfaces[key]["acknowledged"])

    def test_lifecycle_status_copy_avoids_secure_erase_overclaims(self) -> None:
        response = self.client.get("/admin/lifecycle/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        serialized = json.dumps(body).lower()
        self.assertNotIn("permanent deletion", serialized)
        self.assertNotIn("delete forever", serialized)
        self.assertIn("secure erase", serialized)
        self.assertEqual(body["secure_erase"]["status"], "unsupported")
        self.assertIn("active-storage", body["secure_erase"]["summary"])
        self.assertIn("unsupported", body["secure_erase"]["summary"])

    def test_lifecycle_status_reports_artifact_encryption_posture_from_deployment_settings(self) -> None:
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        try:
            response = self.client.get("/admin/lifecycle/status")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["content_encryption"]["status"], "configured")
            self.assertEqual(body["artifact_encryption"]["posture"], "required")

            update = self.client.put(
                "/admin/lifecycle/artifact-encryption-posture",
                json={"posture": "disabled"},
            )
            self.assertEqual(update.status_code, 200)
            self.assertEqual(update.json()["artifact_encryption"]["posture"], "disabled")

            body = self.client.get("/admin/lifecycle/status").json()
            self.assertEqual(body["artifact_encryption"]["posture"], "disabled")
            artifacts = {
                data_class["key"]: data_class
                for data_class in body["data_classes"]
            }["uploaded_document_artifacts"]["confidentiality"]
            self.assertEqual(artifacts["status"], "plaintext_by_operator_choice")

            audit_entries = self.database.get_config_audit_log(limit=10, table_name="deployment_config")
            self.assertEqual(audit_entries[0]["config_key"], "DOCUMENT_ARTIFACT_ENCRYPTION")
            self.assertEqual(audit_entries[0]["changed_by"], "admin-pubkey")
        finally:
            os.environ.pop("CONTENT_ENCRYPTION_KEY", None)

    def test_admin_can_acknowledge_unsupported_deployment_surface(self) -> None:
        acknowledgement = self.client.post(
            "/admin/lifecycle/unsupported-deployment-surfaces/docker_logs/acknowledgement",
            json={"acknowledged": True},
        )

        self.assertEqual(acknowledgement.status_code, 200)

        response = self.client.get("/admin/lifecycle/status")
        self.assertEqual(response.status_code, 200)
        surfaces = {
            surface["key"]: surface
            for surface in response.json()["unsupported_deployment_surfaces"]
        }
        self.assertTrue(surfaces["docker_logs"]["acknowledged"])
        self.assertFalse(surfaces["gateway_logs"]["acknowledged"])
        audit_entries = self.database.get_config_audit_log(limit=10, table_name="instance_settings")
        self.assertEqual(audit_entries[0]["config_key"], "lifecycle_unsupported_surface_acknowledgements")
        self.assertEqual(audit_entries[0]["changed_by"], "admin-pubkey")

    def test_admin_can_acknowledge_unsupported_deployment_surface_category(self) -> None:
        review = self.client.post("/admin/lifecycle/readiness/review")
        self.assertEqual(review.status_code, 200)

        acknowledgement = self.client.post(
            "/admin/lifecycle/unsupported-deployment-surface-categories/browser_held_copies/acknowledgement",
            json={"acknowledged": True},
        )

        self.assertEqual(acknowledgement.status_code, 200)
        categories = {
            category["category"]: category
            for category in acknowledgement.json()["unsupported_deployment_surface_categories"]
        }
        browser_copies = categories["browser_held_copies"]
        self.assertTrue(browser_copies["acknowledged"])
        self.assertEqual(browser_copies["acknowledged_by"], "admin-pubkey")
        self.assertIn("Clear browser storage", browser_copies["guidance"])
        self.assertEqual(browser_copies["surfaces"][0]["key"], "browser_storage")
        stored_acknowledgements = json.loads(self.database.get_setting("lifecycle_unsupported_surface_category_acknowledgements"))
        stored_posture_version = stored_acknowledgements["browser_held_copies"]["posture_version"]
        self.assertEqual(stored_posture_version, self.lifecycle._readiness_version())
        stored_acknowledgements["browser_held_copies"]["acknowledged_by"] = "different-admin"
        stored_acknowledgements["browser_held_copies"]["acknowledged_at"] = "2026-05-17T00:00:00"
        stored_acknowledgements["browser_held_copies"]["posture_version"] = "previous-version"
        self.database.update_setting(
            "lifecycle_unsupported_surface_category_acknowledgements",
            json.dumps(stored_acknowledgements),
        )
        self.assertEqual(stored_posture_version, self.lifecycle._readiness_version())

        status = self.client.get("/admin/lifecycle/status").json()
        readiness = status["lifecycle_readiness"]
        self.assertEqual(readiness["status"], "stale")
        self.assertEqual(readiness["stale_reason"], "unsupported_surface_category_acknowledgement_changed")

        audit_entries = self.database.get_config_audit_log(limit=10, table_name="instance_settings")
        keys = [entry["config_key"] for entry in audit_entries]
        self.assertIn("lifecycle_unsupported_surface_category_acknowledgements", keys)

    def test_admin_can_review_lifecycle_readiness_and_lifecycle_changes_make_it_stale(self) -> None:
        initial = self.client.get("/admin/lifecycle/status").json()["lifecycle_readiness"]
        self.assertEqual(initial["status"], "needs_review")
        self.assertFalse(initial["reviewed"])

        review = self.client.post("/admin/lifecycle/readiness/review")
        self.assertEqual(review.status_code, 200)
        reviewed = review.json()["lifecycle_readiness"]
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertEqual(reviewed["reviewed_by"], "admin-pubkey")
        self.assertIn("browser_held_copies", reviewed["acknowledged_unsupported_surface_categories"])

        update = self.client.put(
            "/admin/lifecycle/retention-policies/sage_session_memory",
            json={
                "enabled": True,
                "retention_window_days": 45,
                "scheduled_enforcement_enabled": True,
            },
        )
        self.assertEqual(update.status_code, 200)

        stale = self.client.get("/admin/lifecycle/status").json()["lifecycle_readiness"]
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["stale_reason"], "retention_policy_changed")

        audit_entries = self.database.get_config_audit_log(limit=10, table_name="instance_settings")
        keys = [entry["config_key"] for entry in audit_entries]
        self.assertIn("lifecycle_readiness", keys)
        self.assertIn("lifecycle_readiness_staleness", keys)

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
