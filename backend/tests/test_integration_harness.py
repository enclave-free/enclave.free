import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "tests" / "run_all_be_tests.py"
AUTH_HARDENING_PATH = (
    REPO_ROOT / "scripts" / "tests" / "AUTH" / "test_3c_auth_hardening_regression.py"
)
INTERNAL_AGENT_CONTRACT_PATH = (
    REPO_ROOT / "scripts" / "tests" / "CONTRACT" / "test_5a_internal_agent_contract.py"
)


def load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class IntegrationHarnessTest(unittest.TestCase):
    def test_docker_database_operations_target_core_backend(self):
        harness = load_script_module("run_all_be_tests", HARNESS_PATH)
        commands: list[str] = []

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with tempfile.NamedTemporaryFile() as backup:
            with patch.object(harness.subprocess, "run", side_effect=fake_run):
                harness.run_docker_cmd("echo ok")
                harness.restore_database(Path(backup.name))

        self.assertIn("exec -T core-backend echo ok", commands[0])
        self.assertIn(" core-backend:/data/enclave.db", commands[1])

    def test_auth_hardening_sqlite_helper_targets_core_backend(self):
        script = load_script_module("test_3c_auth_hardening_regression", AUTH_HARDENING_PATH)
        commands: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

        with patch.object(script.subprocess, "run", side_effect=fake_run):
            script.run_sqlite("SELECT 1", "/data/enclave.db", readonly=True, json_mode=True)

        self.assertEqual(commands[0][:5], ["docker", "compose", "-f", "docker-compose.infra.yml", "-f"])
        self.assertIn("core-backend", commands[0])
        self.assertNotIn("backend", commands[0][commands[0].index("exec") :])

    def test_internal_agent_contract_fixture_sql_does_not_select_dev_mode_column(self):
        source = INTERNAL_AGENT_CONTRACT_PATH.read_text()

        self.assertNotIn("SELECT id, approved, user_type_id, dev_mode FROM users", source)

    def test_auth_hardening_uses_sage_returned_session_id(self):
        source = AUTH_HARDENING_PATH.read_text()

        self.assertIn('created_session_id = create_response.json().get("session_id")', source)
        self.assertIn('f"{api_base}/llm/chat"', source)
        self.assertNotIn('session_id = f"ownership-{uuid.uuid4().hex[:12]}"', source)


if __name__ == "__main__":
    unittest.main()
