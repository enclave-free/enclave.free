import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class InstanceStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_llm_api_key = os.environ.get("LLM_API_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        os.environ["LLM_API_KEY"] = "test-key"

        import database
        import inference_repair
        import main
        import auth

        self.database = importlib.reload(database)
        self.inference_repair = importlib.reload(inference_repair)
        self.auth = importlib.reload(auth)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.database.upsert_deployment_config("LLM_PROVIDER", "sage", category="llm")
        self.database.upsert_deployment_config("LLM_API_URL", "https://inference.tinfoil.sh/v1", category="llm")
        self.database.upsert_deployment_config("LLM_MODEL", "kimi-k2-6", category="llm")
        self.database.upsert_deployment_config("LLM_API_KEY", "test-key", category="llm", is_secret=True)
        self.main.app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "user",
            "id": 1,
            "email": "user@example.test",
            "user_type_id": None,
        }
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.main.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.main.app.dependency_overrides[self.main.deployment_config.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        for route in self.main.app.routes:
            dependant = getattr(route, "dependant", None)
            if dependant is None:
                continue
            for dependency in dependant.dependencies:
                call = getattr(dependency, "call", None)
                if getattr(call, "__name__", None) == "require_admin":
                    self.main.app.dependency_overrides[call] = lambda: {
                        "type": "admin",
                        "pubkey": "admin-pubkey",
                    }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self.database._deployment_secret_key = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("LLM_API_KEY", self._orig_llm_api_key)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_instance_status_reports_degraded_protected_inference(self) -> None:
        self.inference_repair.mark_startup_verification_unavailable(
            status="missing",
            reason="LLM_API_KEY not configured",
        )

        response = self.client.get("/instance/status")

        self.assertEqual(response.status_code, 200)
        protected = response.json()["protected_inference"]
        self.assertEqual(protected["mode"], "degraded_admin_repair")
        self.assertFalse(protected["protected_inference_available"])
        self.assertEqual(protected["reason"], "LLM_API_KEY not configured")

    def test_degraded_admin_repair_keeps_diagnostics_available(self) -> None:
        class FakeProvider:
            name = "sage"

            def health_check(self) -> bool:
                return False

            def complete(self, *_args, **_kwargs):
                raise AssertionError("diagnostic health failure should not generate text")

        self.inference_repair.mark_startup_verification_unavailable(
            status="missing",
            reason="LLM_API_KEY not configured",
        )
        self.main.get_sage_provider = lambda: FakeProvider()

        response = self.client.get("/llm/test")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["provider"], "sage")

    def test_manual_verification_recovery_updates_public_product_status(self) -> None:
        from inference_verification import InferenceVerificationResult

        expected_fingerprint = self.main.deployment_config.current_expected_claims_fingerprint()

        class FakeVerifier:
            def verify(self, **kwargs):
                return InferenceVerificationResult(
                    provider_identity=kwargs["provider_identity"],
                    provider_endpoint=kwargs["provider_endpoint"],
                    model_identifier=kwargs["model_identifier"],
                    status="success",
                    trigger=kwargs["trigger"],
                    expected_claims_fingerprint=expected_fingerprint,
                    actual_claims_fingerprint="actual",
                    verifier_version="fake-verifier/1",
                    attestation_material={"quote": "manual-repair"},
                )

        self.inference_repair.mark_startup_verification_unavailable(
            status="missing",
            reason="LLM_API_KEY not configured",
        )
        self.main.deployment_config.TinfoilVerifier = lambda: FakeVerifier()

        verify_response = self.client.post("/admin/deployment/inference-verification/verify")
        status_response = self.client.get("/instance/status")

        self.assertEqual(verify_response.status_code, 200)
        protected = status_response.json()["protected_inference"]
        self.assertEqual(protected["mode"], "normal")
        self.assertTrue(protected["protected_inference_available"])
        self.assertEqual(protected["reason"], "manual_verification_current")

    def test_admin_language_and_theme_defaults_are_public_instance_settings(self) -> None:
        update = self.client.put("/admin/settings", json={
            "instance_name": "Operator Desk",
            "default_language": "es",
            "default_theme": "dark",
        })

        public_settings = self.client.get("/settings/public").json()["settings"]
        status_settings = self.client.get("/instance/status").json()["settings"]

        self.assertEqual(update.status_code, 200)
        self.assertEqual(public_settings["instance_name"], "Operator Desk")
        self.assertEqual(public_settings["default_language"], "es")
        self.assertEqual(public_settings["default_theme"], "dark")
        self.assertEqual(status_settings["default_language"], "es")
        self.assertEqual(status_settings["default_theme"], "dark")

    def test_admin_language_and_theme_defaults_reject_unknown_values(self) -> None:
        language_response = self.client.put("/admin/settings", json={
            "default_language": "klingon",
            "default_theme": "dark",
        })
        theme_response = self.client.put("/admin/settings", json={
            "default_language": "en",
            "default_theme": "neon",
        })

        self.assertEqual(language_response.status_code, 422)
        self.assertIn("default_language must be one of", language_response.text)
        self.assertEqual(theme_response.status_code, 422)
        self.assertIn("default_theme must be one of", theme_response.text)


if __name__ == "__main__":
    unittest.main()
