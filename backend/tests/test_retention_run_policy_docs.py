from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


class RetentionRunPolicyDocsTest(unittest.TestCase):
    def test_runbook_documents_metadata_snapshots_partial_failure_and_repairable_scheduler_evidence(self) -> None:
        runbook = REPO_ROOT / "docs" / "lifecycle-confidentiality-runbook.md"

        content = runbook.read_text(encoding="utf-8")

        for expected in (
            "metadata-only Retention Run Records",
            "policy snapshot",
            "retention windows",
            "scheduled flags",
            "retry limit",
            "policy hash",
            "partial_failure",
            "Run-level failure",
            "repairable evidence",
            "without hidden automatic retry loops",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, content)


if __name__ == "__main__":
    unittest.main()
