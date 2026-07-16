from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coincurve import PrivateKey


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class ImpersonationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        os.environ["SQLITE_PATH"] = str(self.db_path)

        import auth
        import database
        import impersonation

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.impersonation = importlib.reload(impersonation)
        self.database.init_schema()

        admin_key = PrivateKey()
        self.admin_pubkey = admin_key.public_key.format(compressed=True)[1:].hex()
        self.database.add_admin(self.admin_pubkey)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        if self._orig_sqlite_path is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = self._orig_sqlite_path
        self.tmp.cleanup()

    def test_issue_session_token_uses_provisioned_test_user_email(self) -> None:
        user_type_id = self.database.create_user_type("Student")
        derived_pubkey = self.impersonation.derive_test_user_pubkey(
            self.admin_pubkey,
            user_type_id,
        )
        fallback_email = f"test-user+type{user_type_id}@enclave.test"
        expected_email = "provisioned-user@enclave.test"
        self.assertNotEqual(expected_email, fallback_email)
        user_id = self.database.create_user(
            pubkey=derived_pubkey,
            email=fallback_email,
            name="Test User",
            user_type_id=user_type_id,
        )
        # Seed a legacy plaintext email to make the precedence branch observable.
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                (expected_email, user_id),
            )

        with patch.object(self.auth, "create_session_token", return_value="token") as create_token:
            result = self.impersonation.issue_session_token(
                user_id=user_id,
                issued_by_pubkey=self.admin_pubkey,
            )

        self.assertEqual(result["token"], "token")
        create_token.assert_called_once_with(user_id, expected_email)

    def test_provisioned_test_user_requires_instance_derived_pubkey(self) -> None:
        user_type_id = self.database.create_user_type("Student")
        derived_pubkey = self.impersonation.derive_test_user_pubkey(
            self.admin_pubkey,
            user_type_id,
        )
        test_user_id = self.database.create_user(
            pubkey=derived_pubkey,
            email=f"test-user+type{user_type_id}@enclave.test",
            name="Test User",
            user_type_id=user_type_id,
        )
        ordinary_user_id = self.database.create_user(
            pubkey=PrivateKey().public_key.format(compressed=True)[1:].hex(),
            email="test-user+ordinary@enclave.test",
            name="Ordinary User",
            user_type_id=user_type_id,
        )

        self.assertTrue(
            self.impersonation.is_provisioned_test_user(test_user_id)
        )
        self.assertFalse(
            self.impersonation.is_provisioned_test_user(ordinary_user_id)
        )


if __name__ == "__main__":
    unittest.main()
