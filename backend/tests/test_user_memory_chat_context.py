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


sys.modules.setdefault(
    "sentence_transformers",
    types.SimpleNamespace(SentenceTransformer=DummySentenceTransformer),
)


class FakeProvider:
    name = "fake-provider"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.extractor_payload: str = (
            '{"memories":[{"kind":"preference","content":"Prefers concise answers.",'
            '"importance":4,"confidence":0.8}]}'
        )
        self.fail_extractor = False

    def health_check(self) -> bool:
        return True

    def complete(self, prompt: str, temperature: float = 0.1) -> Any:
        self.prompts.append(prompt)
        if "=== USER MEMORY EXTRACTION ===" in prompt:
            if self.fail_extractor:
                raise RuntimeError("extractor unavailable")
            content = self.extractor_payload
        else:
            content = "User context received."
        return type(
            "LLMResult",
            (),
            {
                "content": content,
                "model": "fake-model",
                "provider": self.name,
            },
        )()


class UserMemoryChatContextTest(unittest.TestCase):
    def setUp(self) -> None:
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

        self.user_id = self.database.create_user(pubkey="a" * 64)
        self.database.create_field_definition(
            field_name="preferred_language",
            field_type="text",
            encryption_enabled=False,
            include_in_chat=True,
        )
        self.database.set_user_field(self.user_id, "preferred_language", "Spanish")
        self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers concise answers.",
            importance=7,
            confidence=0.85,
            source_kind="conversation",
            source_conversation_id="conv-123",
            author_actor="sage",
        )
        self.database.update_setting("ambient_user_memory_capture_enabled", "true")

        self.provider = FakeProvider()
        self.main.get_sage_provider = lambda: self.provider
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "a" * 64,
            "id": self.user_id,
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
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_user_conversation_loads_user_memory_separately_from_user_profile(self) -> None:
        response = self.client.post(
            "/llm/chat",
            json={"message": "How should we proceed?", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        prompt = self.provider.prompts[-1]
        self.assertIn("=== USER PROFILE ===", prompt)
        self.assertIn("- preferred_language: Spanish", prompt)
        self.assertIn("=== USER MEMORY ===", prompt)
        self.assertIn("- preference: Prefers concise answers. (importance: 7, confidence: 0.85)", prompt)
        self.assertLess(prompt.index("=== USER PROFILE ==="), prompt.index("=== USER MEMORY ==="))

    def test_user_conversation_without_user_memory_still_responds(self) -> None:
        user_without_memory_id = self.database.create_user(pubkey="b" * 64)
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "b" * 64,
            "id": user_without_memory_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "Can you help?", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        prompt = self.provider.prompts[-1]
        self.assertNotIn("=== USER MEMORY ===", prompt)
        self.assertIn("=== QUESTION ===", prompt)

    def test_deleted_user_data_does_not_enter_conversation_context(self) -> None:
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.auth.require_admin_or_user] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        delete_response = self.client.delete(f"/users/{self.user_id}")
        self.assertEqual(delete_response.status_code, 200)

        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "a" * 64,
            "id": self.user_id,
        }
        response = self.client.post(
            "/llm/chat",
            json={"message": "How should we proceed?", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        prompt = self.provider.prompts[-1]
        self.assertNotIn("=== USER PROFILE ===", prompt)
        self.assertNotIn("preferred_language", prompt)
        self.assertNotIn("=== USER MEMORY ===", prompt)
        self.assertNotIn("Prefers concise answers.", prompt)

    def test_user_conversation_uses_bounded_user_memory_retrieval(self) -> None:
        for index in range(25):
            self.database.create_user_memory(
                subject_user_id=self.user_id,
                kind="preference",
                content=f"Memory {index}",
                importance=min(index, 10),
                source_kind="conversation",
                author_actor="sage",
            )

        response = self.client.post(
            "/llm/chat",
            json={"message": "What context do you have?", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        prompt = self.provider.prompts[-1]
        memory_lines = [
            line for line in prompt.splitlines()
            if line.startswith("- preference:")
        ]
        self.assertEqual(len(memory_lines), 20)
        self.assertIn("Memory 24", prompt)
        self.assertNotIn("Memory 0", prompt)

    def test_session_user_profile_and_user_memory_context_are_separate_sections(self) -> None:
        import query

        self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Likes checklist responses.",
            importance=6,
            confidence=0.75,
            source_kind="conversation",
            author_actor="sage",
        )
        query.get_sage_provider = lambda: self.provider

        _answer, _questions, prompt, _search_term = query._call_llm_contextual(
            question="What next?",
            context="Retrieved passage.",
            session={
                "messages": [
                    {"role": "user", "content": "I live in Austin."},
                    {"role": "assistant", "content": "Thanks."},
                ],
                "facts_gathered": {"location": "Austin"},
                "_last_sources": [],
            },
            tools=[],
            user_profile_context={"preferred_language": "Spanish"},
            user_memory_context=self.database.list_active_user_memories(self.user_id),
        )

        self.assertIn("=== CONFIRMED FACTS (do NOT re-ask these) ===", prompt)
        self.assertIn("  - location: Austin", prompt)
        self.assertIn("=== USER PROFILE ===", prompt)
        self.assertIn("  - preferred_language: Spanish", prompt)
        self.assertIn("=== USER MEMORY ===", prompt)
        self.assertIn("  - preference: Likes checklist responses. (importance: 6, confidence: 0.75)", prompt)
        self.assertLess(prompt.index("=== CONFIRMED FACTS"), prompt.index("=== USER PROFILE ==="))
        self.assertLess(prompt.index("=== USER PROFILE ==="), prompt.index("=== USER MEMORY ==="))

    def test_user_conversation_ambiently_captures_allowed_personalization_after_response(self) -> None:
        user_id = self.database.create_user(pubkey="c" * 64)
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "c" * 64,
            "id": user_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "Please remember that I prefer concise answers.", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        memories = self.database.list_active_user_memories(user_id)
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["kind"], "preference")
        self.assertEqual(memories[0]["content"], "Prefers concise answers.")
        self.assertEqual(memories[0]["importance"], 4)
        self.assertEqual(memories[0]["confidence"], 0.8)
        self.assertEqual(memories[0]["source_kind"], "ambient")
        self.assertEqual(memories[0]["author_actor"], "sage")

    def test_ambient_capture_disabled_setting_skips_extractor_and_write(self) -> None:
        self.database.update_setting("ambient_user_memory_capture_enabled", "false")
        user_id = self.database.create_user(pubkey="d" * 64)
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "d" * 64,
            "id": user_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "Please remember that I prefer short bullet points.", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.list_active_user_memories(user_id), [])
        self.assertFalse(any("=== USER MEMORY EXTRACTION ===" in prompt for prompt in self.provider.prompts))

    def test_admin_conversation_does_not_run_ambient_capture(self) -> None:
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "Please remember that I prefer concise answers.", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(any("=== USER MEMORY EXTRACTION ===" in prompt for prompt in self.provider.prompts))

    def test_user_conversation_with_tool_context_does_not_run_ambient_capture(self) -> None:
        user_id = self.database.create_user(pubkey="e" * 64)
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "e" * 64,
            "id": user_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={
                "message": "Please remember that I prefer concise answers.",
                "tools": ["web-search"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.list_active_user_memories(user_id), [])
        self.assertFalse(any("=== USER MEMORY EXTRACTION ===" in prompt for prompt in self.provider.prompts))

    def test_ambient_capture_rejects_sensitive_extractor_output(self) -> None:
        user_id = self.database.create_user(pubkey="f" * 64)
        self.provider.extractor_payload = (
            '{"memories":[{"kind":"preference","content":"User has a medical diagnosis.",'
            '"importance":4,"confidence":0.9}]}'
        )
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "f" * 64,
            "id": user_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "Please remember that I prefer concise answers.", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.list_active_user_memories(user_id), [])

    def test_ambient_capture_rejects_negative_importance(self) -> None:
        user_id = self.database.create_user(pubkey="0" * 64)
        self.provider.extractor_payload = (
            '{"memories":[{"kind":"preference","content":"Prefers concise answers.",'
            '"importance":-1,"confidence":0.9}]}'
        )
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "0" * 64,
            "id": user_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "Please remember that I prefer concise answers.", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.list_active_user_memories(user_id), [])

    def test_ambient_capture_skips_duplicate_memory(self) -> None:
        user_id = self.database.create_user(pubkey="1" * 64)
        existing_id = self.database.create_user_memory(
            subject_user_id=user_id,
            kind="preference",
            content="Prefers concise answers.",
            importance=2,
            confidence=0.6,
            source_kind="ambient",
            author_actor="sage",
        )
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "1" * 64,
            "id": user_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "Please remember that I prefer concise answers.", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        memories = self.database.list_active_user_memories(user_id)
        self.assertEqual([memory["id"] for memory in memories], [existing_id])
        self.assertEqual(memories[0]["importance"], 2)

    def test_ambient_capture_failure_is_not_returned_to_user(self) -> None:
        user_id = self.database.create_user(pubkey="2" * 64)
        self.provider.fail_extractor = True
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "2" * 64,
            "id": user_id,
        }

        with self.assertLogs("enclave.user_memory", level="ERROR") as logs:
            response = self.client.post(
                "/llm/chat",
                json={"message": "Please remember that I prefer concise answers.", "tools": []},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "User context received.")
        self.assertEqual(self.database.list_active_user_memories(user_id), [])
        self.assertTrue(any("Ambient User Memory capture failed" in line for line in logs.output))

    def test_ambient_capture_prefilter_skips_messages_without_personalization(self) -> None:
        user_id = self.database.create_user(pubkey="3" * 64)
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "pubkey": "3" * 64,
            "id": user_id,
        }

        response = self.client.post(
            "/llm/chat",
            json={"message": "What is the next step?", "tools": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.list_active_user_memories(user_id), [])
        self.assertFalse(any("=== USER MEMORY EXTRACTION ===" in prompt for prompt in self.provider.prompts))


if __name__ == "__main__":
    unittest.main()
