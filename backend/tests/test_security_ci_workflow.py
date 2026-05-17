from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


class SecurityCiWorkflowTest(unittest.TestCase):
    def test_security_regression_workflow_covers_required_checks(self) -> None:
        workflow = REPO_ROOT / ".github" / "workflows" / "security-regression.yml"

        self.assertTrue(workflow.exists())
        content = workflow.read_text(encoding="utf-8")

        for expected in (
            "backend.tests.test_magic_link_enumeration",
            "backend.tests.test_ingest_batch_replacement",
            "backend.tests.test_query_retrieval_hydration",
            "backend.tests.test_sql_safety",
            "backend.tests.test_rate_limit",
            "backend.tests.test_deployment_config_rate_limits",
            "backend.tests.test_operational_readiness_docs",
            "backend.tests.test_browser_storage_posture_docs",
            "backend.tests.test_retention_run_policy_docs",
            "backend.tests.test_conversation_retention_docs",
            "src/components/chat/ChatMessage.test.tsx",
            "src/pages/AdminDeploymentConfig.test.tsx",
            "src/pages/UserAuth.test.tsx",
            "npm audit",
            "pip-audit",
            "semgrep",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, content)


if __name__ == "__main__":
    unittest.main()
