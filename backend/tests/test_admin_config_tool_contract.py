import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class AdminConfigToolContractTest(unittest.TestCase):
    """Verifies private Admin Config Tool contracts used by Sage."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_internal_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["INTERNAL_AGENT_TOKEN"] = "test-internal-token"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import database
        import ingest_db
        import internal_agent

        self.database = importlib.reload(database)
        self.ingest_db = importlib.reload(ingest_db)
        self.internal_agent = importlib.reload(internal_agent)
        self.database.init_schema()
        self.admin_id = self.database.add_admin("abc123")

        app = FastAPI()
        app.include_router(self.internal_agent.router)
        self.client = TestClient(app)
        self.headers = {"X-Internal-Agent-Token": "test-internal-token"}
        self.admin_actor = {
            "id": self.admin_id,
            "type": "admin",
            "approved": True,
            "pubkey": "abc123",
        }

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("INTERNAL_AGENT_TOKEN", self._orig_internal_token)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_module("sentence_transformers", self._orig_sentence_transformers)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: Optional[str]) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    @staticmethod
    def _restore_module(name: str, value: object | None) -> None:
        if value is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = value

    def test_read_deployment_readiness_returns_structured_masked_tool_result(self) -> None:
        response = self.client.post(
            "/internal/agent/admin-config/deployment-readiness",
            headers=self.headers,
            json={"actor": self.admin_actor},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tool"], "read_deployment_readiness")
        self.assertEqual(payload["secret_policy"], {"mode": "masked"})
        self.assertIsInstance(payload["warnings"], list)
        self.assertIn("generated_at", payload)
        self.assertIn("items", payload["data"])
        self.assertIn("summary", payload["data"])
        self.assertNotIn("test-secret", response.text)

    def test_read_instance_settings_returns_structured_tool_result(self) -> None:
        self.database.update_settings({
            "instance_name": "FreeThem",
            "assistant_name": "Ally",
            "header_tagline": "Political Prisoner Support Team.",
            "description": "Support families and organizers.",
            "primary_color": "#8B5CF6",
            "default_theme": "dark",
            "auto_approve_users": "true",
        })
        self.database.mark_onboarding_configured_keys([
            "instance_name",
            "assistant_name",
            "header_tagline",
            "description",
            "primary_color",
            "default_theme",
            "auto_approve_users",
        ])

        response = self.client.post(
            "/internal/agent/admin-config/instance-settings",
            headers=self.headers,
            json={"actor": self.admin_actor},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tool"], "read_instance_settings")
        self.assertEqual(payload["secret_policy"], {"mode": "masked"})
        self.assertEqual(payload["warnings"], [])
        data = payload["data"]
        self.assertEqual(data["settings"]["instance_name"], "FreeThem")
        self.assertEqual(data["settings"]["assistant_name"], "Ally")
        self.assertEqual(data["settings"]["default_theme"], "dark")
        self.assertIn("instance_name", data["explicitly_set_keys"])
        self.assertNotIn("onboarding_configured_keys", data["settings"])
        fields_by_key = {field["key"]: field for field in data["fields"]}
        self.assertEqual(fields_by_key["instance_name"]["label"], "Instance name")
        self.assertEqual(fields_by_key["instance_name"]["value"], "FreeThem")
        self.assertEqual(fields_by_key["instance_name"]["source"], "operator")
        self.assertTrue(fields_by_key["instance_name"]["editable"])
        self.assertEqual(
            fields_by_key["default_theme"]["supported_values"],
            ["light", "dark", "system"],
        )
        self.assertNotIn("test-secret", response.text)

    def test_read_deployment_settings_returns_masked_secret_status(self) -> None:
        self.database.upsert_deployment_config(
            "LLM_MODEL",
            "kimi-k2-6",
            category="llm",
            requires_restart=False,
            description="Model identifier",
        )
        self.database.upsert_deployment_config(
            "LLM_API_KEY",
            "configured-secret",
            category="llm",
            is_secret=True,
            description="Model provider API key",
        )
        self.database.upsert_deployment_config(
            "SMTP_HOST",
            "smtp.example.test",
            category="email",
            description="SMTP server hostname",
        )
        self.database.upsert_deployment_config(
            "SMTP_PASS",
            "smtp-secret",
            category="email",
            is_secret=True,
            description="SMTP password",
        )

        response = self.client.post(
            "/internal/agent/admin-config/deployment-settings",
            headers=self.headers,
            json={"actor": self.admin_actor},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tool"], "read_deployment_settings")
        self.assertEqual(payload["secret_policy"], {"mode": "masked"})
        data = payload["data"]
        self.assertEqual(data["settings"]["LLM_MODEL"]["value"], "kimi-k2-6")
        self.assertFalse(data["settings"]["LLM_MODEL"]["secret"])
        self.assertTrue(data["settings"]["LLM_MODEL"]["configured"])
        self.assertEqual(data["settings"]["LLM_API_KEY"]["value"], "********")
        self.assertTrue(data["settings"]["LLM_API_KEY"]["secret"])
        self.assertTrue(data["settings"]["LLM_API_KEY"]["configured"])
        self.assertEqual(data["settings"]["SMTP_HOST"]["value"], "smtp.example.test")
        self.assertEqual(data["settings"]["SMTP_PASS"]["value"], "********")
        self.assertIn("LLM_MODEL", data["categories"]["llm"])
        self.assertIn("SMTP_HOST", data["categories"]["email"])
        self.assertNotIn("configured-secret", response.text)
        self.assertNotIn("smtp-secret", response.text)

    def test_read_agent_settings_returns_global_and_user_type_effective_values(self) -> None:
        user_type_id = self.database.create_user_type(
            "Advocates",
            "People doing direct support work",
            icon="Users",
            display_order=7,
        )
        self.database.update_ai_config("temperature", "0.4", changed_by="abc123")
        self.database.upsert_ai_config_override(
            "temperature",
            user_type_id,
            "0.2",
            changed_by="abc123",
        )

        response = self.client.post(
            "/internal/agent/admin-config/agent-settings",
            headers=self.headers,
            json={"actor": self.admin_actor},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tool"], "read_agent_settings")
        self.assertEqual(payload["secret_policy"], {"mode": "masked"})
        data = payload["data"]
        self.assertEqual(
            data["global"]["parameters"]["temperature"]["value"],
            "0.4",
        )
        self.assertIn("prompt_system", data["global"]["prompt_sections"])
        self.assertIn("admin_trace_visibility", data["global"]["defaults"])
        advocate_settings = next(
            item for item in data["per_user_type"]
            if item["user_type_id"] == user_type_id
        )
        self.assertEqual(advocate_settings["user_type_name"], "Advocates")
        self.assertEqual(
            advocate_settings["overrides"]["temperature"]["value"],
            "0.2",
        )
        self.assertEqual(
            advocate_settings["effective_values"]["parameters"]["temperature"]["value"],
            "0.2",
        )
        self.assertTrue(
            advocate_settings["effective_values"]["parameters"]["temperature"]["is_override"]
        )
        self.assertEqual(data["limits"]["user_types_returned"], 1)
        self.assertNotIn("test-secret", response.text)

    def test_read_user_types_returns_onboarding_questions(self) -> None:
        user_type_id = self.database.create_user_type(
            "Family",
            "Family members seeking support",
            icon="Heart",
            display_order=3,
        )
        field_id = self.database.create_field_definition(
            "preferred_language",
            "select",
            required=True,
            display_order=2,
            user_type_id=user_type_id,
            placeholder="Choose a language",
            options=["English", "Spanish"],
            encryption_enabled=False,
            include_in_chat=True,
        )

        response = self.client.post(
            "/internal/agent/admin-config/user-types",
            headers=self.headers,
            json={"actor": self.admin_actor},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tool"], "read_user_types")
        data = payload["data"]
        family = next(
            item for item in data["user_types"]
            if item["id"] == user_type_id
        )
        self.assertEqual(family["name"], "Family")
        self.assertEqual(family["icon"], "Heart")
        self.assertEqual(family["display_order"], 3)
        self.assertEqual(family["onboarding_fields"][0]["id"], field_id)
        question = next(
            item for item in data["onboarding_questions"]
            if item["id"] == field_id
        )
        self.assertEqual(question["user_type_id"], user_type_id)
        self.assertEqual(question["name"], "preferred_language")
        self.assertEqual(question["label"], "Preferred language")
        self.assertEqual(question["field_type"], "select")
        self.assertTrue(question["required"])
        self.assertEqual(question["placeholder"], "Choose a language")
        self.assertEqual(question["options"], ["English", "Spanish"])
        self.assertTrue(question["include_in_chat"])
        self.assertEqual(data["limits"]["user_types_returned"], 1)
        self.assertEqual(data["limits"]["onboarding_questions_returned"], 1)

    def test_read_document_access_returns_global_and_user_type_effective_state(self) -> None:
        user_type_id = self.database.create_user_type(
            "Advocates",
            "People doing direct support work",
            icon="Users",
            display_order=5,
        )
        self.ingest_db.create_job(
            "doc-global",
            "Global Handbook.pdf",
            "/uploads/global.pdf",
            "default",
        )
        self.ingest_db.update_job_status(
            "doc-global",
            "completed",
            total_chunks=3,
            processed_chunks=3,
        )
        self.ingest_db.create_job(
            "doc-optional",
            "Optional Briefing.pdf",
            "/uploads/optional.pdf",
            "default",
        )
        self.ingest_db.update_job_status(
            "doc-optional",
            "completed",
            total_chunks=2,
            processed_chunks=2,
        )
        self.database.upsert_document_defaults(
            "doc-global",
            is_available=True,
            is_default_active=True,
            display_order=1,
            changed_by="abc123",
        )
        self.database.upsert_document_defaults(
            "doc-optional",
            is_available=True,
            is_default_active=False,
            display_order=2,
            changed_by="abc123",
        )
        self.database.upsert_document_defaults_override(
            "doc-optional",
            user_type_id,
            is_available=True,
            is_default_active=True,
            changed_by="abc123",
        )

        response = self.client.post(
            "/internal/agent/admin-config/document-access",
            headers=self.headers,
            json={"actor": self.admin_actor},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tool"], "read_document_access")
        self.assertEqual(payload["secret_policy"], {"mode": "masked"})
        data = payload["data"]
        self.assertEqual(data["global"]["available_document_ids"], ["doc-global", "doc-optional"])
        self.assertEqual(data["global"]["default_document_ids"], ["doc-global"])
        documents_by_id = {document["job_id"]: document for document in data["documents"]}
        self.assertEqual(documents_by_id["doc-global"]["filename"], "Global Handbook.pdf")
        self.assertEqual(documents_by_id["doc-global"]["status"], "completed")
        self.assertEqual(documents_by_id["doc-global"]["total_chunks"], 3)
        advocate_access = next(
            item for item in data["per_user_type"]
            if item["user_type_id"] == user_type_id
        )
        self.assertEqual(advocate_access["user_type_name"], "Advocates")
        self.assertEqual(
            advocate_access["available_document_ids"],
            ["doc-global", "doc-optional"],
        )
        self.assertEqual(
            advocate_access["default_document_ids"],
            ["doc-global", "doc-optional"],
        )
        effective_optional = next(
            document for document in advocate_access["documents"]
            if document["job_id"] == "doc-optional"
        )
        self.assertTrue(effective_optional["is_override"])
        self.assertTrue(effective_optional["is_default_active"])
        self.assertEqual(data["limits"]["documents_returned"], 2)
        self.assertEqual(data["limits"]["user_types_returned"], 1)

    def test_read_onboarding_status_returns_setup_flags_and_guided_checklist(self) -> None:
        user_type_id = self.database.create_user_type(
            "Family",
            "Family members seeking support",
            icon="Heart",
            display_order=3,
        )
        self.database.create_field_definition(
            "preferred_language",
            "select",
            required=True,
            user_type_id=user_type_id,
            options=["English", "Spanish"],
            include_in_chat=True,
        )
        self.database.update_settings({
            "instance_name": "FreeThem",
            "assistant_name": "Ally",
            "header_tagline": "Political Prisoner Support Team.",
            "description": "Support families and organizers.",
            "primary_color": "#8B5CF6",
            "default_theme": "dark",
            "auto_approve_users": "true",
        })
        self.database.mark_onboarding_configured_keys([
            "instance_name",
            "assistant_name",
            "header_tagline",
            "description",
            "primary_color",
            "default_theme",
            "auto_approve_users",
        ])

        response = self.client.post(
            "/internal/agent/admin-config/onboarding-status",
            headers=self.headers,
            json={"actor": self.admin_actor},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tool"], "read_onboarding_status")
        data = payload["data"]
        self.assertTrue(data["instance"]["admin_exists"])
        self.assertTrue(data["instance"]["admin_initialized"])
        self.assertFalse(data["instance"]["setup_complete"])
        self.assertFalse(data["instance"]["ready_for_users"])
        self.assertEqual(data["instance"]["admin_count"], 1)
        guided = data["guided_bootstrap"]
        self.assertFalse(guided["complete"])
        self.assertIn("default_language", guided["missing_required_keys"])
        self.assertIn("instance_name", guided["configured_keys"])
        self.assertEqual(guided["configured_required_count"], 7)
        self.assertEqual(guided["required_count"], 8)
        self.assertEqual(data["limits"]["user_types_returned"], 1)
        self.assertEqual(data["limits"]["onboarding_questions_returned"], 1)

    def test_read_deployment_readiness_rejects_non_admin_actor(self) -> None:
        response = self.client.post(
            "/internal/agent/admin-config/deployment-readiness",
            headers=self.headers,
            json={
                "actor": {
                    "id": 42,
                    "type": "user",
                    "approved": True,
                    "email": "user@example.test",
                }
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("items", response.text)

    def test_read_deployment_readiness_rejects_unregistered_admin_actor(self) -> None:
        response = self.client.post(
            "/internal/agent/admin-config/deployment-readiness",
            headers=self.headers,
            json={
                "actor": {
                    "id": 999,
                    "type": "admin",
                    "approved": True,
                    "pubkey": "not-the-admin",
                }
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("items", response.text)
