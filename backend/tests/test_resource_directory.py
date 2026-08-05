from __future__ import annotations

import importlib
import os
import sqlite3
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
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._original_env = {
            name: os.environ.get(name)
            for name in ("SQLITE_PATH", "SECRET_KEY", "UPLOADS_DIR", "INTERNAL_AGENT_TOKEN")
        }
        self._original_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        os.environ["SQLITE_PATH"] = str(self.db_path)
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

    def _create_ready(
        self,
        resource_id: str,
        *,
        kind: str = "organization",
        tags: list[str] | None = None,
        pointers: list[dict] | None = None,
        regions: list[dict] | None = None,
        languages: list[str] | None = None,
        verified: bool = False,
        display_order: int = 0,
    ) -> dict:
        return self.database.create_resource(
            resource_id=resource_id,
            name=resource_id.replace("-", " ").title(),
            kind=kind,
            description="A curated resource used for testing.",
            tags=tags or ["legal"],
            pointers=pointers
            or [{"type": "url", "value": f"https://{resource_id}.example.test"}],
            regions=regions or [{"level": "global", "code": None}],
            languages=languages or ["en"],
            provenance={
                "verified_at": "2026-01-01T00:00:00Z" if verified else None,
                "vetted_by": "Admin",
            },
            display_order=display_order,
        )

    def _resource_schema(self) -> tuple[list[str], set[str]]:
        with self.database.get_cursor() as cursor:
            cursor.execute("PRAGMA table_info(resources)")
            columns = [row["name"] for row in cursor.fetchall()]
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            tables = {row["name"] for row in cursor.fetchall()}
        return columns, tables

    def _replace_with_legacy_schema(self) -> None:
        with self.database.get_cursor() as cursor:
            cursor.execute("DROP TABLE resources")
            cursor.execute(
                """
                CREATE TABLE resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    resource_type TEXT,
                    description TEXT,
                    contact TEXT,
                    languages TEXT,
                    scope_level TEXT,
                    scope_code TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    verified_at TIMESTAMP,
                    vetted_by TEXT,
                    source_note TEXT,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE help_types (
                    key TEXT PRIMARY KEY,
                    label TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE resource_help_types (
                    resource_id TEXT NOT NULL,
                    help_type TEXT NOT NULL,
                    PRIMARY KEY (resource_id, help_type)
                )
                """
            )
            cursor.execute("INSERT INTO help_types (key, label) VALUES ('legal', 'Legal')")
            cursor.executemany(
                """
                INSERT INTO resources (
                    resource_id, name, resource_type, description, contact, languages,
                    scope_level, scope_code, status, verified_at, vetted_by, source_note,
                    display_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "legacy-ready",
                        "Legacy Ready",
                        "hotline",
                        None,
                        '{"phone":"+1 555 0100"}',
                        '["en"]',
                        "country",
                        "US",
                        "ready",
                        "2026-01-01T00:00:00Z",
                        "Admin",
                        "Imported",
                        3,
                    ),
                    (
                        "legacy-pending",
                        "Legacy Pending",
                        "manual",
                        "A complete but operator-held draft.",
                        '{"url":"https://manual.example.test"}',
                        '["es"]',
                        "global",
                        None,
                        "pending",
                        None,
                        None,
                        None,
                        4,
                    ),
                ],
            )
            cursor.execute(
                "INSERT INTO resource_help_types (resource_id, help_type) VALUES (?, ?)",
                ("legacy-ready", "legal"),
            )

    def test_fresh_database_uses_only_generic_resource_schema(self) -> None:
        columns, tables = self._resource_schema()

        self.assertEqual(
            columns,
            [
                "id",
                "resource_id",
                "name",
                "description",
                "languages",
                "status",
                "kind",
                "tags",
                "pointers",
                "regions",
                "provenance",
                "display_order",
                "created_at",
                "updated_at",
            ],
        )
        self.assertNotIn("help_types", tables)
        self.assertNotIn("resource_help_types", tables)

    def test_legacy_migration_is_idempotent_preserves_data_and_contracts_schema(self) -> None:
        self._replace_with_legacy_schema()

        self.database._migrate_resources_to_generic_contract()
        first = self.database.list_resources()
        first_schema = self._resource_schema()
        self.database._migrate_resources_to_generic_contract()
        second = self.database.list_resources()
        second_schema = self._resource_schema()

        self.assertEqual(first, second)
        self.assertEqual(first_schema, second_schema)
        by_id = {resource["resource_id"]: resource for resource in first}
        ready = by_id["legacy-ready"]
        self.assertEqual(ready["kind"], "service")
        self.assertEqual(ready["tags"], ["legacy_type:hotline", "legal"])
        self.assertEqual(ready["pointers"], [{"type": "phone", "value": "+1 555 0100"}])
        self.assertEqual(ready["regions"], [{"level": "country", "code": "US"}])
        self.assertEqual(ready["provenance"]["vetted_by"], "Admin")
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["display_order"], 3)
        self.assertEqual(by_id["legacy-pending"]["kind"], "reference")
        self.assertEqual(by_id["legacy-pending"]["status"], "pending")
        self.assertEqual(len(first), 2)
        self.assertNotIn("resource_type", first_schema[0])
        self.assertNotIn("help_types", first_schema[1])

    def test_fresh_and_upgraded_databases_converge_on_active_schema(self) -> None:
        fresh_schema = self._resource_schema()
        self._replace_with_legacy_schema()

        self.database._migrate_resources_to_generic_contract()

        self.assertEqual(self._resource_schema(), fresh_schema)

    def test_normal_sqlite_backup_preserves_pre_migration_state(self) -> None:
        self._replace_with_legacy_schema()
        backup_path = Path(self.tmp.name) / "pre-migration-backup.db"
        source = self.database.get_connection()
        backup = sqlite3.connect(backup_path)
        source.backup(backup)
        backup.close()

        self.database._migrate_resources_to_generic_contract()

        restored = sqlite3.connect(backup_path)
        try:
            columns = [row[1] for row in restored.execute("PRAGMA table_info(resources)")]
            row = restored.execute(
                "SELECT resource_type, contact, status FROM resources WHERE resource_id = ?",
                ("legacy-ready",),
            ).fetchone()
        finally:
            restored.close()
        self.assertIn("resource_type", columns)
        self.assertEqual(row, ("hotline", '{"phone":"+1 555 0100"}', "ready"))

    def test_generic_readiness_and_archive_lifecycle(self) -> None:
        pending = self.database.create_resource(
            resource_id="pending",
            name="Pending",
            kind="reference",
            description="Missing pointer.",
            pointers=[{"type": "url", "value": "   "}],
        )
        ready = self._create_ready("ready")
        archived = self.database.update_resource("ready", archived=True)

        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["pointers"], [])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(self.database.search_resources(limit=10), [])

    def test_search_exact_pointer_filters_ranks_and_paginates(self) -> None:
        self._create_ready(
            "global-verified",
            kind="reference",
            tags=["bitcoin", "education"],
            pointers=[{"type": "email", "value": "global@example.test"}],
            verified=True,
            display_order=0,
        )
        self._create_ready(
            "us-unverified",
            kind="reference",
            tags=["bitcoin", "education"],
            pointers=[{"type": "email", "value": "bitcoin@example.test"}],
            regions=[{"level": "country", "code": "US"}],
            languages=["es"],
            verified=False,
            display_order=1,
        )
        self._create_ready(
            "ca-reference",
            kind="reference",
            tags=["bitcoin"],
            regions=[{"level": "country", "code": "CA"}],
        )

        exact = self.database.search_resources(
            region="US",
            query="BITCOIN@EXAMPLE.TEST",
            kind="reference",
            tags=["bitcoin", "education"],
            language="es",
            limit=1,
            return_metadata=True,
        )
        page = self.database.search_resources(
            region="US",
            kind="reference",
            tags=["bitcoin"],
            limit=1,
            return_metadata=True,
        )

        self.assertEqual([item["resource_id"] for item in exact["resources"]], ["us-unverified"])
        self.assertEqual(exact["total_count"], 1)
        self.assertEqual([item["resource_id"] for item in page["resources"]], ["us-unverified"])
        self.assertEqual(page["total_count"], 2)
        self.assertTrue(page["has_more"])
        self.assertEqual(page["next_offset"], 1)

    def test_internal_search_returns_generic_contract_and_continuation(self) -> None:
        self._create_ready(
            "bitcoin-reference",
            kind="reference",
            tags=["bitcoin"],
            pointers=[{"type": "email", "label": "Questions", "value": "bitcoin@example.test"}],
            regions=[{"level": "country", "code": "US"}],
        )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={
                "query": "bitcoin@example.test",
                "kind": "reference",
                "tags": ["bitcoin"],
                "region": "United States",
                "limit": 10,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["resolved_country_code"], "US")
        self.assertEqual(body["returned_count"], 1)
        self.assertEqual(body["resources"][0]["kind"], "reference")
        self.assertEqual(
            body["resources"][0]["pointers"],
            [{"type": "email", "label": "Questions", "value": "bitcoin@example.test"}],
        )
        self.assertNotIn("help_type", body)
        self.assertNotIn("contact", body["resources"][0])

    def test_invalid_explicit_region_fails_closed(self) -> None:
        self._create_ready("global")

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"region": "not-a-real-region", "limit": 10},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Unknown resource region")

    def test_internal_search_requires_internal_token(self) -> None:
        response = self.client.post(
            "/internal/agent/resources/search",
            json={"kind": "reference"},
        )

        self.assertEqual(response.status_code, 403)

    def test_internal_search_rejects_removed_legacy_filters(self) -> None:
        for field, value in (("help_type", "legal"), ("jurisdiction", "US")):
            response = self.client.post(
                "/internal/agent/resources/search",
                headers=self.headers,
                json={field: value},
            )
            self.assertEqual(response.status_code, 422, (field, response.text))


if __name__ == "__main__":
    unittest.main()
