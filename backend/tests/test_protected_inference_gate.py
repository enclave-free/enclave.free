import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class ProtectedInferenceGateTest(unittest.TestCase):
    def test_gate_allows_current_verification_record(self) -> None:
        from protected_inference import ProtectedInferenceGate

        events: list[dict] = []
        gate = ProtectedInferenceGate(
            current_status=lambda: {"status": "current", "record": {"id": 42}},
            audit_block=lambda **kwargs: events.append(kwargs),
        )

        result = gate.require_current(context="conversation")

        self.assertEqual(result["id"], 42)
        self.assertEqual(events, [])

    def test_gate_blocks_missing_failed_or_stale_records_with_audit(self) -> None:
        from protected_inference import ProtectedInferenceBlocked, ProtectedInferenceGate

        for status in ("missing", "failed", "stale"):
            with self.subTest(status=status):
                events: list[dict] = []
                gate = ProtectedInferenceGate(
                    current_status=lambda status=status: {"status": status, "record": None},
                    audit_block=lambda **kwargs: events.append(kwargs),
                )

                with self.assertRaises(ProtectedInferenceBlocked) as raised:
                    gate.require_current(context="conversation")

                self.assertIn("Protected inference is unavailable", str(raised.exception))
                self.assertEqual(events[0]["context"], "conversation")
                self.assertEqual(events[0]["status"], status)

    def test_development_bypass_allows_without_record_and_reports_weakened_posture(self) -> None:
        from protected_inference import ProtectedInferenceGate

        events: list[dict] = []
        gate = ProtectedInferenceGate(
            current_status=lambda: {"status": "missing", "record": None},
            audit_block=lambda **kwargs: events.append(kwargs),
            bypass_enabled=lambda: True,
        )

        result = gate.require_current(context="conversation")

        self.assertEqual(result["id"], None)
        self.assertTrue(result["bypass"])
        self.assertEqual(result["privacy_posture"], "weakened")
        self.assertEqual(events, [])

    def test_diagnostics_do_not_require_gate(self) -> None:
        from protected_inference import inference_requires_verification

        self.assertFalse(inference_requires_verification("diagnostic"))
        self.assertFalse(inference_requires_verification("verification"))
        self.assertTrue(inference_requires_verification("conversation"))
        self.assertTrue(inference_requires_verification("user_memory_extraction"))

    def test_default_expected_claims_fingerprint_matches_empty_claims_policy(self) -> None:
        from inference_verification import fingerprint_claims
        from protected_inference import DEFAULT_EXPECTED_CLAIMS_FINGERPRINT

        self.assertEqual(DEFAULT_EXPECTED_CLAIMS_FINGERPRINT, fingerprint_claims({}))
