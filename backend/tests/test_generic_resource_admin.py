from __future__ import annotations

import importlib
import json
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


class GenericResourceAdminTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._original_env = {
            name: os.environ.get(name)
            for name in ("SQLITE_PATH", "SECRET_KEY", "UPLOADS_DIR", "INTERNAL_AGENT_TOKEN")
        }
        self._original_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")
        os.environ["INTERNAL_AGENT_TOKEN"] = "test-internal-token"

        import auth
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.main.app.dependency_overrides[self.auth.require_admin] = lambda: {
            "type": "admin",
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(self.main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        for name, value in self._original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if self._original_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._original_sentence_transformers
        self.tmp.cleanup()

    def test_admin_creates_generic_resource_and_audits_safe_pointer_facts(self) -> None:
        response = self.client.post(
            "/admin/resources",
            json={
                "resource_id": "bitcoin-guide",
                "name": "Bitcoin Guide",
                "kind": "reference",
                "tags": ["Bitcoin", " Education "],
                "description": "A curated Bitcoin reference.",
                "pointers": [
                    {
                        "type": "url",
                        "label": "Manual",
                        "value": "https://private.example.test/bitcoin",
                    }
                ],
                "regions": [{"level": "global", "code": None}],
                "languages": ["en"],
                "verified": True,
                "provenance": {
                    "vetted_by": "Melissa",
                    "source_note": "Customer manual",
                },
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["kind"], "reference")
        self.assertEqual(body["tags"], ["bitcoin", "education"])
        self.assertEqual(body["status"], "ready")
        self.assertIsNotNone(body["provenance"]["verified_at"])
        self.assertEqual(body["provenance"]["vetted_by"], "Melissa")

        entries = self.database.get_config_audit_log(limit=10, table_name="resources")
        self.assertEqual(len(entries), 1)
        audit_value = json.loads(entries[0]["new_value"])
        self.assertEqual(audit_value["kind"], "reference")
        self.assertEqual(audit_value["pointer_count"], 1)
        self.assertEqual(audit_value["pointers"], [{"label": "Manual", "type": "url"}])
        self.assertNotIn("private.example.test", entries[0]["new_value"])

    def test_admin_product_seam_supports_initial_generic_kinds(self) -> None:
        for kind in ("person", "product", "method", "reference"):
            response = self.client.post(
                "/admin/resources",
                json={
                    "resource_id": f"admin-{kind}",
                    "name": f"Admin {kind.title()}",
                    "kind": kind,
                    "description": f"A curated {kind} created through the Admin API.",
                    "tags": ["generic", kind],
                    "pointers": [
                        {
                            "type": "url",
                            "value": f"https://{kind}.example.test",
                        }
                    ],
                    "regions": [{"level": "global", "code": None}],
                },
            )

            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["kind"], kind)
            self.assertEqual(response.json()["status"], "ready")

        listed = self.client.get("/admin/resources")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(
            {resource["kind"] for resource in listed.json()["resources"]},
            {"person", "product", "method", "reference"},
        )
        searched = self.client.get(
            "/admin/resources",
            params={"query": "product.example.test", "kind": "product"},
        )
        self.assertEqual(searched.status_code, 200, searched.text)
        self.assertEqual(
            [resource["resource_id"] for resource in searched.json()["resources"]],
            ["admin-product"],
        )

    def test_partial_provenance_update_preserves_verification_and_vetter(self) -> None:
        create = self.client.post(
            "/admin/resources",
            json={
                "resource_id": "provenance-guide",
                "name": "Provenance Guide",
                "kind": "reference",
                "description": "A curated reference.",
                "pointers": [{"type": "url", "value": "https://example.test"}],
                "verified": True,
                "provenance": {"vetted_by": "Original", "source_note": "First"},
            },
        )
        self.assertEqual(create.status_code, 200, create.text)
        original = create.json()["provenance"]

        update = self.client.put(
            "/admin/resources/provenance-guide",
            json={"provenance": {"source_note": "Updated"}},
        )

        self.assertEqual(update.status_code, 200, update.text)
        provenance = update.json()["provenance"]
        self.assertEqual(provenance["verified_at"], original["verified_at"])
        self.assertEqual(provenance["vetted_by"], "Original")
        self.assertEqual(provenance["source_note"], "Updated")

    def test_admin_rejects_whitespace_only_pointer_values(self) -> None:
        response = self.client.post(
            "/admin/resources",
            json={
                "name": "Invalid Pointer",
                "kind": "reference",
                "description": "Invalid pointer test.",
                "pointers": [{"type": "url", "value": "   "}],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_admin_rejects_removed_legacy_resource_fields(self) -> None:
        for legacy_field, value in (
            ("resource_type", "ngo"),
            ("contact", {"email": "legacy@example.test"}),
            ("scope_level", "global"),
            ("scope_code", "US"),
            ("help_types", ["legal"]),
            ("verified_at", "2026-01-01T00:00:00Z"),
            ("vetted_by", "Legacy Admin"),
            ("source_note", "Legacy source"),
        ):
            response = self.client.post(
                "/admin/resources",
                json={
                    "name": "Legacy Payload",
                    "kind": "reference",
                    "description": "Must fail rather than silently ignore old inputs.",
                    "pointers": [{"type": "url", "value": "https://example.test"}],
                    legacy_field: value,
                },
            )
            self.assertEqual(response.status_code, 422, (legacy_field, response.text))

        self.assertFalse(
            any(route.path == "/admin/help-types" for route in self.main.app.routes)
        )


if __name__ == "__main__":
    unittest.main()
