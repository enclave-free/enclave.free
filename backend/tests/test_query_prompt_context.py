import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any


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

    def complete(self, prompt: str, temperature: float = 0.1) -> Any:
        self.prompts.append(prompt)
        return type(
            "LLMResult",
            (),
            {
                "content": "Context received.",
                "model": "fake-model",
                "provider": self.name,
            },
        )()


class QueryPromptContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer,
        )
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_protected_bypass = os.environ.get("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        os.environ["PROTECTED_INFERENCE_DEVELOPMENT_BYPASS"] = "true"

        import database
        import query

        self.database = importlib.reload(database)
        self.query = importlib.reload(query)
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
            content="Likes checklist responses.",
            importance=6,
            confidence=0.75,
            source_kind="conversation",
            author_actor="sage",
        )

        self.provider = FakeProvider()
        self.query.get_sage_provider = lambda: self.provider

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS", self._orig_protected_bypass)
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

    def test_session_user_profile_and_user_memory_context_are_separate_sections(self) -> None:
        _answer, _questions, prompt, _search_term, _inference_record = self.query._call_llm_contextual(
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


if __name__ == "__main__":
    unittest.main()
