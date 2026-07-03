import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class AIConfigMaxTokensTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"

        import database
        import auth
        import ai_config

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.ai_config = importlib.reload(ai_config)
        self.database.init_schema()

        app = FastAPI()
        app.include_router(self.ai_config.router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(app)

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

    def test_max_tokens_is_seeded_as_agent_setting(self) -> None:
        response = self.client.get("/admin/ai-config")

        self.assertEqual(response.status_code, 200)
        parameters = response.json()["parameters"]
        max_tokens = next(item for item in parameters if item["key"] == "max_tokens")
        self.assertEqual(max_tokens["value"], "2048")
        self.assertEqual(max_tokens["value_type"], "number")

    def test_user_conversation_defaults_are_seeded_as_agent_settings(self) -> None:
        response = self.client.get("/admin/ai-config")

        self.assertEqual(response.status_code, 200)
        defaults = response.json()["defaults"]
        by_key = {item["key"]: item for item in defaults}

        self.assertEqual(by_key["user_default_tool_ids"]["value"], "[]")
        self.assertEqual(by_key["user_default_tool_ids"]["value_type"], "json")
        self.assertEqual(by_key["knowledge_source_default"]["value"], "none")
        self.assertEqual(by_key["knowledge_source_default"]["value_type"], "string")

    def test_user_default_tool_ids_rejects_admin_only_tools(self) -> None:
        response = self.client.put(
            "/admin/ai-config/user_default_tool_ids",
            json={"value": '["curated-resources", "admin-config"]'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("user_default_tool_ids", response.json()["detail"])

    def test_knowledge_source_default_accepts_supported_values(self) -> None:
        response = self.client.put(
            "/admin/ai-config/knowledge_source_default",
            json={"value": "ALL"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], "all")

    def test_knowledge_source_default_rejects_unknown_values(self) -> None:
        response = self.client.put(
            "/admin/ai-config/knowledge_source_default",
            json={"value": "everything"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Knowledge source default must be one of", response.json()["detail"])

    def test_max_tokens_rejects_values_outside_supported_range(self) -> None:
        response = self.client.put(
            "/admin/ai-config/max_tokens",
            json={"value": "128"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Max tokens must be between 256 and 8192")

    def test_max_tokens_accepts_supported_boundaries(self) -> None:
        for value in ("256", "8192"):
            with self.subTest(value=value):
                response = self.client.put(
                    "/admin/ai-config/max_tokens",
                    json={"value": value},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["key"], "max_tokens")
                self.assertEqual(response.json()["value"], value)

                get_response = self.client.get("/admin/ai-config")
                self.assertEqual(get_response.status_code, 200)
                parameters = get_response.json()["parameters"]
                max_tokens = next(item for item in parameters if item["key"] == "max_tokens")
                self.assertEqual(max_tokens["value"], value)

    def test_llm_parameters_preserve_whole_numbers_as_ints(self) -> None:
        self.client.put(
            "/admin/ai-config/max_tokens",
            json={"value": "2048"},
        )

        params = self.ai_config.get_llm_parameters()

        self.assertEqual(params["max_tokens"], 2048)
        self.assertIsInstance(params["max_tokens"], int)

    def test_max_tokens_rejects_non_integer_values(self) -> None:
        response = self.client.put(
            "/admin/ai-config/max_tokens",
            json={"value": "not-an-int"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid value for type 'number'")


if __name__ == "__main__":
    unittest.main()
