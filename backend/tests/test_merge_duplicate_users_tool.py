import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/merge_duplicate_users.py"


class MergeDuplicateUsersToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    pubkey TEXT,
                    email TEXT,
                    name TEXT,
                    user_type_id INTEGER,
                    approved INTEGER DEFAULT 0,
                    encrypted_email TEXT,
                    ephemeral_pubkey_email TEXT,
                    email_blind_index TEXT,
                    encrypted_name TEXT,
                    ephemeral_pubkey_name TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE user_field_values (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    field_id INTEGER,
                    value TEXT
                )
                """
            )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _insert_user(self, **values: object) -> None:
        columns = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT INTO users ({columns}) VALUES ({placeholders})",
                list(values.values()),
            )

    def _run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--db", str(self.db_path), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_plaintext_duplicate_rows_are_ignored(self) -> None:
        self._insert_user(email="Dup@example.test", name="First")
        self._insert_user(email=" dup@example.test ", name="Second")

        result = self._run_script()

        self.assertEqual(result.returncode, 0)
        self.assertIn("Groups processed: 0", result.stdout)
        self.assertIn("Duplicate users merged: 0", result.stdout)
        self.assertIn("Dry-run only. Re-run with --apply to make changes.", result.stdout)
        self.assertEqual(result.stderr, "")

        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(count, 2)

    def test_blind_index_duplicate_merge_does_not_require_legacy_plaintext_flag(self) -> None:
        self._insert_user(email_blind_index="abc123", encrypted_email="cipher-one")
        self._insert_user(email_blind_index="abc123", encrypted_email="cipher-two")

        result = self._run_script()

        self.assertEqual(result.returncode, 0)
        self.assertIn("Groups processed: 1", result.stdout)
        self.assertIn("Duplicate users merged: 1", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
