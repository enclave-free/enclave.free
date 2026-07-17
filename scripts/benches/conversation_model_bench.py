#!/usr/bin/env python3
"""
Conversation Model Bench.

This is an opt-in evidence runner for real Sage Conversation behavior. The
public interface is the CLI and the `run_bench` function; local Docker/HTTP
details live behind small adapters so deterministic checks can be tested without
live Model Provider calls.
"""

from __future__ import annotations

import argparse
import codecs
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_ARGS = [
    "docker",
    "compose",
    "-f",
    "docker-compose.infra.yml",
    "-f",
    "docker-compose.app.yml",
]
DEFAULT_API_BASE = "http://127.0.0.1:18000"
DEFAULT_TIMEOUT_SECONDS = 180.0
SLOW_FIRST_ANSWER_WARNING_MS = 30_000.0
SLOW_TRACE_FEEDBACK_WARNING_MS = 10_000.0
SLOW_COMPLETION_WARNING_MS = 90_000.0
DEFAULT_SCENARIOS = (
    "admin_no_tools_control",
    "admin_config_bootstrap",
    "admin_config_live_onboarding_prompt",
    "admin_deployment_readiness",
    "admin_database_direct_select",
    "admin_database_natural_language_guardrail",
    "user_knowledge_assistance",
    "user_curated_resource_referral",
    "user_knowledge_and_resource_assistance",
)

LOW_LEVEL_ADMIN_CONFIG_READ_TOOLS: set[str] = {
    "read_instance_settings",
    "read_deployment_settings",
    "read_deployment_readiness",
    "read_agent_settings",
    "read_user_types",
    "read_document_access",
    "read_onboarding_status",
}
USER_CONVERSATION_TOOL_SET_IDS = frozenset(
    {"curated-resources", "knowledge-search", "web-search"}
)


@dataclass(frozen=True)
class BenchOptions:
    api_base: str = DEFAULT_API_BASE
    output: str | None = None
    scenarios: tuple[str, ...] = DEFAULT_SCENARIOS
    models: tuple[str, ...] = ()
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    reset: bool = False
    seed_knowledge: bool = False
    seed_resources: bool = False
    restore_model: bool = True
    verbose: bool = False


@dataclass(frozen=True)
class Scenario:
    id: str
    actor: str
    message: str
    tools: tuple[str, ...]


@dataclass(frozen=True)
class StreamResult:
    answer: str
    events: list[dict[str, Any]]
    done: dict[str, Any]
    trace: dict[str, Any] | None
    admin_change_set: dict[str, Any] | None
    timings: dict[str, float | None]
    error: str | None = None


class BenchEnvironment(Protocol):
    def run_metadata(self) -> dict[str, Any]:
        ...

    def current_model(self) -> str:
        ...

    def verify_runtime_model(self, expected_model: str | None = None) -> dict[str, Any]:
        ...

    def admin_token(self) -> str:
        ...

    def user_token(self, tools: tuple[str, ...] = ()) -> str:
        ...

    def seed_knowledge(self) -> dict[str, Any]:
        ...

    def seed_resources(self) -> dict[str, Any]:
        ...

    def database_user_count(self) -> int:
        ...

    def cleanup_scenario(self) -> None:
        ...

    def switch_model(self, model: str) -> None:
        ...

    def wait_for_health(self) -> None:
        ...

    def restore_model(self, model: str) -> None:
        ...

    def reset_state(self) -> None:
        ...


class ConversationClient(Protocol):
    def stream_chat(self, token: str, payload: dict[str, Any], timeout: float) -> StreamResult:
        ...

    def delete_session(self, token: str, session_id: str, timeout: float) -> None:
        ...


SCENARIOS: dict[str, Scenario] = {
    "admin_no_tools_control": Scenario(
        id="admin_no_tools_control",
        actor="admin",
        message=(
            "Without using any tools, answer this control question in one short "
            "sentence: what is two plus two?"
        ),
        tools=(),
    ),
    "admin_config_bootstrap": Scenario(
        id="admin_config_bootstrap",
        actor="admin",
        message=(
            "Set up the instance with these onboarding answers:\n"
            "1. FreeThem\n"
            "2. We are the Political Prisoners Support Team, an arm of the World Liberty Congress organization that helps former political prisoners and families of political prisoners get support and information and resources.\n"
            "3. Choose a simple assistant name.\n"
            "4. Choose the accent color.\n"
            "5. Dark theme.\n"
            "6. English.\n"
            "7. political prisoner support team.\n"
            "8. Let new users in right away. Create two simple user types: family and friends of current political prisoners, and former political prisoners with their family and friends.\n"
            "9. Add onboarding questions for what country the user is in and what kind of support they need. Include those answers in chat context.\n"
            "10. Add a behavior rule to ask where users are before giving location-specific guidance.\n"
            "Call propose_admin_config_bootstrap directly for this guided setup/bootstrap flow, then prepare the changes for review."
        ),
        tools=("admin-config",),
    ),
    "admin_config_live_onboarding_prompt": Scenario(
        id="admin_config_live_onboarding_prompt",
        actor="admin",
        message=(
            "- 1. FreeThem\n"
            "2. We are the political prisoners support team an arm of the World Liberty Congress\n"
            "3. Your call\n"
            "4. Your call\n"
            "5. dark please\n"
            "6. english\n"
            "7. political prisoners support team\n"
            "8. Yes don't block access\n"
            "9. there are two kinds of users. families and friends of current political prisoners "
            "(support those in the situation) and friends/family/former political prisoners "
            "(support for those after the situation)"
        ),
        tools=("admin-config",),
    ),
    "admin_deployment_readiness": Scenario(
        id="admin_deployment_readiness",
        actor="admin",
        message=(
            "Check our actual instance configuration and deployment readiness. "
            "What is still not set up? Use Admin Config tools; do not ask me to "
            "check manually. Keep it brief."
        ),
        tools=("admin-config",),
    ),
    "user_knowledge_assistance": Scenario(
        id="user_knowledge_assistance",
        actor="user",
        message=(
            "Use the knowledge base if it has anything relevant. A family member "
            "says their loved one was just released after political imprisonment "
            "and feels unsafe. What should they do first today?"
        ),
        tools=("knowledge-search",),
    ),
    "admin_database_direct_select": Scenario(
        id="admin_database_direct_select",
        actor="admin",
        message=(
            "SELECT key, value FROM instance_settings "
            "WHERE key IN ('instance_name', 'assistant_name', 'default_language') "
            "ORDER BY key LIMIT 10"
        ),
        tools=("db-query",),
    ),
    "admin_database_natural_language_guardrail": Scenario(
        id="admin_database_natural_language_guardrail",
        actor="admin",
        message=(
            "Use the Database Query tool to tell me how many users are in SQLite. "
            "Choose and run a safe read-only SELECT yourself; do not ask me to "
            "write SQL."
        ),
        tools=("db-query",),
    ),
    "user_curated_resource_referral": Scenario(
        id="user_curated_resource_referral",
        actor="user",
        message=(
            "My sibling was just released from detention in Nicaragua and needs a "
            "vetted legal referral. Use curated resources if available, and do not "
            "invent contact details."
        ),
        tools=("curated-resources",),
    ),
    "user_knowledge_and_resource_assistance": Scenario(
        id="user_knowledge_and_resource_assistance",
        actor="user",
        message=(
            "A family member in Nicaragua says their loved one was just released "
            "after political imprisonment and feels unsafe. Give first-day safety "
            "steps and a real legal or humanitarian referral if curated resources "
            "have one."
        ),
        tools=("knowledge-search", "curated-resources"),
    ),
}


def run_bench(
    options: BenchOptions,
    *,
    environment: BenchEnvironment | None = None,
    client: ConversationClient | None = None,
) -> dict[str, Any]:
    environment = environment or LocalComposeEnvironment()
    client = client or HttpConversationClient(options.api_base)

    if options.reset:
        environment.reset_state()

    original_model = environment.current_model()
    candidate_models = options.models or (original_model,)
    candidates: list[dict[str, Any]] = []
    all_checks: list[dict[str, Any]] = []
    should_restore = bool(options.models and options.restore_model)

    try:
        for candidate_model in candidate_models:
            if options.models:
                environment.switch_model(candidate_model)
                environment.wait_for_health()
            candidate = run_candidate(
                candidate_model,
                options=options,
                environment=environment,
                client=client,
            )
            candidates.append(candidate)
            all_checks.extend(
                check for scenario in candidate["scenarios"] for check in scenario["checks"]
            )
    finally:
        if should_restore:
            environment.restore_model(original_model)

    run_summary = summarize_checks(all_checks)
    artifact = {
        "schema_version": 1,
        "run": {
            **environment.run_metadata(),
            "api_base": options.api_base,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "original_model": original_model,
            "requested_models": list(options.models),
            "restored_model": original_model if should_restore else None,
        },
        "candidates": candidates,
        "summary": run_summary,
    }
    return artifact


def run_candidate(
    candidate_model: str,
    *,
    options: BenchOptions,
    environment: BenchEnvironment,
    client: ConversationClient,
) -> dict[str, Any]:
    runtime_config = environment.verify_runtime_model(candidate_model)
    scenarios: list[dict[str, Any]] = []
    candidate_checks: list[dict[str, Any]] = []

    for scenario_id in options.scenarios:
        scenario = scenario_by_id(scenario_id)
        scenario_result = run_scenario(
            scenario,
            environment=environment,
            client=client,
            timeout=options.timeout,
            seed_knowledge=options.seed_knowledge,
            seed_resources=options.seed_resources,
        )
        scenarios.append(scenario_result)
        candidate_checks.extend(scenario_result["checks"])

    return {
        "model": candidate_model,
        "runtime_config": sanitize_runtime_config(runtime_config),
        "scenarios": scenarios,
        "summary": summarize_checks(candidate_checks),
    }


def run_scenario(
    scenario: Scenario,
    *,
    environment: BenchEnvironment,
    client: ConversationClient,
    timeout: float,
    seed_knowledge: bool,
    seed_resources: bool,
) -> dict[str, Any]:
    knowledge_fixture: dict[str, Any] | None = None
    resource_fixture: dict[str, Any] | None = None
    database_fixture: dict[str, Any] | None = None
    cleanup_error: str | None = None
    session_cleanup_error: str | None = None
    token: str | None = None
    requested_session_id = str(uuid.uuid4())
    stream_dispatched = False
    stream = failed_stream("scenario setup did not reach the stream")
    try:
        if scenario.actor == "admin":
            token = environment.admin_token()
            if scenario.id == "admin_database_natural_language_guardrail":
                database_fixture = {
                    "expected_user_count": environment.database_user_count()
                }
        elif scenario.actor == "user":
            token = environment.user_token(scenario.tools)
            if seed_knowledge and "knowledge-search" in scenario.tools:
                knowledge_fixture = environment.seed_knowledge()
            if seed_resources and "curated-resources" in scenario.tools:
                resource_fixture = environment.seed_resources()
        else:
            raise ValueError(f"unsupported actor for current bench slice: {scenario.actor}")

        payload = {
            "message": scenario.message,
            "session_id": requested_session_id,
            "tools": list(scenario.tools),
        }
        if knowledge_fixture:
            job_ids = knowledge_fixture.get("job_ids")
            if isinstance(job_ids, list) and job_ids:
                payload["job_ids"] = job_ids
        stream_dispatched = True
        stream = client.stream_chat(token, payload, timeout)
    except Exception as exc:
        stream = failed_stream(f"scenario setup or stream failed: {exc}")
    finally:
        observed_session_id = stream_session_id(stream)
        session_cleanup_errors: list[str] = []
        if stream_dispatched and token:
            session_ids = {requested_session_id}
            if observed_session_id:
                session_ids.add(observed_session_id)
            for session_id in session_ids:
                try:
                    client.delete_session(token, session_id, timeout)
                except Exception as exc:
                    session_cleanup_errors.append(f"{session_id}: {exc}")
        if observed_session_id and observed_session_id != requested_session_id:
            session_cleanup_errors.append(
                f"stream returned session_id {observed_session_id}, expected "
                f"{requested_session_id}"
            )
        elif (stream.events or stream.done) and not observed_session_id:
            session_cleanup_errors.append(
                "completed stream did not expose a session_id"
            )
        if session_cleanup_errors:
            session_cleanup_error = "; ".join(session_cleanup_errors)
        try:
            environment.cleanup_scenario()
        except Exception as exc:
            cleanup_error = str(exc)

    tool_evidence = collect_tool_evidence(stream)
    retrieval_evidence = collect_retrieval_evidence(stream)
    diagnostics = collect_stream_diagnostics(stream)
    checks = checks_for_scenario(
        scenario,
        stream,
        tool_evidence,
        diagnostics=diagnostics,
        knowledge_fixture=knowledge_fixture,
        resource_fixture=resource_fixture,
        database_fixture=database_fixture,
    )
    checks.append(
        check(
            "temporary_session_cleanup_succeeded",
            session_cleanup_error is None,
            "hard",
            session_cleanup_error,
        )
    )
    checks.append(
        check(
            "temporary_fixture_cleanup_succeeded",
            cleanup_error is None,
            "hard",
            cleanup_error,
        )
    )
    return {
        "id": scenario.id,
        "actor": scenario.actor,
        "request": {
            "tools": list(scenario.tools),
            "message_preview": truncate(scenario.message, 500),
        },
        "fixtures": {
            "knowledge": knowledge_fixture,
            "resources": resource_fixture,
            "database": database_fixture,
        },
        "response": {
            "answer_preview": truncate(stream.answer, 2000),
            "model": stream.done.get("model"),
            "provider": stream.done.get("provider"),
            "admin_change_set": stream.admin_change_set,
            "stream_error": stream.error,
        },
        "checks": checks,
        "timing": stream.timings,
        "diagnostics": diagnostics,
        "tool_evidence": tool_evidence,
        "retrieval_evidence": retrieval_evidence,
        "summary": summarize_checks(checks),
        "notes": [],
    }


def failed_stream(error: str) -> StreamResult:
    return StreamResult(
        answer="",
        events=[],
        done={},
        trace=None,
        admin_change_set=None,
        timings={
            "first_event_ms": None,
            "first_trace_or_tool_feedback_ms": None,
            "first_visible_assistant_token_ms": None,
            "done_ms": None,
        },
        error=error,
    )


def stream_session_id(stream: StreamResult) -> str | None:
    candidates = [stream.done]
    candidates.extend(
        event.get("data") or {}
        for event in stream.events
        if isinstance(event, dict)
    )
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        session_id = str(candidate.get("session_id") or "").strip()
        if session_id:
            return session_id
    return None


def scenario_by_id(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError as exc:
        raise ValueError(f"unknown scenario: {scenario_id}") from exc


def checks_for_scenario(
    scenario: Scenario,
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
    *,
    diagnostics: dict[str, Any],
    knowledge_fixture: dict[str, Any] | None,
    resource_fixture: dict[str, Any] | None,
    database_fixture: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    checks = common_stream_checks(stream)
    if scenario.tools:
        checks.extend(trace_feedback_checks(stream))
    if scenario.id == "admin_no_tools_control":
        checks.extend(no_tools_control_checks(stream, tool_evidence, diagnostics))
    elif scenario.id == "admin_config_bootstrap":
        checks.extend(admin_config_bootstrap_checks(stream, tool_evidence))
        checks.extend(deterministic_bootstrap_diagnostic_checks(diagnostics))
    elif scenario.id == "admin_config_live_onboarding_prompt":
        checks.extend(admin_config_live_onboarding_prompt_checks(stream, tool_evidence))
    elif scenario.id == "admin_deployment_readiness":
        checks.extend(admin_deployment_readiness_checks(stream, tool_evidence))
    elif scenario.id == "admin_database_direct_select":
        checks.extend(admin_database_direct_select_checks(stream, tool_evidence))
    elif scenario.id == "admin_database_natural_language_guardrail":
        checks.extend(
            admin_database_natural_language_guardrail_checks(
                stream, tool_evidence, database_fixture
            )
        )
    elif scenario.id == "user_knowledge_assistance":
        checks.extend(
            user_knowledge_assistance_checks(
                stream, tool_evidence, knowledge_fixture
            )
        )
    elif scenario.id == "user_curated_resource_referral":
        checks.extend(
            user_curated_resource_referral_checks(
                stream, tool_evidence, resource_fixture
            )
        )
    elif scenario.id == "user_knowledge_and_resource_assistance":
        checks.extend(
            user_knowledge_and_resource_assistance_checks(
                stream,
                tool_evidence,
                knowledge_fixture,
                resource_fixture,
            )
        )
    if scenario.id not in {
        "admin_config_bootstrap",
        "admin_config_live_onboarding_prompt",
    }:
        checks.extend(plain_answer_streaming_checks(diagnostics))
    return checks


def common_stream_checks(stream: StreamResult) -> list[dict[str, Any]]:
    first_answer_ms = stream.timings.get("first_visible_assistant_token_ms")
    done_ms = stream.timings.get("done_ms")
    return [
        check(
            "stream_completed_without_error",
            stream.error is None,
            "hard",
            stream.error,
        ),
        check("response_payload_present", bool(stream.done), "hard"),
        check("answer_present", bool(stream.answer.strip()), "hard"),
        check(
            "does_not_emit_generic_generation_failure",
            not contains_generic_generation_failure(stream.answer),
            "hard",
        ),
        check(
            "timing_captured",
            stream.timings.get("first_event_ms") is not None
            and stream.timings.get("first_visible_assistant_token_ms") is not None
            and stream.timings.get("done_ms") is not None,
            "hard",
        ),
        check(
            "first_answer_under_30s",
            first_answer_ms is None or first_answer_ms <= SLOW_FIRST_ANSWER_WARNING_MS,
            "warning",
            f"first answer token took {first_answer_ms}ms" if first_answer_ms is not None else None,
        ),
        check(
            "completion_under_90s",
            done_ms is None or done_ms <= SLOW_COMPLETION_WARNING_MS,
            "warning",
            f"completion took {done_ms}ms" if done_ms is not None else None,
        ),
    ]


def collect_stream_diagnostics(stream: StreamResult) -> dict[str, Any]:
    answer_delta_count = 0
    model_call_count = 0
    correction_call_count = 0
    retry_count = 0
    tool_execution_ms = 0.0
    timing_phases: list[dict[str, Any]] = []

    for event in stream.events:
        event_name = str(event.get("event") or "")
        data = event.get("data") or {}
        if event_name == "answer_delta" and str(data.get("delta") or ""):
            answer_delta_count += 1
        elif event_name == "trace_status":
            timing = data.get("timing")
            if isinstance(timing, dict):
                timing_phases.append(timing)
        elif event_name == "trace_delta":
            trace_delta = data.get("trace_delta")
            if not isinstance(trace_delta, dict):
                continue
            kind = str(trace_delta.get("kind") or "")
            status = str(trace_delta.get("status") or "")
            if kind == "model_step" and status == "running":
                model_call_count += 1
            elif kind == "correction" and status == "running":
                correction_call_count += 1
            elif kind == "retry" and status == "running":
                retry_count += 1
            elif kind == "tool_result":
                metadata = trace_delta.get("metadata")
                duration_ms = metadata.get("duration_ms") if isinstance(metadata, dict) else None
                if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
                    tool_execution_ms += float(duration_ms)

    first_event_ms = stream.timings.get("first_event_ms")
    first_feedback_ms = stream.timings.get("first_trace_or_tool_feedback_ms")
    first_answer_ms = stream.timings.get("first_visible_assistant_token_ms")
    done_ms = stream.timings.get("done_ms")
    phase_durations = {
        "event_to_tool_feedback_ms": elapsed_between(first_event_ms, first_feedback_ms),
        "tool_feedback_to_answer_ms": elapsed_between(first_feedback_ms, first_answer_ms),
        "answer_to_done_ms": elapsed_between(first_answer_ms, done_ms),
        "total_ms": done_ms,
    }
    return {
        "answer_delta_count": answer_delta_count,
        "provider_streamed_multiple_answer_deltas": answer_delta_count > 1,
        "model_call_count": model_call_count,
        "model_call_telemetry_present": model_call_count > 0,
        "correction_call_count": correction_call_count,
        "retry_count": retry_count,
        "tool_execution_ms": round(tool_execution_ms, 1),
        "timing_phases": timing_phases,
        "phase_durations": phase_durations,
        "background_timing": {
            "persistence_ms": None,
            "embedding_ms": None,
            "availability": (
                "not exposed by the public stream; deferred persistence and "
                "embedding behavior is covered by Sage runtime tests"
            ),
        },
    }


def elapsed_between(
    earlier: float | None,
    later: float | None,
) -> float | None:
    if earlier is None or later is None:
        return None
    return round(max(0.0, later - earlier), 1)


def no_tools_control_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        check("no_tools_control_used_no_tools", not tool_evidence, "hard"),
        check(
            "no_tools_control_single_model_call",
            diagnostics["model_call_count"] == 1,
            "hard",
            f"observed {diagnostics['model_call_count']} model calls",
        ),
        check(
            "no_tools_control_zero_corrections",
            diagnostics["correction_call_count"] == 0,
            "hard",
        ),
        check(
            "no_tools_control_zero_retries",
            diagnostics["retry_count"] == 0,
            "hard",
        ),
        check(
            "no_tools_control_answer_is_correct",
            bool(re.search(r"\b(?:4|four)\b", stream.answer, flags=re.IGNORECASE)),
            "hard",
        ),
    ]


def deterministic_bootstrap_diagnostic_checks(
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    telemetry_present = bool(diagnostics["model_call_telemetry_present"])
    return [
        check(
            "bootstrap_has_no_final_model_call",
            telemetry_present and diagnostics["model_call_count"] == 1,
            "hard",
            None
            if telemetry_present
            else "model-call telemetry was not emitted by this recorded fixture",
        ),
        check(
            "bootstrap_zero_correction_calls",
            diagnostics["correction_call_count"] == 0,
            "hard",
        ),
        check(
            "bootstrap_zero_retry_calls",
            diagnostics["retry_count"] == 0,
            "hard",
        ),
    ]


def plain_answer_streaming_checks(
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    telemetry_present = bool(diagnostics["model_call_telemetry_present"])
    return [
        check(
            "plain_answer_zero_correction_calls",
            telemetry_present and diagnostics["correction_call_count"] == 0,
            "hard",
            None
            if telemetry_present
            else "model-call telemetry was not emitted by this recorded fixture",
        ),
        check(
            "plain_answer_streamed_multiple_deltas",
            diagnostics["answer_delta_count"] > 1,
            "hard",
            None
            if telemetry_present
            else "model-call telemetry was not emitted by this recorded fixture",
        ),
    ]


def trace_feedback_checks(stream: StreamResult) -> list[dict[str, Any]]:
    first_trace_or_tool_feedback_ms = stream.timings.get(
        "first_trace_or_tool_feedback_ms"
    )
    return [
        check(
            "first_trace_or_tool_feedback_present",
            first_trace_or_tool_feedback_ms is not None,
            "warning",
            "no trace_delta or activity_step arrived before completion"
            if first_trace_or_tool_feedback_ms is None
            else None,
        ),
        check(
            "first_trace_or_tool_feedback_under_10s",
            first_trace_or_tool_feedback_ms is None
            or first_trace_or_tool_feedback_ms <= SLOW_TRACE_FEEDBACK_WARNING_MS,
            "warning",
            f"first trace/tool feedback took {first_trace_or_tool_feedback_ms}ms"
            if first_trace_or_tool_feedback_ms is not None
            else None,
        ),
    ]


def contains_generic_generation_failure(answer: str) -> bool:
    answer_lower = answer.lower()
    return any(
        phrase in answer_lower
        for phrase in [
            "wasn't able to generate a response",
            "was not able to generate a response",
            "unable to generate a response",
        ]
    )


def admin_deployment_readiness_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    answer_lower = stream.answer.lower()
    has_staged_admin_change_set = (
        any(
            tool_evidence_matches(evidence, "admin_change_set")
            for evidence in tool_evidence
        )
        or bool(stream.admin_change_set)
        or bool(stream.done.get("admin_change_set"))
    )
    manual_check_phrases = [
        "please double-check",
        "you'll need to check",
        "you need to check",
        "i cannot actually confirm",
        "i can't actually confirm",
        "share what you're seeing",
    ]
    return [
        check(
            "admin_config_tool_used",
            any(tool_evidence_matches(evidence, "admin-config") for evidence in tool_evidence),
            "hard",
        ),
        check(
            "admin_setup_summary_tool_used",
            any(
                admin_config_tool_invoked(evidence, "read_admin_setup_summary")
                for evidence in tool_evidence
            ),
            "hard",
        ),
        check(
            "broad_status_avoids_low_level_read_fanout",
            count_low_level_admin_config_reads(tool_evidence) <= 1,
            "warning",
            f"low-level Admin Config read tools used: {count_low_level_admin_config_reads(tool_evidence)}",
        ),
        check(
            "admin_change_set_not_staged",
            not has_staged_admin_change_set,
            "hard",
        ),
        check(
            "does_not_ask_admin_to_manually_check_available_settings",
            not any(phrase in answer_lower for phrase in manual_check_phrases),
            "hard",
        ),
    ]


def admin_config_bootstrap_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    change_set = stream.admin_change_set
    requests = change_set.get("requests") if isinstance(change_set, dict) else None
    request_list = requests if isinstance(requests, list) else []
    settings_body = settings_request_body(request_list)
    answer_lower = stream.answer.lower()
    lack_of_authority_phrases = [
        "i don't currently have write access",
        "i do not currently have write access",
        "i can't apply",
        "i cannot apply",
        "you'll need to apply",
        "you need to apply",
    ]
    non_bootstrap_admin_tools = non_bootstrap_admin_config_tools(tool_evidence)

    return [
        check(
            "admin_config_tool_used",
            any(tool_evidence_matches(evidence, "admin-config") for evidence in tool_evidence),
            "hard",
        ),
        check(
            "typed_bootstrap_tool_used",
            any(
                admin_config_tool_invoked(
                    evidence, "propose_admin_config_bootstrap"
                )
                for evidence in tool_evidence
            ),
            "hard",
        ),
        check(
            "bootstrap_uses_only_typed_bootstrap_tool",
            not non_bootstrap_admin_tools,
            "hard",
            (
                "non-bootstrap Admin Config tools used: "
                + ", ".join(sorted(non_bootstrap_admin_tools))
            )
            if non_bootstrap_admin_tools
            else None,
        ),
        check(
            "generic_change_set_tool_not_used_for_bootstrap",
            not any(
                admin_config_tool_invoked(evidence, "propose_config_change_set")
                for evidence in tool_evidence
            ),
            "warning",
        ),
        check("admin_change_set_present", bool(request_list), "hard"),
        check(
            "admin_change_set_uses_canonical_paths",
            admin_change_set_uses_canonical_paths(request_list),
            "hard",
        ),
        check(
            "baseline_settings_present",
            BASELINE_SETTING_KEYS <= set(settings_body),
            "hard",
        ),
        check(
            "user_types_present",
            count_user_type_requests(request_list) >= 2,
            "hard",
        ),
        check(
            "onboarding_fields_present",
            count_user_field_requests(request_list) >= 2,
            "hard",
        ),
        check(
            "behavior_rules_present",
            has_agent_rules_request(request_list, "prompt_rules"),
            "hard",
        ),
        check(
            "does_not_claim_missing_proposal_authority",
            not any(phrase in answer_lower for phrase in lack_of_authority_phrases),
            "hard",
        ),
    ]


def admin_config_live_onboarding_prompt_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    change_set = stream.admin_change_set
    requests = change_set.get("requests") if isinstance(change_set, dict) else None
    request_list = requests if isinstance(requests, list) else []
    settings_body = settings_request_body(request_list)
    user_type_texts = [text.lower() for text in user_type_request_texts(request_list)]

    return [
        check(
            "admin_config_tool_used",
            any(tool_evidence_matches(evidence, "admin-config") for evidence in tool_evidence),
            "hard",
        ),
        check(
            "typed_bootstrap_tool_used",
            any(
                admin_config_tool_invoked(
                    evidence, "propose_admin_config_bootstrap"
                )
                for evidence in tool_evidence
            ),
            "hard",
        ),
        check(
            "generic_change_set_tool_not_used_for_bootstrap",
            not any(
                admin_config_tool_invoked(evidence, "propose_config_change_set")
                for evidence in tool_evidence
            ),
            "warning",
        ),
        check(
            "live_onboarding_bootstrap_not_rejected",
            not any_admin_config_bootstrap_rejection(tool_evidence),
            "hard",
        ),
        check("admin_change_set_present", bool(request_list), "hard"),
        check(
            "admin_change_set_uses_canonical_paths",
            admin_change_set_uses_canonical_paths(request_list),
            "hard",
        ),
        check(
            "live_onboarding_baseline_settings_present",
            BASELINE_SETTING_KEYS <= set(settings_body),
            "hard",
        ),
        check(
            "live_onboarding_instance_name_preserved",
            settings_body.get("instance_name") == "FreeThem",
            "hard",
        ),
        check(
            "live_onboarding_dark_theme_preserved",
            settings_body.get("default_theme") == "dark",
            "hard",
        ),
        check(
            "live_onboarding_default_language_normalized",
            settings_body.get("default_language") == "en",
            "hard",
        ),
        check(
            "live_onboarding_auto_approval_enabled",
            settings_body.get("auto_approve_users") is True,
            "hard",
        ),
        check(
            "live_onboarding_user_types_present",
            count_user_type_requests(request_list) >= 2,
            "hard",
        ),
        check(
            "live_onboarding_user_type_content_present",
            has_separate_live_onboarding_user_types(user_type_texts),
            "hard",
        ),
        check(
            "live_onboarding_does_not_create_user_fields",
            count_user_field_requests(request_list) == 0,
            "hard",
        ),
        check(
            "live_onboarding_does_not_create_behavior_rules",
            not has_agent_rules_request(request_list, "prompt_rules")
            and not has_agent_rules_request(request_list, "prompt_forbidden"),
            "hard",
        ),
    ]


def user_knowledge_assistance_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
    knowledge_fixture: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    retrieval_evidence = collect_retrieval_evidence(stream)
    checks = [
        check(
            "knowledge_search_behavior_recorded",
            any(tool_evidence_matches(evidence, "knowledge-search") for evidence in tool_evidence),
            "hard",
        ),
        check(
            "retrieval_evidence_recorded",
            bool(retrieval_evidence),
            "hard" if knowledge_fixture else "warning",
        ),
        check(
            "answer_present_with_practical_guidance",
            bool(stream.answer.strip()) and contains_practical_safety_guidance(stream.answer),
            "hard",
        ),
    ]
    if knowledge_fixture:
        expected_sources = [
            str(source)
            for source in knowledge_fixture.get("sources") or []
            if str(source).strip()
        ]
        retrieved_titles = {
            str(item.get("title") or "") for item in retrieval_evidence
        }
        expected_phrases = [
            str(phrase)
            for phrase in knowledge_fixture.get("expected_answer_phrases") or []
            if str(phrase).strip()
        ]
        checks.extend(
            [
                check(
                    "seeded_knowledge_source_retrieved",
                    bool(expected_sources)
                    and all(source in retrieved_titles for source in expected_sources),
                    "hard",
                ),
                check(
                    "answer_uses_exact_seeded_knowledge_facts",
                    bool(expected_phrases)
                    and all(
                        phrase.lower() in stream.answer.lower()
                        for phrase in expected_phrases
                    ),
                    "hard",
                ),
            ]
        )
    return checks


def admin_database_direct_select_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        check(
            "db_query_tool_used",
            any(tool_evidence_matches(evidence, "db-query") for evidence in tool_evidence),
            "hard",
        ),
        check(
            "db_query_was_executed",
            not any_tool_warning(tool_evidence, "db-query", "direct_select_required"),
            "hard",
        ),
        check(
            "db_query_results_redacted_from_trace",
            any_tool_warning(tool_evidence, "db-query", "raw_results_redacted"),
            "hard",
        ),
        check(
            "answer_mentions_requested_settings",
            contains_any(
                stream.answer,
                [
                    "instance_name",
                    "assistant_name",
                    "default_language",
                    "instance name",
                    "assistant name",
                    "default language",
                ],
            ),
            "warning",
        ),
    ]


def admin_database_natural_language_guardrail_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
    database_fixture: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    expected_count = (
        database_fixture.get("expected_user_count")
        if isinstance(database_fixture, dict)
        else None
    )
    normalized_answer = stream.answer.replace(",", "")
    return [
        check(
            "db_query_tool_used",
            any(tool_evidence_matches(evidence, "db-query") for evidence in tool_evidence),
            "hard",
        ),
        check(
            "db_query_was_executed_from_natural_language",
            any_tool_warning(tool_evidence, "db-query", "raw_results_redacted"),
            "hard",
        ),
        check(
            "answer_reports_user_count",
            isinstance(expected_count, int)
            and bool(
                re.search(
                    rf"\b{expected_count}\b[^.\n]*\busers?\b|\busers?\b[^.\n]*\b{expected_count}\b",
                    normalized_answer,
                    flags=re.IGNORECASE,
                )
            ),
            "hard",
            f"expected the exact SQLite user count {expected_count}",
        ),
    ]


def user_curated_resource_referral_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
    resource_fixture: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    expected_facts = curated_resource_expected_facts(resource_fixture)
    checks = [
        check(
            "curated_resources_tool_used",
            any(tool_evidence_matches(evidence, "curated-resources") for evidence in tool_evidence),
            "hard",
        ),
        check(
            "curated_resource_found",
            not any_tool_warning(tool_evidence, "curated-resources", "no_curated_resources"),
            "hard" if resource_fixture else "warning",
        ),
        check(
            "answer_surfaces_vetted_resource",
            (
                bool(expected_facts)
                and all(fact.lower() in stream.answer.lower() for fact in expected_facts)
            )
            if resource_fixture
            else contains_any(stream.answer, ["legal", "humanitarian", "resource"]),
            "hard" if resource_fixture else "warning",
        ),
    ]
    return checks


def user_knowledge_and_resource_assistance_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
    knowledge_fixture: dict[str, Any] | None,
    resource_fixture: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    checks = user_knowledge_assistance_checks(
        stream, tool_evidence, knowledge_fixture
    )
    checks.extend(
        user_curated_resource_referral_checks(
            stream, tool_evidence, resource_fixture
        )
    )
    checks.append(
        check(
            "answer_combines_safety_and_referral",
            contains_practical_safety_guidance(stream.answer)
            and contains_any(
                stream.answer,
                [
                    "Bench Liberty Legal Hotline",
                    "bench-legal@example.test",
                    "legal",
                    "humanitarian",
                ],
            ),
            "hard",
        )
    )
    return checks


def curated_resource_expected_facts(
    resource_fixture: dict[str, Any] | None,
) -> list[str]:
    if not resource_fixture:
        return []
    explicit = resource_fixture.get("expected_answer_facts")
    if isinstance(explicit, list):
        return [str(item) for item in explicit if str(item).strip()]
    resources = resource_fixture.get("resources") or []
    if not resources or not isinstance(resources[0], dict):
        return []
    resource = resources[0]
    contact = resource.get("contact") or {}
    values = [resource.get("name")]
    if isinstance(contact, dict):
        values.append(contact.get("email"))
    return [str(item) for item in values if str(item).strip()]


def contains_practical_safety_guidance(answer: str) -> bool:
    answer_lower = answer.lower()
    return any(
        phrase in answer_lower
        for phrase in [
            "safe place",
            "physically safe",
            "trusted",
            "urgent",
            "medical",
            "legal",
            "document",
        ]
    )


def contains_any(value: str, needles: list[str]) -> bool:
    value_lower = value.lower()
    return any(needle.lower() in value_lower for needle in needles)


def any_tool_warning(
    tool_evidence: list[dict[str, Any]],
    tool_set_id: str,
    warning: str,
) -> bool:
    for evidence in tool_evidence:
        if not tool_evidence_matches(evidence, tool_set_id):
            continue
        warnings = evidence.get("warnings") or []
        if isinstance(warnings, list) and warning in warnings:
            return True
    return False


BASELINE_SETTING_KEYS = {
    "instance_name",
    "assistant_name",
    "header_tagline",
    "description",
    "primary_color",
    "default_theme",
    "default_language",
    "auto_approve_users",
}

CANONICAL_ADMIN_CONFIG_WRITES = {
    ("PUT", "/admin/settings"),
    ("POST", "/admin/user-types"),
    ("POST", "/admin/user-fields"),
    ("PUT", "/admin/ai-config/prompt_rules"),
    ("PUT", "/admin/ai-config/prompt_forbidden"),
}

UNSAFE_ADMIN_CONFIG_PATH_PREFIXES = (
    "/admin/tools/execute",
    "/admin/deployment/config/reveal",
    "/admin/export",
)


def settings_request_body(requests: list[Any]) -> dict[str, Any]:
    for request in requests:
        if not isinstance(request, dict):
            continue
        if request.get("method") == "PUT" and request.get("path") == "/admin/settings":
            body = request.get("body")
            return body if isinstance(body, dict) else {}
    return {}


def count_user_type_requests(requests: list[Any]) -> int:
    return sum(
        1
        for request in requests
        if isinstance(request, dict)
        and request.get("method") == "POST"
        and request.get("path") == "/admin/user-types"
    )


def user_type_request_texts(requests: list[Any]) -> list[str]:
    texts: list[str] = []
    for request in requests:
        if not isinstance(request, dict):
            continue
        if request.get("method") != "POST" or request.get("path") != "/admin/user-types":
            continue
        body = request.get("body")
        if not isinstance(body, dict):
            continue
        values = [
            str(body.get("name") or ""),
            str(body.get("description") or ""),
        ]
        texts.append(" ".join(value for value in values if value.strip()))
    return texts


def has_separate_live_onboarding_user_types(user_type_texts: list[str]) -> bool:
    current_family_indexes = {
        index
        for index, text in enumerate(user_type_texts)
        if "famil" in text and "current" in text
    }
    former_after_indexes = {
        index
        for index, text in enumerate(user_type_texts)
        if "former" in text or "after" in text
    }
    return any(
        current_index != former_index
        for current_index in current_family_indexes
        for former_index in former_after_indexes
    )


def count_user_field_requests(requests: list[Any]) -> int:
    return sum(
        1
        for request in requests
        if isinstance(request, dict)
        and request.get("method") == "POST"
        and request.get("path") == "/admin/user-fields"
    )


def has_agent_rules_request(requests: list[Any], key: str) -> bool:
    path = f"/admin/ai-config/{key}"
    for request in requests:
        if not isinstance(request, dict):
            continue
        if request.get("method") != "PUT" or request.get("path") != path:
            continue
        body = request.get("body")
        value = body.get("value") if isinstance(body, dict) else None
        return is_json_string_array(value)
    return False


def is_json_string_array(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in parsed
    ) and bool(parsed)


def any_admin_config_bootstrap_rejection(tool_evidence: list[dict[str, Any]]) -> bool:
    for evidence in tool_evidence:
        if not admin_config_tool_invoked(evidence, "propose_admin_config_bootstrap"):
            continue
        status = str(evidence.get("status") or "").lower()
        summary = str(evidence.get("output_summary") or "").lower()
        warnings = [
            str(warning).lower()
            for warning in evidence.get("warnings") or []
        ]
        if evidence.get("guarded") or status == "guarded":
            return True
        if "invalid_admin_config_bootstrap" in warnings:
            return True
        if "invalid bootstrap" in summary or "invalid admin config bootstrap" in summary:
            return True
    return False


def admin_change_set_uses_canonical_paths(requests: list[Any]) -> bool:
    if not requests:
        return False
    for request in requests:
        if not isinstance(request, dict):
            return False
        method = str(request.get("method") or "").upper()
        path = str(request.get("path") or "")
        if path.startswith(UNSAFE_ADMIN_CONFIG_PATH_PREFIXES):
            return False
        if (method, path) not in CANONICAL_ADMIN_CONFIG_WRITES:
            return False
        body = request.get("body")
        if path == "/admin/settings" and isinstance(body, dict):
            if "tagline" in body or "English" in body.values():
                return False
    return True


def collect_tool_evidence(stream: StreamResult) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()

    for tool in stream.done.get("tools_used") or []:
        if isinstance(tool, dict):
            normalized = normalize_tool_evidence(tool)
            key = json.dumps(normalized, sort_keys=True)
            if key not in seen:
                seen.add(key)
                evidence.append(normalized)

    trace = stream.trace or {}
    for tool in trace.get("tools") or []:
        if isinstance(tool, dict):
            normalized = normalize_tool_evidence(tool)
            key = json.dumps(normalized, sort_keys=True)
            if key not in seen:
                seen.add(key)
                evidence.append(normalized)

    for event in stream.events:
        data = event.get("data") or {}
        step = data.get("activity_step")
        if isinstance(step, dict):
            normalized = normalize_tool_evidence(step)
            key = json.dumps(normalized, sort_keys=True)
            if key not in seen:
                seen.add(key)
                evidence.append(normalized)
    return evidence


def collect_retrieval_evidence(stream: StreamResult) -> list[dict[str, Any]]:
    trace = stream.trace or {}
    retrieval = trace.get("retrieval") if isinstance(trace, dict) else []
    evidence: list[dict[str, Any]] = []
    if not isinstance(retrieval, list):
        return evidence
    for source in retrieval:
        if not isinstance(source, dict):
            continue
        evidence.append(
            {
                "source_type": source.get("source_type"),
                "title": source.get("title"),
                "summary": source.get("summary"),
                "metadata": source.get("metadata") or {},
            }
        )
    return evidence


def normalize_tool_evidence(value: dict[str, Any]) -> dict[str, Any]:
    raw_id = str(value.get("tool_id") or value.get("id") or "").strip()
    raw_name = str(value.get("tool_name") or value.get("name") or value.get("title") or "").strip()
    tool_id = raw_id or tool_id_from_name(raw_name)
    return {
        "tool_id": tool_id,
        "tool_name": raw_name or tool_id,
        "query": value.get("query"),
        "status": value.get("status"),
        "output_summary": value.get("output_summary") or value.get("summary"),
        "warnings": value.get("warnings") or [],
        "guarded": value.get("guarded"),
    }


def tool_evidence_matches(evidence: dict[str, Any], tool_set_id: str) -> bool:
    tool_id = str(evidence.get("tool_id") or "")
    return (
        tool_id == tool_set_id
        or tool_id.startswith(f"{tool_set_id}:")
        or tool_id.startswith(f"tool-{tool_set_id}:")
    )


def admin_config_tool_invoked(evidence: dict[str, Any], tool_name: str) -> bool:
    tool_id = str(evidence.get("tool_id") or "")
    return (
        tool_id == f"admin-config:{tool_name}"
        or tool_id == f"tool-admin-config:{tool_name}"
        or tool_id == tool_name
    )


def non_bootstrap_admin_config_tools(
    tool_evidence: list[dict[str, Any]],
) -> set[str]:
    non_bootstrap_tools: set[str] = set()
    for evidence in tool_evidence:
        if not tool_evidence_matches(evidence, "admin-config"):
            continue
        if admin_config_tool_invoked(evidence, "propose_admin_config_bootstrap"):
            continue
        tool_id = str(evidence.get("tool_id") or "").strip()
        if tool_id.startswith("tool-admin-config:"):
            non_bootstrap_tools.add(tool_id.removeprefix("tool-admin-config:"))
        elif tool_id.startswith("admin-config:"):
            non_bootstrap_tools.add(tool_id.removeprefix("admin-config:"))
        elif tool_id:
            non_bootstrap_tools.add(tool_id)
        else:
            non_bootstrap_tools.add(str(evidence.get("tool_name") or "admin-config"))
    return non_bootstrap_tools


def count_low_level_admin_config_reads(tool_evidence: list[dict[str, Any]]) -> int:
    invoked: set[str] = set()
    for evidence in tool_evidence:
        for tool_name in LOW_LEVEL_ADMIN_CONFIG_READ_TOOLS:
            if admin_config_tool_invoked(evidence, tool_name):
                invoked.add(tool_name)
    return len(invoked)


def tool_id_from_name(name: str) -> str:
    if name.lower() == "admin config":
        return "admin-config"
    return name.lower().replace(" ", "-")


def check(
    name: str,
    passed: bool,
    severity: str,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "severity": severity,
        "detail": detail,
    }


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    hard_failures = [
        item
        for item in checks
        if item.get("severity") == "hard" and item.get("status") != "passed"
    ]
    warnings = [
        item
        for item in checks
        if item.get("severity") == "warning" and item.get("status") != "passed"
    ]
    return {
        "status": "failed" if hard_failures else "passed",
        "hard_failures": hard_failures,
        "warnings": warnings,
        "check_count": len(checks),
    }


def sanitize_runtime_config(payload: dict[str, Any]) -> dict[str, Any]:
    runtime_config = dict(payload.get("runtime_config") or payload)
    api_key = runtime_config.get("TINFOIL_API_KEY")
    if isinstance(api_key, dict):
        runtime_config["TINFOIL_API_KEY"] = {
            "configured": bool(api_key.get("configured")),
            "fingerprint": api_key.get("fingerprint"),
        }
    elif api_key is not None:
        runtime_config["TINFOIL_API_KEY"] = {
            "configured": bool(api_key),
            "fingerprint": None,
        }
    return runtime_config


def truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."


class LocalComposeEnvironment:
    def __init__(self) -> None:
        self._scenario_user_id: int | None = None
        self._scenario_user_type_id: int | None = None
        self._scenario_knowledge_fixture: dict[str, Any] | None = None
        self._scenario_resource_fixture: dict[str, Any] | None = None

    def run_metadata(self) -> dict[str, Any]:
        return {
            "repo": "enclave-free/enclave.free-prototype",
            "git": {
                "prototype": run_command(["git", "rev-parse", "--short", "HEAD"], timeout=10).strip(),
                "dirty": bool(run_command(["git", "status", "--short"], timeout=10).strip()),
            },
        }

    def current_model(self) -> str:
        env = self.container_env("sage")
        return env.get("TINFOIL_MODEL") or "gemma4-31b"

    def verify_runtime_model(self, expected_model: str | None = None) -> dict[str, Any]:
        env = self.container_env("sage")
        token = env.get("INTERNAL_AGENT_TOKEN")
        if not token:
            raise RuntimeError("sage container did not expose INTERNAL_AGENT_TOKEN")
        output = run_command(
            runtime_config_fingerprint_command(token),
            timeout=30,
        )
        payload = json.loads(output)
        active_model = str((payload.get("runtime_config") or {}).get("TINFOIL_MODEL") or "")
        if expected_model and active_model != expected_model:
            raise RuntimeError(
                f"verified Sage model {active_model!r} did not match expected {expected_model!r}"
            )
        return payload

    def admin_token(self) -> str:
        script = """
import auth, database
database.init_schema()
admins = database.list_admins()
if not admins:
    database.add_admin("bench-admin-pubkey")
    admins = database.list_admins()
admin = admins[0]
print(auth.create_admin_session_token(admin["id"], admin["pubkey"], int(admin.get("session_nonce", 0) or 0)))
"""
        return run_backend_python(script, timeout=30).strip()

    def user_token(self, tools: tuple[str, ...] = ()) -> str:
        script = """
import auth, database, json, time
database.init_schema()
suffix = str(int(time.time() * 1000))
email = "conversation-bench-" + suffix + "@example.test"
user_type_id = database.create_user_type(
    "Conversation Bench Users " + suffix,
    description="Temporary Conversation Model Bench users",
)
with database.get_write_cursor() as cursor:
    cursor.execute(
        "INSERT INTO users (email, name, user_type_id, approved, created_at) VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)",
        (email, "Conversation Bench User", user_type_id),
    )
    user_id = cursor.lastrowid
print(json.dumps({
    "token": auth.create_session_token(user_id, email),
    "user_id": user_id,
    "user_type_id": user_type_id,
}))
"""
        payload = json.loads(run_backend_python(script, timeout=30).strip())
        self._scenario_user_id = int(payload["user_id"])
        self._scenario_user_type_id = int(payload["user_type_id"])
        configure_sage_user_policy(self._scenario_user_type_id, tools)
        return str(payload["token"])

    def seed_knowledge(self) -> dict[str, Any]:
        user_type_id = self._scenario_user_type_id
        if user_type_id is None:
            raise RuntimeError("seed_knowledge requires a freshly minted benchmark user")
        suffix = uuid.uuid4().hex[:12]
        job_id = f"conversation-bench-{suffix}"
        chunk_id = f"{job_id}_chunk_0000"
        source_file = f"Conversation Model Bench Post-Release Safety {suffix}.md"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"chunk:{chunk_id}"))
        upload_path = f"/uploads/{source_file}"
        self._scenario_knowledge_fixture = {
            "job_ids": [job_id],
            "sources": [source_file],
            "chunk_id": chunk_id,
            "point_id": point_id,
            "user_type_id": user_type_id,
            "upload_paths": [upload_path],
            "expected_answer_phrases": [
                "physically safe place",
                "contact trusted people",
            ],
        }
        script = """
import json
import os
from pathlib import Path

from qdrant_client.models import PointStruct

import database
import ingest_db
import store

job_id = __BENCH_JOB_ID__
chunk_id = __BENCH_CHUNK_ID__
source_file = __BENCH_SOURCE_FILE__
point_id = __BENCH_POINT_ID__
text = (
    "First-day post-release safety guidance: get to a physically safe place, "
    "contact trusted people, document urgent needs, and seek local professional "
    "legal or medical help when needed."
)
user_type_id = __BENCH_USER_TYPE_ID__
upload_dir = Path(os.getenv("UPLOADS_DIR", "/uploads"))
upload_dir.mkdir(parents=True, exist_ok=True)
file_path = upload_dir / source_file
file_path.write_text(text, encoding="utf-8")

database.init_schema()
ingest_db.init_ingest_schema()
ingest_db.create_job(
    job_id=job_id,
    filename=source_file,
    file_path=str(file_path),
    ontology_id="default",
    canonical_name=source_file,
    is_current=True,
)
ingest_db.update_job_status(job_id, "completed", total_chunks=1, processed_chunks=1)
database.upsert_document_defaults(job_id, is_available=True, is_default_active=False, display_order=0)
database.upsert_document_defaults_override(
    job_id,
    user_type_id,
    is_available=True,
    is_default_active=True,
    changed_by="",
)
database.upsert_ai_config_override(
    "knowledge_source_default",
    user_type_id,
    "selected",
    changed_by="",
)
ingest_db.upsert_retrieval_chunk(
    chunk_id=chunk_id,
    job_id=job_id,
    chunk_index=0,
    source_file=source_file,
    text=text,
)

store.ensure_qdrant_collection()
vector = store.embed_texts(["query: first day after release political imprisonment unsafe"])[0]
store.get_qdrant_client().upsert(
    collection_name=store.COLLECTION_NAME,
    points=[
        PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "type": "chunk",
                "chunk_id": chunk_id,
                "job_id": job_id,
                "source_file": source_file,
                "content_ref": "retrieval_chunk:" + chunk_id,
            },
        )
    ],
)

print(json.dumps({
    "job_ids": [job_id],
    "sources": [source_file],
    "chunk_id": chunk_id,
    "point_id": point_id,
    "user_type_id": user_type_id,
    "upload_paths": [str(file_path)],
    "expected_answer_phrases": ["physically safe place", "contact trusted people"],
}))
"""
        replacements = {
            "__BENCH_USER_TYPE_ID__": user_type_id,
            "__BENCH_JOB_ID__": job_id,
            "__BENCH_CHUNK_ID__": chunk_id,
            "__BENCH_SOURCE_FILE__": source_file,
            "__BENCH_POINT_ID__": point_id,
        }
        for marker, value in replacements.items():
            script = script.replace(marker, json.dumps(value))
        raw = run_backend_python(script, timeout=180)
        try:
            fixture = json.loads(raw.strip().splitlines()[-1])
            self._scenario_knowledge_fixture = fixture
            return fixture
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"knowledge fixture did not return JSON: {raw[:400]}") from exc

    def seed_resources(self) -> dict[str, Any]:
        suffix = uuid.uuid4().hex[:12]
        resource_id = f"conversation-bench-global-legal-{suffix}"
        resource_name = "Bench Liberty Legal Hotline"
        resource_email = f"bench-legal-{suffix}@example.test"
        self._scenario_resource_fixture = {
            "resource_ids": [resource_id],
            "resources": [],
            "expected_answer_facts": [resource_name, resource_email],
        }
        script = """
import json

import database

suffix = __BENCH_SUFFIX__
resource_id = __BENCH_RESOURCE_ID__
resource_name = __BENCH_RESOURCE_NAME__
resource_email = __BENCH_RESOURCE_EMAIL__
database.init_schema()
database.create_resource(
    resource_id=resource_id,
    name=resource_name,
    resource_type="ngo",
    description="Synthetic benchmark fixture for vetted legal triage after detention release.",
    contact={
        "email": resource_email,
        "secure_channel": "Signal: +1-000-000-0000",
        "url": "https://example.test/bench-legal/" + suffix,
    },
    languages=["en", "es"],
    scope_level="global",
    scope_code=None,
    help_types=["legal", "humanitarian"],
    verified_at=database.utc_timestamp_z(),
    vetted_by="conversation-model-bench",
    source_note="Synthetic benchmark fixture.",
    display_order=-100,
)
resource = database.get_resource(resource_id)
print(json.dumps({
    "resource_ids": [resource_id],
    "resources": [resource],
    "expected_answer_facts": [resource_name, resource_email],
}))
"""
        replacements = {
            "__BENCH_SUFFIX__": suffix,
            "__BENCH_RESOURCE_ID__": resource_id,
            "__BENCH_RESOURCE_NAME__": resource_name,
            "__BENCH_RESOURCE_EMAIL__": resource_email,
        }
        for marker, value in replacements.items():
            script = script.replace(marker, json.dumps(value))
        raw = run_backend_python(script, timeout=30)
        try:
            fixture = json.loads(raw.strip().splitlines()[-1])
            self._scenario_resource_fixture = fixture
            return fixture
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"resource fixture did not return JSON: {raw[:400]}") from exc

    def database_user_count(self) -> int:
        script = """
import database
database.init_schema()
with database.get_cursor() as cursor:
    cursor.execute("SELECT COUNT(*) AS count FROM users")
    print(int(cursor.fetchone()["count"]))
"""
        return int(run_backend_python(script, timeout=30).strip())

    def cleanup_scenario(self) -> None:
        user_id = self._scenario_user_id
        user_type_id = self._scenario_user_type_id
        knowledge_fixture = self._scenario_knowledge_fixture
        resource_fixture = self._scenario_resource_fixture

        errors: list[str] = []
        try:
            if user_type_id is not None:
                try:
                    if user_id is None:
                        raise RuntimeError(
                            "benchmark user type exists without its temporary user id"
                        )
                    cleanup_sage_user_state(user_id, user_type_id)
                except Exception as exc:
                    errors.append(f"Sage Postgres fixture cleanup failed: {exc}")
            cleanup_payload = {
                "user_id": user_id,
                "user_type_id": user_type_id,
                "knowledge": knowledge_fixture,
                "resources": resource_fixture,
            }
            if any(
                value is not None
                for value in (user_id, user_type_id, knowledge_fixture, resource_fixture)
            ):
                try:
                    run_backend_python(
                        backend_fixture_cleanup_script(cleanup_payload),
                        timeout=120,
                    )
                except Exception as exc:
                    errors.append(f"backend fixture cleanup failed: {exc}")
        finally:
            self._scenario_user_id = None
            self._scenario_user_type_id = None
            self._scenario_knowledge_fixture = None
            self._scenario_resource_fixture = None
        if errors:
            raise RuntimeError("; ".join(errors))

    def switch_model(self, model: str) -> None:
        env = os.environ.copy()
        env["TINFOIL_MODEL"] = model
        run_command(
            [
                *COMPOSE_ARGS,
                "up",
                "-d",
                "--force-recreate",
                "--no-deps",
                "sage",
            ],
            timeout=240,
            env=env,
        )

    def wait_for_health(self) -> None:
        deadline = time.time() + 180
        last_error = ""
        while time.time() < deadline:
            try:
                result = subprocess.run(
                    [
                        *COMPOSE_ARGS,
                        "exec",
                        "-T",
                        "sage",
                        "curl",
                        "-fsS",
                        "http://127.0.0.1:3000/health",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=REPO_ROOT,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                last_error = "health probe timed out"
                time.sleep(2)
                continue
            except Exception as exc:
                last_error = f"health probe failed: {exc}"
                time.sleep(2)
                continue
            if result.returncode == 0:
                return
            last_error = result.stderr.strip() or result.stdout.strip()
            time.sleep(2)
        raise RuntimeError(f"Sage did not become healthy after model switch: {last_error}")

    def restore_model(self, model: str) -> None:
        self.switch_model(model)
        self.wait_for_health()

    def reset_state(self) -> None:
        run_command(
            ["scripts/reset_local_instance.sh", "--skip-smoke"],
            timeout=900,
        )

    def container_env(self, service: str) -> dict[str, str]:
        output = run_command([*COMPOSE_ARGS, "exec", "-T", service, "env"], timeout=30)
        values: dict[str, str] = {}
        for line in output.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
        return values


class HttpConversationClient:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip("/")

    def stream_chat(self, token: str, payload: dict[str, Any], timeout: float) -> StreamResult:
        request = urllib.request.Request(
            f"{self.api_base}/llm/chat/stream",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"stream request failed with HTTP {exc.code}: {detail}") from exc

        events: list[dict[str, Any]] = []
        answer_parts: list[str] = []
        done: dict[str, Any] = {}
        trace: dict[str, Any] | None = None
        admin_change_set: dict[str, Any] | None = None
        first_event_ms: float | None = None
        first_trace_or_tool_feedback_ms: float | None = None
        first_delta_ms: float | None = None
        done_ms: float | None = None
        stream_error: str | None = None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def process_buffer() -> None:
            nonlocal buffer, first_event_ms, first_trace_or_tool_feedback_ms
            nonlocal first_delta_ms, done_ms
            nonlocal trace, admin_change_set, done
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                event_name, data = parse_sse_event(block)
                if not event_name:
                    continue
                elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                if first_event_ms is None:
                    first_event_ms = elapsed_ms
                if (
                    first_trace_or_tool_feedback_ms is None
                    and is_trace_or_tool_feedback_event(event_name, data)
                ):
                    first_trace_or_tool_feedback_ms = elapsed_ms
                events.append(
                    {
                        "event": event_name,
                        "elapsed_ms": elapsed_ms,
                        "data": data,
                    }
                )
                if event_name == "answer_delta":
                    delta = str(data.get("delta") or "")
                    if delta and first_delta_ms is None:
                        first_delta_ms = elapsed_ms
                    answer_parts.append(delta)
                elif event_name == "trace_final":
                    if isinstance(data.get("trace"), dict):
                        trace = data["trace"]
                    if isinstance(data.get("admin_change_set"), dict):
                        admin_change_set = data["admin_change_set"]
                elif event_name == "done":
                    done = data
                    done_ms = elapsed_ms
                    if isinstance(data.get("admin_change_set"), dict):
                        admin_change_set = data["admin_change_set"]

        def append_raw(raw: bytes) -> None:
            nonlocal buffer
            text = decoder.decode(raw)
            if not text:
                return
            buffer += text
            buffer = buffer.replace("\r\n", "\n")
            process_buffer()

        with response:
            buffer = ""
            while True:
                try:
                    raw = response.read(1)
                except http.client.IncompleteRead as exc:
                    raw = exc.partial or b""
                    if raw:
                        append_raw(raw)
                    if not done:
                        stream_error = f"stream closed before done: {exc}"
                    break
                except (TimeoutError, OSError, urllib.error.URLError) as exc:
                    if not done:
                        stream_error = f"stream read failed before done: {exc}"
                    break
                if not raw:
                    break
                append_raw(raw)

            trailing = decoder.decode(b"", final=True)
            if trailing:
                buffer += trailing
                buffer = buffer.replace("\r\n", "\n")
                process_buffer()

        return StreamResult(
            answer="".join(answer_parts).strip(),
            events=events,
            done=done,
            trace=trace,
            admin_change_set=admin_change_set,
            timings={
                "first_event_ms": first_event_ms,
                "first_trace_or_tool_feedback_ms": first_trace_or_tool_feedback_ms,
                "first_visible_assistant_token_ms": first_delta_ms,
                "done_ms": done_ms,
            },
            error=stream_error,
        )

    def delete_session(self, token: str, session_id: str, timeout: float) -> None:
        request = urllib.request.Request(
            f"{self.api_base}/query/session/{session_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"session cleanup failed with HTTP {exc.code}: {detail}"
            ) from exc
        payload = json.loads(body) if body.strip() else {}
        deletion = payload.get("deletion") if isinstance(payload, dict) else None
        if (
            payload.get("status") != "deleted"
            or not isinstance(deletion, dict)
            or deletion.get("status") != "succeeded"
        ):
            raise RuntimeError(f"session cleanup returned an unexpected payload: {payload}")


def parse_sse_event(block: str) -> tuple[str | None, dict[str, Any]]:
    event_name: str | None = None
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
    raw_data = "\n".join(data_lines)
    data = json.loads(raw_data) if raw_data else {}
    return event_name, data


def is_trace_or_tool_feedback_event(event_name: str, data: dict[str, Any]) -> bool:
    if event_name == "trace_delta":
        return isinstance(data.get("trace_delta"), dict)
    if event_name == "activity_step":
        return isinstance(data.get("activity_step"), dict)
    return False


def run_backend_python(script: str, timeout: int = 120) -> str:
    return run_command(
        [*COMPOSE_ARGS, "exec", "-T", "core-backend", "python", "-c", script],
        timeout=timeout,
    )


def configure_sage_user_policy(user_type_id: int, tool_ids: tuple[str, ...]) -> None:
    if user_type_id < 1:
        raise ValueError("user_type_id must be positive")
    invalid_tool_ids = sorted(set(tool_ids) - USER_CONVERSATION_TOOL_SET_IDS)
    if invalid_tool_ids:
        raise ValueError(f"unsupported user conversation tool IDs: {invalid_tool_ids}")
    normalized_tool_ids = sorted(set(tool_ids))
    knowledge_scope = "selected" if "knowledge-search" in normalized_tool_ids else "none"
    defaults_json = json.dumps(normalized_tool_ids, separators=(",", ":"))
    tool_override_id = uuid.uuid4()
    knowledge_override_id = uuid.uuid4()
    sql = f"""
INSERT INTO ai_config_user_type_overrides (
    id, ai_config_key, user_type_id, value, updated_at
) VALUES
    ('{tool_override_id}', 'user_default_tool_ids', {user_type_id}, '{defaults_json}', NOW()),
    ('{knowledge_override_id}', 'knowledge_source_default', {user_type_id}, '{knowledge_scope}', NOW())
ON CONFLICT (ai_config_key, user_type_id) DO UPDATE SET
    value = EXCLUDED.value,
    updated_at = NOW();
"""
    run_command(
        [
            *COMPOSE_ARGS,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "sage",
            "-d",
            "sage",
            "-c",
            sql,
        ],
        timeout=30,
    )


def cleanup_sage_user_state(user_id: int, user_type_id: int) -> None:
    if user_id < 1:
        raise ValueError("user_id must be positive")
    if user_type_id < 1:
        raise ValueError("user_type_id must be positive")
    memory_user_id = f"user:{user_id}"
    sql = f"""
BEGIN;
DELETE FROM messages
WHERE user_id = '{memory_user_id}'
   OR agent_id IN (
       SELECT agent_id FROM web_sessions
       WHERE owner_type = 'user' AND owner_id = '{user_id}'
   );
DELETE FROM blocks
WHERE agent_id IN (
    SELECT agent_id::text FROM web_sessions
    WHERE owner_type = 'user' AND owner_id = '{user_id}'
);
DELETE FROM passages
WHERE agent_id IN (
    SELECT agent_id::text FROM web_sessions
    WHERE owner_type = 'user' AND owner_id = '{user_id}'
);
DELETE FROM user_preferences
WHERE agent_id IN (
    SELECT agent_id FROM web_sessions
    WHERE owner_type = 'user' AND owner_id = '{user_id}'
);
DELETE FROM scheduled_tasks
WHERE agent_id IN (
    SELECT agent_id FROM web_sessions
    WHERE owner_type = 'user' AND owner_id = '{user_id}'
);
DELETE FROM summaries
WHERE agent_id IN (
    SELECT agent_id FROM web_sessions
    WHERE owner_type = 'user' AND owner_id = '{user_id}'
);
DELETE FROM agents
WHERE id IN (
    SELECT agent_id FROM web_sessions
    WHERE owner_type = 'user' AND owner_id = '{user_id}'
);
DELETE FROM web_sessions
WHERE owner_type = 'user' AND owner_id = '{user_id}';
DELETE FROM external_identities
WHERE identity_type = 'user' AND external_id = '{user_id}';
DELETE FROM chat_contexts
WHERE signal_identifier = '{memory_user_id}';
DELETE FROM ai_config_user_type_overrides
WHERE user_type_id = {user_type_id};
COMMIT;
"""
    run_command(
        [
            *COMPOSE_ARGS,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "sage",
            "-d",
            "sage",
            "-c",
            sql,
        ],
        timeout=30,
    )


def backend_fixture_cleanup_script(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, separators=(",", ":"))
    return f"""
import json
from pathlib import Path

from qdrant_client.models import PointIdsList

import database
import ingest_db
import store

payload = json.loads({json.dumps(serialized)})
errors = []
knowledge = payload.get("knowledge") or {{}}
resources = payload.get("resources") or {{}}

point_ids = [str(value) for value in [knowledge.get("point_id")] if value]
if point_ids:
    try:
        collections = store.get_qdrant_client().get_collections().collections
        if any(collection.name == store.COLLECTION_NAME for collection in collections):
            store.get_qdrant_client().delete(
                collection_name=store.COLLECTION_NAME,
                points_selector=PointIdsList(points=point_ids),
                wait=True,
            )
    except Exception as exc:
        errors.append("Qdrant: " + str(exc))

for upload_path in knowledge.get("upload_paths") or []:
    try:
        Path(upload_path).unlink(missing_ok=True)
    except Exception as exc:
        errors.append("upload: " + str(exc))

database.init_schema()
ingest_db.init_ingest_schema()
for job_id in knowledge.get("job_ids") or []:
    try:
        ingest_db.delete_retrieval_chunks_for_job(str(job_id))
        ingest_db.delete_job(str(job_id))
    except Exception as exc:
        errors.append("knowledge SQLite: " + str(exc))

for resource_id in resources.get("resource_ids") or []:
    try:
        database.delete_resource(str(resource_id))
    except Exception as exc:
        errors.append("resource SQLite: " + str(exc))

user_id = payload.get("user_id")
if user_id is not None:
    try:
        database.delete_user(int(user_id))
    except Exception as exc:
        errors.append("user SQLite: " + str(exc))

user_type_id = payload.get("user_type_id")
if user_type_id is not None:
    try:
        database.delete_ai_config_override(
            "user_default_tool_ids",
            int(user_type_id),
            changed_by="",
        )
        database.delete_ai_config_override(
            "knowledge_source_default",
            int(user_type_id),
            changed_by="",
        )
        database.delete_user_type(int(user_type_id))
    except Exception as exc:
        errors.append("user type SQLite: " + str(exc))

if errors:
    raise RuntimeError(" | ".join(errors))
print(json.dumps({{"status": "clean", "errors": []}}))
"""


def run_command(cmd: list[str], timeout: int, env: dict[str, str] | None = None) -> str:
    redacted_command = " ".join(redact_command(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"command timed out ({redacted_command}) after {timeout}s"
        ) from None
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({redacted_command}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def redact_command(cmd: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for arg in cmd:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        sanitized, redact_next = redact_command_arg(arg)
        redacted.append(sanitized)
    return redacted


def redact_command_arg(arg: str) -> tuple[str, bool]:
    lower_arg = arg.lower()
    if "x-internal-agent-token" not in lower_arg:
        return arg, False

    for separator in (":", "="):
        prefix, found, suffix = arg.partition(separator)
        if found:
            if separator == ":":
                redacted = f"{prefix}{separator} <redacted>"
            else:
                redacted = f"{prefix}=<redacted>"
            return redacted, not bool(suffix.strip())
    return arg, True


def write_artifact(artifact: dict[str, Any], output: str | None) -> Path:
    if output:
        path = Path(output)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = Path(f"/tmp/conversation-model-bench-{stamp}.json")
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def parse_args(argv: list[str]) -> BenchOptions:
    parser = argparse.ArgumentParser(description="Run the Conversation Model Bench")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--output")
    parser.add_argument("--scenario", action="append", dest="scenarios")
    parser.add_argument("--models")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--seed-knowledge", action="store_true")
    parser.add_argument("--seed-resources", action="store_true")
    parser.add_argument("--no-restore-model", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    return BenchOptions(
        api_base=args.api_base,
        output=args.output,
        scenarios=tuple(args.scenarios or DEFAULT_SCENARIOS),
        models=parse_models(args.models),
        timeout=args.timeout,
        reset=args.reset,
        seed_knowledge=args.seed_knowledge,
        seed_resources=args.seed_resources,
        restore_model=not args.no_restore_model,
        verbose=args.verbose,
    )


def parse_models(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def runtime_config_fingerprint_command(token: str) -> list[str]:
    return [
        *COMPOSE_ARGS,
        "exec",
        "-T",
        "sage",
        "curl",
        "-fsS",
        "-H",
        f"X-Internal-Agent-Token: {token}",
        "http://127.0.0.1:3000/internal/runtime-config/fingerprint",
    ]


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv or sys.argv[1:])
    try:
        artifact = run_bench(options)
        output_path = write_artifact(artifact, options.output)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    status = artifact.get("summary", {}).get("status")
    print(f"Conversation Model Bench: {status}")
    print(f"Artifact: {output_path}")
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
