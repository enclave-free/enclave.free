"""
Contract tests for the Sage-only Scoped Config Context internal endpoint.

Issues #312–#314: internal contract, instance-settings scope, and remaining scopes.
"""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class ScopedConfigContextContractTest(unittest.TestCase):
    """Verifies POST /internal/agent/scoped-config-context contract behavior."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_internal_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["INTERNAL_AGENT_TOKEN"] = "test-internal-token"

        import database
        import internal_agent

        self.database = importlib.reload(database)
        self.internal_agent = importlib.reload(internal_agent)
        self.database.init_schema()

        app = FastAPI()
        app.include_router(self.internal_agent.router)
        self.client = TestClient(app)
        self.headers = {"X-Internal-Agent-Token": "test-internal-token"}
        self.admin_payload = {
            "query": "what tools do you have?",
            "actor": {
                "id": 1,
                "type": "admin",
                "approved": True,
                "pubkey": "abc123",
            },
            "mode": "auto",
        }

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("INTERNAL_AGENT_TOKEN", self._orig_internal_token)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_missing_internal_token_returns_403_without_context(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            json=self.admin_payload,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid internal agent token")
        self.assertNotIn("context_text", response.text)

    def test_non_admin_actor_is_rejected_without_context(self) -> None:
        payload = {
            **self.admin_payload,
            "actor": {
                "id": 42,
                "type": "user",
                "approved": True,
                "email": "user@example.com",
                "user_type_id": 1,
            },
        }
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json=payload,
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())
        self.assertNotIn("context_text", response.text)

    def test_overview_response_includes_required_contract_fields(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={**self.admin_payload, "mode": "overview"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["primary_scope"], "overview")
        self.assertEqual(body["included_scopes"], ["overview"])
        self.assertIsInstance(body["context_text"], str)
        self.assertTrue(body["context_text"].startswith("SCOPED CONFIG CONTEXT"))
        self.assertEqual(body["secret_policy"], {"mode": "masked"})
        self.assertIsInstance(body["generated_at"], str)
        self.assertEqual(body["warnings"], [])
        self.assertEqual(len(body["sections"]), 1)
        self.assertEqual(body["sections"][0]["scope"], "overview")

    def test_overview_mode_includes_control_contract_and_instance_summary(self) -> None:
        self.database.update_setting("instance_name", "Free Them")
        self.database.update_setting("assistant_name", "Enclave Assistant")

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={**self.admin_payload, "mode": "overview"},
        )

        self.assertEqual(response.status_code, 200)
        context_text = response.json()["context_text"]
        self.assertIn("ADMIN-VISIBLE TOOL CAPABILITIES", context_text)
        self.assertIn("admin-config", context_text)
        self.assertIn("CHANGESET FORMAT", context_text)
        self.assertIn("INSTANCE OVERVIEW (/admin/settings)", context_text)
        self.assertIn("instance_name: Free Them", context_text)
        self.assertIn("assistant_name: Enclave Assistant", context_text)

    def test_agent_settings_includes_global_ai_config(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "change the admin prompt and max tokens",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "agent-settings")
        self.assertEqual(body["included_scopes"], ["agent-settings"])
        self.assertEqual(body["warnings"], [])
        context_text = body["context_text"]
        self.assertIn("AGENT SETTINGS (/admin/ai-config)", context_text)
        self.assertIn("prompt_system", context_text)
        self.assertIn("max_tokens", context_text)
        section = next(item for item in body["sections"] if item["scope"] == "agent-settings")
        self.assertIn("prompt_system", section["content"])

    def test_deployment_settings_masks_secret_values(self) -> None:
        self.database.upsert_deployment_config(
            key="SMTP_PASSWORD",
            value="super-secret-smtp-password",
            is_secret=True,
            requires_restart=True,
            category="email",
            description="SMTP password",
            changed_by="test-admin",
        )
        self.database.upsert_deployment_config(
            key="LLM_PROVIDER",
            value="sage",
            is_secret=False,
            requires_restart=False,
            category="llm",
            description="Model provider",
            changed_by="test-admin",
        )

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "change the smtp email provider settings",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "deployment-settings")
        self.assertEqual(body["warnings"], [])
        context_text = body["context_text"]
        self.assertIn("DEPLOYMENT SETTINGS (email)", context_text)
        self.assertIn("SMTP_PASSWORD", context_text)
        self.assertIn("secret=true", context_text)
        self.assertIn("[REDACTED]", context_text)
        self.assertNotIn("super-secret-smtp-password", context_text)

    def test_user_types_includes_types_and_fields(self) -> None:
        type_id = self.database.create_user_type(
            name="Bitcoin Designer",
            description="Design-focused users",
            icon="User",
            display_order=0,
        )
        self.database.create_field_definition(
            field_name="Focus Area",
            field_type="select",
            user_type_id=type_id,
            options=["UX", "Research"],
        )

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "add onboarding questions for user types",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "user-types")
        context_text = body["context_text"]
        self.assertIn("USER TYPES (/admin/user-types)", context_text)
        self.assertIn("Bitcoin Designer", context_text)
        self.assertIn("USER FIELDS (user_type_id=", context_text)
        self.assertIn("Focus Area", context_text)

    def test_document_defaults_includes_global_and_per_type_defaults(self) -> None:
        type_id = self.database.create_user_type(name="Advocate", display_order=0)

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "update document access defaults for ingestion",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "document-defaults")
        context_text = body["context_text"]
        self.assertIn("DOCUMENT DEFAULTS (/ingest/admin/documents/defaults)", context_text)
        self.assertIn(f"user_type_id={type_id}", context_text)

    def test_health_scope_includes_service_health_context(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "check deployment readiness and service health",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "health")
        context_text = body["context_text"]
        self.assertIn("SERVICE HEALTH (/admin/deployment/health)", context_text)
        self.assertIn("RESTART-REQUIRED DEPLOYMENT KEYS", context_text)
        section = next(item for item in body["sections"] if item["scope"] == "health")
        self.assertIn("live_service_probes", section["content"])

    def test_cross_boundary_query_includes_multiple_scopes(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "check deployment health and restart the model provider env settings",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "health")
        self.assertEqual(
            body["included_scopes"],
            ["health", "deployment-settings"],
        )
        context_text = body["context_text"]
        self.assertIn("SERVICE HEALTH (/admin/deployment/health)", context_text)
        self.assertIn("DEPLOYMENT SETTINGS", context_text)

    def test_requested_scopes_merge_with_classified_primary_scope(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "change the admin prompt and max tokens",
                "mode": "auto",
                "requested_scopes": ["deployment-settings"],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "agent-settings")
        self.assertEqual(
            body["included_scopes"],
            ["agent-settings", "deployment-settings"],
        )
        context_text = body["context_text"]
        self.assertIn("AGENT SETTINGS (/admin/ai-config)", context_text)
        self.assertIn("DEPLOYMENT SETTINGS", context_text)

    def test_partial_user_type_read_failure_returns_warning_without_failing(self) -> None:
        type_id = self.database.create_user_type(name="Broken Type", display_order=0)
        original_get_field_definitions = self.database.get_field_definitions

        def failing_get_field_definitions(user_type_id: int | None = None, include_global: bool = True):
            if user_type_id == type_id:
                raise RuntimeError("simulated user-fields failure")
            return original_get_field_definitions(user_type_id, include_global=include_global)

        self.database.get_field_definitions = failing_get_field_definitions

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "review onboarding fields for user types",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(any("user-fields user_type_id=" in warning for warning in body["warnings"]))
        self.assertIn("USER TYPES (/admin/user-types)", body["context_text"])
        self.assertIn("WARNINGS", body["context_text"])

    def test_large_user_type_fanout_is_bounded_with_warning(self) -> None:
        for index in range(12):
            self.database.create_user_type(name=f"Type {index}", display_order=index)

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "review onboarding fields for all user types",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(
            any("user-types reduced to first 10 user types of 12 total" in warning for warning in body["warnings"])
        )
        field_sections = body["context_text"].count("USER FIELDS (user_type_id=")
        self.assertEqual(field_sections, 10)

    def test_theme_query_classifies_to_instance_settings(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "update all theme configurations for this instance",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["primary_scope"], "instance-settings")
        self.assertEqual(body["warnings"], [])

    def test_instance_settings_includes_branding_theme_and_copy_keys(self) -> None:
        self.database.update_setting("instance_name", "Free Them")
        self.database.update_setting("description", "PPST support instance")
        self.database.update_setting("assistant_name", "Sage")
        self.database.update_setting("default_theme", "dark")

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "make the theme dark and update the instance copy",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        context_text = body["context_text"]
        for key in (
            "instance_name",
            "description",
            "logo_url",
            "assistant_name",
            "user_label",
            "header_tagline",
            "default_theme",
            "primary_color",
            "chat_bubble_style",
            "chat_bubble_shadow",
            "surface_style",
            "status_icon_set",
            "typography_preset",
        ):
            self.assertIn(key, context_text)

        section = next(item for item in body["sections"] if item["scope"] == "instance-settings")
        field_keys = {field["key"] for field in section["fields"]}
        self.assertTrue(field_keys.issuperset({
            "instance_name",
            "description",
            "default_theme",
            "typography_preset",
        }))

    def test_instance_settings_explains_partial_put_admin_settings_mutation(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "change the primary color and chat bubble style",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        context_text = response.json()["context_text"]
        self.assertIn("partial PUT /admin/settings", context_text)
        self.assertIn('"path": "/admin/settings"', context_text)
        self.assertNotIn("/admin/settings/default_theme", context_text)
        self.assertNotIn("/admin/settings/primary_color", context_text)

    def test_copy_query_classifies_to_instance_settings(self) -> None:
        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "update the header tagline and user label copy",
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["primary_scope"], "instance-settings")

    def test_instance_settings_structured_fields_include_mutation_guidance(self) -> None:
        self.database.update_setting("header_tagline", "Support political prisoners")

        response = self.client.post(
            "/internal/agent/scoped-config-context",
            headers=self.headers,
            json={
                **self.admin_payload,
                "query": "change the header tagline",
                "mode": "auto",
            },
        )

        section = next(
            item for item in response.json()["sections"] if item["scope"] == "instance-settings"
        )
        tagline_field = next(field for field in section["fields"] if field["key"] == "header_tagline")
        self.assertEqual(tagline_field["current_value"], "Support political prisoners")
        self.assertEqual(tagline_field["mutation"], "PUT /admin/settings")
        self.assertIn("valid_values", tagline_field)


if __name__ == "__main__":
    unittest.main()
