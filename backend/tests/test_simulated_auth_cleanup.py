import importlib
import os
import sys
import tempfile
import unittest
from typing import Optional
from pathlib import Path

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SimulatedAuthCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_mock_email = os.environ.get("MOCK_EMAIL")
        self._orig_simulate_user = os.environ.get("SIMULATE_USER_AUTH")
        self._orig_simulate_admin = os.environ.get("SIMULATE_ADMIN_AUTH")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        os.environ["MOCK_EMAIL"] = "true"
        os.environ["SIMULATE_USER_AUTH"] = "true"
        os.environ["SIMULATE_ADMIN_AUTH"] = "true"

        import auth
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.database.add_admin("a" * 64)
        self.database.mark_instance_setup_complete()
        self.database.update_deployment_config("SIMULATE_USER_AUTH", "true", "test")
        self.database.update_deployment_config("SIMULATE_ADMIN_AUTH", "true", "test")
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("MOCK_EMAIL", self._orig_mock_email)
        self._restore_env("SIMULATE_USER_AUTH", self._orig_simulate_user)
        self._restore_env("SIMULATE_ADMIN_AUTH", self._orig_simulate_admin)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: Optional[str]) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_public_config_does_not_expose_simulated_auth_flags(self) -> None:
        response = self.client.get("/config/public")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn("simulated_auth", data)
        self.assertNotIn("simulate_admin_auth", data)
        self.assertNotIn("simulate_user_auth", data)
        self.assertNotIn("simulated_auth_enabled", data)

    def test_dev_session_endpoint_is_absent_even_when_stale_flags_are_enabled(self) -> None:
        response = self.client.post(
            "/auth/dev-session",
            json={"email": "user@example.test", "name": "User"},
        )

        self.assertEqual(response.status_code, 404)

    def test_dev_mode_mock_token_is_rejected_even_when_mock_email_is_enabled(self) -> None:
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": "Bearer dev-mode-mock-token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False, "user": None})

    def test_signed_dev_mode_session_payload_does_not_authenticate_as_synthetic_user(self) -> None:
        token = self.auth._session_serializer.dumps(  # noqa: SLF001
            {"user_id": -1, "email": "dev-mode", "dev_mode": True},
            salt="session",
        )

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False, "user": None})

    def test_signed_dev_mode_session_cookie_does_not_authenticate_as_synthetic_user(self) -> None:
        token = self.auth._session_serializer.dumps(  # noqa: SLF001
            {"user_id": -1, "email": "dev-mode", "dev_mode": True},
            salt="session",
        )

        self.client.cookies.set(self.auth.USER_SESSION_COOKIE_NAME, token)

        response = self.client.get("/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False, "user": None})

    def test_mock_email_does_not_block_normal_signed_user_session(self) -> None:
        user_id = self.database.create_user(
            email="real-user@example.test",
            name="Real User",
        )
        token = self.auth.create_session_token(user_id, "real-user@example.test")

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["authenticated"])
        self.assertEqual(body["user"]["id"], user_id)
        self.assertEqual(body["user"]["email"], "real-user@example.test")

    def test_onboarding_status_rejects_deprecated_dev_mode_session_payload(self) -> None:
        token = self.auth._session_serializer.dumps(  # noqa: SLF001
            {"user_id": -1, "email": "dev-mode", "dev_mode": True},
            salt="session",
        )

        response = self.client.get(
            "/users/me/onboarding-status",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or expired token")

    def test_onboarding_status_accepts_real_signed_user_session(self) -> None:
        user_id = self.database.create_user(
            email="onboarding-user@example.test",
            name="Onboarding User",
        )
        token = self.auth.create_session_token(user_id, "onboarding-user@example.test")

        response = self.client.get(
            "/users/me/onboarding-status",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user_id"], user_id)
        self.assertFalse(body["needs_onboarding"])

    def test_deprecated_dev_mode_session_payload_cannot_create_user_profile(self) -> None:
        token = self.auth._session_serializer.dumps(  # noqa: SLF001
            {"user_id": -1, "email": "dev-mode", "dev_mode": True},
            salt="session",
        )

        response = self.client.post(
            "/users",
            json={"email": "fake@example.test", "name": "Fake User", "fields": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or expired token")
        self.assertIsNone(self.database.get_user_by_email("fake@example.test"))

    def test_real_signed_user_session_can_update_own_profile(self) -> None:
        user_id = self.database.create_user(
            email="profile-user@example.test",
            name="Profile User",
        )
        token = self.auth.create_session_token(user_id, "profile-user@example.test")

        response = self.client.post(
            "/users",
            json={"email": "profile-user@example.test", "name": "Profile User", "fields": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], user_id)


if __name__ == "__main__":
    unittest.main()
