import importlib
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
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"

        import auth
        import database
        import deployment_config

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.deployment_config = importlib.reload(deployment_config)
        self.database.init_schema()
        self.deployment_config._sync_env_to_db()
        self.database.upsert_deployment_config("LLM_PROVIDER", "sage", category="llm")
        self.database.upsert_deployment_config("LLM_API_URL", "https://inference.tinfoil.sh/v1", category="llm")
        self.database.upsert_deployment_config("LLM_MODEL", "kimi-k2-6", category="llm")

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
        self.assertNotIn("attestation_material", body["record"])

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
