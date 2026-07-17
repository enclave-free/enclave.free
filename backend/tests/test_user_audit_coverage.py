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


class UserAuditCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer,
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import database
        import auth
        import deployment_config
        import main

        self.database = importlib.reload(database)
        self.auth = importlib.reload(auth)
        self.deployment_config = importlib.reload(deployment_config)
        self.main = importlib.reload(main)
        self.database.init_schema()

        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.deployment_config.auth.require_admin] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.auth.require_admin_or_user] = lambda: {
            "type": "admin",
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
        if self._orig_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._orig_sentence_transformers
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def audit_entries(self, table_name: str) -> list[dict]:
        response = self.client.get(f"/admin/deployment/audit-log?table_name={table_name}")
        self.assertEqual(response.status_code, 200)
        return response.json()["entries"]

    def test_user_approval_changes_are_audited_and_filterable(self) -> None:
        user_id = self.database.create_user(pubkey="a" * 64)

        response = self.client.put(f"/users/{user_id}", json={"approved": False})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["approved"])
        entries = self.audit_entries("user_approval")
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["config_key"], f"user:{user_id}:approved")
        self.assertEqual(entry["old_value"], "true")
        self.assertEqual(entry["new_value"], "false")
        self.assertEqual(entry["changed_by"], "admin-pubkey")
        self.assertEqual(entry["action_source"], "ordinary_product_flow")
        self.assertIsNone(entry["conversation_id"])
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=user_approval")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_non_admin_user_cannot_change_approval(self) -> None:
        user_pubkey = "c" * 64
        user_id = self.database.create_user(pubkey=user_pubkey)
        self.main.app.dependency_overrides[self.auth.require_admin_or_user] = lambda: {
            "type": "user",
            "id": user_id,
            "pubkey": user_pubkey,
        }

        response = self.client.put(f"/users/{user_id}", json={"approved": False})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.database.get_user(user_id)["approved"])
        self.assertEqual(self.audit_entries("user_approval"), [])

    def test_invalid_field_update_does_not_commit_approval_change(self) -> None:
        user_id = self.database.create_user(pubkey="d" * 64)

        response = self.client.put(
            f"/users/{user_id}",
            json={"approved": False, "fields": {"unknown_field": "value"}},
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.database.get_user(user_id)["approved"])
        self.assertEqual(self.audit_entries("user_approval"), [])

    def test_auto_approval_setting_changes_are_audited_and_filterable(self) -> None:
        response = self.client.put("/admin/settings", json={"auto_approve_users": "false"})

        self.assertEqual(response.status_code, 200)
        entries = self.audit_entries("instance_settings")
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["config_key"], "auto_approve_users")
        self.assertEqual(entry["old_value"], "true")
        self.assertEqual(entry["new_value"], "false")
        self.assertEqual(entry["changed_by"], "admin-pubkey")
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=instance_settings")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_admin_settings_accept_known_keys_and_reject_unknown_keys(self) -> None:
        response = self.client.put(
            "/admin/settings",
            json={
                "instance_name": "FreeThem",
                "public_email_display_name": "World Liberty Congress",
                "primary_color": "#2563EB",
                "description": "Support resources",
                "logo_url": "",
                "favicon_url": "",
                "apple_touch_icon_url": "",
                "icon": "Sparkles",
                "assistant_icon": "Sparkles",
                "user_icon": "User",
                "assistant_name": "Support Team",
                "user_label": "You",
                "header_layout": "icon_name",
                "header_tagline": "Support team",
                "chat_bubble_style": "soft",
                "chat_bubble_shadow": "true",
                "surface_style": "plain",
                "status_icon_set": "classic",
                "typography_preset": "modern",
                "default_language": "en",
                "default_theme": "dark",
                "auto_approve_users": "true",
                "reachout_enabled": "true",
                "reachout_mode": "support",
                "reachout_title": "Contact us",
                "reachout_description": "Send the support team a private note.",
                "reachout_button_label": "Request support",
                "reachout_success_message": "Thanks, we received your note.",
                "reachout_to_email": "ops@example.test",
                "reachout_subject_prefix": "[FreeThem]",
                "reachout_rate_limit_per_hour": "5",
                "reachout_rate_limit_per_day": "20",
                "reachout_include_ip": "false",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.get_setting("header_tagline"), "Support team")
        self.assertEqual(
            self.database.get_setting("public_email_display_name"),
            "World Liberty Congress",
        )
        self.assertEqual(self.database.get_setting("default_language"), "en")
        self.assertEqual(self.database.get_setting("reachout_to_email"), "ops@example.test")

        rejected = self.client.put("/admin/settings", json={"tagline": "Wrong key"})

        self.assertEqual(rejected.status_code, 422)
        self.assertIsNone(self.database.get_setting("tagline"))

    def test_user_type_crud_and_migration_actions_are_audited(self) -> None:
        created = self.client.post(
            "/admin/user-types",
            json={"name": "Member", "description": "Initial", "icon": "User", "display_order": 2},
        )
        self.assertEqual(created.status_code, 200)
        type_id = created.json()["id"]

        updated = self.client.put(
            f"/admin/user-types/{type_id}",
            json={"name": "Operator", "description": "Updated", "icon": "Shield", "display_order": 1},
        )
        self.assertEqual(updated.status_code, 200)

        migration_type_id = self.database.create_user_type(
            name="Migration Target",
            description="Assigned to users",
            icon="Users",
            display_order=3,
        )
        user_id = self.database.create_user(pubkey="b" * 64)
        migration = self.client.post(
            f"/admin/users/{user_id}/migrate-type",
            json={"target_user_type_id": migration_type_id, "allow_incomplete": True},
        )
        self.assertEqual(migration.status_code, 200)

        deleted = self.client.delete(f"/admin/user-types/{type_id}")
        self.assertEqual(deleted.status_code, 200)

        entries = self.audit_entries("user_types")
        actions = {entry["config_key"]: entry for entry in entries}
        self.assertIn(f"user_type:{type_id}:create", actions)
        self.assertIn(f"user_type:{type_id}:update", actions)
        self.assertIn(f"user:{user_id}:migrate_type", actions)
        self.assertIn(f"user_type:{type_id}:delete", actions)
        verify = self.client.get("/admin/deployment/audit-log/verify?table_name=user_types")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])


if __name__ == "__main__":
    unittest.main()
