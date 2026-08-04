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
            description="Encrypted intake instructions.",
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

    def test_legacy_resource_fields_expand_into_generic_contract(self) -> None:
        created = self.database.create_resource(
            resource_id="generic-expanded",
            name="Generic Expanded",
            resource_type="ngo",
            description="Trusted support organization.",
            contact={"email": "help@example.test", "url": "https://example.test"},
            languages=["en"],
            scope_level="global",
            help_types=["legal"],
            verified_at="2026-01-01T00:00:00Z",
            vetted_by="Admin",
            source_note="Customer-supplied directory",
        )

        self.assertEqual(created["kind"], "organization")
        self.assertEqual(created["tags"], ["legacy_type:ngo", "legal"])
        self.assertEqual(
            created["pointers"],
            [
                {"type": "email", "value": "help@example.test"},
                {"type": "url", "value": "https://example.test"},
            ],
        )
        self.assertEqual(created["regions"], [{"level": "global", "code": None}])
        self.assertEqual(
            created["provenance"],
            {
                "verified_at": "2026-01-01T00:00:00Z",
                "vetted_by": "Admin",
                "source_note": "Customer-supplied directory",
            },
        )

    def test_generic_resource_migration_is_idempotent_for_upgraded_databases(self) -> None:
        with self.database.get_cursor() as cursor:
            cursor.execute("DROP TABLE resource_help_types")
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
                CREATE TABLE resource_help_types (
                    resource_id TEXT NOT NULL,
                    help_type TEXT NOT NULL,
                    PRIMARY KEY (resource_id, help_type)
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO resources (
                    resource_id, name, resource_type, description, contact, languages,
                    scope_level, scope_code, status, verified_at, vetted_by, source_note,
                    display_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-upgrade",
                    "Legacy Upgrade",
                    "hotline",
                    "Call for support.",
                    '{"phone":"+1 555 0100"}',
                    '["en"]',
                    "country",
                    "US",
                    "ready",
                    "2026-01-01T00:00:00Z",
                    "Admin",
                    "Imported",
                    1,
                ),
            )
            cursor.execute(
                "INSERT INTO resource_help_types (resource_id, help_type) VALUES (?, ?)",
                ("legacy-upgrade", "legal"),
            )
            cursor.executemany(
                """
                INSERT INTO resources (
                    resource_id, name, resource_type, description, contact, languages,
                    scope_level, scope_code, status, display_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "legacy-invalid-ready",
                        "Invalid Ready",
                        "hotline",
                        None,
                        '{"phone":"+1 555 0101"}',
                        '["en"]',
                        "global",
                        None,
                        "ready",
                        2,
                    ),
                    (
                        "legacy-valid-pending",
                        "Valid Pending",
                        "hotline",
                        "Complete migrated record.",
                        '{"phone":"+1 555 0102"}',
                        '["en"]',
                        "global",
                        None,
                        "pending",
                        3,
                    ),
                ],
            )

        self.database._migrate_resources_to_generic_contract()
        first = self.database.get_resource("legacy-upgrade")
        self.database._migrate_resources_to_generic_contract()
        second = self.database.get_resource("legacy-upgrade")

        self.assertEqual(first, second)
        self.assertEqual(first["kind"], "service")
        self.assertEqual(first["tags"], ["legacy_type:hotline", "legal"])
        self.assertEqual(first["pointers"], [{"type": "phone", "value": "+1 555 0100"}])
        self.assertEqual(first["regions"], [{"level": "country", "code": "US"}])
        self.assertEqual(self.database.get_resource("legacy-invalid-ready")["status"], "ready")
        self.assertEqual(self.database.get_resource("legacy-valid-pending")["status"], "pending")

    def test_generic_resource_kinds_are_ready_without_aid_specific_facets(self) -> None:
        for kind in ("person", "product", "method", "reference"):
            created = self.database.create_resource(
                resource_id=f"generic-{kind}",
                name=f"Generic {kind.title()}",
                kind=kind,
                description=f"A curated {kind} for testing.",
                pointers=[{"type": "url", "value": f"https://{kind}.example.test"}],
                tags=["bitcoin", "education"],
                regions=[{"level": "global", "code": None}],
                languages=["en"],
            )

            self.assertEqual(created["status"], "ready")
            self.assertEqual(created["missing_fields"], [])
            self.assertEqual(created["kind"], kind)

    def test_generic_search_filters_tags_region_and_exact_pointer(self) -> None:
        self.database.create_resource(
            resource_id="bitcoin-reference",
            name="Bitcoin Reference",
            kind="reference",
            description="A curated Bitcoin payment reference.",
            tags=["bitcoin", "payments"],
            pointers=[{"type": "email", "value": "bitcoin@example.test"}],
            regions=[{"level": "country", "code": "US"}],
            languages=["en"],
        )
        self.database.create_resource(
            resource_id="unrelated-reference",
            name="Unrelated Reference",
            kind="reference",
            description="A different reference.",
            tags=["education"],
            pointers=[{"type": "url", "value": "https://unrelated.example.test"}],
            regions=[{"level": "global", "code": None}],
            languages=["en"],
        )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={
                "query": "BITCOIN@EXAMPLE.TEST",
                "kind": "reference",
                "tags": ["bitcoin"],
                "region": "US",
                "limit": 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["resources"][0]["resource_id"], "bitcoin-reference")
        self.assertEqual(
            body["resources"][0]["pointers"],
            [{"type": "email", "value": "bitcoin@example.test"}],
        )
        self.assertEqual(body["resolved_country_code"], "US")

    def test_generic_readiness_requires_explicit_kind_and_useful_pointer(self) -> None:
        missing_kind = self.database.create_resource(
            resource_id="missing-kind",
            name="Missing Kind",
            description="This otherwise looks complete.",
            pointers=[{"type": "url", "value": "https://example.test"}],
        )
        blank_pointer = self.database.create_resource(
            resource_id="blank-pointer",
            name="Blank Pointer",
            kind="reference",
            description="This pointer has no useful value.",
            pointers=[{"type": "url", "value": "   "}],
        )

        self.assertEqual(missing_kind["status"], "pending")
        self.assertIn("kind", missing_kind["missing_fields"])
        self.assertEqual(blank_pointer["status"], "pending")
        self.assertIn("pointers", blank_pointer["missing_fields"])
        self.assertEqual(blank_pointer["pointers"], [])

    def test_invalid_explicit_region_fails_closed(self) -> None:
        self.database.create_resource(
            resource_id="global-reference",
            name="Global Reference",
            kind="reference",
            description="A globally available reference.",
            pointers=[{"type": "url", "value": "https://global.example.test"}],
            regions=[{"level": "global", "code": None}],
        )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"kind": "reference", "region": "not-a-real-region", "limit": 10},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Unknown resource region")

    def test_legacy_and_generic_filters_compose(self) -> None:
        for resource_id, help_type in (("legal-org", "legal"), ("medical-org", "medical")):
            self.database.create_resource(
                resource_id=resource_id,
                name=resource_id.replace("-", " ").title(),
                resource_type="ngo",
                description="A trusted organization.",
                contact={"url": f"https://{resource_id}.example.test"},
                scope_level="global",
                help_types=[help_type],
            )

        resources = self.database.search_resources(
            None,
            help_type="legal",
            kind="organization",
            limit=10,
        )

        self.assertEqual([item["resource_id"] for item in resources], ["legal-org"])

    def test_jurisdiction_matches_and_ranks_generic_only_regions(self) -> None:
        for resource_id, regions, verified in (
            ("global-generic", [{"level": "global", "code": None}], True),
            ("us-generic", [{"level": "country", "code": "US"}], False),
            ("ca-generic", [{"level": "country", "code": "CA"}], True),
        ):
            self.database.create_resource(
                resource_id=resource_id,
                name=resource_id.replace("-", " ").title(),
                kind="reference",
                description="A generic regional reference.",
                pointers=[{"type": "url", "value": f"https://{resource_id}.example.test"}],
                regions=regions,
                provenance={"verified_at": "2026-01-01T00:00:00Z" if verified else None},
            )

        resources = self.database.search_resources("US", limit=10)

        self.assertEqual(
            [item["resource_id"] for item in resources],
            ["us-generic", "global-generic"],
        )

    def test_legacy_partial_edits_preserve_generic_only_data(self) -> None:
        self.database.create_resource(
            resource_id="enriched-legacy",
            name="Enriched Legacy",
            kind="person",
            tags=["legal", "bitcoin", "legacy_type:ngo"],
            pointers=[
                {"type": "email", "value": "old@example.test"},
                {"type": "identifier", "value": "person-123"},
            ],
            regions=[
                {"level": "global", "code": None},
                {"level": "country", "code": "US"},
            ],
            resource_type="ngo",
            description="An enriched migrated entry.",
            contact={"email": "old@example.test"},
            scope_level="global",
            help_types=["legal"],
        )

        updated = self.database.update_resource(
            "enriched-legacy",
            resource_type="hotline",
            help_types=["medical"],
            contact={"phone": "+1 555 0103"},
            scope_level="country",
            scope_code="CA",
        )

        self.assertEqual(updated["kind"], "person")
        self.assertEqual(updated["tags"], ["bitcoin", "legacy_type:hotline", "medical"])
        self.assertEqual(
            updated["pointers"],
            [
                {"type": "identifier", "value": "person-123"},
                {"type": "phone", "value": "+1 555 0103"},
            ],
        )
        self.assertEqual(
            updated["regions"],
            [
                {"level": "country", "code": "US"},
                {"level": "country", "code": "CA"},
            ],
        )

    def test_partial_provenance_update_preserves_existing_facts(self) -> None:
        self.database.create_resource(
            resource_id="provenance-entry",
            name="Provenance Entry",
            kind="reference",
            description="A resource with provenance.",
            pointers=[{"type": "url", "value": "https://provenance.example.test"}],
            provenance={
                "verified_at": "2026-01-01T00:00:00Z",
                "vetted_by": "Original Reviewer",
                "source_note": "Original source",
            },
        )

        updated = self.database.update_resource(
            "provenance-entry",
            provenance={"source_note": "Updated source"},
        )

        self.assertEqual(
            updated["provenance"],
            {
                "verified_at": "2026-01-01T00:00:00Z",
                "vetted_by": "Original Reviewer",
                "source_note": "Updated source",
            },
        )

    def test_internal_resource_search_requires_internal_token(self) -> None:
        response = self.client.post(
            "/internal/agent/resources/search",
            json={"help_type": "legal", "jurisdiction": "NI"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid internal agent token")

    def test_internal_resource_search_blank_help_type_lists_ready_inventory(self) -> None:
        self.database.create_resource(
            resource_id="pending-inventory",
            name="Pending Inventory",
            resource_type="ngo",
            scope_level="country",
            scope_code="NI",
            help_types=["legal"],
        )
        self._create_ready_resource(
            "ready-inventory",
            scope_level="country",
            scope_code="NI",
            languages=["es"],
            verified=True,
        )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"help_type": "   ", "limit": 10},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["help_type"])
        self.assertIsNone(body["resolved_country_code"])
        self.assertEqual(
            [resource["resource_id"] for resource in body["resources"]],
            ["ready-inventory"],
        )

    def test_internal_resource_search_supports_precise_query_and_bounded_metadata(self) -> None:
        self.database.create_resource(
            resource_id="alpha-legal",
            name="Alpha Legal Network",
            resource_type="ngo",
            description="Immigration and asylum support.",
            contact={"email": "help@alpha.example", "phone": "+1 (555) 0100"},
            scope_level="global",
            help_types=["legal"],
            verified_at="2026-01-01T00:00:00Z",
        )
        self.database.create_resource(
            resource_id="beta-legal",
            name="Beta Legal Network",
            resource_type="ngo",
            description="General legal support.",
            contact={"email": "contact@beta.example"},
            scope_level="global",
            help_types=["legal"],
            verified_at="2026-01-01T00:00:00Z",
        )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"query": "HELP@ALPHA.EXAMPLE", "help_type": "legal", "limit": 1},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "help@alpha.example")
        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["returned_count"], 1)
        self.assertEqual(body["limit"], 1)
        self.assertEqual(body["offset"], 0)
        self.assertFalse(body["has_more"])
        self.assertIsNone(body["next_offset"])
        self.assertEqual([r["resource_id"] for r in body["resources"]], ["alpha-legal"])

    def test_internal_resource_search_reports_partial_page_and_excludes_archived_from_total(self) -> None:
        for resource_id, archived in (("page-one", False), ("page-two", False), ("page-archived", True)):
            self.database.create_resource(
                resource_id=resource_id,
                name=resource_id.replace("-", " ").title(),
                resource_type="ngo",
                description="Paginated resource fixture.",
                contact={"url": f"https://{resource_id}.example"},
                scope_level="global",
                help_types=["legal"],
                verified_at="2026-01-01T00:00:00Z",
                archived=archived,
            )

        response = self.client.post(
            "/internal/agent/resources/search",
            headers=self.headers,
            json={"help_type": "legal", "limit": 1, "offset": 1},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_count"], 2)
        self.assertEqual(body["returned_count"], 1)
        self.assertEqual(body["offset"], 1)
        self.assertTrue(body["has_more"] is False)
        self.assertIsNone(body["next_offset"])
        self.assertEqual([r["resource_id"] for r in body["resources"]], ["page-two"])

    def test_internal_resource_search_matches_normalized_ids_contacts_and_partial_text(self) -> None:
        self.database.create_resource(
            resource_id="precise-resource",
            name="Precise Resource",
            resource_type="ngo",
            description="Specialized legal intake desk.",
            contact={
                "email": "Help@Precise.example",
                "phone": "+1 (555) 010-2000",
                "url": "https://precise.example/contact",
                "secure_channel": "Signal: precise-help",
                "address": "200 Main Street",
            },
            scope_level="global",
            help_types=["legal"],
            verified_at="2026-01-01T00:00:00Z",
        )
        for query in (
            "PRECISE-RESOURCE",
            "precise resource",
            "+1 555 010 2000",
            "555-010-2",
            "HTTPS://PRECISE.EXAMPLE/CONTACT",
            "signal: precise-help",
            "200 main street",
            "specialized legal",
        ):
            response = self.client.post(
                "/internal/agent/resources/search",
                headers=self.headers,
                json={"query": query, "help_type": "legal", "limit": 5},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual([r["resource_id"] for r in response.json()["resources"]], ["precise-resource"])

    def test_internal_resource_search_trims_help_type_and_bounds_limit(self) -> None:
        original = self.database.search_resources
        captured: dict[str, object] = {}

        def fake_search_resources(**kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {
                "resources": [],
                "total_count": 0,
                "returned_count": 0,
                "has_more": False,
                "next_offset": None,
            }

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

    def test_deleting_legacy_help_type_does_not_unpublish_generic_resource(self) -> None:
        self.database.upsert_help_type(
            key="transport",
            label="Transport",
            description="Travel support",
        )
        created = self.database.create_resource(
            resource_id="transport-ready",
            name="Transport Ready",
            resource_type="ngo",
            description="Transportation support service.",
            scope_level="global",
            contact={"url": "https://transport.example"},
            help_types=["transport"],
            verified_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(created["status"], "ready")

        self.assertTrue(self.database.delete_help_type("transport"))

        updated = self.database.get_resource("transport-ready")
        self.assertEqual(updated["help_types"], [])
        self.assertEqual(updated["status"], "ready")
        self.assertIn("transport", updated["tags"])

    def test_jurisdiction_prefix_accepts_iso_code(self) -> None:
        self.assertEqual(
            self.database.normalize_jurisdiction("jurisdiction:NI"),
            "NI",
        )

    def test_resource_search_normalizes_country_names_aliases_and_whitespace(self) -> None:
        cases = (
            ("mexico-legal", "MX", "México", "es"),
            (
                "united-arab-emirates-legal",
                "AE",
                "  United   Arab   Emirates  ",
                "en",
            ),
            ("turkey-legal", "TR", "TÜRKİYE", "tr"),
        )
        for resource_id, country_code, jurisdiction, language in cases:
            self._create_ready_resource(
                resource_id,
                scope_level="country",
                scope_code=country_code,
                languages=[language],
                verified=True,
            )

        for resource_id, country_code, jurisdiction, language in cases:
            with self.subTest(jurisdiction=jurisdiction):
                response = self.client.post(
                    "/internal/agent/resources/search",
                    headers=self.headers,
                    json={
                        "query": resource_id.replace("-", " ").title(),
                        "help_type": "legal",
                        "jurisdiction": jurisdiction,
                        "language": language,
                    },
                )

                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["resolved_country_code"], country_code)
                self.assertEqual(
                    [resource["resource_id"] for resource in body["resources"]],
                    [resource_id],
                )


if __name__ == "__main__":
    unittest.main()
