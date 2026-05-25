"""
Tests for the admin-facing Scoped Config Context API (#316).
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class AdminScopedConfigContextEndpointTest(unittest.TestCase):
    """Verifies POST /admin/scoped-config-context uses Control Plane assembly."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import auth
        import admin_scoped_config
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.admin_scoped_config = importlib.reload(admin_scoped_config)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_sentence_transformers()
        self.tmp.cleanup()

    def _restore_sentence_transformers(self) -> None:
        if self._orig_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._orig_sentence_transformers

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_theme_query_returns_server_built_instance_settings_context(self) -> None:
        self.database.update_setting("instance_name", "Free Them")
        self.database.update_setting("default_theme", "dark")

        response = self.client.post(
            "/admin/scoped-config-context",
            json={
                "query": "update all theme configurations for this instance",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "instance-settings")
        self.assertIn("SCOPED CONFIG CONTEXT", body["context_text"])
        self.assertIn("instance_name", body["context_text"])
        self.assertIn("default_theme", body["context_text"])
        self.assertEqual(body["secret_policy"], {"mode": "masked"})

    def test_full_mode_refresh_includes_all_documented_scopes(self) -> None:
        response = self.client.post(
            "/admin/scoped-config-context",
            json={
                "query": "Refresh admin configuration context snapshot",
                "mode": "full",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "overview")
        self.assertEqual(
            body["included_scopes"],
            [
                "overview",
                "instance-settings",
                "deployment-settings",
                "agent-settings",
                "user-types",
                "document-defaults",
                "health",
            ],
        )
        self.assertIn("AGENT SETTINGS (/admin/ai-config)", body["context_text"])
        self.assertIn("USER TYPES (/admin/user-types)", body["context_text"])

    def test_deployment_secret_keys_are_metadata_only(self) -> None:
        self.database.upsert_deployment_config(
            key="SMTP_PASSWORD",
            value="super-secret-smtp-password",
            is_secret=True,
            requires_restart=True,
            category="email",
            description="SMTP password",
            changed_by="test-admin",
        )

        response = self.client.post(
            "/admin/scoped-config-context",
            json={
                "query": "change smtp email settings",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("SMTP_PASSWORD", body["deployment_secret_keys"])
        self.assertNotIn("super-secret-smtp-password", body["context_text"])
        self.assertNotIn("super-secret-smtp-password", response.text)


if __name__ == "__main__":
    unittest.main()
