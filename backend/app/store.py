from __future__ import annotations

"""
Enclave Store Module
Handles storing document chunks and embeddings to Qdrant.
"""

import os
import uuid
import logging
import asyncio
import threading
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configure logging
logger = logging.getLogger("enclave.store")

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# =============================================================================
# EMBEDDING CONFIGURATION
# =============================================================================
# Default document embeddings use the same OpenAI-compatible Tinfoil proxy as
# Sage. Set EMBEDDING_PROVIDER=local to use sentence-transformers instead.
# =============================================================================
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "tinfoil").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL") or os.getenv("LLM_API_URL", "http://tinfoil-proxy:8089/v1")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY")

# Collection name for knowledge base
COLLECTION_NAME = "enclave_knowledge"

# Lazy-loaded resources
_qdrant_client = None
_embedding_model = None
_embedding_client = None
_qdrant_collection_lock = threading.Lock()


def get_qdrant_client():
    """Get or create Qdrant client"""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant_client


def get_embedding_model():
    """Get or create local embedding model (sentence-transformers)"""
    if EMBEDDING_PROVIDER != "local":
        raise RuntimeError("Local embedding model requested while EMBEDDING_PROVIDER is not 'local'")

    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_embedding_client():
    """Get or create OpenAI-compatible embedding client."""
    global _embedding_client
    if _embedding_client is None:
        if not EMBEDDING_API_KEY:
            raise RuntimeError(
                "LLM_API_KEY is required for Tinfoil embeddings"
            )
        from openai import OpenAI

        _embedding_client = OpenAI(
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_API_URL,
        )
    return _embedding_client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using the configured embedding provider.
    Returns list of embedding vectors.
    """
    if EMBEDDING_PROVIDER != "local":
        client = get_embedding_client()
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]


def get_embedding_dimension() -> int:
    """Get the dimension of embeddings from the configured provider."""
    if EMBEDDING_PROVIDER != "local":
        return len(embed_texts(["dimension probe"])[0])

    return get_embedding_model().get_sentence_embedding_dimension()


def _is_qdrant_collection_already_exists_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    content = getattr(error, "content", "")
    message = f"{content!r} {error}".lower()
    return status_code == 409 and "already exists" in message


def ensure_qdrant_collection() -> None:
    """Ensure the knowledge collection exists in Qdrant"""
    client = get_qdrant_client()

    with _qdrant_collection_lock:
        collections = client.get_collections().collections
        collection_exists = any(c.name == COLLECTION_NAME for c in collections)

        if not collection_exists:
            vector_dim = get_embedding_dimension()
            try:
                client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=vector_dim,
                        distance=Distance.COSINE
                    )
                )
            except Exception as error:
                if _is_qdrant_collection_already_exists_error(error):
                    logger.info(
                        "Qdrant collection already exists after concurrent create: %s",
                        COLLECTION_NAME,
                    )
                    return
                raise
            logger.info(
                f"Created Qdrant collection: {COLLECTION_NAME} (dim={vector_dim})"
            )


def _store_chunk_sync(
    chunk_id: str,
    source_text: str,
    source_file: str,
    source_label: str | None = None,
) -> dict[str, Any]:
    logger.info(f"[{chunk_id}] Storing chunk to Qdrant...")
    qdrant_result = {"points_inserted": 0}

    client = get_qdrant_client()

    # Ensure Qdrant collection exists
    ensure_qdrant_collection()

    # Embed the chunk text
    logger.debug(f"[{chunk_id}] Encoding chunk (model={EMBEDDING_MODEL})...")
    embedding = embed_texts([f"passage: {source_text}"])[0]
    logger.debug(f"[{chunk_id}] Encoding complete")

    # Create chunk point
    chunk_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"chunk:{chunk_id}"))
    # Extract job_id from chunk_id (format: {job_id}_chunk_XXXX)
    job_id = chunk_id.split('_chunk_')[0] if '_chunk_' in chunk_id else chunk_id
    payload = {
        "type": "chunk",
        "chunk_id": chunk_id,
        "job_id": job_id,  # Separate field for filtering by document
        "source_file": source_file,
        "content_ref": f"retrieval_chunk:{chunk_id}",
        "embedding_provider": EMBEDDING_PROVIDER,
        "embedding_model": EMBEDDING_MODEL,
    }
    if source_label:
        payload["source_label"] = source_label

    point = PointStruct(
        id=chunk_point_id,
        vector=embedding,
        payload=payload,
    )

    # Insert to Qdrant
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[point]
    )
    qdrant_result["points_inserted"] = 1

    logger.info(f"[{chunk_id}] Chunk stored successfully")
    return {
        "qdrant": qdrant_result,
    }


async def store_chunks_to_qdrant(
    chunk_id: str,
    source_text: str,
    source_file: str,
    source_label: str | None = None,
) -> dict[str, Any]:
    """
    Store a text chunk and its embedding to Qdrant.

    This is a simple storage function that embeds the raw text chunk.

    Returns summary of what was stored.
    """
    return await asyncio.to_thread(
        _store_chunk_sync,
        chunk_id,
        source_text,
        source_file,
        source_label,
    )


async def delete_chunks_from_qdrant(job_id: str) -> int:
    """
    Delete all chunks for a job from Qdrant.

    Args:
        job_id: The job ID whose chunks should be deleted

    Returns:
        Number of points deleted
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue, PointIdsList

    client = get_qdrant_client()

    # Check if collection exists
    collections = client.get_collections().collections
    if not any(c.name == COLLECTION_NAME for c in collections):
        logger.info(f"Collection {COLLECTION_NAME} does not exist, nothing to delete")
        return 0

    # First, scroll to find all matching points
    deleted_count = 0
    offset = None
    batch_size = 100

    while True:
        # Scroll through points with matching job_id
        results = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="job_id",
                        match=MatchValue(value=job_id),
                    )
                ]
            ),
            limit=batch_size,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )

        points, next_offset = results

        if not points:
            break

        # Delete the found points
        point_ids = [p.id for p in points]
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=PointIdsList(points=point_ids),
        )
        deleted_count += len(point_ids)
        logger.debug(f"Deleted {len(point_ids)} points for job {job_id}")

        if next_offset is None:
            break
        offset = next_offset

    logger.info(f"Deleted {deleted_count} total points from Qdrant for job {job_id}")
    return deleted_count
