import copy
import unittest
from unittest.mock import patch

import httpx

from scripts.benches.quality_measurements import (
    JUDGE_INSTRUCTION,
    RUBRIC,
    build_review_packet,
    fingerprint,
    load_calibration_fixture,
    measure_artifact,
)
from scripts.benches.review_bench import tinfoil_judge


def artifact(*, expert_review_status="not_required"):
    return {
        "run": {},
        "candidates": [
            {
                "model": "candidate",
                "scenarios": [
                    {
                        "id": "journey",
                        "scenario_run_id": "journey#1",
                        "expected_turn_count": 2,
                        "summary": {"status": "passed"},
                        "rubric": {"expert_review_status": expert_review_status},
                        "turns": [
                            {
                                "completed": True,
                                "request": {"message": "When is Cedar open?"},
                                "response": {
                                    "answer": "I will check.",
                                    "model": "candidate",
                                    "provider": "provider",
                                    "session_id": "private-session",
                                },
                                "timing": {"done_ms": 10},
                                "tool_evidence": [{"result": "Cedar opens Tuesday."}],
                            },
                            {
                                "completed": True,
                                "request": {"message": "And Thursday?"},
                                "response": {
                                    "answer": "Tuesday and Thursday.",
                                    "model": "candidate",
                                },
                                "timing": {"done_ms": 10},
                            },
                        ],
                    }
                ],
            }
        ],
    }


def calibrated_review(source):
    packet = build_review_packet(source)
    fixture = load_calibration_fixture()
    cases = []
    for case in fixture["cases"]:
        dimensions = {
            name: {
                "status": case["expected"].get(name, "passed"),
                "reason": "Calibration verdict.",
                "evidence_quotes": [],
            }
            for name in RUBRIC
        }
        cases.append({"id": case["id"], "passed": True, "dimensions": dimensions})
    calibration = {
        "fixture_hash": fingerprint(fixture),
        "rubric_hash": packet["rubric_hash"],
        "instruction_hash": fingerprint(JUDGE_INSTRUCTION),
        "model": "independent-judge",
        "reasoning_effort": "low",
        "cases": cases,
    }
    packet["calibration"] = calibration
    for entry in packet["entries"]:
        entry.update(
            reviewer="independent-judge",
            method="calibrated_model",
            reviewed_at="2026-09-10T00:00:00Z",
            calibration_hash=fingerprint(calibration),
        )
        for result in entry["dimensions"].values():
            result.update(status="passed", reason="Reviewed against the complete evidence.")
    return packet


class ReviewRegressionTests(unittest.TestCase):
    def test_prior_tool_evidence_is_retained_in_sanitized_history(self):
        history = build_review_packet(artifact())["entries"][1]["evidence"]["history"]

        self.assertEqual(history[0]["tool_evidence"], [{"result": "Cedar opens Tuesday."}])
        self.assertNotIn("model", history[0]["response"])
        self.assertNotIn("provider", history[0]["response"])
        self.assertNotIn("session_id", history[0]["response"])
        self.assertNotIn("timing", history[0])

    def test_expert_review_pending_prevents_a_passed_release_gate(self):
        source = artifact(expert_review_status="pending")
        review = calibrated_review(source)

        self.assertEqual(measure_artifact(source, review)["release_gate"], "expert_review_pending")

    def test_current_complete_calibration_is_accepted(self):
        source = artifact()

        result = measure_artifact(source, calibrated_review(source))

        self.assertEqual(result["semantic_review"]["status"], "passed")
        self.assertEqual(result["release_gate"], "passed")

    def test_calibration_tampering_is_rejected(self):
        source = artifact()
        mutations = {
            "fixture hash": lambda item: item.update(fixture_hash="forged"),
            "instruction hash": lambda item: item.update(instruction_hash="forged"),
            "reasoning effort": lambda item: item.update(reasoning_effort="none"),
            "missing case": lambda item: item["cases"].pop(),
            "duplicate case": lambda item: item["cases"].__setitem__(1, copy.deepcopy(item["cases"][0])),
            "wrong expected verdict": lambda item: item["cases"][0]["dimensions"][next(iter(load_calibration_fixture()["cases"][0]["expected"]))].update(status="unreviewed"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                review = calibrated_review(source)
                mutate(review["calibration"])
                new_hash = fingerprint(review["calibration"])
                for entry in review["entries"]:
                    entry["calibration_hash"] = new_hash
                self.assertEqual(measure_artifact(source, review)["semantic_review"]["status"], "error")

    def test_evaluated_model_cannot_be_reused_as_judge_during_apply(self):
        source = artifact()
        review = calibrated_review(source)
        review["calibration"]["model"] = "candidate"
        calibration_hash = fingerprint(review["calibration"])
        for entry in review["entries"]:
            entry.update(reviewer="candidate", calibration_hash=calibration_hash)

        self.assertEqual(measure_artifact(source, review)["semantic_review"]["status"], "error")

    def test_judge_transport_errors_do_not_expose_exception_text(self):
        request = httpx.Request("POST", "http://127.0.0.1:18089/v1/chat/completions")
        error = httpx.ConnectError("credential=SECRET", request=request)
        with patch.dict("os.environ", {"LLM_API_KEY": "SECRET"}), patch(
            "httpx.post", side_effect=error
        ):
            call = tinfoil_judge("http://127.0.0.1:18089/v1", "judge", "low", 1)
            with self.assertRaisesRegex(ValueError, "ConnectError") as raised:
                call({"question": "test"})

        self.assertNotIn("SECRET", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
