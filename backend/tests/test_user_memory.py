import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class UserMemoryPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "sanctum.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"

        import database

        self.database = importlib.reload(database)
        self.database.init_schema()
        self.user_id = self.database.create_user(pubkey="a" * 64)

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

    def test_active_user_memory_is_durable_and_retrievable_for_subject_user(self) -> None:
        memory_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers concise answers.",
            importance=7,
            confidence=0.85,
            source_kind="conversation",
            source_conversation_id="conv-123",
            author_actor="sage",
        )

        memories = self.database.list_active_user_memories(self.user_id)

        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["id"], memory_id)
        self.assertEqual(memories[0]["subject_user_id"], self.user_id)
        self.assertEqual(memories[0]["kind"], "preference")
        self.assertEqual(memories[0]["content"], "Prefers concise answers.")
        self.assertEqual(memories[0]["importance"], 7)
        self.assertEqual(memories[0]["confidence"], 0.85)
        self.assertEqual(memories[0]["status"], "active")
        self.assertEqual(memories[0]["source_kind"], "conversation")
        self.assertEqual(memories[0]["source_conversation_id"], "conv-123")
        self.assertEqual(memories[0]["author_actor"], "sage")
        self.assertIsNone(memories[0]["superseded_by_id"])
        self.assertIsNone(memories[0]["deleted_at"])
        self.assertIsNotNone(memories[0]["created_at"])
        self.assertIsNotNone(memories[0]["updated_at"])

    def test_active_user_memory_retrieval_is_bounded_ordered_and_deduplicated(self) -> None:
        low_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Likes examples.",
            importance=2,
            source_kind="conversation",
            author_actor="sage",
        )
        duplicate_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind=" Preference ",
            content=" likes   examples. ",
            importance=10,
            source_kind="conversation",
            author_actor="sage",
        )
        high_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers direct answers.",
            importance=9,
            source_kind="conversation",
            author_actor="sage",
        )

        memories = self.database.list_active_user_memories(self.user_id, limit=1)

        self.assertEqual(duplicate_id, low_id)
        self.assertEqual([memory["id"] for memory in memories], [high_id])

    def test_user_memory_can_be_soft_deleted_without_destroying_the_record(self) -> None:
        memory_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers morning meetings.",
            source_kind="conversation",
            author_actor="sage",
        )

        deleted = self.database.soft_delete_user_memory(
            memory_id,
            deleted_by_actor="admin",
            deletion_reason="outdated",
        )
        active_memories = self.database.list_active_user_memories(self.user_id)
        stored_memory = self.database.get_user_memory(memory_id)

        self.assertTrue(deleted)
        self.assertEqual(active_memories, [])
        self.assertEqual(stored_memory["status"], "deleted")
        self.assertEqual(stored_memory["deleted_by_actor"], "admin")
        self.assertEqual(stored_memory["deletion_reason"], "outdated")
        self.assertIsNotNone(stored_memory["deleted_at"])

    def test_user_memory_can_be_superseded_without_overwriting_the_original(self) -> None:
        old_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers weekly summaries.",
            source_kind="conversation",
            author_actor="sage",
        )

        new_id = self.database.supersede_user_memory(
            old_id,
            content="Prefers daily summaries.",
            importance=8,
            confidence=0.9,
            source_kind="admin-confirmed",
            source_conversation_id="admin-conv-1",
            author_actor="admin",
        )
        active_memories = self.database.list_active_user_memories(self.user_id)
        old_memory = self.database.get_user_memory(old_id)
        new_memory = self.database.get_user_memory(new_id)

        self.assertEqual([memory["id"] for memory in active_memories], [new_id])
        self.assertEqual(old_memory["status"], "superseded")
        self.assertEqual(old_memory["superseded_by_id"], new_id)
        self.assertEqual(old_memory["content"], "Prefers weekly summaries.")
        self.assertEqual(new_memory["supersedes_id"], old_id)
        self.assertEqual(new_memory["content"], "Prefers daily summaries.")
        self.assertEqual(new_memory["source_kind"], "admin-confirmed")
        self.assertEqual(new_memory["source_conversation_id"], "admin-conv-1")

    def test_user_memory_can_be_purged_for_deleted_subject_user(self) -> None:
        other_user_id = self.database.create_user(pubkey="b" * 64)
        purged_memory_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Uses metric units.",
            source_kind="conversation",
            author_actor="sage",
        )
        retained_memory_id = self.database.create_user_memory(
            subject_user_id=other_user_id,
            kind="preference",
            content="Uses imperial units.",
            source_kind="conversation",
            author_actor="sage",
        )

        purged_count = self.database.purge_user_memories_for_subject_user(self.user_id)

        self.assertEqual(purged_count, 1)
        self.assertIsNone(self.database.get_user_memory(purged_memory_id))
        self.assertEqual(self.database.get_user_memory(retained_memory_id)["subject_user_id"], other_user_id)


if __name__ == "__main__":
    unittest.main()
