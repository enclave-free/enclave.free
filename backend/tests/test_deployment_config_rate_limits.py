from __future__ import annotations

import importlib
import hashlib
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
        self._orig_protected_inference_bypass = os.environ.get("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS")
        self._orig_simulate_user_auth = os.environ.get("SIMULATE_USER_AUTH")
        self._orig_simulate_admin_auth = os.environ.get("SIMULATE_ADMIN_AUTH")
        self._orig_rate_limit_backend = os.environ.get("RATE_LIMIT_BACKEND")
        self._orig_rate_limit_valkey_url = os.environ.get("RATE_LIMIT_VALKEY_URL")
        self._orig_session_cookie_secure = os.environ.get("SESSION_COOKIE_SECURE")
        self._orig_backend_reload = os.environ.get("BACKEND_RELOAD")
        self._orig_published_service_host = os.environ.get("PUBLISHED_SERVICE_HOST")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["MOCK_EMAIL"] = "false"
        os.environ.pop("LLM_API_KEY", None)
        os.environ.pop("MOCK_SMTP", None)
        os.environ.pop("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS", None)
        os.environ.pop("SIMULATE_USER_AUTH", None)
        os.environ.pop("SIMULATE_ADMIN_AUTH", None)
        os.environ.pop("RATE_LIMIT_BACKEND", None)
        os.environ.pop("RATE_LIMIT_VALKEY_URL", None)
        os.environ.pop("SESSION_COOKIE_SECURE", None)
        os.environ.pop("BACKEND_RELOAD", None)
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
        self._restore_env("PROTECTED_INFERENCE_DEVELOPMENT_BYPASS", self._orig_protected_inference_bypass)
        self._restore_env("SIMULATE_USER_AUTH", self._orig_simulate_user_auth)
        self._restore_env("SIMULATE_ADMIN_AUTH", self._orig_simulate_admin_auth)
        self._restore_env("RATE_LIMIT_BACKEND", self._orig_rate_limit_backend)
        self._restore_env("RATE_LIMIT_VALKEY_URL", self._orig_rate_limit_valkey_url)
        self._restore_env("SESSION_COOKIE_SECURE", self._orig_session_cookie_secure)
        self._restore_env("BACKEND_RELOAD", self._orig_backend_reload)
        self._restore_env("PUBLISHED_SERVICE_HOST", self._orig_published_service_host)
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

    def test_llm_api_key_read_does_not_fall_back_to_environment(self) -> None:
        os.environ["LLM_API_KEY"] = "env-only-key"

        response = self.client.get("/admin/deployment/config/LLM_API_KEY/reveal")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"key": "LLM_API_KEY", "value": ""})

    def test_startup_sync_does_not_persist_llm_api_key_from_environment(self) -> None:
        os.environ["LLM_API_KEY"] = "env-only-key"

        self.deployment_config._sync_env_to_db()

        self.assertEqual(self.database.get_deployment_config_value("LLM_API_KEY"), "")

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


if __name__ == "__main__":
    unittest.main()
