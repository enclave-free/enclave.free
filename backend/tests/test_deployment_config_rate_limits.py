from __future__ import annotations

import importlib
import hashlib
import json
import os
import sys
import tempfile
import unittest
from base64 import b64encode
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from Crypto.Cipher import AES


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DeploymentConfigRateLimitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_enclave_env = os.environ.get("ENCLAVE_ENV")
        self._orig_mock_email = os.environ.get("MOCK_EMAIL")
        self._orig_mock_smtp = os.environ.get("MOCK_SMTP")
        self._orig_llm_api_key = os.environ.get("LLM_API_KEY")
        self._orig_llm_api_url = os.environ.get("LLM_API_URL")
        self._orig_llm_model = os.environ.get("LLM_MODEL")
        self._orig_embedding_model = os.environ.get("EMBEDDING_MODEL")
        self._orig_protected_inference_bypass = os.environ.get("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS")
        self._orig_simulate_user_auth = os.environ.get("SIMULATE_USER_AUTH")
        self._orig_simulate_admin_auth = os.environ.get("SIMULATE_ADMIN_AUTH")
        self._orig_rate_limit_backend = os.environ.get("RATE_LIMIT_BACKEND")
        self._orig_rate_limit_valkey_url = os.environ.get("RATE_LIMIT_VALKEY_URL")
        self._orig_session_cookie_secure = os.environ.get("SESSION_COOKIE_SECURE")
        self._orig_backend_reload = os.environ.get("BACKEND_RELOAD")
        self._orig_internal_agent_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        self._orig_published_service_host = os.environ.get("PUBLISHED_SERVICE_HOST")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        os.environ["MOCK_EMAIL"] = "false"
        os.environ.pop("LLM_API_KEY", None)
        os.environ.pop("LLM_API_URL", None)
        os.environ.pop("LLM_MODEL", None)
        os.environ.pop("EMBEDDING_MODEL", None)
        os.environ.pop("MOCK_SMTP", None)
        os.environ.pop("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS", None)
        os.environ.pop("SIMULATE_USER_AUTH", None)
        os.environ.pop("SIMULATE_ADMIN_AUTH", None)
        os.environ.pop("RATE_LIMIT_BACKEND", None)
        os.environ.pop("RATE_LIMIT_VALKEY_URL", None)
        os.environ.pop("SESSION_COOKIE_SECURE", None)
        os.environ.pop("BACKEND_RELOAD", None)
        os.environ.pop("INTERNAL_AGENT_TOKEN", None)
        os.environ.pop("PUBLISHED_SERVICE_HOST", None)

        import auth
        import database
        import deployment_config

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.deployment_config = importlib.reload(deployment_config)
        self.database.init_schema()
        self.deployment_config._sync_env_to_db()

        app = FastAPI()
        app.include_router(self.deployment_config.router)
        app.include_router(self.deployment_config.internal_router)
        app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("ENCLAVE_ENV", self._orig_enclave_env)
        self._restore_env("MOCK_EMAIL", self._orig_mock_email)
        self._restore_env("MOCK_SMTP", self._orig_mock_smtp)
        self._restore_env("LLM_API_KEY", self._orig_llm_api_key)
        self._restore_env("LLM_API_URL", self._orig_llm_api_url)
        self._restore_env("LLM_MODEL", self._orig_llm_model)
        self._restore_env("EMBEDDING_MODEL", self._orig_embedding_model)
        self._restore_env("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS", self._orig_protected_inference_bypass)
        self._restore_env("SIMULATE_USER_AUTH", self._orig_simulate_user_auth)
        self._restore_env("SIMULATE_ADMIN_AUTH", self._orig_simulate_admin_auth)
        self._restore_env("RATE_LIMIT_BACKEND", self._orig_rate_limit_backend)
        self._restore_env("RATE_LIMIT_VALKEY_URL", self._orig_rate_limit_valkey_url)
        self._restore_env("SESSION_COOKIE_SECURE", self._orig_session_cookie_secure)
        self._restore_env("BACKEND_RELOAD", self._orig_backend_reload)
        self._restore_env("INTERNAL_AGENT_TOKEN", self._orig_internal_agent_token)
        self._restore_env("PUBLISHED_SERVICE_HOST", self._orig_published_service_host)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_rate_limit_config_rejects_non_positive_and_non_integer_values(self) -> None:
        for key in self.deployment_config.RATE_LIMIT_KEYS:
            for value in ("", "   ", "0", "-1", "abc"):
                with self.subTest(key=key, value=value):
                    response = self.client.put(
                        f"/admin/deployment/config/{key}",
                        json={"value": value},
                    )

                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["detail"], f"{key} must be a positive integer")

    def test_rate_limit_config_persists_positive_integer_values(self) -> None:
        for key in self.deployment_config.RATE_LIMIT_KEYS:
            with self.subTest(key=key):
                response = self.client.put(
                    f"/admin/deployment/config/{key}",
                    json={"value": "42"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["key"], key)
                self.assertEqual(response.json()["value"], "42")

    def test_rate_limit_backend_accepts_memory_or_valkey_only(self) -> None:
        for value in ("memory", "valkey"):
            with self.subTest(value=value):
                response = self.client.put(
                    "/admin/deployment/config/RATE_LIMIT_BACKEND",
                    json={"value": value},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["value"], value)

        response = self.client.put(
            "/admin/deployment/config/RATE_LIMIT_BACKEND",
            json={"value": "postgres"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "RATE_LIMIT_BACKEND must be memory or valkey")

    def test_production_validation_rejects_testing_only_flags(self) -> None:
        os.environ["ENCLAVE_ENV"] = "production"
        self.database.update_deployment_config("MOCK_EMAIL", "true", "admin-pubkey")

        response = self.client.post("/admin/deployment/config/validate")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["valid"])
        self.assertIn("MOCK_EMAIL must be disabled in production", body["errors"])

    def test_production_validation_requires_shared_rate_limit_store(self) -> None:
        os.environ["ENCLAVE_ENV"] = "production"
        self.database.upsert_deployment_config(
            "RATE_LIMIT_BACKEND",
            "memory",
            is_secret=False,
            requires_restart=True,
            category="security",
            description="Shared rate limit backend: memory or valkey",
            changed_by="admin-pubkey",
        )

        response = self.client.post("/admin/deployment/config/validate")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["valid"])
        self.assertIn("RATE_LIMIT_BACKEND must be valkey in production", body["errors"])

    def test_production_validation_reports_network_and_tls_misconfiguration(self) -> None:
        os.environ["ENCLAVE_ENV"] = "production"
        for key, value, category in (
            ("RATE_LIMIT_BACKEND", "valkey", "security"),
            ("RATE_LIMIT_VALKEY_URL", "redis://valkey:6379/0", "security"),
            ("INSTANCE_URL", "http://example.com", "domains"),
            ("API_BASE_URL", "http://api.example.com", "domains"),
            ("ADMIN_BASE_URL", "http://admin.example.com", "domains"),
            ("FRONTEND_URL", "http://example.com", "security"),
            ("FORCE_HTTPS", "false", "ssl"),
            ("HSTS_MAX_AGE", "0", "ssl"),
            ("TRUSTED_PROXIES", "", "ssl"),
            ("LLM_API_URL", "http://models.example.com/v1", "llm"),
            ("EMBEDDING_API_URL", "http://tinfoil-proxy:8089/v1", "embedding"),
        ):
            self.database.upsert_deployment_config(
                key,
                value,
                is_secret=False,
                requires_restart=True,
                category=category,
                description=key,
                changed_by="admin-pubkey",
            )

        response = self.client.post("/admin/deployment/config/validate")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["valid"])
        self.assertIn("INSTANCE_URL must use HTTPS in production", body["errors"])
        self.assertIn("API_BASE_URL must use HTTPS in production", body["errors"])
        self.assertIn("ADMIN_BASE_URL must use HTTPS in production", body["errors"])
        self.assertIn("FRONTEND_URL must use HTTPS in production", body["errors"])
        self.assertIn("FORCE_HTTPS must be enabled in production", body["errors"])
        self.assertIn("HSTS_MAX_AGE must be at least 31536000 in production", body["errors"])
        self.assertIn("TRUSTED_PROXIES should name the TLS-terminating reverse proxy in production", body["warnings"])
        self.assertIn("LLM_API_URL must use HTTPS for external provider endpoints in production", body["errors"])
        self.assertNotIn("EMBEDDING_API_URL must use HTTPS for internal Compose endpoint tinfoil-proxy", body["errors"])

    def test_production_validation_rejects_weak_secrets_and_dev_runtime_modes(self) -> None:
        os.environ["ENCLAVE_ENV"] = "production"
        os.environ["SECRET_KEY"] = "replace-this-with-a-long-random-secret"
        os.environ["SIMULATE_USER_AUTH"] = "true"
        os.environ["SIMULATE_ADMIN_AUTH"] = "true"
        os.environ["PROTECTED_INFERENCE_DEVELOPMENT_BYPASS"] = "true"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        os.environ["BACKEND_RELOAD"] = "true"
        os.environ["PUBLISHED_SERVICE_HOST"] = "0.0.0.0"
        for key, value, category in (
            ("RATE_LIMIT_BACKEND", "valkey", "security"),
            ("RATE_LIMIT_VALKEY_URL", "redis://valkey:6379/0", "security"),
            ("INSTANCE_URL", "https://example.com", "domains"),
            ("API_BASE_URL", "https://api.example.com", "domains"),
            ("ADMIN_BASE_URL", "https://admin.example.com", "domains"),
            ("FRONTEND_URL", "https://example.com", "security"),
            ("FORCE_HTTPS", "true", "ssl"),
            ("HSTS_MAX_AGE", "31536000", "ssl"),
            ("LLM_API_URL", "https://models.example.com/v1", "llm"),
        ):
            self.database.upsert_deployment_config(
                key,
                value,
                is_secret=False,
                requires_restart=True,
                category=category,
                description=key,
                changed_by="admin-pubkey",
            )

        response = self.client.post("/admin/deployment/config/validate")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["valid"])
        self.assertIn("SECRET_KEY must be strong, stable, and managed outside the image in production", body["errors"])
        self.assertIn("SIMULATE_USER_AUTH must be disabled in production", body["errors"])
        self.assertIn("SIMULATE_ADMIN_AUTH must be disabled in production", body["errors"])
        self.assertIn("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS must be disabled in production", body["errors"])
        self.assertIn("SESSION_COOKIE_SECURE must not be disabled in production", body["errors"])
        self.assertIn("BACKEND_RELOAD must be disabled in production", body["errors"])
        self.assertIn("Published service host 0.0.0.0 requires an explicit production exposure review", body["warnings"])

        os.environ["PUBLISHED_SERVICE_HOST"] = "::"
        response = self.client.post("/admin/deployment/config/validate")

        self.assertIn(
            "Published service host :: requires an explicit production exposure review",
            response.json()["warnings"],
        )

    def test_operational_readiness_exposes_monitoring_and_recovery_drills(self) -> None:
        response = self.client.get("/admin/deployment/operational-readiness")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        monitoring = {item["category"]: item for item in body["runtime_alerting"]}
        self.assertEqual(
            set(monitoring),
            {"repeated_auth_failures", "unusual_admin_actions", "destructive_endpoint_usage"},
        )
        for item in monitoring.values():
            self.assertEqual(item["owner"], "operator")
            self.assertIn("audit", item["evidence_source"].lower())
            self.assertIn("alert", item["verification"])

        backup_targets = {item["target"]: item for item in body["backup_restore_verification"]["targets"]}
        self.assertIn("sqlite_database", backup_targets)
        self.assertIn("deployment_config", backup_targets)
        self.assertIn("uploads_directory", backup_targets)
        self.assertIn("retrieval_index", backup_targets)
        self.assertIn("restore drill", body["backup_restore_verification"]["evidence"])

        self.assertIn("incident_response", body)
        self.assertIn("key_recovery", body["incident_response"]["runbooks"])
        self.assertIn("docs/admin-key-recovery-runbook.md", body["incident_response"]["runbooks"]["key_recovery"])
        self.assertIn("checklist", body["drill_evidence"])

    def test_deployment_readiness_treats_verifiable_inference_as_deferred_warning(self) -> None:
        response = self.client.get("/admin/deployment/readiness")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "warnings")
        self.assertEqual(body["summary"]["blockers"], 0)
        self.assertGreaterEqual(body["summary"]["warnings"], 1)

        items_by_key = {item["key"]: item for item in body["items"]}
        for item in items_by_key.values():
            self.assertEqual(
                item["label_key"],
                f"adminDeployment.readiness.{item['key']}.label",
            )
            self.assertTrue(item["summary_key"].startswith("adminDeployment.readiness."))
            self.assertTrue(item["summary_key"].endswith(".summary"))
            self.assertTrue(item["next_action_key"].startswith("adminDeployment.readiness."))
            self.assertTrue(item["next_action_key"].endswith(".nextAction"))
            self.assertIsInstance(item["summary_values"], dict)
            self.assertIsInstance(item["next_action_values"], dict)
        self.assertEqual(items_by_key["verifiable_inference"]["severity"], "warning")
        self.assertEqual(items_by_key["verifiable_inference"]["source"], "inference_verification")
        self.assertEqual(items_by_key["verifiable_inference"]["status"], "deferred_missing")
        self.assertIn("deferred for this prototype", items_by_key["verifiable_inference"]["summary"])
        self.assertFalse(items_by_key["verifiable_inference"]["conversation_blocking"])

        self.assertEqual(items_by_key["lifecycle_readiness"]["severity"], "warning")
        self.assertEqual(items_by_key["lifecycle_readiness"]["source"], "lifecycle_readiness")
        self.assertIn("unsupported Deployment Surface", items_by_key["lifecycle_readiness"]["summary"])
        self.assertFalse(items_by_key["lifecycle_readiness"]["conversation_blocking"])

        self.assertEqual(items_by_key["backup_restore_drill"]["severity"], "warning")
        self.assertEqual(items_by_key["backup_restore_drill"]["source"], "operational_readiness")
        self.assertIn("restore drill", items_by_key["backup_restore_drill"]["summary"])
        self.assertNotIn("deployment_surface_acknowledgements", items_by_key)
        self.assertNotIn("sage_runtime_env", items_by_key)
        self.assertNotIn("core_backend_runtime_env", items_by_key)
        self.assertNotIn("service_health", items_by_key)

    def test_readiness_items_reject_undeclared_localization_keys(self) -> None:
        item_kwargs = {
            "label": "Test readiness item",
            "source": "test",
            "severity": "info",
            "summary": "Summary",
            "next_action": "Next action",
        }

        with self.assertRaisesRegex(ValueError, "Undeclared Deployment Readiness item"):
            self.deployment_config._readiness_item(
                key="new_unregistered_item",
                status="current",
                **item_kwargs,
            )

        with self.assertRaisesRegex(ValueError, "Undeclared Deployment Readiness status"):
            self.deployment_config._readiness_item(
                key="restart_required",
                status="new_unregistered_status",
                **item_kwargs,
            )

    def test_deployment_readiness_counts_unacknowledged_unsupported_surfaces(self) -> None:
        lifecycle_status = {
            "lifecycle_readiness": {"status": "reviewed"},
            "unsupported_deployment_surface_categories": [
                {
                    "category": "runtime",
                    "label": "Runtime artifacts",
                    "acknowledged": True,
                },
            ],
            "unsupported_deployment_surfaces": [
                {
                    "key": "session_logs",
                    "label": "Session logs",
                    "acknowledged": False,
                },
            ],
        }
        item = self.deployment_config._unsupported_surface_readiness_item(lifecycle_status)

        self.assertEqual(item["severity"], "warning")
        self.assertEqual(item["status"], "needs_acknowledgement")
        self.assertIn("1 unsupported Deployment Surface entries", item["summary"])

        lifecycle_item = self.deployment_config._lifecycle_readiness_item(lifecycle_status)
        self.assertEqual(lifecycle_item["key"], "lifecycle_readiness")
        self.assertEqual(lifecycle_item["label"], "Data Lifecycle Review")
        self.assertEqual(lifecycle_item["severity"], "warning")
        self.assertIn("1 unsupported Deployment Surface", lifecycle_item["summary"])
        self.assertEqual(
            lifecycle_item["summary_key"],
            "adminDeployment.readiness.deployment_surface_acknowledgements.status.needs_acknowledgement.summary",
        )
        self.assertEqual(lifecycle_item["summary_values"], {"count": 1})

    def test_deployment_readiness_reports_current_verifiable_inference_as_ready(self) -> None:
        from datetime import datetime, timezone

        self.database.upsert_deployment_config("LLM_PROVIDER", "sage", category="llm")
        self.database.upsert_deployment_config("LLM_API_URL", "https://inference.tinfoil.sh/v1", category="llm")
        self.database.upsert_deployment_config("LLM_MODEL", "kimi-k2-6", category="llm")
        self.database.create_inference_verification_record(
            provider_identity="sage",
            provider_endpoint="https://inference.tinfoil.sh/v1",
            model_identifier="kimi-k2-6",
            status="success",
            trigger="manual",
            expected_claims_fingerprint=self.deployment_config.current_expected_claims_fingerprint(),
            actual_claims_fingerprint="actual",
            verifier_version="test-verifier/1",
            attestation_material={"quote": "full"},
            checked_at=datetime.now(timezone.utc),
        )

        response = self.client.get("/admin/deployment/readiness")

        self.assertEqual(response.status_code, 200)
        items_by_key = {item["key"]: item for item in response.json()["items"]}
        self.assertEqual(items_by_key["verifiable_inference"]["severity"], "ready")
        self.assertFalse(items_by_key["verifiable_inference"]["conversation_blocking"])

    def test_simulated_auth_flags_are_not_exposed_as_config(self) -> None:
        os.environ["SIMULATE_USER_AUTH"] = "true"
        os.environ["SIMULATE_ADMIN_AUTH"] = "true"

        response = self.client.get("/admin/deployment/config")

        self.assertEqual(response.status_code, 200)
        exposed_keys = {
            item["key"]
            for section in response.json().values()
            if isinstance(section, list)
            for item in section
        }
        self.assertNotIn("SIMULATE_USER_AUTH", exposed_keys)
        self.assertNotIn("SIMULATE_ADMIN_AUTH", exposed_keys)

    def test_mock_email_is_the_only_supported_mock_mail_config_key(self) -> None:
        os.environ["MOCK_SMTP"] = "true"
        os.environ["MOCK_EMAIL"] = "false"

        import config_loader

        self.config_loader = importlib.reload(config_loader)
        self.config_loader.invalidate_cache()

        response = self.client.get("/admin/deployment/config")

        self.assertEqual(response.status_code, 200)
        email_keys = {item["key"] for item in response.json()["email"]}
        self.assertIn("MOCK_EMAIL", email_keys)
        self.assertNotIn("MOCK_SMTP", email_keys)
        self.assertFalse(self.config_loader.get_smtp_config()["mock_mode"])

    def test_protected_inference_development_bypass_is_not_exposed_as_config(self) -> None:
        os.environ["PROTECTED_INFERENCE_DEVELOPMENT_BYPASS"] = "true"

        response = self.client.get("/admin/deployment/config")

        self.assertEqual(response.status_code, 200)
        exposed_keys = {
            item["key"]
            for section in response.json().values()
            if isinstance(section, list)
            for item in section
        }
        self.assertNotIn("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS", exposed_keys)

    def test_full_sensitive_audit_log_detail_retention_is_not_exposed_as_config(self) -> None:
        response = self.client.get("/admin/deployment/config")

        self.assertEqual(response.status_code, 200)
        exposed_keys = {
            item["key"]
            for section in response.json().values()
            if isinstance(section, list)
            for item in section
        }
        self.assertNotIn("AUDIT_LOG_RETAIN_FULL_DETAIL", exposed_keys)
        self.assertNotIn("AUDIT_LOG_DISABLE_DETAIL_COMPACTION", exposed_keys)

    def test_llm_provider_rejects_maple_compatibility_label(self) -> None:
        response = self.client.put(
            "/admin/deployment/config/LLM_PROVIDER",
            json={"value": "maple"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], 'LLM_PROVIDER only supports "sage"')

    def test_empty_llm_api_key_update_preserves_existing_secret(self) -> None:
        self.database.update_deployment_config("LLM_API_KEY", "configured-secret", "admin-pubkey")

        response = self.client.put(
            "/admin/deployment/config/LLM_API_KEY",
            json={"value": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.get_deployment_config_value("LLM_API_KEY"), "configured-secret")

    def test_llm_api_key_reveal_returns_startup_synced_runtime_secret(self) -> None:
        os.environ["LLM_API_KEY"] = "env-only-key"

        with TestClient(self.client.app) as client:
            response = client.get("/admin/deployment/config/LLM_API_KEY/reveal")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"key": "LLM_API_KEY", "value": "env-only-key"})

    def test_startup_sync_exposes_runtime_llm_api_key_in_admin_config(self) -> None:
        os.environ["LLM_API_KEY"] = "env-only-key"

        with TestClient(self.client.app) as client:
            response = client.get("/admin/deployment/config")

        self.assertEqual(response.status_code, 200)
        llm_items = {item["key"]: item for item in response.json()["llm"]}
        self.assertEqual(llm_items["LLM_API_KEY"]["value"], "********")

    def test_sage_runtime_env_export_maps_desired_deployment_settings_and_audits_export(self) -> None:
        for key, value in (
            ("LLM_API_URL", "https://tinfoil.example/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi k2"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "https://app.example"),
            ("CORS_ORIGINS", "https://app.example,https://admin.example"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")

        response = self.client.get("/admin/deployment/config/runtime-env/sage")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        body = response.text
        self.assertIn("# Enclave Sage Runtime Env", body)
        self.assertIn("TINFOIL_API_URL=https://tinfoil.example/v1", body)
        self.assertIn("TINFOIL_API_KEY=configured-secret", body)
        self.assertIn('TINFOIL_MODEL="kimi k2"', body)
        self.assertIn("TINFOIL_EMBEDDING_MODEL=nomic-embed-text", body)
        self.assertIn("FRONTEND_URL=https://app.example", body)
        self.assertIn("CORS_ORIGINS=https://app.example,https://admin.example", body)
        self.assertIn("SEARXNG_URL=http://searxng:8080", body)

        audit_entry = self.database.get_config_audit_log(limit=1, table_name="deployment_config")[0]
        self.assertEqual(audit_entry["config_key"], self.deployment_config.SAGE_RUNTIME_ENV_EXPORT_KEY)
        self.assertNotIn("configured-secret", audit_entry["new_value"])
        self.assertEqual(audit_entry["changed_by"], "admin-pubkey")

    def test_core_backend_runtime_env_export_maps_desired_settings_and_reports_generated_status(self) -> None:
        for key, value in (
            ("LLM_API_URL", "https://tinfoil.example/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi k2"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "https://app.example"),
            ("CORS_ORIGINS", "https://app.example,https://admin.example"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")

        initial = self.deployment_config._runtime_env_comparison_status()
        self.assertEqual(initial["core_backend"]["generated"]["status"], "not_generated")

        response = self.client.get("/admin/deployment/config/runtime-env/core-backend")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        body = response.text
        self.assertIn("# Enclave Core Backend Runtime Env", body)
        self.assertIn("LLM_API_URL=https://tinfoil.example/v1", body)
        self.assertIn("LLM_API_KEY=configured-secret", body)
        self.assertIn('LLM_MODEL="kimi k2"', body)
        self.assertIn("EMBEDDING_MODEL=nomic-embed-text", body)
        self.assertIn("FRONTEND_URL=https://app.example", body)
        self.assertIn("CORS_ORIGINS=https://app.example,https://admin.example", body)
        self.assertIn("SEARXNG_URL=http://searxng:8080", body)
        self.assertNotIn("DATABASE_URL", body)
        self.assertNotIn("INTERNAL_AGENT_TOKEN", body)
        self.assertNotIn("SECRET_KEY", body)

        current = self.deployment_config._runtime_env_comparison_status()
        self.assertEqual(current["core_backend"]["generated"]["status"], "current")

        audit_entry = self.database.get_config_audit_log(limit=1, table_name="deployment_config")[0]
        self.assertEqual(audit_entry["config_key"], self.deployment_config.CORE_BACKEND_RUNTIME_ENV_EXPORT_KEY)
        self.assertNotIn("configured-secret", audit_entry["new_value"])
        self.assertEqual(audit_entry["changed_by"], "admin-pubkey")

        self.database.update_deployment_config("FRONTEND_URL", "https://new.example", "admin-pubkey")
        stale = self.deployment_config._runtime_env_comparison_status()
        self.assertEqual(stale["core_backend"]["generated"]["status"], "stale")

    def test_smtp_import_time_constants_are_not_exported(self) -> None:
        for name in (
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
            "SMTP_FROM",
            "SMTP_TIMEOUT",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(self.auth, name))

    def test_deployment_secret_decryption_rejects_legacy_key_material(self) -> None:
        plaintext = "old-secret-value"
        legacy_key = hashlib.sha256(
            f"{'san' + 'ctum'}-deployment-config:test-secret".encode("utf-8")
        ).digest()
        nonce = b"0" * self.database.DEPLOYMENT_SECRET_NONCE_BYTES
        cipher = AES.new(legacy_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
        legacy_encrypted = (
            f"{self.database.DEPLOYMENT_SECRET_PREFIX}"
            f"{b64encode(nonce).decode('ascii')}:"
            f"{b64encode(tag).decode('ascii')}:"
            f"{b64encode(ciphertext).decode('ascii')}"
        )

        with self.assertRaises(ValueError):
            self.database._decrypt_deployment_secret_value(legacy_encrypted)

    def test_deployment_secret_migration_rejects_legacy_key_material(self) -> None:
        plaintext = "old-secret-value"
        legacy_key = hashlib.sha256(
            f"{'san' + 'ctum'}-deployment-config:test-secret".encode("utf-8")
        ).digest()
        nonce = b"1" * self.database.DEPLOYMENT_SECRET_NONCE_BYTES
        cipher = AES.new(legacy_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
        legacy_encrypted = (
            f"{self.database.DEPLOYMENT_SECRET_PREFIX}"
            f"{b64encode(nonce).decode('ascii')}:"
            f"{b64encode(tag).decode('ascii')}:"
            f"{b64encode(ciphertext).decode('ascii')}"
        )

        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE deployment_config SET value = ? WHERE key = 'LLM_API_KEY'",
                (legacy_encrypted,),
            )

        with self.assertRaises(RuntimeError):
            self.database._migrate_encrypt_deployment_config_secrets()

        with self.database.get_cursor() as cursor:
            cursor.execute("SELECT value FROM deployment_config WHERE key = 'LLM_API_KEY'")
            stored = cursor.fetchone()["value"]
        self.assertEqual(stored, legacy_encrypted)

    def test_deployment_secret_decryption_accepts_canonical_key_material(self) -> None:
        encrypted = self.database._encrypt_deployment_secret_value("current-secret-value")

        self.assertEqual(
            self.database._decrypt_deployment_secret_value(encrypted),
            "current-secret-value",
        )

    def test_deployment_readiness_reports_stale_sage_runtime_env_after_source_change(self) -> None:
        item = self.deployment_config._runtime_env_readiness_item()
        self.assertEqual(item["status"], "not_generated")

        export_response = self.client.get("/admin/deployment/config/runtime-env/sage")
        self.assertEqual(export_response.status_code, 200)

        item = self.deployment_config._runtime_env_readiness_item()
        self.assertEqual(item["status"], "current")

        update_response = self.client.put("/admin/deployment/config/LLM_MODEL", json={"value": "new-model"})
        self.assertEqual(update_response.status_code, 200)

        item = self.deployment_config._runtime_env_readiness_item()
        self.assertEqual(item["status"], "stale")
        self.assertEqual(item["severity"], "warning")

    def test_deployment_readiness_reports_drifted_running_sage_runtime_config(self) -> None:
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")
        export_response = self.client.get("/admin/deployment/config/runtime-env/sage")
        self.assertEqual(export_response.status_code, 200)

        running_config = {
            "TINFOIL_API_URL": "http://tinfoil-proxy:8089/v1",
            "TINFOIL_API_KEY": {
                "configured": True,
                "fingerprint": hashlib.sha256(b"configured-secret").hexdigest(),
            },
            "TINFOIL_MODEL": "different-model",
            "TINFOIL_EMBEDDING_MODEL": "nomic-embed-text",
            "FRONTEND_URL": "http://localhost:5173",
            "CORS_ORIGINS": ["http://localhost:5173"],
            "SEARXNG_URL": "http://searxng:8080",
        }

        item = self.deployment_config._runtime_env_readiness_item(running_config)

        self.assertEqual(item["status"], "drifted")
        self.assertEqual(item["severity"], "warning")
        self.assertIn("differs from desired Deployment Settings", item["summary"])
        self.assertIn("Investigate Sage runtime config drift", item["next_action"])

    def test_deployment_readiness_reports_matching_running_sage_runtime_config(self) -> None:
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")
        export_response = self.client.get("/admin/deployment/config/runtime-env/sage")
        self.assertEqual(export_response.status_code, 200)

        running_config = {
            "TINFOIL_API_URL": "http://tinfoil-proxy:8089/v1",
            "TINFOIL_API_KEY": {
                "configured": True,
                "fingerprint": hashlib.sha256(b"configured-secret").hexdigest(),
            },
            "TINFOIL_MODEL": "kimi-k2-6",
            "TINFOIL_EMBEDDING_MODEL": "nomic-embed-text",
            "FRONTEND_URL": "http://localhost:5173",
            "CORS_ORIGINS": ["http://localhost:5173"],
            "SEARXNG_URL": "http://searxng:8080",
        }

        item = self.deployment_config._runtime_env_readiness_item(running_config)

        self.assertEqual(item["status"], "matches_desired")
        self.assertEqual(item["severity"], "ready")
        self.assertIn("matches desired Deployment Settings", item["summary"])

    def test_deployment_readiness_reports_drifted_running_core_backend_runtime_config(self) -> None:
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")
        export_response = self.client.get("/admin/deployment/config/runtime-env/core-backend")
        self.assertEqual(export_response.status_code, 200)

        running_config = {
            "LLM_API_URL": "http://tinfoil-proxy:8089/v1",
            "LLM_API_KEY": {
                "configured": True,
                "fingerprint": hashlib.sha256(b"configured-secret").hexdigest(),
            },
            "LLM_MODEL": "different-model",
            "EMBEDDING_MODEL": "nomic-embed-text",
            "FRONTEND_URL": "http://localhost:5173",
            "CORS_ORIGINS": ["http://localhost:5173"],
            "SEARXNG_URL": "http://searxng:8080",
        }

        item = self.deployment_config._core_backend_runtime_env_readiness_item(running_config)

        self.assertEqual(item["key"], "core_backend_runtime_env")
        self.assertEqual(item["status"], "drifted")
        self.assertEqual(item["severity"], "warning")
        self.assertIn("differs from desired Deployment Settings", item["summary"])
        self.assertIn("apply the generated core-backend env", item["next_action"])

    def test_deployment_readiness_reports_stale_core_backend_runtime_env_after_source_change(self) -> None:
        item = self.deployment_config._core_backend_runtime_env_readiness_item()
        self.assertEqual(item["status"], "not_generated")
        self.assertEqual(item["severity"], "warning")
        self.assertIn("core-backend runtime env", item["next_action"])

        export_response = self.client.get("/admin/deployment/config/runtime-env/core-backend")
        self.assertEqual(export_response.status_code, 200)

        item = self.deployment_config._core_backend_runtime_env_readiness_item()
        self.assertEqual(item["status"], "current")

        update_response = self.client.put("/admin/deployment/config/LLM_MODEL", json={"value": "new-model"})
        self.assertEqual(update_response.status_code, 200)

        item = self.deployment_config._core_backend_runtime_env_readiness_item()
        self.assertEqual(item["status"], "stale")
        self.assertEqual(item["severity"], "warning")
        self.assertIn("fresh core-backend runtime env", item["next_action"])

    def test_deployment_readiness_endpoint_excludes_runtime_env_artifacts(self) -> None:
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")
        export_response = self.client.get("/admin/deployment/config/runtime-env/sage")
        self.assertEqual(export_response.status_code, 200)

        async def fake_running_config():
            return {
                "TINFOIL_API_URL": "http://tinfoil-proxy:8089/v1",
                "TINFOIL_API_KEY": {
                    "configured": True,
                    "fingerprint": hashlib.sha256(b"configured-secret").hexdigest(),
                },
                "TINFOIL_MODEL": "different-model",
                "TINFOIL_EMBEDDING_MODEL": "nomic-embed-text",
                "FRONTEND_URL": "http://localhost:5173",
                "CORS_ORIGINS": ["http://localhost:5173"],
                "SEARXNG_URL": "http://searxng:8080",
            }

        original_fetch = getattr(self.deployment_config, "_fetch_sage_running_runtime_config", None)
        self.deployment_config._fetch_sage_running_runtime_config = fake_running_config
        try:
            response = self.client.get("/admin/deployment/readiness")
        finally:
            if original_fetch is None:
                delattr(self.deployment_config, "_fetch_sage_running_runtime_config")
            else:
                self.deployment_config._fetch_sage_running_runtime_config = original_fetch

        self.assertEqual(response.status_code, 200)
        items_by_key = {item["key"]: item for item in response.json()["items"]}
        self.assertNotIn("sage_runtime_env", items_by_key)
        self.assertNotIn("core_backend_runtime_env", items_by_key)

    def test_service_health_includes_runtime_env_alignment_summary(self) -> None:
        comparison = self.deployment_config._runtime_env_comparison_status()

        self.assertIn("sage", comparison)
        self.assertIn("core_backend", comparison)
        self.assertEqual(comparison["sage"]["generated"]["status"], "not_generated")
        self.assertEqual(comparison["sage"]["desired"]["total_keys"], 7)
        self.assertEqual(comparison["sage"]["running"]["status"], "not_directly_introspected")
        self.assertEqual(comparison["core_backend"]["generated"]["status"], "not_generated")
        self.assertEqual(comparison["core_backend"]["desired"]["total_keys"], 7)
        self.assertEqual(comparison["core_backend"]["running"]["status"], "not_directly_introspected")

        export_response = self.client.get("/admin/deployment/config/runtime-env/sage")
        self.assertEqual(export_response.status_code, 200)

        comparison = self.deployment_config._runtime_env_comparison_status()
        self.assertEqual(comparison["sage"]["generated"]["status"], "current")

    def test_service_health_includes_core_backend_running_alignment(self) -> None:
        os.environ["INTERNAL_AGENT_TOKEN"] = "internal-test-token"
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")
        os.environ["LLM_API_URL"] = "http://running-core-backend:8080/v1"
        os.environ["LLM_API_KEY"] = "configured-secret"
        os.environ["LLM_MODEL"] = "running-model"
        os.environ["EMBEDDING_MODEL"] = "running-embedding"

        async def fake_sage_config():
            return None

        original_fetch = self.deployment_config._fetch_sage_running_runtime_config
        self.deployment_config._fetch_sage_running_runtime_config = fake_sage_config
        try:
            response = self.client.get("/admin/deployment/health")
        finally:
            self.deployment_config._fetch_sage_running_runtime_config = original_fetch

        self.assertEqual(response.status_code, 200)
        core_backend = response.json()["runtime_env"]["core_backend"]
        self.assertEqual(core_backend["running"]["status"], "drifted")
        self.assertNotIn("configured-secret", json.dumps(core_backend))

    def test_runtime_env_alignment_compares_running_sage_fingerprint_without_secrets(self) -> None:
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")

        running_config = {
            "TINFOIL_API_URL": "http://tinfoil-proxy:8089/v1",
            "TINFOIL_API_KEY": {
                "configured": True,
                "fingerprint": __import__("hashlib").sha256(b"configured-secret").hexdigest(),
            },
            "TINFOIL_MODEL": "kimi-k2-6",
            "TINFOIL_EMBEDDING_MODEL": "nomic-embed-text",
            "FRONTEND_URL": "http://localhost:5173",
            "CORS_ORIGINS": ["http://localhost:5173"],
            "SEARXNG_URL": "http://searxng:8080",
        }

        comparison = self.deployment_config._runtime_env_comparison_status(running_config)

        self.assertEqual(comparison["sage"]["running"]["status"], "matches_desired")
        self.assertNotIn("configured-secret", str(comparison))

        running_config["TINFOIL_MODEL"] = "different-model"
        comparison = self.deployment_config._runtime_env_comparison_status(running_config)
        self.assertEqual(comparison["sage"]["running"]["status"], "drifted")

    def test_runtime_env_alignment_compares_running_core_backend_fingerprint_without_secrets(self) -> None:
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")

        running_config = {
            "LLM_API_URL": "http://tinfoil-proxy:8089/v1",
            "LLM_API_KEY": {
                "configured": True,
                "fingerprint": hashlib.sha256(b"configured-secret").hexdigest(),
            },
            "LLM_MODEL": "kimi-k2-6",
            "EMBEDDING_MODEL": "nomic-embed-text",
            "FRONTEND_URL": "http://localhost:5173",
            "CORS_ORIGINS": ["http://localhost:5173"],
            "SEARXNG_URL": "http://searxng:8080",
        }

        comparison = self.deployment_config._runtime_env_comparison_status(
            running_core_backend_config=running_config
        )

        self.assertEqual(comparison["core_backend"]["running"]["status"], "matches_desired")
        self.assertEqual(comparison["core_backend"]["desired"]["total_keys"], 7)
        self.assertNotIn("configured-secret", str(comparison))

        running_config["LLM_MODEL"] = "different-model"
        comparison = self.deployment_config._runtime_env_comparison_status(
            running_core_backend_config=running_config
        )
        self.assertEqual(comparison["core_backend"]["running"]["status"], "drifted")

    def test_core_backend_runtime_fingerprint_requires_internal_token_and_hides_secret(self) -> None:
        os.environ["INTERNAL_AGENT_TOKEN"] = "internal-test-token"
        for key, value in (
            ("LLM_API_URL", "http://tinfoil-proxy:8089/v1"),
            ("LLM_API_KEY", "configured-secret"),
            ("LLM_MODEL", "kimi-k2-6"),
            ("EMBEDDING_MODEL", "nomic-embed-text"),
            ("FRONTEND_URL", "http://localhost:5173"),
            ("CORS_ORIGINS", "http://localhost:5173"),
            ("SEARXNG_URL", "http://searxng:8080"),
        ):
            self.database.update_deployment_config(key, value, "admin-pubkey")
        os.environ["LLM_API_URL"] = "http://running-core-backend:8080/v1"
        os.environ["LLM_API_KEY"] = "configured-secret"
        os.environ["LLM_MODEL"] = "running-model"
        os.environ["EMBEDDING_MODEL"] = "running-embedding"

        misplaced = self.client.get("/admin/deployment/internal/runtime-config/fingerprint")
        self.assertEqual(misplaced.status_code, 404)

        missing = self.client.get("/internal/runtime-config/fingerprint")
        self.assertEqual(missing.status_code, 403)

        wrong = self.client.get(
            "/internal/runtime-config/fingerprint",
            headers={"X-Internal-Agent-Token": "wrong-token"},
        )
        self.assertEqual(wrong.status_code, 403)

        response = self.client.get(
            "/internal/runtime-config/fingerprint",
            headers={"X-Internal-Agent-Token": "internal-test-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["service"], "core-backend")
        self.assertEqual(payload["runtime_config"]["LLM_API_URL"], "http://running-core-backend:8080/v1")
        self.assertEqual(payload["runtime_config"]["LLM_MODEL"], "running-model")
        self.assertEqual(payload["runtime_config"]["EMBEDDING_MODEL"], "running-embedding")
        self.assertEqual(payload["runtime_config"]["LLM_API_KEY"]["configured"], True)
        self.assertEqual(
            payload["runtime_config"]["LLM_API_KEY"]["fingerprint"],
            hashlib.sha256(b"configured-secret").hexdigest(),
        )
        self.assertNotIn("configured-secret", response.text)


if __name__ == "__main__":
    unittest.main()
