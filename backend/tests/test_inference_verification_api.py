import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class InferenceVerificationApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_llm_api_key = os.environ.get("LLM_API_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["LLM_API_KEY"] = "test-key"

        import auth
        import database
        import deployment_config
        import inference_repair

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.inference_repair = importlib.reload(inference_repair)
        self.deployment_config = importlib.reload(deployment_config)
        self.database.init_schema()
        self.deployment_config._sync_env_to_db()
        self.database.upsert_deployment_config("LLM_PROVIDER", "sage", category="llm")
        self.database.upsert_deployment_config("LLM_API_URL", "https://inference.tinfoil.sh/v1", category="llm")
        self.database.upsert_deployment_config("LLM_MODEL", "kimi-k2-6", category="llm")
        self.database.update_deployment_config("LLM_API_KEY", "test-key", changed_by="admin-pubkey")
        self.inference_repair.reset_inference_repair_status()

        app = FastAPI()
        app.include_router(self.deployment_config.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self.database._deployment_secret_key = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("LLM_API_KEY", self._orig_llm_api_key)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_admin_can_fetch_current_inference_verification_status(self) -> None:
        now = datetime.now(timezone.utc)
        record = self.database.create_inference_verification_record(
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            status="success",
            trigger="manual",
            expected_claims_fingerprint=self.deployment_config.current_expected_claims_fingerprint(),
            actual_claims_fingerprint="actual-1",
            verifier_version="test-verifier/1",
            attestation_material={"quote": "full"},
            checked_at=now - timedelta(minutes=5),
        )

        response = self.client.get("/admin/deployment/inference-verification/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "current")
        self.assertEqual(body["record"]["id"], record["id"])
        self.assertEqual(body["configured_provider"]["provider_identity"], "sage")
        self.assertEqual(body["configured_provider"]["provider_endpoint"], "https://inference.tinfoil.sh/v1")
        self.assertEqual(body["configured_provider"]["model_identifier"], "kimi-k2-6")
        self.assertIn("repair", body)
        self.assertNotIn("attestation_material", body["record"])

    def test_startup_verification_success_permits_protected_inference(self) -> None:
        from inference_verification import InferenceVerificationResult

        expected_fingerprint = self.deployment_config.current_expected_claims_fingerprint()

        class FakeVerifier:
            def verify(self, **kwargs):
                return InferenceVerificationResult(
                    provider_identity=kwargs["provider_identity"],
                    provider_endpoint=kwargs["provider_endpoint"],
                    model_identifier=kwargs["model_identifier"],
                    status="success",
                    trigger=kwargs["trigger"],
                    expected_claims_fingerprint=expected_fingerprint,
                    actual_claims_fingerprint="actual",
                    verifier_version="fake-verifier/1",
                    attestation_material={"quote": "startup"},
                )

        self.deployment_config.TinfoilVerifier = lambda: FakeVerifier()

        repair = self.deployment_config.run_startup_inference_verification()
        status = self.client.get("/admin/deployment/inference-verification/status").json()

        self.assertEqual(repair["mode"], "normal")
        self.assertTrue(repair["protected_inference_available"])
        self.assertEqual(status["status"], "current")
        self.assertEqual(status["record"]["trigger"], "startup")

    def test_startup_verification_failure_enters_degraded_admin_repair_mode(self) -> None:
        self.database.update_deployment_config("LLM_API_KEY", "", changed_by="admin-pubkey")
        self._restore_env("LLM_API_KEY", None)

        repair = self.deployment_config.run_startup_inference_verification()

        self.assertEqual(repair["mode"], "degraded_admin_repair")
        self.assertFalse(repair["protected_inference_available"])
        self.assertEqual(repair["status"], "missing")
        self.assertEqual(repair["reason"], "LLM_API_KEY not configured")
        response = self.client.get("/admin/deployment/inference-verification/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["repair"]["mode"], "degraded_admin_repair")

    def test_admin_can_fetch_history_and_full_attestation_detail(self) -> None:
        record = self.database.create_inference_verification_record(
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            status="failed",
            trigger="manual",
            expected_claims_fingerprint=self.deployment_config.current_expected_claims_fingerprint(),
            actual_claims_fingerprint="actual-1",
            verifier_version="test-verifier/1",
            failure_category="claim_mismatch",
            failure_message="PCR mismatch",
            attestation_material={"quote": "full-failed-evidence"},
        )

        history_response = self.client.get("/admin/deployment/inference-verification/records")
        detail_response = self.client.get(f"/admin/deployment/inference-verification/records/{record['id']}")

        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.json()["records"][0]["id"], record["id"])
        self.assertNotIn("attestation_material", history_response.json()["records"][0])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["attestation_material"], {"quote": "full-failed-evidence"})

    def test_admin_can_trigger_manual_verification(self) -> None:
        from inference_verification import InferenceVerificationResult

        class FakeVerifier:
            def verify(self, **kwargs):
                return InferenceVerificationResult(
                    provider_identity=kwargs["provider_identity"],
                    provider_endpoint=kwargs["provider_endpoint"],
                    model_identifier=kwargs["model_identifier"],
                    status="success",
                    trigger=kwargs["trigger"],
                    expected_claims_fingerprint="expected",
                    actual_claims_fingerprint="actual",
                    verifier_version="fake-verifier/1",
                    attestation_material={"quote": "manual"},
                )

        self.deployment_config.TinfoilVerifier = lambda: FakeVerifier()

        response = self.client.post("/admin/deployment/inference-verification/verify")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["trigger"], "manual")
        self.assertEqual(body["attestation_material"], {"quote": "manual"})
        self.assertEqual(len(self.database.list_inference_verification_records()), 1)
        self.assertEqual(self.inference_repair.current_inference_repair_status()["mode"], "normal")

        audit_response = self.client.get("/admin/deployment/audit-log?table_name=inference_verification")
        self.assertEqual(audit_response.status_code, 200)
        audit_entries = audit_response.json()["entries"]
        entries_by_key = {entry["config_key"]: entry for entry in audit_entries}
        self.assertIn("verification_status_changed", entries_by_key)
        self.assertIn("manual_verification", entries_by_key)
        self.assertEqual(entries_by_key["manual_verification"]["changed_by"], "admin-pubkey")
        self.assertEqual(entries_by_key["verification_status_changed"]["changed_by"], "admin-pubkey")
        self.assertIn('"status":"success"', entries_by_key["verification_status_changed"]["new_value"])
        self.assertIn('"trigger":"manual"', entries_by_key["verification_status_changed"]["new_value"])
        manual_event = json.loads(entries_by_key["manual_verification"]["new_value"])
        status_change_event = json.loads(entries_by_key["verification_status_changed"]["new_value"])
        self.assertNotIn("attestation_material", manual_event)
        self.assertNotIn("attestation_material", status_change_event)

    def test_manual_verification_requires_configured_model_provider_api_key(self) -> None:
        self.database.update_deployment_config("LLM_API_KEY", "", changed_by="admin-pubkey")
        self._restore_env("LLM_API_KEY", None)

        response = self.client.post("/admin/deployment/inference-verification/verify")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "LLM_API_KEY not configured")

    def test_users_cannot_access_inference_verification_attestation_detail(self) -> None:
        app = FastAPI()
        app.include_router(self.deployment_config.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: (_ for _ in ()).throw(HTTPException(status_code=403, detail="Admin authentication required"))
        client = TestClient(app)

        response = client.get("/admin/deployment/inference-verification/records/1")

        self.assertEqual(response.status_code, 403)

    def test_blocked_protected_inference_audit_is_visible_without_content(self) -> None:
        from protected_inference import audit_blocked_protected_inference

        audit_blocked_protected_inference(context="conversation", status="missing")

        response = self.client.get("/admin/deployment/audit-log?table_name=inference_verification")

        self.assertEqual(response.status_code, 200)
        entries = response.json()["entries"]
        self.assertEqual(entries[0]["config_key"], "protected_inference_blocked")
        self.assertEqual(entries[0]["changed_by"], "system:protected-inference-gate")
        self.assertIn('"context":"conversation"', entries[0]["new_value"])
        self.assertIn('"status":"missing"', entries[0]["new_value"])
        self.assertNotIn("message", entries[0]["new_value"])
        self.assertNotIn("content", entries[0]["new_value"])
