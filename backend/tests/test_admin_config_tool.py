import asyncio
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class AdminConfigToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"

        import database
        from tools.admin_config import AdminConfigTool

        self.database = importlib.reload(database)
        self.database.init_schema()
        self.tool = AdminConfigTool()

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def _admin_config_context(self, query: str) -> str:
        result = asyncio.run(self.tool.execute(query=query))
        self.assertTrue(result.success)
        return self.tool.format_result(result)

    def test_admin_config_overview_lists_admin_visible_tool_capabilities(self) -> None:
        context = self._admin_config_context("what tools do you have?")

        self.assertIn("ADMIN-VISIBLE TOOL CAPABILITIES", context)
        self.assertIn("web-search", context)
        self.assertIn("admin-config", context)
        self.assertIn("db-query", context)
        self.assertIn("safe read-only", context)
        self.assertNotIn("knowledge_search", context)

    def test_theme_requests_use_instance_visual_identity_context(self) -> None:
        context = self._admin_config_context("update all theme configurations for this instance")

        self.assertIn("scope: instance-settings", context)
        self.assertIn("INSTANCE VISUAL IDENTITY SETTINGS", context)
        self.assertIn("default_theme", context)
        self.assertIn("primary_color", context)
        self.assertIn("chat_bubble_style", context)
        self.assertIn("chat_bubble_shadow", context)
        self.assertIn("surface_style", context)
        self.assertIn("status_icon_set", context)
        self.assertIn("typography_preset", context)
        self.assertIn("valid values: system, light, dark", context)

    def test_visual_identity_context_includes_confirmed_change_set_contract(self) -> None:
        context = self._admin_config_context("make the theme dark and the visual identity minimal")

        self.assertIn("CHANGESET FORMAT", context)
        self.assertIn('"method": "PUT"', context)
        self.assertIn('"path": "/admin/settings"', context)
        self.assertIn('"default_theme": "dark"', context)
        self.assertIn("Change Confirmation", context)
        self.assertIn("valid JSON change set", context)
        self.assertNotIn("/admin/settings/default_theme", context)

    def test_agent_behavior_requests_use_agent_settings_context(self) -> None:
        context = self._admin_config_context("change the admin prompt and max tokens")

        self.assertIn("scope: agent-settings", context)
        self.assertIn("AGENT SETTINGS", context)
        self.assertIn("prompt", context)
        self.assertIn("max tokens", context)

    def test_deployment_requests_still_use_deployment_settings_context(self) -> None:
        context = self._admin_config_context("change the model provider and restart settings")

        self.assertIn("scope: deployment-settings", context)
        self.assertIn("DEPLOYMENT SETTINGS", context)

    def test_tool_definitions_include_examples_and_expanded_descriptions(self) -> None:
        result = asyncio.run(self.tool.execute(query="what tools do you have?"))

        self.assertTrue(result.success)
        tools = result.data["tool_capabilities"]
        self.assertIsInstance(tools, (list, tuple))
        self.assertGreaterEqual(len(tools), 3)

        tool_ids = {tool["id"] for tool in tools}
        self.assertSetEqual(tool_ids, {"web-search", "admin-config", "db-query"})

        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("access", tool)
            self.assertIn("examples", tool)
            examples = tool["examples"]
            self.assertIsInstance(examples, (list, tuple))
            self.assertGreaterEqual(len(examples), 2, f"Tool {tool['id']} should have at least 2 examples")
            for example in examples:
                self.assertIsInstance(example, str)
                self.assertGreater(len(example), 0)

    def test_ambiguous_query_returns_error_with_available_scopes(self) -> None:
        result = asyncio.run(self.tool.execute(query="how do I set up the system?"))

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("available_scopes", result.data)
        available = result.data["available_scopes"]
        self.assertIsInstance(available, (list, tuple))
        self.assertGreater(len(available), 0)
        for scope_entry in available:
            self.assertIn("id", scope_entry)
            self.assertIn("description", scope_entry)

    def test_ambiguous_user_configuration_query_returns_error(self) -> None:
        result = asyncio.run(self.tool.execute(query="tell me about the configuration"))

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIsInstance(result.data.get("available_scopes"), (list, tuple))

    def test_clear_queries_still_succeed(self) -> None:
        clear_queries = [
            "Show me SMTP settings",
            "Help me create a user type with private fields",
            "change the admin prompt and max tokens",
            "update all theme configurations for this instance",
        ]
        for query in clear_queries:
            with self.subTest(query=query):
                result = asyncio.run(self.tool.execute(query=query))
                self.assertTrue(
                    result.success,
                    f"Expected success for query: {query}, got error: {result.error}",
                )
                self.assertIsNone(result.error)

    def test_db_query_tool_includes_available_tables(self) -> None:
        result = asyncio.run(self.tool.execute(query="what tools do you have?"))

        self.assertTrue(result.success)
        tools = result.data["tool_capabilities"]
        db_query_tool = next(tool for tool in tools if tool["id"] == "db-query")
        self.assertIn("available_tables", db_query_tool)
        available_tables = db_query_tool["available_tables"]
        self.assertIsInstance(available_tables, (list, tuple))
        self.assertGreaterEqual(len(available_tables), 4)

        table_names = {table["name"] for table in available_tables}
        expected_tables = {"users", "user_types", "user_field_definitions", "user_field_values", "instance_settings", "admins"}
        self.assertSetEqual(table_names, expected_tables)

    def test_db_query_available_tables_have_descriptions_and_key_columns(self) -> None:
        result = asyncio.run(self.tool.execute(query="what tools do you have?"))

        tools = result.data["tool_capabilities"]
        db_query_tool = next(tool for tool in tools if tool["id"] == "db-query")

        for table in db_query_tool["available_tables"]:
            with self.subTest(table=table["name"]):
                self.assertIn("name", table)
                self.assertIn("description", table)
                self.assertIn("key_columns", table)
                self.assertIsInstance(table["description"], str)
                self.assertGreater(len(table["description"]), 0)
                self.assertIsInstance(table["key_columns"], (list, tuple))
                self.assertGreaterEqual(len(table["key_columns"]), 2)

    def test_db_query_schema_key_columns_include_important_fields(self) -> None:
        result = asyncio.run(self.tool.execute(query="what tools do you have?"))

        tools = result.data["tool_capabilities"]
        db_query_tool = next(tool for tool in tools if tool["id"] == "db-query")

        tables_by_name = {table["name"]: table["key_columns"] for table in db_query_tool["available_tables"]}

        self.assertIn("user_type_id", tables_by_name.get("users", []))
        self.assertIn("approved", tables_by_name.get("users", []))
        self.assertIn("encryption_enabled", tables_by_name.get("user_field_definitions", []))
        self.assertIn("user_type_id", tables_by_name.get("user_field_definitions", []))


if __name__ == "__main__":
    unittest.main()
