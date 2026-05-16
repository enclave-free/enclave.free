import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class InferenceVerificationTest(unittest.TestCase):
    def test_claim_fingerprint_is_stable_and_order_independent(self) -> None:
        from inference_verification import fingerprint_claims

        left = fingerprint_claims({"model": "kimi", "claims": {"tee": "tdx", "measurements": [1, 2]}})
        right = fingerprint_claims({"claims": {"measurements": [1, 2], "tee": "tdx"}, "model": "kimi"})

        self.assertEqual(left, right)
        self.assertEqual(len(left), 64)

    def test_redacts_identified_secret_and_credential_fields(self) -> None:
        from inference_verification import redact_attestation_material

        redacted = redact_attestation_material({
            "authorization": "Bearer secret",
            "api_key": "secret-key",
            "nested": {
                "credential": "secret-credential",
                "public_key": "safe-public-key",
            },
        })

        self.assertEqual(redacted["authorization"], "[REDACTED]")
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["credential"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["public_key"], "safe-public-key")

    def test_tinfoil_verifier_returns_success_with_full_sanitized_attestation(self) -> None:
        from inference_verification import TinfoilVerifier

        requests: list[dict] = []

        def fetcher(url: str, headers: dict[str, str], timeout: float):
            requests.append({"url": url, "headers": headers, "timeout": timeout})
            return 200, {
                "predicateType": "https://tinfoil.sh/predicate/hardware-measurements/v1",
                "subject": [{"name": "inference-server"}],
                "predicate": {
                    "tee": "tdx",
                    "measurement": "abc123",
                    "api_key": "must-not-store",
                },
            }

        result = TinfoilVerifier(fetcher=fetcher).verify(
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            expected_claims={"tee": "tdx"},
            api_key="secret-token",
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(requests[0]["url"], "https://inference.tinfoil.sh/.well-known/tinfoil-attestation")
        self.assertEqual(requests[0]["headers"]["Authorization"], "Bearer secret-token")
        self.assertEqual(result.failure_category, None)
        self.assertEqual(result.attestation_material["predicate"]["api_key"], "[REDACTED]")
        self.assertEqual(len(result.actual_claims_fingerprint or ""), 64)

    def test_tinfoil_verifier_returns_failed_record_with_artifact_when_claims_mismatch(self) -> None:
        from inference_verification import TinfoilVerifier

        def fetcher(_url: str, _headers: dict[str, str], _timeout: float):
            return 200, {
                "predicate": {
                    "tee": "sgx",
                    "measurement": "abc123",
                },
            }

        result = TinfoilVerifier(fetcher=fetcher).verify(
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            expected_claims={"tee": "tdx"},
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_category, "claim_mismatch")
        self.assertEqual(result.attestation_material["predicate"]["tee"], "sgx")

    def test_tinfoil_verifier_returns_failed_record_without_artifact_on_fetch_error(self) -> None:
        from inference_verification import TinfoilVerifier

        def fetcher(_url: str, _headers: dict[str, str], _timeout: float):
            raise TimeoutError("network timed out")

        result = TinfoilVerifier(fetcher=fetcher).verify(
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            expected_claims={"tee": "tdx"},
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_category, "attestation_unavailable")
        self.assertIsNone(result.attestation_material)
        self.assertIn("network timed out", result.failure_message or "")

    def test_verify_and_store_writes_normalized_result_to_storage(self) -> None:
        from inference_verification import InferenceVerificationResult, verify_and_store

        class FakeVerifier:
            def verify(self, **_kwargs):
                return InferenceVerificationResult(
                    provider_identity="sage",
                    provider_endpoint="https://inference.tinfoil.sh/v1",
                    model_identifier="kimi-k2-6",
                    status="success",
                    trigger="manual",
                    expected_claims_fingerprint="expected",
                    actual_claims_fingerprint="actual",
                    verifier_version="fake/1",
                    attestation_material={"quote": "full"},
                )

        writes: list[dict] = []

        class FakeStorage:
            def create_inference_verification_record(self, **kwargs):
                writes.append(kwargs)
                return {"id": 1, **kwargs}

        record = verify_and_store(
            verifier=FakeVerifier(),
            storage=FakeStorage(),
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            expected_claims={"tee": "tdx"},
            trigger="manual",
        )

        self.assertEqual(record["id"], 1)
        self.assertEqual(writes[0]["status"], "success")
        self.assertEqual(writes[0]["attestation_material"], {"quote": "full"})

    def test_verify_and_store_can_audit_status_change_without_attestation_material(self) -> None:
        from inference_verification import InferenceVerificationResult, verify_and_store

        class FakeVerifier:
            def verify(self, **_kwargs):
                return InferenceVerificationResult(
                    provider_identity="sage",
                    provider_endpoint="https://inference.tinfoil.sh/v1",
                    model_identifier="kimi-k2-6",
                    status="failed",
                    trigger="startup",
                    expected_claims_fingerprint="expected",
                    actual_claims_fingerprint="actual",
                    verifier_version="fake/1",
                    failure_category="claim_mismatch",
                    failure_message="PCR mismatch",
                    attestation_material={"quote": "full-attestation-material"},
                )

        class FakeStorage:
            def create_inference_verification_record(self, **kwargs):
                return {"id": 7, **kwargs}

        audit_events: list[dict] = []

        verify_and_store(
            verifier=FakeVerifier(),
            storage=FakeStorage(),
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            expected_claims={"tee": "tdx"},
            trigger="startup",
            audit_status_change=lambda event: audit_events.append(event),
        )

        self.assertEqual(audit_events[0]["record_id"], 7)
        self.assertEqual(audit_events[0]["status"], "failed")
        self.assertEqual(audit_events[0]["trigger"], "startup")
        self.assertEqual(audit_events[0]["failure_category"], "claim_mismatch")
        self.assertNotIn("attestation_material", audit_events[0])
        self.assertNotIn("full-attestation-material", str(audit_events[0]))

    def test_verify_and_store_returns_record_when_status_change_audit_fails(self) -> None:
        from inference_verification import InferenceVerificationResult, verify_and_store

        class FakeVerifier:
            def verify(self, **_kwargs):
                return InferenceVerificationResult(
                    provider_identity="sage",
                    provider_endpoint="https://inference.tinfoil.sh/v1",
                    model_identifier="kimi-k2-6",
                    status="success",
                    trigger="manual",
                    expected_claims_fingerprint="expected",
                    actual_claims_fingerprint="actual",
                    verifier_version="fake/1",
                    attestation_material={"quote": "full"},
                )

        class FakeStorage:
            def create_inference_verification_record(self, **kwargs):
                return {"id": 8, **kwargs}

        def failing_audit(_event):
            raise RuntimeError("audit unavailable")

        record = verify_and_store(
            verifier=FakeVerifier(),
            storage=FakeStorage(),
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            expected_claims={"tee": "tdx"},
            trigger="manual",
            audit_status_change=failing_audit,
        )

        self.assertEqual(record["id"], 8)
        self.assertEqual(record["status"], "success")
