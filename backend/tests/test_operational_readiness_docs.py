from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


class OperationalReadinessDocsTest(unittest.TestCase):
    def test_monitoring_and_recovery_runbook_covers_alerts_restore_and_drills(self) -> None:
        runbook = REPO_ROOT / "docs" / "operational-monitoring-and-recovery.md"

        self.assertTrue(runbook.exists())
        content = runbook.read_text(encoding="utf-8")

        for expected in (
            "repeated auth failures",
            "unusual Admin actions",
            "destructive endpoint usage",
            "SQLite",
            "deployment config",
            "uploads",
            "Retrieval Index",
            "restore drill",
            "incident response",
            "admin key recovery",
            "drill evidence",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, content)


if __name__ == "__main__":
    unittest.main()
