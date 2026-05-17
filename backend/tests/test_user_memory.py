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
        self.db_path = Path(self.tmp.name) / "enclave.db"
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

    def test_user_memory_retention_class_follows_source_and_supersession(self) -> None:
        ambient_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers compact ambient summaries.",
            source_kind="ambient",
            author_actor="sage:ambient_capture",
        )
        admin_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers durable admin-confirmed summaries.",
            source_kind="admin-confirmed",
            author_actor="admin",
        )
        duplicate_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers compact ambient summaries.",
            source_kind="admin-confirmed",
            author_actor="admin",
        )
        self.assertEqual(duplicate_id, ambient_id)
        self.assertEqual(self.database.get_user_memory(duplicate_id)["retention_class"], "durable")
        replacement_id = self.database.supersede_user_memory(
            ambient_id,
            content="Prefers updated compact summaries.",
            source_kind="admin-confirmed",
            author_actor="admin",
        )
        normalized_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Runtime creation cannot create active superseded memory.",
            source_kind="ambient",
            author_actor="sage:ambient_capture",
            retention_class="superseded",
        )

        self.assertEqual(self.database.get_user_memory(ambient_id)["retention_class"], "superseded")
        self.assertEqual(self.database.get_user_memory(admin_id)["retention_class"], "durable")
        self.assertEqual(self.database.get_user_memory(replacement_id)["retention_class"], "durable")
        self.assertEqual(self.database.get_user_memory(replacement_id)["supersedes_id"], ambient_id)
        self.assertEqual(self.database.get_user_memory(normalized_id)["status"], "active")
        self.assertEqual(self.database.get_user_memory(normalized_id)["retention_class"], "expirable")

    def test_existing_user_memory_migrates_to_conservative_retention_classes(self) -> None:
        with self.database.get_cursor() as cursor:
            cursor.execute("DROP TABLE user_memories")
            cursor.execute("""
                CREATE TABLE user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_user_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    normalized_kind TEXT NOT NULL,
                    normalized_content TEXT NOT NULL,
                    importance INTEGER NOT NULL DEFAULT 5,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    status TEXT NOT NULL DEFAULT 'active',
                    source_kind TEXT NOT NULL,
                    source_conversation_id TEXT,
                    author_actor TEXT NOT NULL,
                    supersedes_id INTEGER,
                    superseded_by_id INTEGER,
                    deleted_at TIMESTAMP,
                    deleted_by_actor TEXT,
                    deletion_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                """
                INSERT INTO user_memories (
                    subject_user_id, kind, content, normalized_kind, normalized_content,
                    status, source_kind, author_actor
                ) VALUES (?, 'preference', 'Keep admin memory.', 'preference', 'keep admin memory.',
                    'active', 'admin-confirmed', 'admin')
                """,
                (self.user_id,),
            )
            active_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO user_memories (
                    subject_user_id, kind, content, normalized_kind, normalized_content,
                    status, source_kind, author_actor
                ) VALUES (?, 'preference', 'Ambient memory.', 'preference', 'ambient memory.',
                    'active', 'ambient', 'sage:ambient_capture')
                """,
                (self.user_id,),
            )
            ambient_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO user_memories (
                    subject_user_id, kind, content, normalized_kind, normalized_content,
                    status, source_kind, author_actor
                ) VALUES (?, 'preference', 'Old memory.', 'preference', 'old memory.',
                    'superseded', 'conversation', 'sage')
                """,
                (self.user_id,),
            )
            superseded_id = int(cursor.lastrowid)

        self.database.init_schema()

        self.assertEqual(self.database.get_user_memory(active_id)["retention_class"], "durable")
        self.assertEqual(self.database.get_user_memory(ambient_id)["retention_class"], "expirable")
        self.assertEqual(self.database.get_user_memory(superseded_id)["retention_class"], "superseded")

    def test_user_memory_rejects_non_string_kind_and_content(self) -> None:
        with self.assertRaises(ValueError):
            self.database.create_user_memory(
                subject_user_id=self.user_id,
                kind={"not": "text"},
                content="Prefers concise answers.",
                source_kind="conversation",
                author_actor="sage",
            )
        memory_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers concise answers.",
            source_kind="conversation",
            author_actor="sage",
        )
        with self.assertRaises(ValueError):
            self.database.supersede_user_memory(
                memory_id,
                content={"not": "text"},
                source_kind="admin-confirmed",
                author_actor="admin",
            )

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

    def test_user_memory_rejects_out_of_range_scores(self) -> None:
        with self.assertRaises(ValueError):
            self.database.create_user_memory(
                subject_user_id=self.user_id,
                kind="preference",
                content="Prefers invalid importance.",
                importance=-1,
                source_kind="conversation",
                author_actor="sage",
            )

        memory_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers validated replacement.",
            source_kind="conversation",
            author_actor="sage",
        )
        with self.assertRaises(ValueError):
            self.database.supersede_user_memory(
                memory_id,
                content="Prefers invalid confidence.",
                confidence=7,
                source_kind="admin-confirmed",
                author_actor="admin",
            )

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

    def test_delete_user_explicitly_purges_user_memory(self) -> None:
        memory_id = self.database.create_user_memory(
            subject_user_id=self.user_id,
            kind="preference",
            content="Prefers deletion cleanup.",
            source_kind="conversation",
            author_actor="sage",
        )

        deleted = self.database.delete_user(self.user_id)

        self.assertTrue(deleted)
        self.assertIsNone(self.database.get_user_memory(memory_id))


if __name__ == "__main__":
    unittest.main()
