import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class ProfilePlaintextRemovalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"

        import auth
        import database

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.database.init_schema()
        self.database.add_admin("a" * 64)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self.database._deployment_secret_key = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def _insert_plaintext_user(self, email: str = "legacy@example.test", name: str = "Legacy User") -> int:
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (email, name, approved) VALUES (?, ?, 1)",
                (email, name),
            )
            return int(cursor.lastrowid)

    def test_plaintext_email_rows_are_not_reachable_after_fallback_removal(self) -> None:
        self._insert_plaintext_user(email="legacy@example.test", name="Legacy User")

        user = self.database.get_user_by_email("legacy@example.test")

        self.assertIsNone(user)

    def test_current_encrypted_users_remain_reachable_by_blind_index(self) -> None:
        user_id = self.database.create_user(
            pubkey="b" * 64,
            email="Current@example.test",
            name="Current User",
        )

        user = self.database.get_user_by_email(" current@example.test ")

        self.assertIsNotNone(user)
        self.assertEqual(user["id"], user_id)
        self.assertIsNone(user["email"])
        self.assertIsNotNone(user["email_encrypted"])
        self.assertIsNotNone(user["email_blind_index"])

    def test_plaintext_profile_migration_helpers_are_removed(self) -> None:
        self.assertFalse(hasattr(self.database, "profile_plaintext_migration_inventory"))
        self.assertFalse(hasattr(self.database, "migrate_encrypt_existing_data"))


if __name__ == "__main__":
    unittest.main()
