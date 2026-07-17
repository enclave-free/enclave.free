#!/usr/bin/env python3
"""
Measure Admin Conversation streaming timing through the local Compose gateway.

This is an evidence harness, not a pass/fail regression test. It mints an admin
bearer token inside the supported Compose topology, posts to /llm/chat/stream via
the gateway, and records time to first visible assistant token plus the
admin-only Conversation Turn Timing phases emitted by Sage.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
COMPOSE_ARGS = [
    "docker",
    "compose",
    "-f",
    "docker-compose.infra.yml",
    "-f",
    "docker-compose.app.yml",
]


@dataclass(frozen=True)
class Scenario:
    name: str
    message: str
    tools: list[str]


SCENARIOS = [
    Scenario(
        name="no_tools",
        message="In one short sentence, say hello and identify your role.",
        tools=[],
    ),
    Scenario(
        name="config_setup_summary",
        message=(
            "Check the current instance setup and deployment readiness with Admin "
            "Config tools. Briefly summarize what is configured and what still needs "
            "attention. Do not change anything."
        ),
        tools=["admin-config"],
    ),
    Scenario(
        name="config_only",
        message="In one short sentence, summarize the current admin configuration shape.",
        tools=["admin-config"],
    ),
    Scenario(
        name="database_natural_language_guarded",
        message="Which users are active?",
        tools=["db-query"],
    ),
    Scenario(
        name="database_direct_select",
        message="SELECT 1 AS one",
        tools=["db-query"],
    ),
]


def mint_admin_token() -> str:
    script = """
import auth, database
admin = database.list_admins()[0]
print(auth.create_admin_session_token(admin["id"], admin["pubkey"], int(admin.get("session_nonce", 0) or 0)))
"""
    result = subprocess.run(
        [*COMPOSE_ARGS, "exec", "-T", "core-backend", "python", "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to mint admin token: {result.stderr.strip()}")
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("failed to mint admin token: no token returned")
    return token


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


def delete_query_session(
    api_base: str,
    token: str,
    session_id: str,
    timeout: float = 30,
) -> None:
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/query/session/{session_id}",
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


def measure_stream(api_base: str, token: str, scenario: Scenario) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    started = time.perf_counter()
    first_event_ms: float | None = None
    first_trace_or_tool_feedback_ms: float | None = None
    first_delta_ms: float | None = None
    done_ms: float | None = None
    timing_phases: list[dict[str, Any]] = []
    tool_statuses: list[dict[str, Any]] = []
    answer_chars = 0
    answer_delta_count = 0
    model_call_count = 0
    correction_call_count = 0
    retry_count = 0
    tool_execution_ms = 0.0
    done_payload: dict[str, Any] = {}

    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/llm/chat/stream",
        data=json.dumps(
            {
                "message": scenario.message,
                "session_id": session_id,
                "tools": scenario.tools,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    try:
        buffer = ""
        try:
            response = urllib.request.urlopen(request, timeout=180)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{scenario.name}: HTTP {exc.code}: {detail}") from exc

        with response:
            while True:
                raw_chunk = response.read(1)
                if not raw_chunk:
                    break
                buffer += raw_chunk.decode("utf-8", errors="replace").replace("\r\n", "\n")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    event_name, data = parse_sse_event(block)
                    if not event_name:
                        continue

                    elapsed_ms = (time.perf_counter() - started) * 1000
                    if first_event_ms is None:
                        first_event_ms = elapsed_ms
                    if (
                        first_trace_or_tool_feedback_ms is None
                        and event_name in {"trace_delta", "activity_step"}
                    ):
                        first_trace_or_tool_feedback_ms = elapsed_ms

                    if event_name == "trace_status":
                        timing = data.get("timing")
                        if isinstance(timing, dict):
                            timing_phases.append(timing)
                    elif event_name == "activity_step":
                        step = data.get("step")
                        if isinstance(step, dict):
                            tool_statuses.append(
                                {
                                    "id": step.get("id"),
                                    "status": step.get("status"),
                                    "warnings": step.get("warnings") or [],
                                }
                            )
                    elif event_name == "trace_delta":
                        trace_delta = data.get("trace_delta")
                        if isinstance(trace_delta, dict):
                            kind = str(trace_delta.get("kind") or "")
                            status = str(trace_delta.get("status") or "")
                            metadata = trace_delta.get("metadata")
                            if kind == "model_step" and status == "running":
                                model_call_count += 1
                            elif kind == "correction" and status == "running":
                                correction_call_count += 1
                            elif kind == "retry" and status == "running":
                                retry_count += 1
                            elif kind == "tool_result" and isinstance(metadata, dict):
                                duration_ms = metadata.get("duration_ms")
                                if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
                                    tool_execution_ms += float(duration_ms)
                    elif event_name == "answer_delta":
                        delta = str(data.get("delta") or "")
                        answer_chars += len(delta)
                        if delta:
                            answer_delta_count += 1
                        if delta and first_delta_ms is None:
                            first_delta_ms = elapsed_ms
                    elif event_name == "trace_final":
                        trace = data.get("trace")
                        if isinstance(trace, dict):
                            for tool in trace.get("tools") or []:
                                if isinstance(tool, dict):
                                    tool_statuses.append(
                                        {
                                            "id": tool.get("id"),
                                            "status": tool.get("status"),
                                            "warnings": tool.get("warnings") or [],
                                        }
                                    )
                    elif event_name == "done":
                        done_ms = elapsed_ms
                        done_payload = data

        if first_delta_ms is None:
            raise RuntimeError(f"{scenario.name}: stream completed without an answer_delta")
        if done_ms is None:
            done_ms = (time.perf_counter() - started) * 1000
        if done_payload.get("session_id") != session_id:
            raise RuntimeError(
                f"{scenario.name}: stream did not preserve requested session_id"
            )
        if scenario.name == "config_setup_summary":
            direct_write_ids = {
                "admin-config:configure_instance",
                "admin-config:update_instance_settings",
                "admin-config:update_deployment_settings",
                "admin-config:update_agent_settings",
                "admin-config:manage_user_types",
                "admin-config:manage_onboarding_questions",
                "admin-config:update_document_access",
            }
            invoked_write_ids = sorted(
                {
                    str(item.get("id") or "")
                    for item in tool_statuses
                    if str(item.get("id") or "") in direct_write_ids
                }
            )
            if invoked_write_ids:
                raise RuntimeError(
                    "config_setup_summary invoked write Tools: "
                    + ", ".join(invoked_write_ids)
                )

        return {
            "scenario": scenario.name,
            "tools": scenario.tools,
            "first_event_ms": round(first_event_ms or 0, 1),
            "first_trace_or_tool_feedback_ms": (
                round(first_trace_or_tool_feedback_ms, 1)
                if first_trace_or_tool_feedback_ms is not None
                else None
            ),
            "first_visible_assistant_token_ms": round(first_delta_ms, 1),
            "done_ms": round(done_ms, 1),
            "answer_chars": answer_chars,
            "answer_delta_count": answer_delta_count,
            "provider_streamed_multiple_answer_deltas": answer_delta_count > 1,
            "model_call_count": model_call_count,
            "correction_call_count": correction_call_count,
            "retry_count": retry_count,
            "tool_execution_ms": round(tool_execution_ms, 1),
            "terminal_prose_zero_corrections": (
                correction_call_count == 0 and retry_count == 0
            ),
            "deterministic_terminal_no_final_model_call": (
                model_call_count == 1
                if scenario.name == "config_setup_summary"
                else None
            ),
            "model": done_payload.get("model"),
            "provider": done_payload.get("provider"),
            "timing_phases": timing_phases,
            "tool_statuses": tool_statuses,
            "background_timing": {
                "persistence_ms": None,
                "embedding_ms": None,
                "availability": (
                    "not exposed by the public stream; deferred persistence/embedding "
                    "behavior is covered by Sage runtime tests"
                ),
            },
        }
    finally:
        stream_failed = sys.exc_info()[0] is not None
        try:
            delete_query_session(api_base, token, session_id)
        except Exception as exc:
            if not stream_failed:
                raise
            print(
                f"[WARN] Failed to clean up query session {session_id}: {exc}",
                file=sys.stderr,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure streamed Admin Conversation timing through Compose"
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:18000")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    try:
        token = mint_admin_token()
        results = [measure_stream(args.api_base, token, scenario) for scenario in SCENARIOS]
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    payload = {
        "api_base": args.api_base,
        "topology": "docker compose gateway",
        "results": results,
    }
    rendered = json.dumps(payload, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
