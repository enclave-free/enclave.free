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
        self.assertIn("scheduled retention depends on an external Retention Scheduler", sessions)
        self.assertIn("unsupported Deployment Surfaces", sessions)

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

    def test_active_storage_lifecycle_docs_cover_scheduler_evidence_boundaries(self) -> None:
        runbook = (REPO_ROOT / "docs/lifecycle-confidentiality-runbook.md").read_text(encoding="utf-8")

        for expected in [
            "Retention Run Records",
            "Retention Scheduler Observation",
            "disabled, never observed, healthy, stale, or failing",
            "external scheduler",
            "metadata-only",
            "Audit Log evidence",
            "docs/adr/0015-external-retention-scheduler-with-product-owned-run-records.md",
        ]:
            self.assertIn(expected, runbook)

    def test_active_storage_lifecycle_docs_name_not_scheduled_deletion_boundaries(self) -> None:
        runbook = (REPO_ROOT / "docs/lifecycle-confidentiality-runbook.md").read_text(encoding="utf-8")

        for expected in [
            "Inference Verification Records remain indefinitely retained",
            "separate evidence-retention policy",
            "active User Profiles",
            "current Document Library records",
            "current Retrieval Index entries",
            "not scheduled for deletion in this milestone",
            "docs/adr/0006-retention-and-deletion-are-operator-controlled-but-incomplete.md",
            "docs/adr/0007-audit-log-is-a-product-boundary-but-coverage-is-partial.md",
        ]:
            self.assertIn(expected, runbook)

    def test_operator_docs_align_with_active_storage_lifecycle_milestone(self) -> None:
        admin_doc = (REPO_ROOT / "docs/admin-deployment-config.md").read_text(encoding="utf-8")
        checklist = (REPO_ROOT / "docs/security-data-protection-checklist.md").read_text(encoding="utf-8")
        security = (REPO_ROOT / "docs/security.md").read_text(encoding="utf-8")
        sessions = (REPO_ROOT / "docs/sessions.md").read_text(encoding="utf-8")

        for text in (admin_doc, checklist, security, sessions):
            self.assertIn("Active Storage Lifecycle", text)

        for expected in [
            "Retention Run Records",
            "Retention Scheduler Observation",
            "external Retention Scheduler",
            "Inference Verification Records remain indefinitely retained",
            "current Document Library records",
            "current Retrieval Index entries",
            "logs, WAL files, backups, snapshots, browser caches, copied exports, and provider traces",
        ]:
            self.assertIn(expected, admin_doc + checklist + security + sessions)


if __name__ == "__main__":
    unittest.main()
