"""Ambient User Memory capture for normal User Conversations."""

import json
import logging
import re
from typing import Any

import database

logger = logging.getLogger("sanctum.user_memory")

ALLOWED_AMBIENT_KINDS = {"preference", "communication_style", "interest"}
MAX_AMBIENT_IMPORTANCE = 5
SENSITIVE_TERMS = {
    "asylum",
    "citizenship",
    "criminal",
    "diagnosis",
    "disability",
    "eviction",
    "health",
    "income",
    "legal",
    "medical",
    "passport",
    "password",
    "political",
    "religion",
    "risk",
    "secret",
    "ssn",
    "trauma",
    "visa",
}


def ambient_capture_enabled() -> bool:
    return database.get_setting("ambient_user_memory_capture_enabled") == "true"


def likely_contains_personalization(message: str) -> bool:
    normalized = message.strip().lower()
    if not normalized:
        return False
    patterns = (
        r"\bremember\b",
        r"\bi prefer\b",
        r"\bi like\b",
        r"\bi usually\b",
        r"\bi tend to\b",
        r"\bmy preference\b",
        r"\bcall me\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def capture_ambient_user_memory(
    *,
    subject_user_id: int,
    user_message: str,
    assistant_message: str,
    provider: Any,
) -> None:
    """Best-effort post-response ambient capture. Logs failures without surfacing them."""
    try:
        if not ambient_capture_enabled():
            return
        if not likely_contains_personalization(user_message):
            return

        prompt = _build_extraction_prompt(
            user_message=user_message,
            assistant_message=assistant_message,
        )
        result = provider.complete(prompt, temperature=0.0)
        memories = _parse_extractor_output(result.content)
        for memory in memories:
            if not _ambient_memory_allowed(memory):
                continue
            database.create_user_memory(
                subject_user_id=subject_user_id,
                kind=memory["kind"],
                content=memory["content"],
                importance=int(memory.get("importance", 1)),
                confidence=float(memory.get("confidence", 0.5)),
                source_kind="ambient",
                source_conversation_id=None,
                author_actor="sage",
            )
    except Exception:
        logger.exception("Ambient User Memory capture failed")


def _build_extraction_prompt(*, user_message: str, assistant_message: str) -> str:
    return f"""=== USER MEMORY EXTRACTION ===
Extract only low-sensitivity durable personalization about the current User from the user's own message.
Ignore assistant text except as context. Ignore tool, retrieval, document, or third-party facts.
Return strict JSON only:
{{"memories":[{{"kind":"preference","content":"...","importance":1,"confidence":0.0}}]}}

Allowed kinds: preference, communication_style, interest.
Maximum ambient importance: {MAX_AMBIENT_IMPORTANCE}.

USER MESSAGE:
{user_message}

ASSISTANT RESPONSE:
{assistant_message}
"""


def _parse_extractor_output(content: str) -> list[dict]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        logger.debug("Ambient User Memory extractor returned malformed JSON: %s", str(e))
        return []
    memories = parsed.get("memories")
    if not isinstance(memories, list):
        return []
    return [memory for memory in memories if isinstance(memory, dict)]


def contains_direct_identifier(content: str) -> bool:
    normalized_content = content.lower()
    return any((
        re.search(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", normalized_content),
        re.search(r"(?:\+?\d[\s().-]*){7,15}", normalized_content),
        re.search(r"\b\d{3}-\d{2}-\d{4}\b", normalized_content),
        re.search(r"\b\d+\s+[\w\s.-]+?\b(?:st|street|ave|avenue|road|rd|lane|ln|apt|suite)\b", normalized_content),
    ))


def _ambient_memory_allowed(memory: dict) -> bool:
    kind = str(memory.get("kind", "")).strip()
    content = str(memory.get("content", "")).strip()
    if kind not in ALLOWED_AMBIENT_KINDS:
        return False
    if not content:
        return False
    try:
        importance = int(memory.get("importance", 1))
        confidence = float(memory.get("confidence", 0.5))
    except (TypeError, ValueError):
        return False
    if importance < 0 or importance > MAX_AMBIENT_IMPORTANCE:
        return False
    if confidence < 0 or confidence > 1:
        return False

    normalized_content = content.lower()
    if any(term in normalized_content for term in SENSITIVE_TERMS):
        return False
    if contains_direct_identifier(content):
        return False
    return True
