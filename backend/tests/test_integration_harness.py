import importlib.util
import subprocess
import sys
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
CRM_HELPERS_PATH = REPO_ROOT / "scripts" / "tests" / "CRM" / "test_helpers.py"
KEY_MIGRATION_EXECUTE_PATH = (
    REPO_ROOT / "scripts" / "tests" / "AUTH" / "test_3b_key_migration_execute.py"
)
PHASE3_CONFIG_PATH = (
    REPO_ROOT / "scripts" / "tests" / "AUTH" / "test_3d_phase3_config_integrity.py"
)
RAG_PERSISTENCE_PATH = (
    REPO_ROOT / "scripts" / "tests" / "RAG" / "test_2a_document_persistence.py"
)
DECRYPT_FIDELITY_PATH = (
    REPO_ROOT / "scripts" / "tests" / "CRM" / "test_1b_decrypt_fidelity.py"
)
KEY_MIGRATION_APP_PATH = REPO_ROOT / "backend" / "app" / "key_migration.py"
TOOLS_PARITY_PATH = (
    REPO_ROOT / "scripts" / "tests" / "TOOLS" / "test_4a_unified_chat_tools_parity.py"
)
STREAM_TRANSPORT_PATH = (
    REPO_ROOT / "scripts" / "tests" / "TOOLS" / "test_5c_chat_streaming_transport.py"
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
            rendered = (
                " ".join(str(part) for part in cmd)
                if isinstance(cmd, list)
                else str(cmd)
            )
            commands.append(rendered)
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

    def test_legacy_integration_sqlite_helpers_target_core_backend(self):
        for path in (CRM_HELPERS_PATH, KEY_MIGRATION_EXECUTE_PATH, PHASE3_CONFIG_PATH):
            source = path.read_text()
            self.assertIn("core-backend", source, str(path))
            self.assertNotIn('"backend", "sqlite3"', source, str(path))

    def test_runner_creates_harness_admin_token_for_token_aware_tests(self):
        source = HARNESS_PATH.read_text()

        self.assertIn("def create_harness_admin_token", source)
        self.assertIn("def script_accepts_token_argument", source)
        self.assertIn("harness_token = create_harness_admin_token()", source)
        self.assertIn('test_extra_args.extend(["--token", harness_token])', source)

    def test_rag_persistence_has_builtin_pdf_fallback(self):
        source = RAG_PERSISTENCE_PATH.read_text()

        self.assertIn("if not REPORTLAB_AVAILABLE:", source)
        self.assertIn("Path(output_path).write_bytes", source)
        self.assertNotIn("reportlab required", source)

    def test_rag_persistence_uses_auth_and_core_backend_for_status_and_cleanup(self):
        source = RAG_PERSISTENCE_PATH.read_text()

        self.assertIn('headers["Authorization"] = f"Bearer {token}"', source)
        self.assertIn("wait_for_job_completion(api_base, job_id, timeout=180, token=token)", source)
        self.assertIn('CORE_BACKEND_SERVICE = "core-backend"', source)
        self.assertNotIn('"backend", "sqlite3"', source)

    def test_decrypt_fidelity_parses_json_sql_ids_from_helper(self):
        sys.path.insert(0, str(DECRYPT_FIDELITY_PATH.parent))
        try:
            script = load_script_module("test_1b_decrypt_fidelity", DECRYPT_FIDELITY_PATH)
        finally:
            sys.path.remove(str(DECRYPT_FIDELITY_PATH.parent))

        self.assertEqual(script.first_id_from_sql_output('[{"id":1}]'), 1)
        self.assertIsNone(script.first_id_from_sql_output("[]"))

    def test_runner_only_passes_tokens_to_token_aware_scripts(self):
        harness = load_script_module("run_all_be_tests", HARNESS_PATH)

        self.assertTrue(harness.script_accepts_token_argument(TOOLS_PARITY_PATH))
        self.assertFalse(harness.script_accepts_token_argument(STREAM_TRANSPORT_PATH))

    def test_key_migration_preserves_config_audit_hash_chain(self):
        source = KEY_MIGRATION_APP_PATH.read_text()

        self.assertIn("database._insert_config_audit_log", source)
        self.assertNotIn("INSERT INTO config_audit_log", source)

    def test_tools_parity_does_not_expect_disabled_web_search_reporting(self):
        source = TOOLS_PARITY_PATH.read_text()

        self.assertIn('expected = ["db-query"]', source)
        self.assertNotIn('expected = ["db-query", "web-search"]', source)


if __name__ == "__main__":
    unittest.main()
