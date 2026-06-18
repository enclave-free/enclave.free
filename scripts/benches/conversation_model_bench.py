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
import subprocess
import sys
import time
import urllib.error
import urllib.request
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
SLOW_COMPLETION_WARNING_MS = 90_000.0
DEFAULT_SCENARIOS = (
    "admin_config_bootstrap",
    "admin_deployment_readiness",
    "user_knowledge_assistance",
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

    def user_token(self) -> str:
        ...

    def seed_knowledge(self) -> dict[str, Any]:
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


SCENARIOS: dict[str, Scenario] = {
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
            "Read the current Admin Config first, then prepare the changes for review."
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
) -> dict[str, Any]:
    knowledge_fixture: dict[str, Any] | None = None
    if scenario.actor == "admin":
        token = environment.admin_token()
    elif scenario.actor == "user":
        token = environment.user_token()
        if seed_knowledge:
            knowledge_fixture = environment.seed_knowledge()
    else:
        raise ValueError(f"unsupported actor for current bench slice: {scenario.actor}")

    payload = {
        "message": scenario.message,
        "tools": list(scenario.tools),
    }
    if knowledge_fixture:
        job_ids = knowledge_fixture.get("job_ids")
        if isinstance(job_ids, list) and job_ids:
            payload["job_ids"] = job_ids
    try:
        stream = client.stream_chat(token, payload, timeout)
    except Exception as exc:
        stream = StreamResult(
            answer="",
            events=[],
            done={},
            trace=None,
            admin_change_set=None,
            timings={
                "first_event_ms": None,
                "first_visible_assistant_token_ms": None,
                "done_ms": None,
            },
            error=f"scenario stream failed: {exc}",
        )
    tool_evidence = collect_tool_evidence(stream)
    retrieval_evidence = collect_retrieval_evidence(stream)
    checks = checks_for_scenario(scenario, stream, tool_evidence)
    return {
        "id": scenario.id,
        "actor": scenario.actor,
        "request": {
            "tools": list(scenario.tools),
            "message_preview": truncate(scenario.message, 500),
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
        "tool_evidence": tool_evidence,
        "retrieval_evidence": retrieval_evidence,
        "summary": summarize_checks(checks),
        "notes": [],
    }


def scenario_by_id(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError as exc:
        raise ValueError(f"unknown scenario: {scenario_id}") from exc


def checks_for_scenario(
    scenario: Scenario,
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks = common_stream_checks(stream)
    if scenario.id == "admin_config_bootstrap":
        checks.extend(admin_config_bootstrap_checks(stream, tool_evidence))
    elif scenario.id == "admin_deployment_readiness":
        checks.extend(admin_deployment_readiness_checks(stream, tool_evidence))
    elif scenario.id == "user_knowledge_assistance":
        checks.extend(user_knowledge_assistance_checks(stream, tool_evidence))
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

    return [
        check(
            "admin_config_tool_used",
            any(tool_evidence_matches(evidence, "admin-config") for evidence in tool_evidence),
            "hard",
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
            "does_not_claim_missing_proposal_authority",
            not any(phrase in answer_lower for phrase in lack_of_authority_phrases),
            "hard",
        ),
    ]


def user_knowledge_assistance_checks(
    stream: StreamResult,
    tool_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    retrieval_evidence = collect_retrieval_evidence(stream)
    return [
        check(
            "knowledge_search_behavior_recorded",
            any(tool_evidence_matches(evidence, "knowledge-search") for evidence in tool_evidence),
            "warning",
        ),
        check(
            "retrieval_evidence_recorded",
            bool(retrieval_evidence),
            "warning",
        ),
        check(
            "answer_present_with_practical_guidance",
            bool(stream.answer.strip()) and contains_practical_safety_guidance(stream.answer),
            "warning",
        ),
    ]


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
        "status": value.get("status"),
        "output_summary": value.get("output_summary") or value.get("summary"),
        "warnings": value.get("warnings") or [],
    }


def tool_evidence_matches(evidence: dict[str, Any], tool_set_id: str) -> bool:
    tool_id = str(evidence.get("tool_id") or "")
    return (
        tool_id == tool_set_id
        or tool_id.startswith(f"{tool_set_id}:")
        or tool_id.startswith(f"tool-{tool_set_id}:")
    )


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
        return env.get("TINFOIL_MODEL") or "kimi-k2-6"

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

    def user_token(self) -> str:
        script = """
import auth, database, time
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
print(auth.create_session_token(user_id, email))
"""
        return run_backend_python(script, timeout=30).strip()

    def seed_knowledge(self) -> dict[str, Any]:
        script = """
import json
import os
import time
import uuid
from pathlib import Path

from qdrant_client.models import PointStruct

import database
import ingest_db
import store

job_id = "conversation-bench-" + str(int(time.time() * 1000))
chunk_id = job_id + "_chunk_0000"
source_file = "Conversation Model Bench Post-Release Safety.md"
text = (
    "First-day post-release safety guidance: get to a physically safe place, "
    "contact trusted people, document urgent needs, and seek local professional "
    "legal or medical help when needed."
)
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
ingest_db.upsert_retrieval_chunk(
    chunk_id=chunk_id,
    job_id=job_id,
    chunk_index=0,
    source_file=source_file,
    text=text,
)

store.ensure_qdrant_collection()
vector = store.embed_texts(["query: first day after release political imprisonment unsafe"])[0]
point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"chunk:{chunk_id}"))
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

print(json.dumps({"job_ids": [job_id], "sources": [source_file], "chunk_id": chunk_id, "point_id": point_id}))
"""
        raw = run_backend_python(script, timeout=180)
        try:
            return json.loads(raw.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"knowledge fixture did not return JSON: {raw[:400]}") from exc

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
        first_delta_ms: float | None = None
        done_ms: float | None = None
        stream_error: str | None = None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def process_buffer() -> None:
            nonlocal buffer, first_event_ms, first_delta_ms, done_ms
            nonlocal trace, admin_change_set, done
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                event_name, data = parse_sse_event(block)
                if not event_name:
                    continue
                elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                if first_event_ms is None:
                    first_event_ms = elapsed_ms
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
                "first_visible_assistant_token_ms": first_delta_ms,
                "done_ms": done_ms,
            },
            error=stream_error,
        )


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


def run_backend_python(script: str, timeout: int = 120) -> str:
    return run_command(
        [*COMPOSE_ARGS, "exec", "-T", "core-backend", "python", "-c", script],
        timeout=timeout,
    )


def run_command(cmd: list[str], timeout: int, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({' '.join(cmd)}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


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
