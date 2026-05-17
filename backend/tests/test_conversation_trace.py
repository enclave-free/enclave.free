import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
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
                "content": "Traceable response.",
                "model": "fake-model",
                "provider": self.name,
            },
        )()


class ConversationTraceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer,
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_llm_provider = os.environ.get("LLM_PROVIDER")
        self._orig_llm_api_url = os.environ.get("LLM_API_URL")
        self._orig_llm_model = os.environ.get("LLM_MODEL")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        os.environ["LLM_PROVIDER"] = "sage"
        os.environ["LLM_API_URL"] = ""
        os.environ["LLM_MODEL"] = ""

        import database
        import auth
        import ai_config
        import deployment_config
        import protected_inference
        import query
        import main

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.ai_config = importlib.reload(ai_config)
        self.deployment_config = importlib.reload(deployment_config)
        self.protected_inference = importlib.reload(protected_inference)
        self.query = importlib.reload(query)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self._create_current_inference_verification_record()

        self.provider = FakeProvider()
        self.main.get_sage_provider = lambda: self.provider
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("LLM_PROVIDER", self._orig_llm_provider)
        self._restore_env("LLM_API_URL", self._orig_llm_api_url)
        self._restore_env("LLM_MODEL", self._orig_llm_model)
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

    def _create_current_inference_verification_record(self) -> None:
        now = datetime.now(timezone.utc)
        self.database.create_inference_verification_record(
            provider_identity="sage",
            provider_endpoint="",
            model_identifier="",
            status="success",
            trigger="test",
            expected_claims_fingerprint=self.protected_inference.DEFAULT_EXPECTED_CLAIMS_FINGERPRINT,
            actual_claims_fingerprint=self.protected_inference.DEFAULT_EXPECTED_CLAIMS_FINGERPRINT,
            verifier_version="test",
            checked_at=now,
            expires_at=now + timedelta(hours=1),
        )

    def authenticate_as_user(self) -> None:
        self.user_id = self.database.create_user(pubkey="a" * 64)
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "a" * 64,
            "id": self.user_id,
        }

    def authenticate_as_admin(self) -> None:
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.ai_config.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.deployment_config.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }

    def test_trace_visibility_policy_is_seeded_as_agent_settings(self) -> None:
        self.authenticate_as_admin()

        response = self.client.get("/admin/ai-config")

        self.assertEqual(response.status_code, 200)
        defaults = {item["key"]: item["value"] for item in response.json()["defaults"]}
        self.assertEqual(defaults["admin_trace_visibility"], "detailed")
        self.assertEqual(defaults["user_trace_visibility"], "minimal")

    def test_user_trace_visibility_rejects_detailed(self) -> None:
        self.authenticate_as_admin()

        response = self.client.put(
            "/admin/ai-config/user_trace_visibility",
            json={"value": "detailed"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("User Conversation trace visibility", response.json()["detail"])

    def test_trace_visibility_policy_changes_are_audited(self) -> None:
        self.authenticate_as_admin()

        response = self.client.put(
            "/admin/ai-config/user_trace_visibility",
            json={"value": "summary"},
        )

        self.assertEqual(response.status_code, 200)
        entries = self.database.get_config_audit_log(limit=10, table_name="ai_config")
        self.assertTrue(any(
            entry["config_key"] == "user_trace_visibility"
            and entry["old_value"] == "minimal"
            and entry["new_value"] == "summary"
            for entry in entries
        ))

    def test_db_query_trace_redacts_raw_sql_literals_and_results(self) -> None:
        from conversation_trace import build_conversation_trace
        from tools import ToolCallInfo

        trace = build_conversation_trace(
            actor_type="admin",
            tools_used=[
                ToolCallInfo(
                    tool_id="db-query",
                    tool_name="Database",
                    query="SELECT email FROM users WHERE email = 'alice@example.com'",
                )
            ],
        )

        self.assertIsNotNone(trace)
        body = trace.model_dump()
        self.assertEqual(body["visibility"], "detailed")
        self.assertEqual(body["tools"][0]["id"], "db-query")
        self.assertEqual(body["tools"][0]["input_summary"], "SELECT email FROM users WHERE email = '[redacted]'")
        self.assertEqual(body["tools"][0]["output_summary"], "Database results were redacted from the trace.")
        self.assertIn("raw_results_redacted", body["tools"][0]["warnings"])
        serialized = str(body)
        self.assertNotIn("alice@example.com", serialized)

    def test_db_query_trace_includes_safe_read_only_metadata(self) -> None:
        from conversation_trace import build_conversation_trace
        from tools import ToolCallInfo

        trace = build_conversation_trace(
            actor_type="admin",
            tools_used=[
                ToolCallInfo(
                    tool_id="db-query",
                    tool_name="Database",
                    query="SELECT id, email FROM users WHERE email = 'alice@example.com' LIMIT 5",
                )
            ],
        )

        self.assertIsNotNone(trace)
        tool = trace.model_dump()["tools"][0]
        self.assertEqual(tool["status"], "success")
        self.assertEqual(tool["execution"], "server")
        self.assertEqual(tool["metadata"]["statement_type"], "select")
        self.assertTrue(tool["metadata"]["read_only"])
        self.assertEqual(tool["metadata"]["selected_columns"], ["id", "email"])
        self.assertEqual(tool["metadata"]["limit"], 5)
        serialized = str(tool)
        self.assertNotIn("alice@example.com", serialized)

    def test_db_query_trace_marks_non_read_only_sql_without_results(self) -> None:
        from conversation_trace import build_conversation_trace
        from tools import ToolCallInfo

        trace = build_conversation_trace(
            actor_type="admin",
            tools_used=[
                ToolCallInfo(
                    tool_id="db-query",
                    tool_name="Database",
                    query="DELETE FROM users WHERE email = 'alice@example.com'",
                )
            ],
        )

        self.assertIsNotNone(trace)
        tool = trace.model_dump()["tools"][0]
        self.assertEqual(tool["metadata"]["statement_type"], "delete")
        self.assertFalse(tool["metadata"]["read_only"])
        self.assertIn("non_read_only_sql", tool["warnings"])
        self.assertEqual(tool["output_summary"], "Database results were redacted from the trace.")
        self.assertNotIn("alice@example.com", str(tool))

    def test_trace_redaction_failure_suppresses_trace_and_audits_without_secret(self) -> None:
        from conversation_trace import build_conversation_trace
        from tools import ToolCallInfo

        trace = build_conversation_trace(
            actor_type="admin",
            tools_used=[
                ToolCallInfo(
                    tool_id="web-search",
                    tool_name="Web search",
                    query="Find docs with SECRET_KEY=super-secret-value",
                )
            ],
        )

        self.assertIsNotNone(trace)
        self.assertTrue(trace.suppressed)
        self.assertEqual(trace.tools, [])
        entries = self.database.get_config_audit_log(limit=10, table_name="conversation_trace")
        self.assertEqual(entries[0]["config_key"], "redaction_failure")
        serialized = str(entries)
        self.assertIn("trace_suppressed", serialized)
        self.assertNotIn("super-secret-value", serialized)

    def test_trace_redaction_failure_audit_is_visible_to_admin_audit_api(self) -> None:
        from conversation_trace import build_conversation_trace
        from tools import ToolCallInfo

        self.authenticate_as_admin()

        build_conversation_trace(
            actor_type="admin",
            tools_used=[
                ToolCallInfo(
                    tool_id="web-search",
                    tool_name="Web search",
                    query="Find docs with LLM_API_KEY=super-secret-value",
                )
            ],
        )
        response = self.client.get("/admin/deployment/audit-log?table_name=conversation_trace")

        self.assertEqual(response.status_code, 200)
        entries = response.json()["entries"]
        self.assertEqual(entries[0]["table_name"], "conversation_trace")
        self.assertEqual(entries[0]["config_key"], "redaction_failure")
        serialized = str(entries)
        self.assertIn("trace_suppressed", serialized)
        self.assertNotIn("super-secret-value", serialized)
