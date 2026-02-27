"""
EnclaveFree Store Module
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
logger = logging.getLogger("enclavefree.store")

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# =============================================================================
# EMBEDDING CONFIGURATION
# =============================================================================
# Embeddings run locally using sentence-transformers.
# =============================================================================
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")

# Collection names for knowledge base
_QDRANT_COLLECTION_ENV = os.getenv("QDRANT_COLLECTION")
QDRANT_COLLECTION_EXPLICIT = bool(_QDRANT_COLLECTION_ENV and _QDRANT_COLLECTION_ENV.strip())
PRIMARY_COLLECTION_NAME = (
    _QDRANT_COLLECTION_ENV.strip()
    if QDRANT_COLLECTION_EXPLICIT
    else "enclavefree_knowledge"
)
LEGACY_COLLECTION_NAME = os.getenv("QDRANT_LEGACY_COLLECTION", "sanctum_knowledge")

# Backward-compatible alias kept for existing imports
COLLECTION_NAME = PRIMARY_COLLECTION_NAME

# Lazy-loaded resources
_qdrant_client = None
_embedding_model = None
_active_collection_name = None


def get_qdrant_client():
    """Get or create Qdrant client"""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant_client


def _list_collection_names(client: QdrantClient) -> set[str]:
    """List current Qdrant collection names as a set."""
    return {c.name for c in client.get_collections().collections}


def get_collection_name(refresh: bool = False) -> str:
    """
    Resolve the active knowledge collection name.

    Preference order:
    0) If QDRANT_COLLECTION is explicitly configured, always use it
    1) Primary collection if present
    2) Legacy collection if present (upgrade compatibility)
    3) Primary collection name for fresh installs
    """
    global _active_collection_name
    if _active_collection_name is not None and not refresh:
        return _active_collection_name

    client = get_qdrant_client()
    collection_names = _list_collection_names(client)

    if QDRANT_COLLECTION_EXPLICIT:
        _active_collection_name = PRIMARY_COLLECTION_NAME
        if (
            LEGACY_COLLECTION_NAME in collection_names
            and PRIMARY_COLLECTION_NAME not in collection_names
        ):
            logger.info(
                "QDRANT_COLLECTION is explicitly set to '%s'; using it even though legacy '%s' exists",
                PRIMARY_COLLECTION_NAME,
                LEGACY_COLLECTION_NAME,
            )
    elif PRIMARY_COLLECTION_NAME in collection_names:
        _active_collection_name = PRIMARY_COLLECTION_NAME
    elif LEGACY_COLLECTION_NAME in collection_names:
        _active_collection_name = LEGACY_COLLECTION_NAME
        logger.warning(
            "Using legacy Qdrant collection '%s'; set QDRANT_COLLECTION='%s' to migrate names explicitly",
            LEGACY_COLLECTION_NAME,
            PRIMARY_COLLECTION_NAME,
        )
    else:
        _active_collection_name = PRIMARY_COLLECTION_NAME

    return _active_collection_name


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

    collection_name = get_collection_name()
    collection_exists = collection_name in _list_collection_names(client)

    if not collection_exists:
        vector_dim = get_embedding_dimension()
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_dim,
                distance=Distance.COSINE
            )
        )
        logger.info(f"Created Qdrant collection: {collection_name} (dim={vector_dim})")


def _store_chunk_sync(
    chunk_id: str,
    source_text: str,
    source_file: str,
) -> dict[str, Any]:
    logger.info(f"[{chunk_id}] Storing chunk to Qdrant...")
    qdrant_result = {"points_inserted": 0}

    client = get_qdrant_client()
    collection_name = get_collection_name()

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
    point = PointStruct(
        id=chunk_point_id,
        vector=embedding,
        payload={
            "type": "chunk",
            "chunk_id": chunk_id,
            "job_id": job_id,  # Separate field for filtering by document
            "text": source_text[:2000],  # Store more text for context
            "source_file": source_file,
        }
    )

    # Insert to Qdrant
    client.upsert(
        collection_name=collection_name,
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
    collection_name = get_collection_name()

    # Check if collection exists
    if collection_name not in _list_collection_names(client):
        logger.info(f"Collection {collection_name} does not exist, nothing to delete")
        return 0

    # First, scroll to find all matching points
    deleted_count = 0
    offset = None
    batch_size = 100

    while True:
        # Scroll through points with matching job_id
        results = client.scroll(
            collection_name=collection_name,
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
            collection_name=collection_name,
            points_selector=PointIdsList(points=point_ids),
        )
        deleted_count += len(point_ids)
        logger.debug(f"Deleted {len(point_ids)} points for job {job_id}")

        if next_offset is None:
            break
        offset = next_offset

    logger.info(f"Deleted {deleted_count} total points from Qdrant for job {job_id}")
    return deleted_count
