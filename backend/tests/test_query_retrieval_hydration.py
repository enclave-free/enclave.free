import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
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
        self.query._sessions.clear()

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
        self.original_call_llm = self.query._call_llm_contextual
        self.original_extract_facts = self.query._extract_facts_from_conversation

        self.internal_agent.embed_texts = lambda _texts: [[0.1, 0.2, 0.3]]
        self.query._extract_facts_from_conversation = lambda session: session.get("facts_gathered", {})

    def tearDown(self) -> None:
        self.internal_agent.embed_texts = self.original_internal_embed_texts
        self.query._call_llm_contextual = self.original_call_llm
        self.query._extract_facts_from_conversation = self.original_extract_facts
        self.query._sessions.clear()
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
        fake_post = lambda *_args, **_kwargs: FakeQdrantResponse([
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
        self.assertEqual(body["sources"][0]["source_file"], "Handbook.md")
        self.assertTrue(body["sources"][0]["hydrated"])
        self.assertEqual(body["sources"][0]["text"], "Encrypted retrieval context reaches the model.")

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
        fake_post = lambda *_args, **_kwargs: FakeQdrantResponse([
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
        fake_post = lambda *_args, **_kwargs: FakeQdrantResponse([
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
