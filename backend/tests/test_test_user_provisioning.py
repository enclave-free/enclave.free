from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coincurve import PrivateKey
from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class TestUserProvisioningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.tmp.name) / "enclave.db"),
            "SECRET_KEY": "test-user-provisioning-fixture",
            "UPLOADS_DIR": str(Path(self.tmp.name) / "uploads"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        import auth
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.admin_pubkey = (
            PrivateKey(bytes.fromhex("01" * 32))
            .public_key.format(compressed=True)[1:].hex()
        )
        self.database.add_admin(self.admin_pubkey)
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "pubkey": self.admin_pubkey,
        }
        self.client = TestClient(self.main.app)
        self.family = self.database.create_user_type("Family Member")
        self.former = self.database.create_user_type("Former Political Prisoner")

    def tearDown(self) -> None:
        self.client.close()
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self.database._deployment_secret_key = None

    def provision(self, user_type_id: int | None) -> dict:
        params = {} if user_type_id is None else {"user_type_id": user_type_id}
        response = self.client.post("/admin/test-users/provision", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def assert_session(self, user_id: int) -> None:
        response = self.client.post(f"/admin/test-users/{user_id}/impersonation-token")
        self.assertEqual(response.status_code, 200, response.text)
        session = self.auth.verify_session_token(response.json()["token"])
        self.assertIsNotNone(session)
        self.assertEqual(session["user_id"], user_id)

    def test_start_multiple_personas_reuses_distinct_accounts(self) -> None:
        users = []
        for persona in (self.family, self.former, None):
            with self.subTest(persona=persona):
                first = self.provision(persona)
                self.assertTrue(first["created"])
                self.assert_session(first["user_id"])
                again = self.provision(persona)
                self.assertFalse(again["created"])
                self.assertEqual(again["user_id"], first["user_id"])
                self.assert_session(again["user_id"])
                users.append(first["user_id"])
        self.assertEqual(len(set(users)), 3)

    def test_start_repairs_persona_after_admin_type_migration(self) -> None:
        for persona in (self.former, None):
            with self.subTest(persona=persona):
                first = self.provision(persona)
                user_id = first["user_id"]
                response = self.client.post(f"/admin/users/{user_id}/migrate-type", json={
                    "target_user_type_id": self.family,
                    "allow_incomplete": True,
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.database.update_user_approval(user_id, False)
                again = self.provision(persona)
                self.assertEqual(again["user_id"], user_id)
                self.assertFalse(again["created"])
                self.assert_session(user_id)
                user = self.database.get_user(user_id)
                self.assertEqual(user["user_type_id"], persona)
                self.assertTrue(user["approved"])
                self.assert_session(self.provision(persona)["user_id"])

    def test_ordinary_user_cannot_receive_impersonation_token(self) -> None:
        user_id = self.database.create_user(
            pubkey=(
                PrivateKey(bytes.fromhex("02" * 32))
                .public_key.format(compressed=True)[1:].hex()
            ),
            email="ordinary@example.test",
            user_type_id=self.former,
        )
        response = self.client.post(f"/admin/test-users/{user_id}/impersonation-token")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            "Refusing to impersonate a user that is not an instance-derived test user",
        )


if __name__ == "__main__":
    unittest.main()
