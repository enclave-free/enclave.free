import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

class _SentenceTransformerStub:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass


class FakeProvider:
    name = "fake-provider"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def health_check(self) -> bool:
        return True

    def complete(self, prompt: str, temperature: float = 0.1) -> Any:
        self.prompts.append(prompt)
        return type(
            "LLMResult",
            (),
            {
                "content": "Config context received.",
                "model": "fake-model",
                "provider": self.name,
            },
        )()


class AdminConfigToolChatTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "sanctum.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sentence_transformers_stub = types.ModuleType("sentence_transformers")
        sentence_transformers_stub.SentenceTransformer = _SentenceTransformerStub
        sys.modules["sentence_transformers"] = sentence_transformers_stub
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import database
        import auth
        import main

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.database.update_setting("instance_name", "Test Sanctum")
        self.database.upsert_deployment_config(
            key="SMTP_HOST",
            value="smtp.example.com",
            category="email",
            description="SMTP server hostname",
        )
        self.database.upsert_deployment_config(
            key="SMTP_PASS",
            value="secret-password",
            is_secret=True,
            category="email",
            description="SMTP password",
        )

        self.provider = FakeProvider()
        self.main.get_sage_provider = lambda: self.provider
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        if self._orig_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._orig_sentence_transformers
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_admin_chat_executes_admin_config_tool(self) -> None:
        response = self.client.post(
            "/llm/chat",
            json={
                "message": "What is this instance called?",
                "tools": ["admin-config"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["tools_used"],
            [
                {
                    "tool_id": "admin-config",
                    "tool_name": "admin-config",
                    "query": "What is this instance called?",
                }
            ],
        )
        self.assertTrue(self.provider.prompts)
        self.assertIn("SCOPED CONFIG CONTEXT", self.provider.prompts[0])
        self.assertIn("instance_name", self.provider.prompts[0])
        self.assertIn("Test Sanctum", self.provider.prompts[0])

    def test_user_chat_cannot_execute_admin_config_tool(self) -> None:
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "user-pubkey",
            "id": 1,
        }

        response = self.client.post(
            "/llm/chat",
            json={
                "message": "What is this instance called?",
                "tools": ["admin-config"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tools_used"], [])
        self.assertTrue(self.provider.prompts)
        self.assertNotIn("SCOPED CONFIG CONTEXT", self.provider.prompts[-1])
        self.assertNotIn("Test Sanctum", self.provider.prompts[-1])

    def test_admin_config_tool_scopes_deployment_settings_for_email_questions(self) -> None:
        response = self.client.post(
            "/llm/chat",
            json={
                "message": "Check my SMTP email deployment settings",
                "tools": ["admin-config"],
            },
        )

        self.assertEqual(response.status_code, 200)
        prompt = self.provider.prompts[-1]
        self.assertIn("scope: deployment-settings", prompt)
        self.assertIn("DEPLOYMENT SETTINGS", prompt)
        self.assertIn("SMTP_HOST", prompt)
        self.assertIn("smtp.example.com", prompt)
        self.assertIn("SMTP_PASS", prompt)
        self.assertIn("********", prompt)
        self.assertNotIn("secret-password", prompt)


if __name__ == "__main__":
    unittest.main()
