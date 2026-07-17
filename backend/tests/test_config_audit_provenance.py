import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class ConfigAuditProvenanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.sqlite_path = Path(self.tmp.name) / "enclave.db"
        self.original_sqlite_path = os.environ.get("SQLITE_PATH")
        os.environ["SQLITE_PATH"] = str(self.sqlite_path)

    def tearDown(self) -> None:
        import database

        if database._connection is not None:
            database._connection.close()
            database._connection = None
        if self.original_sqlite_path is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = self.original_sqlite_path
        self.tmp.cleanup()

    def _reload_database(self):
        import database

        if database._connection is not None:
            database._connection.close()
            database._connection = None
        return importlib.reload(database)

    def test_new_ordinary_product_flow_and_sage_sources_remain_distinct(self) -> None:
        database = self._reload_database()
        database.init_schema()
        database.log_config_audit_event(
            table_name="instance_settings",
            config_key="instance_name",
            old_value="Old",
            new_value="New",
            changed_by="admin-pubkey",
        )
        database.log_config_audit_event(
            table_name="instance_settings",
            config_key="assistant_name",
            old_value="Old",
            new_value="New",
            changed_by="admin-pubkey",
            action_source="sage_conversation",
            conversation_id="conversation-123",
        )

        entries = database.get_config_audit_log(limit=None)
        by_key = {entry["config_key"]: entry for entry in entries}
        self.assertEqual(
            by_key["instance_name"]["action_source"],
            "ordinary_product_flow",
        )
        self.assertIsNone(by_key["instance_name"]["conversation_id"])
        self.assertEqual(by_key["assistant_name"]["action_source"], "sage_conversation")
        self.assertEqual(by_key["assistant_name"]["conversation_id"], "conversation-123")
        self.assertTrue(database.verify_config_audit_log_chain()["valid"])

    def test_legacy_rows_migrate_to_unknown_without_fabricated_conversation(self) -> None:
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute(
            """
            CREATE TABLE config_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                config_key TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by TEXT NOT NULL,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                prev_hash TEXT,
                entry_hash TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO config_audit_log (
                table_name, config_key, old_value, new_value, changed_by
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("instance_settings", "instance_name", "Legacy", "Existing", "admin-pubkey"),
        )
        conn.commit()
        conn.close()

        database = self._reload_database()
        database.init_schema()
        entry = database.get_config_audit_log(limit=1)[0]
        self.assertEqual(entry["action_source"], "unknown")
        self.assertIsNone(entry["conversation_id"])
        self.assertTrue(database.verify_config_audit_log_chain()["valid"])


if __name__ == "__main__":
    unittest.main()
