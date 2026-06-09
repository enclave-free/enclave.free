from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class ResourceDirectoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_internal_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
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

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("INTERNAL_AGENT_TOKEN", self._orig_internal_token)
        self._restore_sentence_transformers()
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def _restore_sentence_transformers(self) -> None:
        if self._orig_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._orig_sentence_transformers

    def _create_ready_resource(
        self,
        resource_id: str,
        *,
        scope_level: str,
        scope_code: str | None,
        languages: list[str],
        verified: bool,
        display_order: int = 0,
    ) -> None:
        self.database.create_resource(
            resource_id=resource_id,
            name=resource_id.replace("-", " ").title(),
            resource_type="ngo",
            description="Referral resource for testing.",
            contact={"url": f"https://{resource_id}.example"},
            languages=languages,
            scope_level=scope_level,
            scope_code=scope_code,
            help_types=["legal"],
            verified_at="2026-01-01T00:00:00Z" if verified else None,
            display_order=display_order,
        )

    def test_internal_resource_search_ranks_scope_before_verified_and_language(self) -> None:
        self._create_ready_resource(
            "global-spanish",
            scope_level="global",
            scope_code=None,
            languages=["es"],
            verified=True,
        )
        self._create_ready_resource(
            "central-america-spanish",
            scope_level="subregion",
            scope_code="013",
            languages=["es"],
            verified=True,
        )
        self._create_ready_resource(
            "nicaragua-spanish-unverified",
            scope_level="country",
            scope_code="NI",
            languages=["es"],
            verified=False,
        )
        self._create_ready_resource(
            "nicaragua-english-verified",
            scope_level="country",
            scope_code="NI",
            languages=["en"],
            verified=True,
        )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"help_type": "legal", "jurisdiction": "Nicaragua", "language": "es", "limit": 10},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["resolved_country_code"], "NI")
        self.assertEqual(
            [resource["resource_id"] for resource in body["resources"]],
            [
                "nicaragua-english-verified",
                "nicaragua-spanish-unverified",
                "central-america-spanish",
                "global-spanish",
            ],
        )

    def test_internal_resource_search_excludes_pending_resources(self) -> None:
        self.database.create_resource(
            resource_id="pending-legal",
            name="Pending Legal",
            resource_type="ngo",
            scope_level="country",
            scope_code="NI",
            help_types=["legal"],
        )
        self._create_ready_resource(
            "ready-legal",
            scope_level="country",
            scope_code="NI",
            languages=["es"],
            verified=False,
        )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"help_type": "legal", "jurisdiction": "NI", "limit": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [resource["resource_id"] for resource in response.json()["resources"]],
            ["ready-legal"],
        )

    def test_internal_resource_search_requires_internal_token(self) -> None:
        response = self.client.post(
            "/internal/agent/resources/search",
            json={"help_type": "legal", "jurisdiction": "NI"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid internal agent token")


if __name__ == "__main__":
    unittest.main()
