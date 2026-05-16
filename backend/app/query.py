"""
Private Retrieval helpers for the Sage-to-Python Control Plane contract.

Public Agent Runtime routes and Conversation session storage live in Sage.
Python keeps only the Document Library search helpers Sage calls through
`/internal/agent/document-search`.
"""

import logging

import ingest_db

logger = logging.getLogger("enclave.query")


def _build_search_query(question: str, session: dict) -> str:
    """Build search query including relevant caller-provided context."""
    parts = [question]

    if session.get("jurisdiction"):
        parts.append(f"jurisdiction: {session['jurisdiction']}")

    if session.get("situation_details"):
        situation_details = session["situation_details"]
        if isinstance(situation_details, str):
            details_text = situation_details
        elif isinstance(situation_details, (list, tuple)):
            details_text = " ".join(str(detail) for detail in situation_details)
        else:
            details_text = str(situation_details)
        parts.append(details_text[-500:])

    return " ".join(parts)


def _process_search_results(search_results: list) -> tuple[list, set, list]:
    """Process Qdrant results into sources, entity names, and chunk texts."""
    sources = []
    entity_names = set()
    chunk_texts = []

    for result in search_results:
        payload = result.get("payload", {})
        score = result.get("score", 0)

        source = {
            "score": score,
            "type": payload.get("type", "unknown"),
            "text": "",
            "chunk_id": payload.get("chunk_id", ""),
            "source_file": payload.get("source_file", ""),
            "hydrated": False,
            "hydration_status": "not_applicable",
        }

        payload_text = payload.get("text") or payload.get("fact_text", "")
        if payload.get("type") == "chunk":
            hydrated_text, hydration_status = _hydrate_chunk_text(payload)
            source["hydrated"] = hydrated_text is not None
            source["hydration_status"] = hydration_status
            if hydrated_text is not None:
                source["text"] = hydrated_text
                chunk_texts.append(hydrated_text)
            elif payload.get("text") and hydration_status != "missing_payload_job_id":
                source["text"] = payload["text"]
                source["hydration_status"] = "legacy_payload"
                chunk_texts.append(payload["text"])
        elif payload_text:
            source["text"] = payload_text
            chunk_texts.append(payload_text)

        sources.append(source)

        if payload.get("type") == "fact":
            entity_names.add(payload.get("from_entity", ""))
            entity_names.add(payload.get("to_entity", ""))

        raw_entity_names = payload.get("entity_names")
        if isinstance(raw_entity_names, str):
            payload_entity_names = [raw_entity_names]
        elif isinstance(raw_entity_names, (list, tuple, set)):
            payload_entity_names = raw_entity_names
        else:
            payload_entity_names = []

        for name in payload_entity_names:
            entity_names.add(name)

    entity_names.discard("")
    return sources, entity_names, chunk_texts


def _hydrate_chunk_text(payload: dict) -> tuple[str | None, str]:
    """Hydrate minimized Qdrant chunk hits from encrypted product-owned storage."""
    chunk_id = payload.get("chunk_id")
    if not chunk_id:
        return None, "missing_chunk_id"

    payload_job_id = payload.get("job_id")
    if not payload_job_id:
        logger.warning("Retrieval chunk hydration skipped for %s: missing payload job_id", chunk_id)
        return None, "missing_payload_job_id"

    try:
        chunk = ingest_db.get_retrieval_chunk(chunk_id)
    except Exception as exc:
        logger.warning("Retrieval chunk hydration failed for %s: %s", chunk_id, exc)
        return None, "error"

    if chunk is None:
        return None, "missing"
    if chunk.get("text") is None and chunk.get("decryption_error"):
        logger.warning(
            "Retrieval chunk hydration failed for %s: %s",
            chunk_id,
            chunk.get("decryption_error"),
        )
        return None, "decryption_error"

    if chunk.get("job_id") != payload_job_id:
        logger.warning(
            "Retrieval chunk hydration skipped for %s: payload job_id %s does not match stored job_id %s",
            chunk_id,
            payload_job_id,
            chunk.get("job_id"),
        )
        return None, "job_mismatch"

    return chunk["text"], "hydrated"


def _build_context(chunk_texts: list[str], sources: list[dict]) -> str:
    """Build context string from retrieved chunks."""
    parts = []

    if chunk_texts:
        parts.append("=== RELEVANT PASSAGES ===")
        for i, text in enumerate(chunk_texts[:6], 1):
            parts.append(f"[{i}] {text[:800]}")
            parts.append("")

    return "\n".join(parts)
