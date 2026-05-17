from __future__ import annotations

import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class StoreMinimizedPayloadTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_llm_api_key = os.environ.get("LLM_API_KEY")
        self._orig_embedding_api_key = os.environ.get("EMBEDDING_API_KEY")
        self._orig_tinfoil_api_key = os.environ.get("TINFOIL_API_KEY")

        import store

        self.store = importlib.reload(store)
        self.upserted_points = []
        self.original_get_qdrant_client = self.store.get_qdrant_client
        self.original_ensure_qdrant_collection = self.store.ensure_qdrant_collection
        self.original_embed_texts = self.store.embed_texts

        class FakeQdrantClient:
            def __init__(inner_self, points):
                inner_self.points = points

            def upsert(inner_self, *, collection_name, points):
                inner_self.points.extend(points)

        self.store.get_qdrant_client = lambda: FakeQdrantClient(self.upserted_points)
        self.store.ensure_qdrant_collection = lambda: None
        self.store.embed_texts = lambda texts: [[0.1, 0.2, 0.3] for _ in texts]

    def tearDown(self) -> None:
        self.store.get_qdrant_client = self.original_get_qdrant_client
        self.store.ensure_qdrant_collection = self.original_ensure_qdrant_collection
        self.store.embed_texts = self.original_embed_texts
        self._restore_env("LLM_API_KEY", self._orig_llm_api_key)
        self._restore_env("EMBEDDING_API_KEY", self._orig_embedding_api_key)
        self._restore_env("TINFOIL_API_KEY", self._orig_tinfoil_api_key)

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_new_qdrant_chunk_payload_omits_plaintext_text(self) -> None:
        plaintext = "sensitive retrieval passage about operator strategy"

        result = asyncio.run(self.store.store_chunks_to_qdrant(
            chunk_id="job123_chunk_0000",
            source_text=plaintext,
            source_file="Handbook.md",
        ))

        self.assertEqual(result["qdrant"]["points_inserted"], 1)
        payload = self.upserted_points[0].payload
        self.assertEqual(payload["type"], "chunk")
        self.assertEqual(payload["chunk_id"], "job123_chunk_0000")
        self.assertEqual(payload["job_id"], "job123")
        self.assertEqual(payload["source_file"], "Handbook.md")
        self.assertNotIn("text", payload)
        self.assertNotIn("fact_text", payload)
        self.assertNotIn("sensitive retrieval passage", repr(payload))

    def test_tinfoil_embeddings_ignore_env_only_llm_api_key(self) -> None:
        os.environ["LLM_API_KEY"] = "env-only-llm-key"
        os.environ.pop("EMBEDDING_API_KEY", None)
        os.environ.pop("TINFOIL_API_KEY", None)

        self.store = importlib.reload(self.store)

        self.assertIsNone(self.store.EMBEDDING_API_KEY)


if __name__ == "__main__":
    unittest.main()
