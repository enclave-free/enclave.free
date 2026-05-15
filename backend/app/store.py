"""
Sanctum Store Module
Handles storing document chunks and embeddings to Qdrant.
"""

import os
import uuid
import logging
import asyncio
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configure logging
logger = logging.getLogger("sanctum.store")

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# =============================================================================
# EMBEDDING CONFIGURATION
# =============================================================================
# Embeddings run locally using sentence-transformers.
# =============================================================================
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")

# Collection name for knowledge base
COLLECTION_NAME = "sanctum_knowledge"
_LEGACY_PLAINTEXT_KEYS = {"text", "fact_text"}

# Lazy-loaded resources
_qdrant_client = None
_embedding_model = None


def get_qdrant_client():
    """Get or create Qdrant client"""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant_client


def detect_legacy_plaintext_payloads(limit: int = 500) -> dict[str, Any]:
    """Best-effort scan for legacy Qdrant payloads that still contain raw text."""
    legacy_count = 0
    affected = []
    try:
        client = get_qdrant_client()
        next_offset = None
        while True:
            points, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                offset=next_offset,
            )
            for point in points:
                payload = getattr(point, "payload", None) or {}
                if any(payload.get(key) for key in _LEGACY_PLAINTEXT_KEYS):
                    legacy_count += 1
                    affected.append({
                        "point_id": str(getattr(point, "id", "")),
                        "chunk_id": payload.get("chunk_id"),
                        "job_id": payload.get("job_id"),
                        "source_file": payload.get("source_file"),
                    })
            if next_offset is None:
                break
    except Exception as exc:
        logger.warning("Could not inspect Qdrant payload confidentiality: %s", exc)
        return {
            "checked": False,
            "legacy_plaintext_payloads": None,
            "summary": "Qdrant payload confidentiality could not be inspected from this process.",
        }

    return {
        "checked": True,
        "legacy_plaintext_payloads": legacy_count,
        "affected": affected,
        "summary": (
            f"Found {legacy_count} Qdrant points with legacy plaintext payload text."
            if legacy_count
            else "No legacy plaintext Qdrant payload text was detected in the inspected active index."
        ),
    }


def list_legacy_plaintext_payloads(limit: int = 500) -> list[dict[str, Any]]:
    """Return legacy Qdrant payloads with recoverable text for confidentiality migration."""
    client = get_qdrant_client()
    legacy_points = []
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=limit,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )
        for point in points:
            payload = getattr(point, "payload", None) or {}
            text = payload.get("text") or payload.get("fact_text")
            if not text:
                continue
            legacy_points.append({
                "point_id": getattr(point, "id", None),
                "chunk_id": payload.get("chunk_id"),
                "job_id": payload.get("job_id"),
                "source_file": payload.get("source_file"),
                "text": text,
                "payload": payload,
            })
        if next_offset is None:
            break
    return legacy_points


def rewrite_payload_without_plaintext(point_id: Any, payload: dict[str, Any]) -> None:
    """Overwrite a Qdrant payload while preserving retrieval metadata and removing raw text."""
    minimized_payload = {
        key: value
        for key, value in payload.items()
        if key not in _LEGACY_PLAINTEXT_KEYS
    }
    get_qdrant_client().overwrite_payload(
        collection_name=COLLECTION_NAME,
        points=[point_id],
        payload=minimized_payload,
    )


def get_embedding_model():
    """Get or create local embedding model (sentence-transformers)"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using the local sentence-transformers model.
    Returns list of embedding vectors.
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]


def get_embedding_dimension() -> int:
    """Get the dimension of embeddings from the local embedding model."""
    model = get_embedding_model()
    return model.get_sentence_embedding_dimension()


def ensure_qdrant_collection():
    """Ensure the knowledge collection exists in Qdrant"""
    client = get_qdrant_client()
    
    collections = client.get_collections().collections
    collection_exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not collection_exists:
        vector_dim = get_embedding_dimension()
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_dim,
                distance=Distance.COSINE
            )
        )
        logger.info(f"Created Qdrant collection: {COLLECTION_NAME} (dim={vector_dim})")


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
