from __future__ import annotations

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


class AdminSingletonTest(unittest.TestCase):
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

        self.database = importlib.reload(database)

    def tearDown(self) -> None:
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

    def _create_legacy_duplicate_admins(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pubkey TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "INSERT INTO admins (pubkey, created_at) VALUES (?, ?)",
                ("a" * 64, "2026-06-10 14:33:56"),
            )
            conn.execute(
                "INSERT INTO admins (pubkey, created_at) VALUES (?, ?)",
                ("b" * 64, "2026-06-10 14:38:45"),
            )
            conn.commit()
        finally:
            conn.close()

    def test_init_schema_migrates_and_enforces_single_admin(self) -> None:
        self._create_legacy_duplicate_admins()

        self.database.init_schema()

        admins = self.database.list_admins()
        self.assertEqual([admin["pubkey"] for admin in admins], ["a" * 64])

        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.get_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO admins (pubkey) VALUES (?)",
                    ("c" * 64,),
                )


if __name__ == "__main__":
    unittest.main()
