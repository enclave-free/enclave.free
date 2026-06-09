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
from datetime import datetime, timezone
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

    def test_admin_settings_write_invalidates_scoped_context_cache(self) -> None:
        self.database.update_setting("instance_name", "Before Endpoint Cache")
        payload = {
            "query": "update the instance name and theme",
            "mode": "auto",
        }

        first = self.client.post("/admin/scoped-config-context", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertIn("Before Endpoint Cache", first.json()["context_text"])

        update = self.client.put(
            "/admin/settings",
            json={"instance_name": "After Endpoint Cache"},
        )
        self.assertEqual(update.status_code, 200)

        refreshed = self.client.post("/admin/scoped-config-context", json=payload)
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("After Endpoint Cache", refreshed.json()["context_text"])
        self.assertNotIn("Before Endpoint Cache", refreshed.json()["context_text"])

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
                "resources",
                "health",
            ],
        )
        self.assertIn("AGENT SETTINGS (/admin/ai-config)", body["context_text"])
        self.assertIn("USER TYPES (/admin/user-types)", body["context_text"])
        self.assertIn("RESOURCE DIRECTORY (/admin/resources)", body["context_text"])

    def test_admin_resource_create_uses_utc_verified_timestamp(self) -> None:
        response = self.client.post(
            "/admin/resources",
            json={
                "name": "UTC Verified Resource",
                "resource_type": "ngo",
                "scope_level": "global",
                "help_types": ["legal"],
                "contact": {"url": "https://example.org/help"},
                "verified": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        verified_at = response.json()["verified_at"]
        self.assertTrue(verified_at.endswith("Z"))
        parsed = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
        self.assertEqual(parsed.tzinfo, timezone.utc)

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

    def test_ppst_free_them_instance_settings_includes_branding_theme_and_copy(self) -> None:
        self.database.update_setting("instance_name", "Free Them")
        self.database.update_setting("description", "PPST support instance")
        self.database.update_setting("assistant_name", "Sage")
        self.database.update_setting("header_tagline", "Support political prisoners")
        self.database.update_setting("user_label", "Advocate")
        self.database.update_setting("default_theme", "dark")
        self.database.update_setting("primary_color", "#C53030")
        self.database.update_setting("chat_bubble_style", "soft")
        self.database.update_setting("status_icon_set", "minimal")
        self.database.update_setting("typography_preset", "modern")
        self.database.upsert_deployment_config(
            key="LLM_API_KEY",
            value="secret-api-key",
            is_secret=True,
            requires_restart=False,
            category="llm",
            description="Model Provider API key",
            changed_by="test-admin",
        )

        response = self.client.post(
            "/admin/scoped-config-context",
            json={
                "query": (
                    "Help me configure a Free Them instance for PPST. "
                    "Set up branding, theme, and copy that fits a political "
                    "prisoner support organization."
                ),
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        context_text = body["context_text"]

        self.assertEqual(body["primary_scope"], "instance-settings")
        self.assertEqual(body["secret_policy"], {"mode": "masked"})

        branding_copy_keys = [
            "instance_name",
            "description",
            "logo_url",
            "icon",
            "assistant_icon",
            "assistant_name",
            "user_label",
            "header_tagline",
        ]
        for key in branding_copy_keys:
            self.assertIn(key, context_text, f"Branding/copy key {key} missing from context")

        theme_identity_keys = [
            "default_theme",
            "primary_color",
            "chat_bubble_style",
            "chat_bubble_shadow",
            "surface_style",
            "status_icon_set",
            "typography_preset",
        ]
        for key in theme_identity_keys:
            self.assertIn(key, context_text, f"Theme/identity key {key} missing from context")

        self.assertIn("Free Them", context_text)
        self.assertIn("PPST support instance", context_text)
        self.assertIn("Sage", context_text)
        self.assertIn("dark", context_text)

        self.assertIn("partial PUT /admin/settings", context_text)
        self.assertIn('"method": "PUT"', context_text)
        self.assertIn('"path": "/admin/settings"', context_text)
        self.assertIn("Change Confirmation", context_text)
        self.assertIn("valid JSON change set", context_text)

        self.assertNotIn("secret-api-key", context_text)
        self.assertNotIn("secret-api-key", response.text)

        self.assertIn("LLM_API_KEY", body["deployment_secret_keys"])
        secret_keys_in_context = body["deployment_secret_keys"]
        self.assertIn("LLM_API_KEY", secret_keys_in_context)

    def test_ppst_free_them_instance_settings_claims_no_keys_unavailable(self) -> None:
        self.database.update_setting("instance_name", "Free Them")
        self.database.update_setting("assistant_name", "Sage")

        response = self.client.post(
            "/admin/scoped-config-context",
            json={
                "query": "What branding and copy settings are available for my Free Them instance?",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        context_text = response.json()["context_text"]

        self.assertNotIn("/admin/settings/default_theme", context_text)
        self.assertNotIn("/admin/settings/primary_color", context_text)
        self.assertNotIn("/admin/settings/instance_name", context_text)
        self.assertNotIn("not configurable", context_text.lower())
        self.assertNotIn("read only", context_text.lower())


if __name__ == "__main__":
    unittest.main()
