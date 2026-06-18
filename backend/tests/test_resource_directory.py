from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
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

    def test_resource_search_language_sort_uses_bounded_candidate_window(self) -> None:
        self._create_ready_resource(
            "nicaragua-english-one",
            scope_level="country",
            scope_code="NI",
            languages=["en"],
            verified=True,
            display_order=0,
        )
        self._create_ready_resource(
            "nicaragua-english-two",
            scope_level="country",
            scope_code="NI",
            languages=["en"],
            verified=True,
            display_order=1,
        )
        self._create_ready_resource(
            "nicaragua-spanish-three",
            scope_level="country",
            scope_code="NI",
            languages=["es"],
            verified=True,
            display_order=2,
        )

        resources = self.database.search_resources("NI", "legal", language="es", limit=2)

        self.assertEqual(resources[0]["resource_id"], "nicaragua-spanish-three")
        self.assertEqual(len(resources), 2)

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

    def test_notes_contact_counts_as_ready_contact_method(self) -> None:
        created = self.database.create_resource(
            resource_id="notes-only-contact",
            name="Notes Only Contact",
            resource_type="ngo",
            scope_level="global",
            contact={"notes": "Contact through the encrypted intake desk."},
            help_types=["legal"],
            verified_at="2026-01-01T00:00:00Z",
        )

        self.assertEqual(created["status"], "ready")
        self.assertEqual(created["missing_fields"], [])

    def test_utc_timestamp_helper_returns_true_utc_z_timestamp(self) -> None:
        timestamp = self.database.utc_timestamp_z()

        self.assertTrue(timestamp.endswith("Z"))
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_internal_resource_search_requires_internal_token(self) -> None:
        response = self.client.post(
            "/internal/agent/resources/search",
            json={"help_type": "legal", "jurisdiction": "NI"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid internal agent token")

    def test_internal_resource_search_rejects_blank_help_type(self) -> None:
        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"help_type": "   ", "jurisdiction": "NI"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "help_type is required")

    def test_internal_resource_search_trims_help_type_and_bounds_limit(self) -> None:
        original = self.database.search_resources
        captured: dict[str, object] = {}

        def fake_search_resources(**kwargs):
            captured.update(kwargs)
            return []

        self.database.search_resources = fake_search_resources
        try:
            response = self.client.post(
                "/internal/agent/resources/search",
                headers=self.headers,
                json={"help_type": " legal ", "jurisdiction": "NI", "limit": 999},
            )
        finally:
            self.database.search_resources = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["help_type"], "legal")
        self.assertEqual(captured["limit"], self.internal_agent.MAX_RESOURCE_SEARCH_LIMIT)

        self.database.search_resources = fake_search_resources
        try:
            response = self.client.post(
                "/internal/agent/resources/search",
                headers=self.headers,
                json={"help_type": "legal", "jurisdiction": "NI", "limit": 0},
            )
        finally:
            self.database.search_resources = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["limit"], 0)

    def test_resource_scope_validation_rejects_unknown_country_on_create_and_update(self) -> None:
        with self.assertRaises(ValueError):
            self.database.create_resource(
                resource_id="bad-country-create",
                name="Bad Country Create",
                resource_type="ngo",
                scope_level="country",
                scope_code="ZZ",
                contact={"url": "https://bad-country-create.example"},
                help_types=["legal"],
            )

        self._create_ready_resource(
            "valid-country",
            scope_level="global",
            scope_code=None,
            languages=["en"],
            verified=True,
        )

        with self.assertRaises(ValueError):
            self.database.update_resource(
                "valid-country",
                scope_level="country",
                scope_code="ZZ",
            )

        self.assertEqual(
            self.database.get_resource("valid-country")["scope_level"],
            "global",
        )

    def test_resource_create_normalizes_blank_resource_id_to_name_only(self) -> None:
        from models import ResourceCreate

        resource = ResourceCreate(resource_id="   ", name="Named Resource")

        self.assertIsNone(resource.resource_id)

    def test_region_data_accepts_western_europe_microstates(self) -> None:
        import region_data

        self.assertTrue(region_data.is_valid_scope("country", "LI"))
        self.assertTrue(region_data.is_valid_scope("country", "MC"))

    def test_global_scope_rejects_scope_code(self) -> None:
        import region_data

        self.assertTrue(region_data.is_valid_scope("global", None))
        self.assertTrue(region_data.is_valid_scope("global", ""))
        self.assertFalse(region_data.is_valid_scope("global", "US"))

    def test_resource_help_types_enforces_help_type_vocabulary_fk(self) -> None:
        self._create_ready_resource(
            "fk-resource",
            scope_level="global",
            scope_code=None,
            languages=["en"],
            verified=True,
        )

        with self.database.get_cursor() as cursor:
            cursor.execute("PRAGMA foreign_key_list(resource_help_types)")
            foreign_keys = cursor.fetchall()

        self.assertTrue(
            any(row["table"] == "help_types" and row["from"] == "help_type" for row in foreign_keys)
        )
        with self.assertRaises(self.database.sqlite3.IntegrityError):
            with self.database.get_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO resource_help_types (resource_id, help_type) VALUES (?, ?)",
                    ("fk-resource", "not-in-vocabulary"),
                )

    def test_resource_help_types_migration_drops_unknown_help_types(self) -> None:
        self._create_ready_resource(
            "migration-resource",
            scope_level="global",
            scope_code=None,
            languages=["en"],
            verified=True,
        )
        conn = self.database.get_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE resource_help_types")
        cursor.execute("""
            CREATE TABLE resource_help_types (
                resource_id TEXT NOT NULL,
                help_type TEXT NOT NULL,
                PRIMARY KEY (resource_id, help_type),
                FOREIGN KEY (resource_id) REFERENCES resources(resource_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(
            "INSERT INTO resource_help_types (resource_id, help_type) VALUES (?, ?)",
            ("migration-resource", "legal"),
        )
        cursor.execute(
            "INSERT INTO resource_help_types (resource_id, help_type) VALUES (?, ?)",
            ("migration-resource", "ghost-help-type"),
        )
        conn.commit()
        cursor.close()

        self.database.init_schema()

        with self.database.get_cursor() as cursor:
            cursor.execute(
                "SELECT help_type FROM resource_help_types WHERE resource_id = ? ORDER BY help_type",
                ("migration-resource",),
            )
            help_types = [row["help_type"] for row in cursor.fetchall()]
            cursor.execute("PRAGMA foreign_key_list(resource_help_types)")
            foreign_keys = cursor.fetchall()

        self.assertEqual(help_types, ["legal"])
        self.assertTrue(any(row["table"] == "help_types" for row in foreign_keys))

    def test_search_resources_applies_sql_level_limit(self) -> None:
        for index in range(3):
            self._create_ready_resource(
                f"limited-resource-{index}",
                scope_level="country",
                scope_code="NI",
                languages=["en"],
                verified=True,
                display_order=index,
            )

        statements: list[str] = []
        conn = self.database.get_connection()
        conn.set_trace_callback(statements.append)
        try:
            resources = self.database.search_resources("NI", "legal", limit=2)
        finally:
            conn.set_trace_callback(None)

        self.assertEqual(len(resources), 2)
        self.assertTrue(
            any(
                "FROM resources" in statement
                and "JOIN resource_help_types" in statement
                and "LIMIT 2" in statement
                for statement in statements
            )
        )

    def test_delete_help_type_recomputes_resource_status_after_cascade(self) -> None:
        self.database.upsert_help_type(
            key="transport",
            label="Transport",
            description="Travel support",
        )
        created = self.database.create_resource(
            resource_id="transport-ready",
            name="Transport Ready",
            resource_type="ngo",
            scope_level="global",
            contact={"url": "https://transport.example"},
            help_types=["transport"],
            verified_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(created["status"], "ready")

        self.assertTrue(self.database.delete_help_type("transport"))

        updated = self.database.get_resource("transport-ready")
        self.assertEqual(updated["help_types"], [])
        self.assertEqual(updated["status"], "pending")

    def test_jurisdiction_prefix_accepts_iso_code(self) -> None:
        self.assertEqual(
            self.database.normalize_jurisdiction("jurisdiction:NI"),
            "NI",
        )


if __name__ == "__main__":
    unittest.main()
