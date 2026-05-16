import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class LifecycleCopyGuardrailsTest(unittest.TestCase):
    def test_product_copy_does_not_overclaim_deletion_guarantees(self) -> None:
        checked_paths = [
            REPO_ROOT / "frontend/src/pages/AdminDeploymentConfig.tsx",
            REPO_ROOT / "frontend/src/pages/AdminDocumentUpload.tsx",
            REPO_ROOT / "frontend/src/i18n/locales/en.json",
            REPO_ROOT / "docs/sessions.md",
            REPO_ROOT / "docs/security.md",
            REPO_ROOT / "docs/internal-agent-contract.md",
            REPO_ROOT / "docs/security-data-protection-checklist.md",
            REPO_ROOT / "docs/lifecycle-confidentiality-runbook.md",
            REPO_ROOT / "docs/adr/0006-retention-and-deletion-are-operator-controlled-but-incomplete.md",
            REPO_ROOT / "docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md",
        ]
        forbidden_phrases = [
            "permanently delete",
            "permanently remove",
            "delete forever",
            "deleted forever",
        ]

        violations = []
        for path in checked_paths:
            text = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden_phrases:
                if phrase in text:
                    violations.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")

        self.assertEqual(violations, [])

    def test_lifecycle_docs_name_active_storage_and_unsupported_surfaces(self) -> None:
        sessions = (REPO_ROOT / "docs/sessions.md").read_text(encoding="utf-8")
        adr = (
            REPO_ROOT
            / "docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md"
        ).read_text(encoding="utf-8")

        self.assertIn("logical active-storage deletion", adr)
        self.assertIn("not a Secure Erase guarantee", adr)
        self.assertIn("WAL, backups, snapshots, logs", adr)
        self.assertIn("Deletion Tombstone", adr)
        self.assertIn("scheduled retention for every historical Session Memory or log surface is still not implemented", sessions)

    def test_lifecycle_confidentiality_runbook_covers_regression_and_scheduler_paths(self) -> None:
        runbook = (REPO_ROOT / "docs/lifecycle-confidentiality-runbook.md").read_text(encoding="utf-8")

        for expected in [
            "Issue #57",
            "Issues #58-#67",
            "RETENTION_AUTOMATION_TOKEN",
            "X-Retention-Automation-Token",
            "/admin/lifecycle/retention/scheduled/automation/run",
            "external cron",
            "unsupported Deployment Surfaces",
            "Secure Erase",
            "backend.tests.test_ingest_batch_replacement",
            "backend.tests.test_query_retrieval_hydration",
            "backend.tests.test_lifecycle_status",
            "npm test -- --run src/pages/AdminDeploymentConfig.test.tsx",
            "/admin/lifecycle/confidentiality-migration/preview",
            "/admin/lifecycle/confidentiality-migration/execute",
        ]:
            self.assertIn(expected, runbook)


if __name__ == "__main__":
    unittest.main()
