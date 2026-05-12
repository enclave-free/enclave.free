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

    def health_check(self) -> bool:
        return True

    def complete(self, prompt: str, temperature: float = 0.1) -> Any:
        self.prompts.append(prompt)
        return type(
            "LLMResult",
            (),
            {
                "content": "Admin context received.",
                "model": "fake-model",
                "provider": self.name,
            },
        )()


class AdminSubjectUserMemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "sanctum.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import database
        import auth
        import deployment_config
        import main

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.deployment_config = importlib.reload(deployment_config)
        self.main = importlib.reload(main)
        self.database.init_schema()

        self.user_id = self.database.create_user(pubkey="a" * 64)
        self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers checklist responses.",
            importance=6,
            confidence=0.75,
            source_kind="ambient",
            author_actor="sage",
        )

        self.provider = FakeProvider()
        self.main.get_sage_provider = lambda: self.provider
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.deployment_config.auth.require_admin] = lambda: {
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
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def audit_entries(self, table_name: str) -> list[dict]:
        response = self.client.get(f"/admin/deployment/audit-log?table_name={table_name}")
        self.assertEqual(response.status_code, 200)
        return response.json()["entries"]

    def test_admin_conversation_sets_subject_user_and_loads_only_that_users_memory(self) -> None:
        other_user_id = self.database.create_user(pubkey="c" * 64)
        self.database.create_user_memory(
            subject_user_id=other_user_id,
            kind="preference",
            content="Other user prefers long-form analysis.",
            importance=4,
            confidence=0.7,
            source_kind="ambient",
            author_actor="sage",
        )

        response = self.client.post(
            "/llm/chat",
            json={
                "session_id": "admin-session-1",
                "message": f"Set subject user to user {self.user_id}. What do we know?",
                "tools": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_id"], "admin-session-1")
        prompt = self.provider.prompts[-1]
        self.assertIn("=== SUBJECT USER ===", prompt)
        self.assertIn(f"Subject User ID: {self.user_id}", prompt)
        self.assertIn("=== SUBJECT USER MEMORY ===", prompt)
        self.assertIn("This User Memory is about the Subject User, not the Admin.", prompt)
        self.assertIn("Prefers checklist responses.", prompt)
        self.assertNotIn("Other user prefers long-form analysis.", prompt)
        self.assertNotIn("=== USER MEMORY ===", prompt)

    def test_subject_user_persists_switches_and_clears_within_admin_conversation(self) -> None:
        other_user_id = self.database.create_user(pubkey="b" * 64)
        self.database.create_user_memory(
            subject_user_id=other_user_id,
            kind="preference",
            content="Prefers narrative responses.",
            importance=5,
            confidence=0.8,
            source_kind="ambient",
            author_actor="sage",
        )

        self.client.post(
            "/llm/chat",
            json={
                "session_id": "admin-session-2",
                "message": f"Set subject user to user {self.user_id}.",
                "tools": [],
            },
        )
        self.client.post(
            "/llm/chat",
            json={"session_id": "admin-session-2", "message": "Inspect memory.", "tools": []},
        )
        persisted_prompt = self.provider.prompts[-1]

        self.client.post(
            "/llm/chat",
            json={
                "session_id": "admin-session-2",
                "message": f"Switch subject user to user {other_user_id}.",
                "tools": [],
            },
        )
        switched_prompt = self.provider.prompts[-1]

        self.client.post(
            "/llm/chat",
            json={"session_id": "admin-session-2", "message": "Clear subject user.", "tools": []},
        )
        cleared_prompt = self.provider.prompts[-1]

        self.assertIn(f"Subject User ID: {self.user_id}", persisted_prompt)
        self.assertIn("Prefers checklist responses.", persisted_prompt)
        self.assertIn(f"Subject User ID: {other_user_id}", switched_prompt)
        self.assertIn("Prefers narrative responses.", switched_prompt)
        self.assertNotIn("Prefers checklist responses.", switched_prompt)
        self.assertNotIn("=== SUBJECT USER ===", cleared_prompt)
        self.assertNotIn("=== SUBJECT USER MEMORY ===", cleared_prompt)

    def test_subject_user_state_is_session_scoped_and_not_stored_as_user_memory(self) -> None:
        before_memories = self.database.list_active_user_memories(self.user_id)

        self.client.post(
            "/llm/chat",
            json={
                "session_id": "admin-session-3",
                "message": f"Set subject user to user {self.user_id}.",
                "tools": [],
            },
        )
        self.client.post(
            "/llm/chat",
            json={"session_id": "admin-session-4", "message": "Inspect memory.", "tools": []},
        )

        after_memories = self.database.list_active_user_memories(self.user_id)
        new_session_prompt = self.provider.prompts[-1]

        self.assertEqual([memory["id"] for memory in after_memories], [memory["id"] for memory in before_memories])
        self.assertNotIn("=== SUBJECT USER ===", new_session_prompt)
        self.assertNotIn("=== SUBJECT USER MEMORY ===", new_session_prompt)

    def test_admin_memory_write_is_staged_until_confirmation_then_audited(self) -> None:
        session_id = "admin-session-confirm-write"
        self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": f"Set subject user to user {self.user_id}.",
                "tools": [],
            },
        )

        stage_response = self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": "Remember for the subject user: Prefers high detail answers. Kind: preference. Importance: 8.",
                "tools": [],
            },
        )
        staged_prompt = self.provider.prompts[-1]
        staged_memories = self.database.list_active_user_memories(self.user_id)

        confirm_response = self.client.post(
            "/llm/chat",
            json={"session_id": session_id, "message": "Confirm this User Memory write.", "tools": []},
        )
        confirmed_memories = self.database.list_active_user_memories(self.user_id)
        audit_entries = self.database.get_config_audit_log(limit=10, table_name="user_memories")

        self.assertEqual(stage_response.status_code, 200)
        self.assertIn("=== PENDING USER MEMORY WRITE ===", staged_prompt)
        self.assertIn("Subject User ID: " + str(self.user_id), staged_prompt)
        self.assertIn("Kind: preference", staged_prompt)
        self.assertIn("Content: Prefers high detail answers.", staged_prompt)
        self.assertIn("Importance: 8", staged_prompt)
        self.assertEqual([memory["content"] for memory in staged_memories], ["Prefers checklist responses."])
        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(confirmed_memories[0]["content"], "Prefers high detail answers.")
        self.assertEqual(confirmed_memories[0]["importance"], 8)
        self.assertEqual(confirmed_memories[0]["source_kind"], "admin-confirmed")
        self.assertTrue(any(entry["config_key"] == str(confirmed_memories[0]["id"]) for entry in audit_entries))
        filter_entries = self.audit_entries("user_memories")
        self.assertTrue(any(entry["config_key"] == str(confirmed_memories[0]["id"]) for entry in filter_entries))
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=user_memories")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_negated_admin_memory_confirmation_does_not_commit(self) -> None:
        session_id = "admin-session-negated-confirm"
        self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": f"Set subject user to user {self.user_id}.",
                "tools": [],
            },
        )
        self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": "Remember for the subject user: Prefers short answers. Kind: preference. Importance: 4.",
                "tools": [],
            },
        )

        response = self.client.post(
            "/llm/chat",
            json={"session_id": session_id, "message": "Do not confirm this User Memory yet.", "tools": []},
        )

        memories = self.database.list_active_user_memories(self.user_id)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Prefers short answers.", [memory["content"] for memory in memories])

    def test_admin_memory_write_without_subject_user_requests_clarification(self) -> None:
        response = self.client.post(
            "/llm/chat",
            json={
                "session_id": "admin-session-missing-subject",
                "message": "Remember for this user: Prefers concise explanations. Kind: preference. Importance: 5.",
                "tools": [],
            },
        )

        prompt = self.provider.prompts[-1]
        memories = self.database.list_active_user_memories(self.user_id)

        self.assertEqual(response.status_code, 200)
        self.assertIn("=== SUBJECT USER REQUIRED ===", prompt)
        self.assertIn("Ask the Admin to resolve exactly one Subject User before writing User Memory.", prompt)
        self.assertEqual([memory["content"] for memory in memories], ["Prefers checklist responses."])

    def test_admin_memory_write_with_ambiguous_subject_users_requests_clarification(self) -> None:
        other_user_id = self.database.create_user(pubkey="d" * 64)

        response = self.client.post(
            "/llm/chat",
            json={
                "session_id": "admin-session-ambiguous-subject",
                "message": f"Remember for user {self.user_id} and user {other_user_id}: Prefers short answers. Kind: preference.",
                "tools": [],
            },
        )

        prompt = self.provider.prompts[-1]
        memories = self.database.list_active_user_memories(self.user_id)
        other_memories = self.database.list_active_user_memories(other_user_id)

        self.assertEqual(response.status_code, 200)
        self.assertIn("=== SUBJECT USER REQUIRED ===", prompt)
        self.assertIn("Ask the Admin to resolve exactly one Subject User before writing User Memory.", prompt)
        self.assertEqual([memory["content"] for memory in memories], ["Prefers checklist responses."])
        self.assertEqual(other_memories, [])

    def test_admin_memory_write_rejects_sensitive_facts_and_redirects(self) -> None:
        session_id = "admin-session-sensitive-memory"
        self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": f"Set subject user to user {self.user_id}.",
                "tools": [],
            },
        )

        response = self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": "Remember for the subject user: User has a medical diagnosis. Kind: preference. Importance: 7.",
                "tools": [],
            },
        )

        prompt = self.provider.prompts[-1]
        memories = self.database.list_active_user_memories(self.user_id)

        self.assertEqual(response.status_code, 200)
        self.assertIn("=== USER MEMORY WRITE REJECTED ===", prompt)
        self.assertIn("Redirect the Admin to encrypted User Profile or Onboarding Question design.", prompt)
        self.assertNotIn("=== PENDING USER MEMORY WRITE ===", prompt)
        self.assertEqual([memory["content"] for memory in memories], ["Prefers checklist responses."])

    def test_admin_can_confirm_supersede_and_delete_user_memory_with_audit(self) -> None:
        session_id = "admin-session-maintain-memory"
        existing_memory_id = self.database.list_active_user_memories(self.user_id)[0]["id"]
        self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": f"Set subject user to user {self.user_id}.",
                "tools": [],
            },
        )

        supersede_stage = self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": f"Supersede memory {existing_memory_id} with: Prefers concise checklist responses. Importance: 7.",
                "tools": [],
            },
        )
        supersede_prompt = self.provider.prompts[-1]

        supersede_confirm = self.client.post(
            "/llm/chat",
            json={"session_id": session_id, "message": "Confirm this User Memory change.", "tools": []},
        )
        replacement = self.database.list_active_user_memories(self.user_id)[0]

        delete_stage = self.client.post(
            "/llm/chat",
            json={
                "session_id": session_id,
                "message": f"Delete memory {replacement['id']}. Reason: stale preference.",
                "tools": [],
            },
        )
        delete_prompt = self.provider.prompts[-1]

        delete_confirm = self.client.post(
            "/llm/chat",
            json={"session_id": session_id, "message": "Confirm this User Memory change.", "tools": []},
        )
        active_memories = self.database.list_active_user_memories(self.user_id)
        audit_entries = self.database.get_config_audit_log(limit=10, table_name="user_memories")

        self.assertEqual(supersede_stage.status_code, 200)
        self.assertIn("=== PENDING USER MEMORY SUPERSEDE ===", supersede_prompt)
        self.assertIn(f"Memory ID: {existing_memory_id}", supersede_prompt)
        self.assertEqual(supersede_confirm.status_code, 200)
        self.assertEqual(replacement["content"], "Prefers concise checklist responses.")
        self.assertEqual(replacement["importance"], 7)
        self.assertEqual(self.database.get_user_memory(existing_memory_id)["status"], "superseded")
        self.assertEqual(delete_stage.status_code, 200)
        self.assertIn("=== PENDING USER MEMORY DELETE ===", delete_prompt)
        self.assertIn(f"Memory ID: {replacement['id']}", delete_prompt)
        self.assertEqual(delete_confirm.status_code, 200)
        self.assertEqual(active_memories, [])
        self.assertTrue(any(entry["config_key"] == str(existing_memory_id) and "supersede" in entry["new_value"] for entry in audit_entries))
        self.assertTrue(any(entry["config_key"] == str(replacement["id"]) and "delete" in entry["new_value"] for entry in audit_entries))

    def test_admin_direct_database_mutation_tool_is_constrained_to_read_only_queries(self) -> None:
        response = self.client.post(
            "/admin/tools/execute",
            json={
                "tool_id": "db-query",
                "query": f"UPDATE users SET approved = 0 WHERE id = {self.user_id}",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("Only SELECT queries are allowed", body["error"])
        self.assertTrue(self.database.get_user(self.user_id)["approved"])

    def test_admin_database_explorer_mutation_endpoints_are_constrained(self) -> None:
        insert_response = self.client.post(
            "/admin/db/tables/user_types/rows",
            json={"data": {"name": "Escalation", "description": "Direct insert"}},
        )
        update_response = self.client.put(
            f"/admin/db/tables/users/rows/{self.user_id}",
            json={"data": {"approved": 0}},
        )
        delete_response = self.client.delete(f"/admin/db/tables/users/rows/{self.user_id}")

        for response in (insert_response, update_response, delete_response):
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertFalse(body["success"])
            self.assertIn("Direct database mutations are not supported", body["error"])

        self.assertTrue(self.database.get_user(self.user_id)["approved"])
        self.assertEqual(self.database.list_user_types(), [])


if __name__ == "__main__":
    unittest.main()
