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
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }

    def test_chat_response_includes_backend_message_id_and_minimal_user_trace(self) -> None:
        self.authenticate_as_user()

        response = self.client.post(
            "/llm/chat",
            json={"message": "Can you help?", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["message_id"].startswith("msg_"))
        self.assertEqual(body["trace"]["visibility"], "minimal")
        self.assertEqual(body["trace"]["reasoning"]["summary"], "Sage answered from the conversation context and configured instructions.")
        self.assertEqual(body["trace"]["tools"], [])
        self.assertEqual(body["trace"]["retrieval"], [])

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

    def test_trace_policy_off_omits_trace_from_future_chat_turns(self) -> None:
        self.authenticate_as_user()
        self.assertTrue(
            self.database.update_ai_config(
                "user_trace_visibility",
                "off",
                changed_by="admin-pubkey",
            )
        )

        response = self.client.post(
            "/llm/chat",
            json={"message": "Can you help?", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["trace"])

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

    def test_retrieval_session_history_persists_assistant_trace(self) -> None:
        self.authenticate_as_user()
        self.stub_retrieval_query()
        session_id = "trace-session"

        query_response = self.client.post(
            "/query",
            json={"question": "What does the policy say?", "session_id": session_id},
        )
        response = self.client.get(f"/query/session/{session_id}")

        self.assertEqual(query_response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        messages = response.json()["messages"]
        self.assertEqual(messages[-1]["id"], query_response.json()["message_id"])
        self.assertEqual(messages[-1]["trace"], query_response.json()["trace"])

    def test_deleted_retrieval_session_no_longer_exposes_persisted_trace(self) -> None:
        import query

        self.authenticate_as_user()
        self.stub_retrieval_query()
        session_id = "delete-trace-session"

        create_response = self.client.post(
            "/query",
            json={"question": "What does the policy say?", "session_id": session_id},
        )

        delete_response = self.client.delete(f"/query/session/{session_id}")
        get_response = self.client.get(f"/query/session/{session_id}")

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(get_response.status_code, 404)
        self.assertNotIn(session_id, query._sessions)

    def test_streaming_chat_emits_message_delta_trace_and_done_events(self) -> None:
        self.authenticate_as_user()

        with self.client.stream(
            "POST",
            "/llm/chat/stream",
            json={"message": "Can you help?", "tools": []},
        ) as response:
            self.assertEqual(response.status_code, 200)
            body = "".join(response.iter_text())

        self.assertIn("event: assistant_message_started", body)
        self.assertIn("event: answer_delta", body)
        self.assertIn("event: trace_final", body)
        self.assertIn("event: done", body)
        self.assertIn('"message_id":"msg_', body)
        self.assertIn('"visibility":"minimal"', body)

    def stub_retrieval_query(self) -> None:
        import query

        class FakeSearchResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {
                    "result": [
                        {
                            "score": 0.82,
                            "payload": {
                                "type": "chunk",
                                "chunk_id": "chunk-1",
                                "job_id": "job-1",
                                "source_file": "Policy.pdf",
                                "text": "Policy context",
                            },
                        }
                    ]
                }

        query.embed_texts = lambda _texts: [[0.1, 0.2, 0.3]]
        query.httpx.post = lambda *_args, **_kwargs: FakeSearchResponse()
        query._call_llm_contextual = lambda *_args, **_kwargs: (
            "The policy says yes.",
            [],
            "=== PROMPT ===\nredacted",
            None,
        )
        query._extract_facts_from_conversation = lambda _session: {}
