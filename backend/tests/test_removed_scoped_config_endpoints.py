from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class RemovedScopedConfigEndpointsTest(unittest.TestCase):
    """Verifies scoped prompt-context endpoints are absent after the Tool loop hard cut."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_internal_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_coincurve = sys.modules.get("coincurve")
        self._orig_python_multipart = sys.modules.get("python_multipart")
        self._orig_lifecycle = sys.modules.get("lifecycle")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["INTERNAL_AGENT_TOKEN"] = "test-internal-token"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        sys.modules["coincurve"] = self._fake_coincurve_module()
        sys.modules["python_multipart"] = type(
            "FakePythonMultipart", (), {"__version__": "0.0.99"}
        )
        sys.modules["lifecycle"] = self._fake_lifecycle_module()

        import auth
        import database
        import internal_agent
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.internal_agent = importlib.reload(internal_agent)
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
        self._restore_env("INTERNAL_AGENT_TOKEN", self._orig_internal_token)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_module("coincurve", self._orig_coincurve)
        self._restore_module("python_multipart", self._orig_python_multipart)
        self._restore_module("lifecycle", self._orig_lifecycle)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
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

    @staticmethod
    def _fake_coincurve_module() -> object:
        class PrivateKey:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

        class PublicKey:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

        class PublicKeyXOnly:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def verify(self, *_args: object, **_kwargs: object) -> bool:
                return True

        return type(
            "FakeCoincurve",
            (),
            {
                "PrivateKey": PrivateKey,
                "PublicKey": PublicKey,
                "PublicKeyXOnly": PublicKeyXOnly,
            },
        )

    @staticmethod
    def _fake_lifecycle_module() -> object:
        async def close_sage_client() -> None:
            return None

        return type(
            "FakeLifecycle",
            (),
            {"router": APIRouter(), "close_sage_client": close_sage_client},
        )

    def test_public_scoped_config_context_endpoint_is_removed(self) -> None:
        response = self.client.post(
            "/admin/scoped-config-context",
            json={"query": "what still needs setup?", "mode": "auto"},
        )

        self.assertIn(response.status_code, {404, 405})
        self.assertNotIn("SCOPED CONFIG CONTEXT", response.text)

    def test_internal_scoped_config_context_endpoint_is_removed(self) -> None:
        app = FastAPI()
        app.include_router(self.internal_agent.router)
        client = TestClient(app)

        response = client.post(
            "/internal/agent/scoped-config-context",
            headers={"X-Internal-Agent-Token": "test-internal-token"},
            json={
                "query": "what still needs setup?",
                "actor": {
                    "id": 1,
                    "type": "admin",
                    "approved": True,
                    "pubkey": "admin-pubkey",
                },
                "mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("SCOPED CONFIG CONTEXT", response.text)

    def test_admin_document_context_preview_endpoint_is_removed(self) -> None:
        response = self.client.get("/ingest/admin/documents/context-preview")

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("BOUNDED DOCUMENT CONTEXT", response.text)

    def test_python_helper_registry_does_not_expose_admin_config_classifier(self) -> None:
        import tools
        import tools.registry

        importlib.reload(tools.registry)
        reloaded_tools = importlib.reload(tools)

        registry = reloaded_tools.init_tools()

        self.assertNotIn("admin-config", registry.tool_ids)
