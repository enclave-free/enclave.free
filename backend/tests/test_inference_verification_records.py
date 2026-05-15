import importlib
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class InferenceVerificationRecordStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_auth = sys.modules.get("auth")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        sys.modules["auth"] = types.SimpleNamespace(SECRET_KEY="test-secret")

        import database

        self.database = importlib.reload(database)
        self.database.init_schema()

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self.database._deployment_secret_key = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        if self._orig_auth is None:
            sys.modules.pop("auth", None)
        else:
            sys.modules["auth"] = self._orig_auth
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_creates_record_with_encrypted_attestation_and_queryable_metadata(self) -> None:
        checked_at = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)

        record = self.database.create_inference_verification_record(
            provider_identity="tinfoil",
            provider_endpoint="https://llm.example.test/v1",
            model_identifier="kimi-k2-6",
            status="success",
            trigger="manual",
            expected_claims_fingerprint="expected-1",
            actual_claims_fingerprint="actual-1",
            verifier_version="tinfoil-verifier/1",
            attestation_material={"quote": "full-attestation-material"},
            checked_at=checked_at,
        )

        self.assertEqual(record["provider_identity"], "tinfoil")
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["attestation_material"], {"quote": "full-attestation-material"})
        history = self.database.list_inference_verification_records()
        self.assertEqual(history[0]["id"], record["id"])
        self.assertNotIn("attestation_material", history[0])

        raw_conn = sqlite3.connect(self.db_path)
        try:
            raw_value = raw_conn.execute(
                "SELECT encrypted_attestation_material FROM inference_verification_records WHERE id = ?",
                (record["id"],),
            ).fetchone()[0]
        finally:
            raw_conn.close()
        self.assertTrue(raw_value.startswith(self.database.DEPLOYMENT_SECRET_PREFIX))
        self.assertNotIn("full-attestation-material", raw_value)

        detail = self.database.get_inference_verification_record(record["id"])
        self.assertEqual(detail["attestation_material"], {"quote": "full-attestation-material"})

    def test_current_status_requires_fresh_successful_matching_record(self) -> None:
        now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        stale = now - timedelta(hours=25)
        fresh = now - timedelta(hours=1)

        self.database.create_inference_verification_record(
            provider_identity="tinfoil",
            provider_endpoint="https://llm.example.test/v1",
            model_identifier="kimi-k2-6",
            status="success",
            trigger="startup",
            expected_claims_fingerprint="expected-1",
            actual_claims_fingerprint="actual-stale",
            verifier_version="tinfoil-verifier/1",
            attestation_material={"quote": "stale"},
            checked_at=stale,
            expires_at=stale + timedelta(hours=24),
        )
        failed = self.database.create_inference_verification_record(
            provider_identity="tinfoil",
            provider_endpoint="https://llm.example.test/v1",
            model_identifier="kimi-k2-6",
            status="failed",
            trigger="manual",
            expected_claims_fingerprint="expected-1",
            actual_claims_fingerprint="actual-failed",
            verifier_version="tinfoil-verifier/1",
            failure_category="claim_mismatch",
            failure_message="PCR mismatch",
            attestation_material={"quote": "failed-evidence"},
            checked_at=now - timedelta(minutes=30),
        )
        current = self.database.create_inference_verification_record(
            provider_identity="tinfoil",
            provider_endpoint="https://llm.example.test/v1",
            model_identifier="kimi-k2-6",
            status="success",
            trigger="manual",
            expected_claims_fingerprint="expected-1",
            actual_claims_fingerprint="actual-current",
            verifier_version="tinfoil-verifier/1",
            attestation_material={"quote": "current"},
            checked_at=fresh,
        )

        status = self.database.get_current_inference_verification_status(
            provider_identity="tinfoil",
            provider_endpoint="https://llm.example.test/v1",
            model_identifier="kimi-k2-6",
            expected_claims_fingerprint="expected-1",
            now=now,
        )

        self.assertEqual(status["status"], "current")
        self.assertEqual(status["record"]["id"], current["id"])
        self.assertIsNone(self.database.get_current_inference_verification_status(
            provider_identity="tinfoil",
            provider_endpoint="https://other.example.test/v1",
            model_identifier="kimi-k2-6",
            expected_claims_fingerprint="expected-1",
            now=now,
        )["record"])
        self.assertEqual(self.database.get_inference_verification_record(failed["id"])["attestation_material"], {"quote": "failed-evidence"})

    def test_configured_provider_setting_change_makes_prior_record_non_current(self) -> None:
        now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        self.database.upsert_deployment_config("LLM_PROVIDER", "sage", category="llm")
        self.database.upsert_deployment_config("LLM_API_URL", "https://llm.example.test/v1", category="llm")
        self.database.upsert_deployment_config("LLM_MODEL", "kimi-k2-6", category="llm")
        self.database.create_inference_verification_record(
            provider_identity="sage",
            provider_endpoint="https://llm.example.test/v1",
            model_identifier="kimi-k2-6",
            status="success",
            trigger="manual",
            expected_claims_fingerprint="expected-1",
            actual_claims_fingerprint="actual-current",
            verifier_version="tinfoil-verifier/1",
            attestation_material={"quote": "current"},
            checked_at=now - timedelta(minutes=5),
        )

        self.assertEqual(self.database.get_current_inference_verification_status_for_config(
            expected_claims_fingerprint="expected-1",
            now=now,
        )["status"], "current")

        self.database.update_deployment_config("LLM_MODEL", "new-model", changed_by="admin-pubkey")

        status = self.database.get_current_inference_verification_status_for_config(
            expected_claims_fingerprint="expected-1",
            now=now,
        )
        self.assertEqual(status["status"], "missing")
        self.assertIsNone(status["record"])
