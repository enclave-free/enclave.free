from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class FakeQdrantResponse:
    def __init__(self, results: list[dict]) -> None:
        self._results = results

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"result": self._results}


class QueryRetrievalHydrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self.uploads_dir = Path(self.tmp.name) / "uploads"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_content_encryption_key = os.environ.get("CONTENT_ENCRYPTION_KEY")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["UPLOADS_DIR"] = str(self.uploads_dir)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["CONTENT_ENCRYPTION_KEY"] = "test-content-key"
        self._orig_internal_token = os.environ.get("INTERNAL_AGENT_TOKEN")
        os.environ["INTERNAL_AGENT_TOKEN"] = "test-internal-token"

        import auth
        import database
        import ingest_db
        import internal_agent
        import query

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.ingest_db = importlib.reload(ingest_db)
        self.query = importlib.reload(query)
        self.internal_agent = importlib.reload(internal_agent)
        self.database.init_schema()

        app = FastAPI()
        app.include_router(self.internal_agent.router)
        app.dependency_overrides[self.auth.require_admin_or_approved_user] = lambda: {
            "type": "admin",
            "id": 1,
            "pubkey": "admin-pubkey",
        }
        self.client = TestClient(app)
        self.internal_headers = {"X-Internal-Agent-Token": "test-internal-token"}

        self.original_internal_embed_texts = self.internal_agent.embed_texts

        def embed_texts(_texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2, 0.3]]

        self.internal_agent.embed_texts = embed_texts

    def tearDown(self) -> None:
        self.internal_agent.embed_texts = self.original_internal_embed_texts
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("CONTENT_ENCRYPTION_KEY", self._orig_content_encryption_key)
        self._restore_env("INTERNAL_AGENT_TOKEN", self._orig_internal_token)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def create_completed_document(self, job_id: str, filename: str = "Handbook.md") -> None:
        artifact_path = self.uploads_dir / filename
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("artifact body", encoding="utf-8")
        self.ingest_db.create_job(
            job_id=job_id,
            filename=filename,
            file_path=str(artifact_path),
            ontology_id="default",
        )
        self.ingest_db.update_job_status(job_id, "completed", total_chunks=1, processed_chunks=1)
        self.database.upsert_document_defaults(job_id, is_available=True, is_default_active=True)

    def test_query_hydrates_minimized_qdrant_hit_from_encrypted_chunk_storage(self) -> None:
        self.create_completed_document("job-1")
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="chunk-1",
            job_id="job-1",
            chunk_index=0,
            source_file="Handbook.md",
            text="Encrypted retrieval context reaches the model.",
        )
        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([
                {
                    "score": 0.93,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "chunk-1",
                        "job_id": "job-1",
                        "source_file": "Handbook.md",
                        "content_ref": "retrieval_chunks:chunk-1",
                    },
                }
            ])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "What does the handbook say?",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("Encrypted retrieval context reaches the model.", body["context"])
        self.assertEqual(body["sources"][0]["chunk_id"], "chunk-1")
        self.assertEqual(body["sources"][0]["job_id"], "job-1")
        self.assertEqual(body["sources"][0]["source_file"], "Handbook.md")
        self.assertEqual(body["sources"][0]["content_ref"], "retrieval_chunks:chunk-1")
        self.assertTrue(body["sources"][0]["hydrated"])
        self.assertEqual(body["sources"][0]["hydration_status"], "hydrated")
        self.assertEqual(body["sources"][0]["text"], "Encrypted retrieval context reaches the model.")

    def test_query_hydrates_plaintext_utf8_chunk_storage_when_content_key_is_unset(self) -> None:
        original_content_key = os.environ.pop("CONTENT_ENCRYPTION_KEY", None)
        try:
            self.create_completed_document("world-liberty", filename="World Liberty Congress.pdf")
            chunk_text = "World Liberty Congress supports political prisoners, families, and civic leaders — across borders."
            self.ingest_db.upsert_retrieval_chunk(
                chunk_id="world-liberty_chunk_0000",
                job_id="world-liberty",
                chunk_index=0,
                source_file="World Liberty Congress.pdf",
                text=chunk_text,
            )

            def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
                return FakeQdrantResponse([
                    {
                        "score": 0.93,
                        "payload": {
                            "type": "chunk",
                            "chunk_id": "world-liberty_chunk_0000",
                            "job_id": "world-liberty",
                            "source_file": "World Liberty Congress.pdf",
                        },
                    }
                ])

            with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
                response = self.client.post(
                    "/internal/agent/document-search",
                    headers=self.internal_headers,
                    json={
                        "query": "Get a basic understanding of our org from the uploaded PDF.",
                        "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                    },
                )
        finally:
            self._restore_env("CONTENT_ENCRYPTION_KEY", original_content_key)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(chunk_text, body["context"])
        self.assertEqual(body["sources"][0]["text"], chunk_text)
        self.assertTrue(body["sources"][0]["hydrated"])
        self.assertEqual(body["sources"][0]["hydration_status"], "hydrated")

    def test_document_overview_query_includes_opening_document_context(self) -> None:
        self.create_completed_document("world-liberty", filename="World Liberty Congress.pdf")
        opening_text = "World Liberty Congress is a global movement supporting democracy activists and political prisoners."
        matched_text = "Communications campaigns should define hashtags, publication timing, and strategic tagging."
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="world-liberty_chunk_0000",
            job_id="world-liberty",
            chunk_index=0,
            source_file="World Liberty Congress.pdf",
            text=opening_text,
        )
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="world-liberty_chunk_0088",
            job_id="world-liberty",
            chunk_index=88,
            source_file="World Liberty Congress.pdf",
            text=matched_text,
        )

        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([
                {
                    "score": 0.89,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "world-liberty_chunk_0088",
                        "job_id": "world-liberty",
                        "source_file": "World Liberty Congress.pdf",
                    },
                }
            ])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "Read my uploaded doc and get a basic understanding of our org",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(opening_text, body["context"])
        self.assertIn(matched_text, body["context"])
        self.assertLess(body["context"].index(opening_text), body["context"].index(matched_text))

    def test_uploaded_resource_learn_about_my_org_query_includes_opening_document_context(self) -> None:
        self.create_completed_document(
            "wlc-political-prisoners",
            filename="WLC_Political-Prisoners_EN.pdf",
        )
        opening_text = "PPST supports political prisoners and their families through international advocacy."
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="wlc-political-prisoners_chunk_0000",
            job_id="wlc-political-prisoners",
            chunk_index=0,
            source_file="WLC_Political-Prisoners_EN.pdf",
            text=opening_text,
        )

        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "Learn about my org PPST from my uploaded resource WLC_Political-Prisoners_EN.pdf",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(opening_text, body["context"])

    def test_document_overview_query_caps_opening_document_context(self) -> None:
        for index in range(6):
            job_id = f"doc-{index:02d}"
            self.create_completed_document(job_id, filename=f"{job_id}.pdf")
            self.ingest_db.upsert_retrieval_chunk(
                chunk_id=f"{job_id}_chunk_0000",
                job_id=job_id,
                chunk_index=0,
                source_file=f"{job_id}.pdf",
                text=f"Opening excerpt for {job_id}.",
            )

        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "Read my uploaded doc and get a basic understanding of our org",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        for index in range(5):
            self.assertIn(f"Opening excerpt for doc-{index:02d}.", body["context"])
        self.assertNotIn("Opening excerpt for doc-05.", body["context"])

    def test_retrieval_evaluation_returns_expected_hydrated_sources(self) -> None:
        self.create_completed_document("safety-handbook", filename="Safety Handbook.md")
        self.create_completed_document("benefits-guide", filename="Benefits Guide.md")
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="safety-handbook_chunk_0000",
            job_id="safety-handbook",
            chunk_index=0,
            source_file="Safety Handbook.md",
            text="Evacuation drills happen every Wednesday at 10 AM.",
        )
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="benefits-guide_chunk_0000",
            job_id="benefits-guide",
            chunk_index=0,
            source_file="Benefits Guide.md",
            text="Dental benefits include two preventive visits each year.",
        )
        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([
                {
                    "score": 0.91,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "safety-handbook_chunk_0000",
                        "job_id": "safety-handbook",
                        "source_file": "Safety Handbook.md",
                    },
                },
                {
                    "score": 0.74,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "benefits-guide_chunk_0000",
                        "job_id": "benefits-guide",
                        "source_file": "Benefits Guide.md",
                    },
                },
            ])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "When are evacuation drills and what dental visits are covered?",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                    "top_k": 2,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["top_k"], 2)
        self.assertEqual(
            [source["chunk_id"] for source in body["sources"]],
            ["safety-handbook_chunk_0000", "benefits-guide_chunk_0000"],
        )
        self.assertIn("Evacuation drills happen every Wednesday at 10 AM.", body["context"])
        self.assertIn("Dental benefits include two preventive visits each year.", body["context"])
        self.assertTrue(all(source["hydrated"] for source in body["sources"]))

    def test_user_retrieval_does_not_serve_inaccessible_document_returned_by_vector_backend(self) -> None:
        self.create_completed_document("allowed-job", filename="Allowed.md")
        self.create_completed_document("blocked-job", filename="Blocked.md")
        user_type_id = self.database.create_user_type("Allowed Users")
        self.database.upsert_document_defaults_override("blocked-job", user_type_id, is_available=False)
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="allowed-job_chunk_0000",
            job_id="allowed-job",
            chunk_index=0,
            source_file="Allowed.md",
            text="Allowed context may be served to this user.",
        )
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="blocked-job_chunk_0000",
            job_id="blocked-job",
            chunk_index=0,
            source_file="Blocked.md",
            text="Blocked context must not be served to this user.",
        )
        captured_payloads = []

        def fake_post(_url: str, json: dict[str, Any], **_kwargs: Any) -> FakeQdrantResponse:
            captured_payloads.append(json)
            return FakeQdrantResponse([
                {
                    "score": 0.95,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "blocked-job_chunk_0000",
                        "job_id": "blocked-job",
                        "source_file": "Blocked.md",
                    },
                },
                {
                    "score": 0.86,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "allowed-job_chunk_0000",
                        "job_id": "allowed-job",
                        "source_file": "Allowed.md",
                    },
                },
            ])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "What context can I see?",
                    "user": {
                        "id": 2,
                        "type": "user",
                        "approved": True,
                        "user_type_id": user_type_id,
                    },
                    "top_k": 2,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("Allowed context may be served", body["context"])
        self.assertNotIn("Blocked context must not be served", body["context"])
        self.assertEqual([source["chunk_id"] for source in body["sources"]], ["allowed-job_chunk_0000"])
        self.assertEqual(
            captured_payloads[0]["filter"],
            {"should": [{"key": "job_id", "match": {"value": "allowed-job"}}]},
        )

    def test_required_context_job_ids_limit_admin_retrieval_context(self) -> None:
        self.create_completed_document("required-context", filename="Required Context.md")
        self.create_completed_document("unselected-context", filename="Unselected Context.md")
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="required-context_chunk_0000",
            job_id="required-context",
            chunk_index=0,
            source_file="Required Context.md",
            text="Required Context reaches Sage even when other documents also match.",
        )
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="unselected-context_chunk_0000",
            job_id="unselected-context",
            chunk_index=0,
            source_file="Unselected Context.md",
            text="Unselected context must not be included when Required Context is set.",
        )
        captured_payloads = []

        def fake_post(_url: str, json: dict[str, Any], **_kwargs: Any) -> FakeQdrantResponse:
            captured_payloads.append(json)
            return FakeQdrantResponse([
                {
                    "score": 0.99,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "unselected-context_chunk_0000",
                        "job_id": "unselected-context",
                        "source_file": "Unselected Context.md",
                    },
                },
                {
                    "score": 0.72,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "required-context_chunk_0000",
                        "job_id": "required-context",
                        "source_file": "Required Context.md",
                    },
                },
            ])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "Use the selected document",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                    "job_ids": ["required-context"],
                    "top_k": 2,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([source["chunk_id"] for source in body["sources"]], ["required-context_chunk_0000"])
        self.assertIn("Required Context reaches Sage", body["context"])
        self.assertNotIn("Unselected context must not be included", body["context"])
        self.assertEqual(
            captured_payloads[0]["filter"],
            {"should": [{"key": "job_id", "match": {"value": "required-context"}}]},
        )

    def test_admin_retrieval_ignores_superseded_document_chunks_after_replacement(self) -> None:
        self.create_completed_document("old-policy", filename="Policy.md")
        self.create_completed_document("new-policy", filename="Policy.md")
        with self.database.get_write_cursor() as cursor:
            cursor.execute("UPDATE ingest_jobs SET is_current = 0 WHERE job_id = ?", ("old-policy",))
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="old-policy_chunk_0000",
            job_id="old-policy",
            chunk_index=0,
            source_file="Policy.md",
            text="The superseded policy says the old rule still applies.",
        )
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="new-policy_chunk_0000",
            job_id="new-policy",
            chunk_index=0,
            source_file="Policy.md",
            text="The replacement policy says the new rule applies.",
        )
        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([
                {
                    "score": 0.99,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "old-policy_chunk_0000",
                        "job_id": "old-policy",
                        "source_file": "Policy.md",
                    },
                },
                {
                    "score": 0.88,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "new-policy_chunk_0000",
                        "job_id": "new-policy",
                        "source_file": "Policy.md",
                    },
                },
            ])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "Which policy applies?",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                    "top_k": 2,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([source["chunk_id"] for source in body["sources"]], ["new-policy_chunk_0000"])
        self.assertIn("replacement policy says the new rule applies", body["context"])
        self.assertNotIn("superseded policy says the old rule", body["context"])

    def test_deleted_document_chunks_do_not_reenter_retrieval_context(self) -> None:
        self.create_completed_document("deleted-guide", filename="Deleted Guide.md")
        with self.database.get_write_cursor() as cursor:
            cursor.execute("UPDATE ingest_jobs SET is_current = 0 WHERE job_id = ?", ("deleted-guide",))
            cursor.execute("DELETE FROM document_defaults WHERE job_id = ?", ("deleted-guide",))
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="deleted-guide_chunk_0000",
            job_id="deleted-guide",
            chunk_index=0,
            source_file="Deleted Guide.md",
            text="Deleted guide text must not be hydrated into context.",
        )
        embed_calls = []
        def embed_texts(texts: list[str]) -> list[list[float]]:
            embed_calls.append(texts)
            return [[0.1, 0.2, 0.3]]

        self.internal_agent.embed_texts = embed_texts
        with patch.object(self.internal_agent.httpx, "post") as fake_post:
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "Can deleted material come back?",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                    "job_ids": ["deleted-guide"],
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sources"], [])
        self.assertEqual(body["context"], "")
        self.assertEqual(embed_calls, [])
        fake_post.assert_not_called()

    def test_query_skips_hydration_when_chunk_row_belongs_to_different_document(self) -> None:
        self.create_completed_document("allowed-job")
        self.create_completed_document("blocked-job")
        self.ingest_db.upsert_retrieval_chunk(
            chunk_id="cross-document-chunk",
            job_id="blocked-job",
            chunk_index=0,
            source_file="Blocked.md",
            text="This unauthorized passage must not enter context.",
        )
        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([
                {
                    "score": 0.71,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "cross-document-chunk",
                        "job_id": "allowed-job",
                        "source_file": "Allowed.md",
                    },
                }
            ])

        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "What is available?",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("unauthorized passage", response.json()["context"])
        self.assertFalse(response.json()["sources"][0]["hydrated"])
        self.assertEqual(response.json()["sources"][0]["hydration_status"], "job_mismatch")

    def test_query_handles_missing_deleted_retrieval_chunk_without_payload_text(self) -> None:
        self.create_completed_document("job-1")
        def fake_post(*_args: Any, **_kwargs: Any) -> FakeQdrantResponse:
            return FakeQdrantResponse([
                {
                    "score": 0.5,
                    "payload": {
                        "type": "chunk",
                        "chunk_id": "deleted-chunk",
                        "job_id": "job-1",
                        "source_file": "Handbook.md",
                    },
                }
            ])
        with patch.object(self.internal_agent.httpx, "post", side_effect=fake_post):
            response = self.client.post(
                "/internal/agent/document-search",
                headers=self.internal_headers,
                json={
                    "query": "What remains?",
                    "user": {"id": 1, "type": "admin", "pubkey": "admin-pubkey"},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["sources"][0]["hydrated"])
        self.assertEqual(response.json()["sources"][0]["hydration_status"], "missing")
