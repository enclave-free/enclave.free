"""
Enclave Retrieval Query Module

Session-aware Retrieval for querying the Document Library.
Pipeline: Query → Embed → Vector Search → Model Provider → Answer

Key principles:
- Provide clear, helpful responses
- Ask clarifying questions when context is needed
- Cite sources accurately
"""

import os
import re
import logging
import threading
import uuid
import json
from copy import deepcopy
from types import MappingProxyType
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import httpx

import auth
import ingest_db
from conversation_trace import ConversationTrace, RetrievalTrace, build_conversation_trace, build_live_trace_status
from protected_inference import ProtectedInferenceBlocked, inference_verification_reference, require_current_inference_verification
from data_deletion import (
    deletion_target_failed,
    deletion_target_skipped,
    deletion_target_succeeded,
    summarize_deletion_results,
)
from store import (
    embed_texts,
    COLLECTION_NAME,
    QDRANT_HOST,
    QDRANT_PORT,
)
from llm import get_sage_provider
from utils import sanitize_profile_value
from rate_limit import RateLimiter
from rate_limit_key import rate_limit_key as _stable_rate_limit_key

logger = logging.getLogger("enclave.query")

router = APIRouter(prefix="/query", tags=["query"])


def _require_protected_inference_or_503(context: str) -> dict:
    try:
        return require_current_inference_verification(context=context)
    except ProtectedInferenceBlocked as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# Configuration
TOP_K_VECTORS = int(os.getenv("RAG_TOP_K", "8"))  # More context for nuance
GRAPH_HOPS = int(os.getenv("RAG_GRAPH_HOPS", "2"))
QUERY_RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_QUERY_PER_MINUTE", "90"))

# Simple in-memory session store (replace with Redis/DB for production)
_sessions: dict[str, dict] = {}
_sessions_lock = threading.RLock()


def _rate_limit_key(request: Request) -> str:
    """Prefer auth identity for rate limiting; fallback to client IP."""
    return _stable_rate_limit_key(request)


query_limiter = RateLimiter(
    limit=QUERY_RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
    key_func=_rate_limit_key,
)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None


class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None  # For conversation continuity
    top_k: Optional[int] = None
    graph_hops: Optional[int] = None
    # Optional context the user provides upfront
    jurisdiction: Optional[str] = None  # e.g., "California", "Germany"
    situation_details: Optional[str] = None  # Any facts they share
    tools: list[str] = []  # Tool IDs enabled for this request
    job_ids: Optional[list[str]] = None  # Filter to specific documents by job ID


class QueryResponse(BaseModel):
    answer: str
    message_id: str
    session_id: str  # Return for continuity
    sources: list[dict]
    graph_context: dict
    clarifying_questions: list[str]  # Questions we need answered
    search_term: Optional[str] = None  # Auto-search term (if search tool enabled)
    # Debug/trace info
    context_used: str  # The actual context passed to LLM (for debugging)
    temperature: float  # Temperature used
    trace: Optional[ConversationTrace] = None
    inference_verification: Optional[dict] = None


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    user: dict = Depends(auth.require_admin_or_approved_user),
    _: None = Depends(query_limiter),
):
    """
    Retrieval query with session support.
    Requires authenticated admin OR approved user.

    1. Load/create session for conversation history
    2. Embed query with conversation context
    3. Vector search for relevant chunks
    4. Send context + history + query to the Model Provider
    5. Return answer with clarifying questions if needed
    """
    from ai_config import get_llm_parameters

    question = request.question

    # Get user_type_id from authenticated user for per-type config
    user_type_id = user.get("user_type_id")

    llm_params = get_llm_parameters(user_type_id=user_type_id) or {}

    # Get top_k from config if not specified in request
    if request.top_k is not None:
        top_k = request.top_k
    else:
        try:
            top_k = int(llm_params.get("top_k", TOP_K_VECTORS))
        except (ValueError, TypeError):
            top_k = TOP_K_VECTORS
    hops = min(request.graph_hops or GRAPH_HOPS, 2)
    
    # Session management
    session_id = request.session_id or str(uuid.uuid4())
    session = _get_or_create_session(session_id, user)
    session_lock = _session_lock(session)
    
    with session_lock:
        # Add user context if provided
        if request.jurisdiction and not session.get("jurisdiction"):
            session["jurisdiction"] = request.jurisdiction
        if request.situation_details:
            session["situation_details"] = session.get("situation_details", "") + "\n" + request.situation_details

        # Add user message to history
        session["messages"].append({
            "role": "user",
            "content": question,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    logger.info(f"RAG query (session={session_id[:8]}): '{question[:50]}...'")
    
    try:
        # Import database module once at the start of the function
        import database

        # 1. Embed the query (include conversation context for better retrieval)
        with session_lock:
            search_query = _build_search_query(question, session)
        query_embedding = embed_texts([f"query: {search_query}"])[0]

        # 2. Build filter for document access control
        # Admins can search all documents; non-admin users are restricted to their allowed documents
        search_filter = None
        is_admin_user = user.get("type") == "admin"

        if is_admin_user:
            # Admins: only filter if they explicitly request specific job_ids
            if request.job_ids and len(request.job_ids) > 0:
                search_filter = {
                    "should": [
                        {"key": "job_id", "match": {"value": job_id}}
                        for job_id in request.job_ids
                    ]
                }
                logger.debug(f"Admin filtering search to {len(request.job_ids)} documents")
        else:
            # Non-admin users: always filter to their allowed documents
            if user_type_id is None:
                # No user type means no document access for non-admin users.
                # Avoid querying availability with None to prevent global access.
                available_job_ids: set[str] = set()
            else:
                available_job_ids = set(database.get_available_documents_for_user_type(user_type_id))

            if request.job_ids and len(request.job_ids) > 0:
                # User requested specific documents - intersect with allowed
                allowed_job_ids = [jid for jid in request.job_ids if jid in available_job_ids]
            else:
                # No specific request - use all allowed documents for their user type
                allowed_job_ids = list(available_job_ids)

            if not allowed_job_ids:
                # No accessible documents - return zero results
                logger.warning(f"User has no accessible documents (user_type_id={user_type_id})")
                search_filter = {"must": [{"key": "job_id", "match": {"value": "__impossible__"}}]}
            else:
                # Build OR filter: match any of the allowed job_ids
                search_filter = {
                    "should": [
                        {"key": "job_id", "match": {"value": job_id}}
                        for job_id in allowed_job_ids
                    ]
                }
                logger.debug(f"Filtering search to {len(allowed_job_ids)} documents for user_type_id={user_type_id}")

        # 3. Vector search in Qdrant
        qdrant_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION_NAME}/points/search"
        search_payload = {
            "vector": query_embedding,
            "limit": top_k,
            "with_payload": True,
        }
        if search_filter:
            search_payload["filter"] = search_filter

        search_response = httpx.post(
            qdrant_url,
            json=search_payload,
            timeout=30.0,
        )
        search_response.raise_for_status()
        search_results = search_response.json().get("result", [])
        
        # Extract sources and chunk texts
        sources, entity_names, chunk_texts = _process_search_results(search_results)

        # Graph context no longer used - simple vector search only
        graph_context = {"actions": [], "risks": [], "guidance": [], "warnings": [], "resources": [], "preconditions": []}

        # 4. Build context and call LLM with context-aware prompt
        context = _build_context(chunk_texts, sources)
        with session_lock:
            session["_last_sources"] = sources  # For dynamic citation
            llm_session = _session_public_snapshot(session)

        # Get user profile context for chat personalization (unencrypted fields only)
        # Skip for dev mode (id=-1) and admin accounts (no user profile in users table)
        user_profile_context = None
        user_memory_context = None
        user_id = user.get("id")
        if user_id and user_id != -1 and user.get("type") != "admin":
            user_profile_context = database.get_user_chat_context_values(
                user_id=user_id,
                user_type_id=user_type_id
            )
            # Only pass if there's actual data
            if not user_profile_context:
                user_profile_context = None
            user_memory_context = database.list_active_user_memories(user_id, limit=20)
            if not user_memory_context:
                user_memory_context = None

        answer, clarifying_questions, full_prompt, search_term, inference_record = _call_llm_contextual(
            question, context, llm_session, tools=request.tools, user_type_id=user_type_id,
            user_profile_context=user_profile_context,
            user_memory_context=user_memory_context,
        )
        
        message_id = f"msg_{uuid.uuid4().hex}"
        trace = build_conversation_trace(
            actor_type=user.get("type", "user"),
            tools_used=[],
            retrieval=[
                RetrievalTrace(
                    source_type=str(source.get("type") or "document"),
                    title=str(source.get("source_file") or source.get("chunk_id") or "Retrieved source"),
                    summary="Retrieved matching source context.",
                    score=source.get("score"),
                )
                for source in sources
            ],
        )

        with session_lock:
            session["facts_gathered"].update(llm_session.get("facts_gathered", {}))
            append_assistant_message_with_trace(
                session,
                content=answer,
                message_id=message_id,
                trace=trace,
            )

            # Run dedicated fact extraction after response (more reliable than in-response tags)
            session["facts_gathered"] = _extract_facts_from_conversation(session)

            # Update jurisdiction from extracted facts if we got location/country
            if not session.get("jurisdiction"):
                facts = session.get("facts_gathered", {})
                if facts.get("location"):
                    session["jurisdiction"] = facts["location"]

            # Track what we still need to know
            if clarifying_questions:
                session["pending_questions"] = clarifying_questions
        
        # Get actual temperature for response (same logic as _call_llm_contextual)
        try:
            actual_temperature = float(llm_params.get("temperature", 0.1))
        except (ValueError, TypeError):
            actual_temperature = 0.1

        logger.info(f"RAG complete. Answer: {len(answer)} chars, {len(clarifying_questions)} clarifying Qs, search_term={search_term}, facts={session.get('facts_gathered', {})}")

        # Redact user profile and memory sections from debug output to avoid exposing sensitive data
        # Use line-anchored pattern to avoid stopping at === inside values
        debug_prompt = re.sub(
            r'^=== USER PROFILE ===.*?(?=^===|\Z)',
            '=== USER PROFILE ===\n[REDACTED]\n\n',
            full_prompt,
            flags=re.MULTILINE | re.DOTALL
        )
        debug_prompt = re.sub(
            r'^=== USER MEMORY ===.*?(?=^===|\Z)',
            '=== USER MEMORY ===\n[REDACTED]\n\n',
            debug_prompt,
            flags=re.MULTILINE | re.DOTALL
        )

        return QueryResponse(
            answer=answer,
            message_id=message_id,
            session_id=session_id,
            sources=sources,
            graph_context=graph_context,
            clarifying_questions=clarifying_questions,
            search_term=search_term,  # Auto-search trigger (if web-search tool enabled)
            context_used=debug_prompt,  # For debugging - redacted to protect user data
            temperature=actual_temperature,
            trace=trace,
            inference_verification=inference_verification_reference(inference_record),
        )
        
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def query_stream(
    request: QueryRequest,
    user: dict = Depends(auth.require_admin_or_approved_user),
    _: None = Depends(query_limiter),
):
    """Streaming Retrieval Conversation endpoint with final trace events."""

    async def event_stream():
        try:
            response_payload = await query(request=request, user=user, _=None)
            yield _sse_event(
                "assistant_message_started",
                {
                    "message_id": response_payload.message_id,
                    "session_id": response_payload.session_id,
                },
            )
            if response_payload.answer:
                trace_status = build_live_trace_status(response_payload.trace)
                if trace_status:
                    yield _sse_event(
                        "trace_status",
                        {
                            "message_id": response_payload.message_id,
                            "status": trace_status,
                        },
                    )
                yield _sse_event(
                    "answer_delta",
                    {
                        "message_id": response_payload.message_id,
                        "delta": response_payload.answer,
                    },
                )
            if response_payload.trace is not None:
                yield _sse_event(
                    "trace_final",
                    {
                        "message_id": response_payload.message_id,
                        "trace": response_payload.trace.model_dump(),
                    },
                )
            yield _sse_event(
                "done",
                {
                    "message_id": response_payload.message_id,
                    "session_id": response_payload.session_id,
                    "search_term": response_payload.search_term,
                    "inference_verification": response_payload.inference_verification,
                },
            )
        except HTTPException as exc:
            yield _sse_event(
                "error",
                {
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
        except Exception as exc:
            logger.exception("Streaming Retrieval query failed")
            yield _sse_event(
                "error",
                {
                    "status_code": 500,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _session_owner_for_user(user: dict) -> tuple[str, str]:
    """Build stable owner identity for session authorization."""
    uid = user.get("id")
    if uid is None:
        raise ValueError("User dict missing required 'id' field")
    if user.get("type") == "admin":
        return "admin", str(uid)
    return "user", str(uid)


def _can_access_session(user: dict, session: dict) -> bool:
    """
    Check whether a caller can access a session.
    Admins may access all sessions; users may only access their own.
    """
    if user.get("type") == "admin":
        return True

    owner_type, owner_id = _session_owner_for_user(user)
    return (
        session.get("owner_type") == owner_type
        and session.get("owner_id") == owner_id
    )


def _get_or_create_session(session_id: str, user: dict) -> dict:
    """Get existing authorized session or create a new owner-scoped session."""
    owner_type, owner_id = _session_owner_for_user(user)

    with _sessions_lock:
        if session_id in _sessions:
            session = _sessions[session_id]
            if not _can_access_session(user, session):
                raise HTTPException(status_code=403, detail="Session access denied")
            return session

        # New sessions are always owned by the caller creating them.
        _sessions[session_id] = {
            "id": session_id,
            "_lock": threading.RLock(),
            "owner_type": owner_type,
            "owner_id": owner_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "jurisdiction": None,
            "situation_details": None,
            "facts_gathered": {},
            "pending_questions": [],
        }
        return _sessions[session_id]


def _session_lock(session: dict) -> threading.RLock:
    lock = session.get("_lock")
    if lock is None:
        lock = threading.RLock()
        session["_lock"] = lock
    return lock


def _session_public_snapshot(session: dict) -> dict:
    return {key: deepcopy(value) for key, value in session.items() if key != "_lock"}


def append_assistant_message_with_trace(
    session: dict,
    *,
    content: str,
    message_id: str,
    trace: ConversationTrace | dict | None,
) -> None:
    """Append assistant turn metadata to a Conversation session."""
    message = {
        "id": message_id,
        "role": "assistant",
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if trace is not None:
        message["trace"] = trace.model_dump() if hasattr(trace, "model_dump") else trace
    session["messages"].append(message)


def delete_sessions_for_owner(owner_type: str, owner_id: str) -> int:
    """Return the count of in-memory Retrieval sessions removed for an owner.

    This convenience wrapper calls pop_sessions_for_owner and discards the
    popped session dicts. Callers that need Sage/Session Memory cleanup must use
    pop_sessions_for_owner(owner_type, owner_id) directly and handle each
    returned session.
    """
    return len(pop_sessions_for_owner(owner_type, owner_id))


def pop_sessions_for_owner(owner_type: str, owner_id: str) -> list[dict]:
    """Remove and return in-memory Retrieval sessions owned by a profile or admin actor."""
    with _sessions_lock:
        session_ids = _session_ids_for_owner(owner_type, owner_id)
        sessions = []
        for session_id in session_ids:
            original = _sessions.get(session_id)
            if original is not None:
                _sessions[session_id] = _freeze_session_snapshot(original)
            session = _sessions.pop(session_id, None)
            if session is not None:
                sessions.append(session)
    return sessions


def sessions_for_owner(owner_type: str, owner_id: str) -> list[dict]:
    """Return frozen snapshots for in-memory Retrieval sessions owned by an actor."""
    with _sessions_lock:
        return [
            _freeze_session_snapshot(_sessions[session_id])
            for session_id in _session_ids_for_owner(owner_type, owner_id)
        ]


def _session_ids_for_owner(owner_type: str, owner_id: str) -> list[str]:
    return [
        session_id
        for session_id, session in _sessions.items()
        if session.get("owner_type") == owner_type and session.get("owner_id") == owner_id
    ]


def _freeze_session_snapshot(session: dict) -> MappingProxyType:
    snapshot = {
        key: deepcopy(value)
        for key, value in session.items()
        if key != "_lock"
    }
    return MappingProxyType(snapshot)


def _extract_facts_from_conversation(session: dict) -> dict:
    """
    Dedicated fact extraction pass - runs after main response.
    Uses a focused prompt to reliably extract structured facts from conversation.
    """
    import json as json_module
    llm = get_sage_provider()
    
    # Format conversation for fact extraction
    messages = session.get("messages", [])
    if not messages:
        return {}
    
    conversation_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}"
        for m in messages[-8:]  # Last 4 exchanges max
    ])
    
    # Get existing facts to avoid overwriting with "unknown"
    existing_facts = session.get("facts_gathered", {})
    
    prompt = f"""Extract ONLY facts that are EXPLICITLY stated in this conversation.
Do NOT guess or infer. If something is not clearly stated, use null.

Conversation:
{conversation_text}

Extract these facts (use null if not explicitly mentioned):
- location: Where is the USER currently located? (city/country)
- topic: What is the main topic or subject of the query?
- context_details: Any relevant context provided by the user
- timeframe: When did relevant events happen? (e.g., "3 days ago", "last week")

Return ONLY valid JSON, no explanation:
{{"location": ..., "topic": ..., "context_details": ..., "timeframe": ...}}"""

    try:
        response = llm.complete(prompt, temperature=0.0)
        content = response.content.strip()
        
        # Try to extract JSON from response (handle markdown code blocks)
        if "```" in content:
            # Extract from code block
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
        
        # Parse JSON
        extracted = json_module.loads(content)
        
        # Merge with existing facts, only updating non-null values
        for key, value in extracted.items():
            if value is not None and value != "null" and value != "":
                existing_facts[key] = value
        
        logger.info(f"Fact extraction complete: {existing_facts}")
        return existing_facts
        
    except Exception as e:
        logger.warning(f"Fact extraction failed: {e}")
        return existing_facts


def _build_search_query(question: str, session: dict) -> str:
    """Build search query including relevant session context."""
    parts = [question]
    
    if session.get("jurisdiction"):
        parts.append(f"jurisdiction: {session['jurisdiction']}")
    
    if session.get("situation_details"):
        # Include recent situation details for better retrieval
        parts.append(session["situation_details"][-500:])
    
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
        
        for name in payload.get("entity_names", []):
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

    # Include full chunk texts
    if chunk_texts:
        parts.append("=== RELEVANT PASSAGES ===")
        for i, text in enumerate(chunk_texts[:6], 1):
            parts.append(f"[{i}] {text[:800]}")
            parts.append("")

    return "\n".join(parts)


def _call_llm_contextual(
    question: str,
    context: str,
    session: dict,
    tools: Optional[list[str]] = None,
    user_type_id: int | None = None,
    user_profile_context: dict[str, str] | None = None,
    user_memory_context: list[dict] | None = None,
) -> tuple[str, list[str], str, Optional[str], dict | None]:
    """
    Call LLM with context-aware prompt.
    Returns (answer, list of clarifying questions, full_prompt for debugging, search_term or None).

    Args:
        question: The user's question
        context: Retrieved context from vector search
        session: Session state dict
        tools: List of enabled tool IDs
        user_type_id: If provided, uses user-type-specific prompt sections and parameters
        user_profile_context: Optional dict of {field_name: value} for user profile data
        user_memory_context: Optional active User Memory records for Sage-owned context
    """
    import re
    from ai_config import get_prompt_sections, get_llm_parameters
    llm = get_sage_provider()
    tools = tools or []

    # Get prompt sections from database with user-type overrides if applicable
    prompt_sections = get_prompt_sections(user_type_id=user_type_id) or {}
    llm_params = get_llm_parameters(user_type_id=user_type_id) or {}

    # Get temperature from config (with fallback and type coercion)
    try:
        temperature = float(llm_params.get("temperature", 0.1))
    except (ValueError, TypeError):
        temperature = 0.1

    # Build conversation history for context
    history_str = ""
    if session["messages"]:
        recent = session["messages"][-6:]  # Last 3 exchanges
        history_str = "\n".join([
            f"{'User' if m['role']=='user' else 'Assistant'}: {m['content'][:300]}"
            for m in recent[:-1]  # Exclude current message
        ])

    # Extract source files from context for citation
    source_files = set()
    for src in session.get("_last_sources", []):
        sf = src.get("source_file", "")
        if sf:
            source_files.add(sf.replace(".pdf", "").replace("-", " ").replace("_", " "))
    source_citation = ", ".join(source_files) if source_files else "knowledge base documents"

    # Build known facts section - treat these as CONFIRMED, do not re-ask
    facts = session.get("facts_gathered", {})
    if facts:
        facts_lines = []
        for key, value in facts.items():
            if value:
                facts_lines.append(f"  - {key}: {value}")
        known_facts_section = "=== CONFIRMED FACTS (do NOT re-ask these) ===\n" + "\n".join(facts_lines)
        jurisdiction_note = "Use the confirmed facts above. Only ask clarifying questions about things NOT already known."
    else:
        known_facts_section = "=== NO FACTS CONFIRMED YET ===\nAsk about location and context early, but only once per conversation."
        jurisdiction_note = "We don't know location yet. Ask about it, but don't repeatedly ask if user doesn't answer."

    # Build user profile section (if any profile data is available)
    user_profile_section = ""
    if user_profile_context:
        profile_lines = [f"  - {field_name}: {sanitize_profile_value(value)}" for field_name, value in user_profile_context.items()]
        user_profile_section = "\n\n=== USER PROFILE ===\nThe following information is known about the user:\n" + "\n".join(profile_lines)

    # Build User Memory section separately from User Profile and Session Memory.
    user_memory_section = ""
    if user_memory_context:
        memory_lines = []
        for memory in user_memory_context:
            kind = sanitize_profile_value(str(memory.get("kind", "")))
            content = sanitize_profile_value(str(memory.get("content", "")))
            importance = memory.get("importance")
            confidence = memory.get("confidence")
            memory_lines.append(f"  - {kind}: {content} (importance: {importance}, confidence: {confidence})")
        user_memory_section = "\n\n=== USER MEMORY ===\nThe following low-sensitivity Sage-owned context is known about the user:\n" + "\n".join(memory_lines)

    # Auto-search instruction if web-search tool is enabled
    search_instruction = ""
    if "web-search" in tools:
        search_instruction = """
=== AUTO-SEARCH (IMPORTANT!) ===
Add [SEARCH: specific term] at the END of your response when:
- User says "I don't know anyone/any lawyers/who to call" → SEARCH NOW
- User needs embassy, lawyer, NGO, or hotline contacts → SEARCH NOW
- User asks "who do I contact" or "where do I find" → SEARCH NOW

Do NOT tell them to "look up" or "search for" something - just trigger the search.
Make search terms specific: "[SEARCH: local library hours downtown]"
"""

    # Build system prompt and style sections from config
    configured_system_prompt = str(prompt_sections.get("prompt_system") or "").strip()
    system_prompt = configured_system_prompt or "You are a helpful, knowledgeable assistant."
    system_section = f"=== SYSTEM PROMPT ===\n{system_prompt}"
    prompt_tone = prompt_sections.get("prompt_tone", "Be helpful, concise, and professional.")
    style_section = f"=== STYLE ===\n{prompt_tone}"
    if search_instruction:
        style_section += f"\n{search_instruction}"

    # Build rules section from config
    prompt_rules = prompt_sections.get("prompt_rules", [])
    if isinstance(prompt_rules, list) and prompt_rules:
        rules_lines = [f"{i}. {rule}" for i, rule in enumerate(prompt_rules, 1)]
        rules_lines.append(f"{len(prompt_rules) + 1}. {jurisdiction_note}")
        rules_lines.append(f"{len(prompt_rules) + 2}. Do NOT repeat questions already answered in CONFIRMED FACTS above")
        rules_section = "=== RULES ===\n" + "\n".join(rules_lines)
    else:
        rules_section = f"""=== RULES ===
1. ONE action per response when providing step-by-step guidance
2. NEVER invent sources, organization names, or contact information
3. If asked about topics outside your knowledge base, acknowledge limitations
4. {jurisdiction_note}
5. Do NOT repeat questions already answered in CONFIRMED FACTS above"""

    # Build forbidden topics section from config (if any)
    prompt_forbidden = prompt_sections.get("prompt_forbidden", [])
    forbidden_section = ""
    if isinstance(prompt_forbidden, list) and prompt_forbidden:
        forbidden_section = "\n\n=== FORBIDDEN TOPICS ===\nIf asked about these topics, politely decline:\n"
        forbidden_section += "\n".join([f"- {topic}" for topic in prompt_forbidden])

    prompt = f"""{system_section}

{known_facts_section}{user_profile_section}{user_memory_section}

{style_section}

{rules_section}{forbidden_section}

=== SOURCE ===
{source_citation}

=== CONVERSATION ===
{history_str if history_str else "(Start)"}

=== CONTEXT ===
{context}

=== QUESTION ===
{question}

=== RESPOND ==="""

    inference_record = _require_protected_inference_or_503("rag_query")
    response = llm.complete(prompt, temperature=temperature)
    answer = response.content
    
    # Extract search term if present
    search_term = None
    search_match = re.search(r'\[SEARCH:\s*([^\]]+)\]', answer)
    if search_match:
        search_term = search_match.group(1).strip()
        # Remove the search tag from the visible answer
        answer = re.sub(r'\s*\[SEARCH:\s*[^\]]+\]\s*', '', answer).strip()
    
    # Extract and store facts (always strip from visible answer)
    answer = re.sub(r'\s*\[FACTS:[^\]]*\]\s*', '', answer).strip()
    facts_match = re.search(r'\[FACTS:\s*([^\]]+)\]', response.content)
    if facts_match:
        facts_str = facts_match.group(1).strip()
        if facts_str:
            with _session_lock(session):
                for pair in facts_str.split(','):
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        key, value = key.strip(), value.strip()
                        if key and value:
                            if "facts_gathered" not in session:
                                session["facts_gathered"] = {}
                            session["facts_gathered"][key] = value
            logger.info(f"Session facts updated: {session.get('facts_gathered', {})}")
    
    # Extract clarifying questions (lines starting with ?)
    clarifying_questions = []
    lines = answer.split("\n")
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("?"):
            clarifying_questions.append(stripped[1:].strip())
    
    # Return answer, questions, full prompt for debugging, and search term
    return answer, clarifying_questions, prompt, search_term, inference_record


@router.get("/session/{session_id}")
async def get_session(session_id: str, user: dict = Depends(auth.require_admin_or_approved_user)):
    """Get session history and state. Requires auth."""
    with _sessions_lock:
        if session_id not in _sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        session = _sessions[session_id]
        if not _can_access_session(user, session):
            raise HTTPException(status_code=403, detail="Session access denied")
        with _session_lock(session):
            return _session_public_snapshot(session)


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(auth.require_admin_or_approved_user)):
    """Delete a session. Requires auth."""
    deleted_session = None
    with _sessions_lock:
        if session_id in _sessions:
            session = _sessions[session_id]
            if not _can_access_session(user, session):
                raise HTTPException(status_code=403, detail="Session access denied")
            _sessions[session_id] = _freeze_session_snapshot(session)
            deleted_session = _sessions.pop(session_id)
    if deleted_session is None:
        deletion = summarize_deletion_results([
            deletion_target_skipped(
                target_kind="conversation",
                target_id=session_id,
                action="delete_session_record",
                detail="Conversation record was already absent.",
            )
        ])
        import lifecycle
        lifecycle.audit_lifecycle_deletion(
            config_key=f"conversation:{session_id}:delete",
            changed_by=user.get("pubkey", str(user.get("id", "unknown"))),
            workflow="delete_conversation",
            target_id=session_id,
            deletion=deletion,
        )
        return {"status": "deleted", "deletion": deletion}

    import lifecycle

    try:
        session_memory_deletion = await lifecycle.delete_session_memory_for_conversation(deleted_session)
    except Exception as exc:
        logger.warning(
            "Failed to delete Session Memory for Conversation session_id=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        session_memory_deletion = summarize_deletion_results([
            deletion_target_failed(
                target_kind="session_memory",
                target_id=session_id,
                action="delete_session_memory",
                detail=lifecycle.categorize_error(exc),
                retryable=True,
            )
        ])
    if session_memory_deletion["status"] != "succeeded":
        try:
            lifecycle.create_session_memory_tombstone(
                session=deleted_session,
                source="user_conversation_delete" if user.get("type") != "admin" else "admin_conversation_delete",
                workflow="delete_conversation",
                deletion=session_memory_deletion,
            )
        except Exception as exc:
            logger.exception(
                "Failed to create Session Memory deletion tombstone for session_id=%s",
                session_id,
            )
            with _sessions_lock:
                if session_id not in _sessions:
                    restored_session = deepcopy(dict(deleted_session))
                    restored_session["_lock"] = threading.RLock()
                    _sessions[session_id] = restored_session
            session_memory_deletion = summarize_deletion_results([
                *session_memory_deletion.get("results", []),
                deletion_target_failed(
                    target_kind="deletion_tombstone",
                    target_id=session_id,
                    action="create_session_memory_tombstone",
                    detail=lifecycle.categorize_error(exc),
                    retryable=True,
                ),
            ])
    session_memory_results = session_memory_deletion.get("results", [])
    if not isinstance(session_memory_results, list):
        session_memory_results = []
    deletion = summarize_deletion_results([
        deletion_target_succeeded(
            target_kind="conversation",
            target_id=session_id,
            action="delete_session_record",
            detail="Deleted active Conversation record.",
        ),
        *session_memory_results,
    ])
    lifecycle.audit_lifecycle_deletion(
        config_key=f"conversation:{session_id}:delete",
        changed_by=user.get("pubkey", str(user.get("id", "unknown"))),
        workflow="delete_conversation",
        target_id=session_id,
        deletion=deletion,
    )
    return {"status": "deleted", "deletion": deletion}
