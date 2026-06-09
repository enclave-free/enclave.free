"""
Enclave Seed Script
Seeds Qdrant with a test embedding.
Uses the shared backend embedding provider.
Also initializes SQLite database for user/admin management.
"""

import os
import sys
import time
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
# SQLite database module
import database

# Use unified embedding from store.py
from store import embed_texts, get_embedding_dimension, EMBEDDING_MODEL, EMBEDDING_PROVIDER
from seed_status import (
    should_continue_after_qdrant_seed_failure,
    write_degraded_seed_status,
    write_ready_seed_status,
)

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

COLLECTION_NAME = "enclave_smoke_test"

# Seed data - Spanish sentence about knowledge
SEED_CLAIM = {
    "id": "claim_knowledge_sharing",
    "text": "El conocimiento es poder cuando se comparte de manera segura.",
    "text_english": "Knowledge is power when shared securely.",
    "language": "es",
    "type": "general_fact"
}


def wait_for_qdrant(client, max_retries=30, delay=2):
    """Wait for Qdrant to be ready"""
    print("Waiting for Qdrant to be ready...")
    for i in range(max_retries):
        try:
            client.get_collections()
            print("Qdrant is ready!")
            return True
        except Exception as e:
            print(f"  Attempt {i+1}/{max_retries}: Qdrant not ready yet...")
            time.sleep(delay)
    return False


def seed_qdrant(client):
    """Seed Qdrant with the claim embedding"""
    print("\nSeeding Qdrant...")

    vector_dim = get_embedding_dimension()
    print(f"  Embedding provider: {EMBEDDING_PROVIDER}")
    print(f"  Embedding model: {EMBEDDING_MODEL}")
    print(f"  Vector dimension: {vector_dim}")

    if not isinstance(vector_dim, int) or vector_dim <= 0:
        raise RuntimeError(
            "Invalid embedding dimension from model "
            f"(EMBEDDING_MODEL='{EMBEDDING_MODEL}', vector_dim={vector_dim}). "
            "Aborting seed."
        )

    # Validate the actual encoded embedding shape before touching collections.
    print(f"  Generating embedding for: '{SEED_CLAIM['text']}'")
    embedding = embed_texts([f"passage: {SEED_CLAIM['text']}"])[0]
    actual_vector_dim = len(embedding)
    if actual_vector_dim != vector_dim:
        raise RuntimeError(
            "Embedding dimension mismatch for "
            f"EMBEDDING_MODEL='{EMBEDDING_MODEL}': "
            f"model reported {vector_dim}, encoded vector has {actual_vector_dim}. "
            "Aborting seed before collection creation."
        )

    # Create collection if it doesn't exist
    collections = client.get_collections().collections
    collection_exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if collection_exists:
        print(f"  Deleting existing collection: {COLLECTION_NAME}")
        client.delete_collection(COLLECTION_NAME)
    
    print(f"  Creating collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=vector_dim,
            distance=Distance.COSINE
        )
    )
    
    # Insert into Qdrant - use UUID derived from claim ID
    point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, SEED_CLAIM["id"]))
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_uuid,
                vector=embedding,
                payload={
                    "claim_id": SEED_CLAIM["id"],
                    "text": SEED_CLAIM["text"],
                    "language": SEED_CLAIM["language"],
                    "type": "chunk"
                }
            )
        ]
    )
    print(f"  Inserted point: {SEED_CLAIM['id']} (UUID: {point_uuid})")

    print("Qdrant seeding complete!")


# A few example resources so the path is demonstrable end-to-end. These intentionally span
# the scope hierarchy (country -> subregion -> global) to show specificity ranking.
EXAMPLE_RESOURCES = [
    {
        "resource_id": "example-ni-detention-lawyer",
        "name": "Nicaragua Detention Defense (example)",
        "resource_type": "lawyer",
        "description": "In-country lawyer handling arbitrary-detention and habeas cases.",
        "contact": {"email": "contact@example.org", "secure_channel": "Signal: +505-000-0000"},
        "languages": ["es"],
        "scope_level": "country",
        "scope_code": "NI",
        "help_types": ["legal"],
        "vetted_by": "seed",
        "source_note": "Example seed data — replace with vetted entries.",
    },
    {
        "resource_id": "example-centralamerica-hr-lawyer",
        "name": "Central America Human Rights Counsel (example)",
        "resource_type": "ngo",
        "description": "Spanish-speaking human-rights legal network across Central America.",
        "contact": {"url": "https://example.org", "email": "info@example.org"},
        "languages": ["es", "en"],
        "scope_level": "subregion",
        "scope_code": "013",
        "help_types": ["legal", "humanitarian"],
        "vetted_by": "seed",
        "source_note": "Example seed data — replace with vetted entries.",
    },
    {
        "resource_id": "example-un-enforced-disappearances",
        "name": "UN Committee on Enforced Disappearances (example)",
        "resource_type": "un_body",
        "description": "UN mechanism receiving urgent actions on disappeared and forcibly conscripted persons.",
        "contact": {"url": "https://www.ohchr.org"},
        "languages": ["en", "fr", "es", "ar"],
        "scope_level": "global",
        "scope_code": None,
        "help_types": ["humanitarian"],
        "vetted_by": "seed",
        "source_note": "Example seed data — replace with vetted entries.",
    },
]


def seed_resource_directory():
    """Seed example resources (region map + core help types are seeded by init_schema)."""
    for resource in EXAMPLE_RESOURCES:
        if database.get_resource(resource["resource_id"]) is None:
            database.create_resource(verified_at=database.utc_timestamp_z(), **resource)
    print("  Example resources seeded")


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def seed_sqlite(seed_demo_resources: bool | None = None):
    """Initialize SQLite database and seed default settings"""
    print("\nInitializing SQLite database...")
    database.init_schema()
    print("  Schema initialized")
    database.seed_default_settings()
    print("  Default settings seeded")
    should_seed_demo_resources = (
        _env_flag_enabled("SEED_DEMO_RESOURCES")
        if seed_demo_resources is None
        else seed_demo_resources
    )
    if should_seed_demo_resources:
        seed_resource_directory()
    print("SQLite initialization complete!")


def main():
    """Main seeding function"""
    print("=" * 60)
    print("Enclave Seed Script")
    print("=" * 60)

    # Initialize SQLite first (no external service to wait for)
    try:
        seed_sqlite()
    except Exception as e:
        print(f"ERROR initializing SQLite: {e}")
        sys.exit(1)

    # Initialize Qdrant client
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Wait for Qdrant
    if not wait_for_qdrant(client):
        print("ERROR: Qdrant did not become ready in time")
        sys.exit(1)

    # Seed data
    try:
        seed_qdrant(client)
        write_ready_seed_status()

        print("\n" + "=" * 60)
        print("Seeding complete!")
        print("Test with: curl http://localhost:8000/test")
        print("=" * 60)

    except Exception as e:
        if should_continue_after_qdrant_seed_failure(e):
            status = write_degraded_seed_status(e)
            print(f"WARNING: {status['message']}")
            print(f"Seed degraded reason: {status['reason']}")
            return
        print(f"ERROR during seeding: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
