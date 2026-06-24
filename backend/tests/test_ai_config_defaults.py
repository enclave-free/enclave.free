from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class AIConfigDefaultsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        os.environ["SQLITE_PATH"] = str(self.db_path)

        import database

        self.database = importlib.reload(database)
        self.database.init_schema()

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        if self._orig_sqlite_path is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = self._orig_sqlite_path
        self.tmp.cleanup()

    def test_default_agent_settings_bias_admin_configuration_toward_action(self) -> None:
        prompt_system = self.database.get_ai_config("prompt_system")
        prompt_rules = self.database.get_ai_config("prompt_rules")

        self.assertIsNotNone(prompt_system)
        self.assertIsNotNone(prompt_rules)

        system_value = prompt_system["value"]
        rules_value = json.loads(prompt_rules["value"])

        self.assertIn("Admin Conversations", system_value)
        self.assertIn("first-party context", system_value)
        self.assertIn("reasonable defaults", system_value)
        self.assertIn("Change Confirmation", system_value)
        self.assertTrue(any("group related" in rule for rule in rules_value))
        self.assertTrue(any("propose_config_change_set" in rule for rule in rules_value))
        self.assertTrue(any("PUT /admin/deployment/config/{key}" in rule for rule in rules_value))
        self.assertTrue(any("PUT /admin/ai-config/prompt_rules" in rule for rule in rules_value))
        self.assertTrue(any("PUT /admin/ai-config/prompt_forbidden" in rule for rule in rules_value))
        self.assertTrue(any("/ingest/admin/documents/..." in rule for rule in rules_value))
        self.assertTrue(any("do not surface them merely because a topic matches" in rule for rule in rules_value))
        self.assertFalse(any(rule == "ONE action per response when providing step-by-step guidance" for rule in rules_value))


if __name__ == "__main__":
    unittest.main()
