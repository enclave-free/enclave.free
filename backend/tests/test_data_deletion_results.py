import importlib
import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DataDeletionResultTest(unittest.TestCase):
    def setUp(self) -> None:
        import data_deletion

        self.data_deletion = importlib.reload(data_deletion)

    def test_deletion_summary_reports_success_idempotent_and_retryable_failure(self) -> None:
        results = [
            self.data_deletion.deletion_target_succeeded(
                target_kind="conversation",
                target_id="session-1",
                action="delete_session_record",
                detail="Session record deleted.",
            ),
            self.data_deletion.deletion_target_skipped(
                target_kind="session_memory",
                target_id="session-1",
                action="delete_session_memory",
                detail="Session Memory was already absent.",
            ),
            self.data_deletion.deletion_target_failed(
                target_kind="retrieval_index",
                target_id="job-1",
                action="delete_points",
                detail="Qdrant is unavailable.",
                retryable=True,
            ),
        ]

        summary = self.data_deletion.summarize_deletion_results(results)

        self.assertEqual(summary["status"], "partial_failure")
        self.assertTrue(summary["retryable"])
        self.assertEqual(summary["counts"]["succeeded"], 1)
        self.assertEqual(summary["counts"]["skipped"], 1)
        self.assertEqual(summary["counts"]["failed"], 1)
        self.assertEqual(summary["results"][1]["status"], "skipped")
        self.assertTrue(summary["results"][2]["retryable"])

    def test_all_skipped_deletion_targets_are_successful_idempotent_outcome(self) -> None:
        results = [
            self.data_deletion.deletion_target_skipped(
                target_kind="document",
                target_id="job-1",
                action="delete_document_metadata",
                detail="Document was already absent.",
            ),
            self.data_deletion.deletion_target_skipped(
                target_kind="retrieval_index",
                target_id="job-1",
                action="delete_points",
                detail="Retrieval points were already absent.",
            ),
        ]

        summary = self.data_deletion.summarize_deletion_results(results)

        self.assertEqual(summary["status"], "succeeded")
        self.assertFalse(summary["retryable"])
        self.assertEqual(summary["counts"]["skipped"], 2)

    def test_all_succeeded_deletion_targets_are_successful(self) -> None:
        results = [
            self.data_deletion.deletion_target_succeeded(
                target_kind="document",
                target_id="job-1",
                action="delete_document_metadata",
                detail="Document metadata deleted.",
            ),
            self.data_deletion.deletion_target_succeeded(
                target_kind="retrieval_index",
                target_id="job-1",
                action="delete_points",
                detail="Retrieval points deleted.",
            ),
        ]

        summary = self.data_deletion.summarize_deletion_results(results)

        self.assertEqual(summary["status"], "succeeded")
        self.assertFalse(summary["retryable"])
        self.assertEqual(summary["counts"], {"succeeded": 2, "skipped": 0, "failed": 0})

    def test_all_failed_deletion_targets_report_failure_and_retryability(self) -> None:
        results = [
            self.data_deletion.deletion_target_failed(
                target_kind="retrieval_index",
                target_id="job-1",
                action="delete_points",
                detail="Qdrant unavailable.",
                retryable=True,
            ),
            self.data_deletion.deletion_target_failed(
                target_kind="uploaded_document_artifact",
                target_id="job-1",
                action="delete_uploaded_document_artifact",
                detail="Path refused.",
                retryable=False,
            ),
        ]

        summary = self.data_deletion.summarize_deletion_results(results)

        self.assertEqual(summary["status"], "failed")
        self.assertTrue(summary["retryable"])
        self.assertEqual(summary["counts"], {"succeeded": 0, "skipped": 0, "failed": 2})

    def test_non_retryable_failures_are_not_retryable(self) -> None:
        results = [
            self.data_deletion.deletion_target_failed(
                target_kind="uploaded_document_artifact",
                target_id="job-1",
                action="delete_uploaded_document_artifact",
                detail="Path refused.",
                retryable=False,
            ),
        ]

        summary = self.data_deletion.summarize_deletion_results(results)

        self.assertEqual(summary["status"], "failed")
        self.assertFalse(summary["retryable"])

    def test_empty_deletion_results_are_successful_noop(self) -> None:
        summary = self.data_deletion.summarize_deletion_results([])

        self.assertEqual(summary["status"], "succeeded")
        self.assertFalse(summary["retryable"])
        self.assertEqual(summary["counts"], {"succeeded": 0, "skipped": 0, "failed": 0})


if __name__ == "__main__":
    unittest.main()
