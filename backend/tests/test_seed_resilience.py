from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SeedResilienceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_seed_status_path = os.environ.get("SEED_STATUS_PATH")
        self._orig_enclave_env = os.environ.get("ENCLAVE_ENV")
        os.environ["SEED_STATUS_PATH"] = str(Path(self.tmp.name) / "seed_status.json")
        os.environ["ENCLAVE_ENV"] = "development"

        import seed_status

        self.seed_status = importlib.reload(seed_status)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        self._restore_env("SEED_STATUS_PATH", self._orig_seed_status_path)
        self._restore_env("ENCLAVE_ENV", self._orig_enclave_env)

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_development_embedding_quota_failure_records_degraded_seed_status(self) -> None:
        exc = RuntimeError("Tinfoil embedding request failed: insufficient_quota")

        self.assertTrue(
            self.seed_status.should_continue_after_qdrant_seed_failure(exc)
        )
        status = self.seed_status.write_degraded_seed_status(exc)

        self.assertEqual(status["status"], "degraded")
        self.assertEqual(status["reason"], "embedding_provider_unavailable")
        self.assertIn("Qdrant seed skipped", status["message"])
        self.assertNotIn("insufficient_quota", status["message"])
        self.assertEqual(self.seed_status.read_seed_status()["status"], "degraded")

    def test_production_embedding_quota_failure_still_fails_startup(self) -> None:
        os.environ["ENCLAVE_ENV"] = "production"

        self.assertFalse(
            self.seed_status.should_continue_after_qdrant_seed_failure(
                RuntimeError("Tinfoil embedding request failed: insufficient_quota")
            )
        )


if __name__ == "__main__":
    unittest.main()
