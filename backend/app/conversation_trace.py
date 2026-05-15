"""Conversation Trace contracts and policy filtering."""

from __future__ import annotations

import json
import logging
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

import database
from tools import ToolCallInfo

logger = logging.getLogger("enclave.conversation_trace")


TraceVisibility = Literal["off", "minimal", "summary", "detailed"]
TraceExecution = Literal["client", "server"]
TraceStatus = Literal["success", "error", "skipped"]

TRACE_VISIBILITIES = {"off", "minimal", "summary", "detailed"}
USER_TRACE_VISIBILITIES = {"off", "minimal", "summary"}
FORBIDDEN_TRACE_PATTERNS = (
    re.compile(r"\bSECRET_KEY\s*=", re.IGNORECASE),
    re.compile(r"\bLLM_API_KEY\s*=", re.IGNORECASE),
    re.compile(r"\bTINFOIL_API_KEY\s*=", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\s*=", re.IGNORECASE),
)


class TraceRedactionFailure(Exception):
    """Raised when trace metadata contains content that cannot be safely summarized."""


class ReasoningTrace(BaseModel):
    summary: str


class ToolTrace(BaseModel):
    id: str
    name: str
    status: TraceStatus = "success"
    execution: TraceExecution = "server"
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RetrievalTrace(BaseModel):
    source_type: str = "document"
    title: Optional[str] = None
    summary: Optional[str] = None
    score: Optional[float] = None
    metadata: dict = Field(default_factory=dict)


class ConversationTrace(BaseModel):
    visibility: TraceVisibility
    reasoning: ReasoningTrace
    tools: list[ToolTrace] = Field(default_factory=list)
    retrieval: list[RetrievalTrace] = Field(default_factory=list)
    suppressed: bool = False


def validate_trace_visibility(actor_type: str, value: str) -> TraceVisibility:
    normalized = (value or "").strip().lower()
    allowed = USER_TRACE_VISIBILITIES if actor_type == "user" else TRACE_VISIBILITIES
    if normalized not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"Trace visibility for {actor_type} must be one of: {allowed_list}")
    return normalized  # type: ignore[return-value]


def get_trace_visibility_for_actor(actor_type: str) -> TraceVisibility:
    key = "admin_trace_visibility" if actor_type == "admin" else "user_trace_visibility"
    default = "detailed" if actor_type == "admin" else "minimal"
    row = database.get_ai_config(key)
    value = row["value"] if row else default
    return validate_trace_visibility(actor_type, value)


def build_reasoning_summary(*, tools: list[ToolTrace], retrieval: list[RetrievalTrace]) -> str:
    if retrieval and tools:
        return "Sage used retrieval and enabled tools before answering."
    if retrieval:
        return "Sage searched available documents before answering."
    if tools:
        names = ", ".join(tool.name for tool in tools)
        return f"Sage used {names} before answering."
    return "Sage answered from the conversation context and configured instructions."


def summarize_tool_call(info: ToolCallInfo, *, execution: TraceExecution = "server") -> ToolTrace:
    warnings: list[str] = []
    metadata: dict = {}
    input_summary = _summarize_query(info.tool_id, info.query)
    output_summary: Optional[str] = None

    if info.tool_id == "db-query":
        warnings.append("raw_results_redacted")
        output_summary = "Database results were redacted from the trace."
        metadata["redacted"] = True

    return ToolTrace(
        id=info.tool_id,
        name=info.tool_name,
        execution=execution,
        input_summary=input_summary,
        output_summary=output_summary,
        metadata=metadata,
        warnings=warnings,
    )


def build_conversation_trace(
    *,
    actor_type: str,
    tools_used: list[ToolCallInfo],
    retrieval: Optional[list[RetrievalTrace]] = None,
) -> ConversationTrace | None:
    visibility = get_trace_visibility_for_actor(actor_type)
    if visibility == "off":
        return None

    try:
        tool_traces = [summarize_tool_call(info) for info in tools_used]
        retrieval_traces = retrieval or []
        trace = ConversationTrace(
            visibility=visibility,
            reasoning=ReasoningTrace(summary=build_reasoning_summary(tools=tool_traces, retrieval=retrieval_traces)),
            tools=tool_traces,
            retrieval=retrieval_traces,
        )
        return filter_trace_for_visibility(trace, actor_type=actor_type)
    except TraceRedactionFailure:
        _audit_trace_redaction_failure(actor_type=actor_type)
        return ConversationTrace(
            visibility=visibility,
            reasoning=ReasoningTrace(summary="Conversation Trace was suppressed because safe redaction could not be verified."),
            tools=[],
            retrieval=[],
            suppressed=True,
        )


def build_live_trace_status(trace: ConversationTrace | None) -> str | None:
    if trace is None or trace.visibility == "off" or trace.suppressed:
        return None
    if trace.retrieval:
        return "Searching documents"
    if trace.tools:
        names = ", ".join(tool.name for tool in trace.tools)
        return f"Using {names}"
    return "Writing answer"


def filter_trace_for_visibility(trace: ConversationTrace, *, actor_type: str) -> ConversationTrace:
    visibility = validate_trace_visibility(actor_type, trace.visibility)
    if visibility == "minimal":
        return ConversationTrace(
            visibility=visibility,
            reasoning=trace.reasoning,
            tools=[
                ToolTrace(id=tool.id, name=tool.name, status=tool.status, execution=tool.execution)
                for tool in trace.tools
            ],
            retrieval=[
                RetrievalTrace(source_type=item.source_type, title=item.title)
                for item in trace.retrieval
            ],
            suppressed=trace.suppressed,
        )
    if visibility == "summary":
        return ConversationTrace(
            visibility=visibility,
            reasoning=trace.reasoning,
            tools=[
                ToolTrace(
                    id=tool.id,
                    name=tool.name,
                    status=tool.status,
                    execution=tool.execution,
                    input_summary=tool.input_summary,
                    output_summary=tool.output_summary,
                    warnings=tool.warnings,
                )
                for tool in trace.tools
            ],
            retrieval=trace.retrieval,
            suppressed=trace.suppressed,
        )
    return trace


def _summarize_query(tool_id: str, query: str | None) -> str | None:
    if not query:
        return None
    compact = " ".join(str(query).split())
    _ensure_trace_text_is_safe(compact)
    if tool_id == "db-query":
        compact = _redact_sql_literals(compact)
    if len(compact) > 160:
        compact = compact[:157].rstrip() + "..."
    return compact


def _redact_sql_literals(sql: str) -> str:
    redacted = re.sub(r"'[^']*'", "'[redacted]'", sql)
    redacted = re.sub(r'"[^"]*"', '"[redacted]"', redacted)
    return redacted


def _ensure_trace_text_is_safe(value: str) -> None:
    for pattern in FORBIDDEN_TRACE_PATTERNS:
        if pattern.search(value):
            raise TraceRedactionFailure("unsafe trace content")


def _audit_trace_redaction_failure(*, actor_type: str) -> None:
    try:
        database.log_config_audit_event(
            table_name="conversation_trace",
            config_key="redaction_failure",
            old_value=None,
            new_value=json.dumps({
                "event": "trace_suppressed",
                "actor_type": actor_type,
                "reason": "redaction_failure",
            }, separators=(",", ":")),
            changed_by=f"system:conversation-trace:{actor_type}",
        )
    except Exception as exc:
        logger.warning("Failed to audit Conversation Trace redaction failure: %s", exc)
