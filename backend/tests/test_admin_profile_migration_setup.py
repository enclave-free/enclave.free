import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class AdminProfileMigrationSetupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import auth
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "id": 1,
            "pubkey": "a" * 64,
        }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self.database._deployment_secret_key = None
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

    def _insert_plaintext_user(self, email: str) -> None:
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (email, name, approved) VALUES (?, ?, 1)",
                (email, "Legacy User"),
            )

    def _admin_auth_body(self) -> dict:
        return {
            "event": {
                "id": "0" * 64,
                "pubkey": "a" * 64,
                "created_at": 1,
                "kind": 22242,
                "tags": [["action", "admin_auth"]],
                "content": "",
                "sig": "0" * 128,
            }
        }

    def test_profile_plaintext_migration_admin_endpoints_are_removed(self) -> None:
        self.database.add_admin("a" * 64)

        inventory = self.client.get("/admin/profile-plaintext-migration/inventory")
        migrate = self.client.post("/admin/profile-plaintext-migration/migrate")

        self.assertEqual(inventory.status_code, 404)
        self.assertEqual(migrate.status_code, 404)

    def test_first_admin_setup_ignores_legacy_plaintext_profile_conflicts(self) -> None:
        self._insert_plaintext_user("Dup@example.test")
        self._insert_plaintext_user(" dup@example.test ")

        with (
            patch.object(self.main, "verify_auth_event", return_value=(True, None)),
            patch.object(self.main, "get_pubkey_from_event", return_value="a" * 64),
        ):
            response = self.client.post("/admin/auth", json=self._admin_auth_body())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_new"])
        self.assertTrue(self.database.has_admin())
        self.assertTrue(self.database.is_instance_setup_complete())

    def test_first_admin_setup_does_not_migrate_legacy_profile_plaintext(self) -> None:
        self._insert_plaintext_user("legacy@example.test")

        with (
            patch.object(self.main, "verify_auth_event", return_value=(True, None)),
            patch.object(self.main, "get_pubkey_from_event", return_value="a" * 64),
        ):
            response = self.client.post("/admin/auth", json=self._admin_auth_body())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_new"])
        self.assertTrue(self.database.has_admin())
        self.assertIsNone(self.database.get_user_by_email("legacy@example.test"))


if __name__ == "__main__":
    unittest.main()
