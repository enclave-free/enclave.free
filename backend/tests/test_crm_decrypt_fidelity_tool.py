import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/tests/CRM/test_1b_decrypt_fidelity.py"


def load_tool_module():
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("crm_decrypt_fidelity_tool", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CrmDecryptFidelityToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = load_tool_module()

    def test_find_test_user_does_not_fall_back_to_plaintext_email_by_default(self) -> None:
        queries: list[str] = []

        def fake_sql(query: str, db_path: str, **_kwargs) -> str:
            queries.append(query)
            if "ORDER BY id DESC" in query:
                return "42"
            return ""

        with (
            patch.object(self.tool, "compute_blind_index_in_docker", return_value=None),
            patch.object(self.tool, "run_docker_sql", side_effect=fake_sql),
        ):
            user_id = self.tool.find_test_user("/data/enclave.db", "legacy@example.test")

        self.assertEqual(user_id, 42)
        self.assertFalse(any("LOWER(email)" in query for query in queries))

    def test_cli_does_not_expose_legacy_plaintext_lookup_flag(self) -> None:
        result = self.tool.subprocess.run(
            [self.tool.sys.executable, str(SCRIPT), "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--allow-legacy-plaintext-email-lookup", result.stdout)


if __name__ == "__main__":
    unittest.main()
