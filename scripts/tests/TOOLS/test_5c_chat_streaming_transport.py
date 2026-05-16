#!/usr/bin/env python3
"""
Test 5C: Assistant Chat Streaming Transport

Verifies Sage-owned /llm/chat/stream through the Docker gateway container so
host-port collisions do not accidentally test a local non-Docker process.
"""

from __future__ import annotations

import json
import argparse
import subprocess
import sys
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


@dataclass
class StreamEvent:
    event: str
    data: dict[str, Any]


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


def post_stream(token: str, payload: dict[str, Any], timeout: int = 120) -> str:
    result = subprocess.run(
        [
            *COMPOSE_ARGS,
            "exec",
            "-T",
            "backend",
            "wget",
            "-qO-",
            f"--timeout={timeout}",
            f"--header=Authorization: Bearer {token}",
            "--header=Content-Type: application/json",
            "--header=Accept: text/event-stream",
            f"--post-data={json.dumps(payload)}",
            "http://127.0.0.1:8000/llm/chat/stream",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=timeout + 10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"stream request failed with {result.returncode}: {result.stderr.strip()} {result.stdout[:400]}"
        )
    return result.stdout


def parse_sse(raw: str) -> list[StreamEvent]:
    events: list[StreamEvent] = []
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        event_name: str | None = None
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())
        if not event_name:
            continue
        raw_data = "\n".join(data_lines)
        try:
            data = json.loads(raw_data) if raw_data else {}
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid JSON for {event_name}: {raw_data}") from exc
        events.append(StreamEvent(event=event_name, data=data))
    return events


def expect(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"[PASS] {label}")
        return True
    print(f"[FAIL] {label}{': ' + detail if detail else ''}")
    return False


def event_names(events: list[StreamEvent]) -> list[str]:
    return [event.event for event in events]


def final_trace(events: list[StreamEvent]) -> dict[str, Any]:
    for event in events:
        if event.event == "trace_final":
            trace = event.data.get("trace")
            if isinstance(trace, dict):
                return trace
    return {}


def done_payload(events: list[StreamEvent]) -> dict[str, Any]:
    for event in reversed(events):
        if event.event == "done":
            return event.data
    return {}


def nonempty_answer(events: list[StreamEvent]) -> str:
    return "".join(
        str(event.data.get("delta") or "")
        for event in events
        if event.event == "answer_delta"
    ).strip()


def check_common(label: str, events: list[StreamEvent]) -> int:
    failures = 0
    names = event_names(events)
    failures += 0 if expect(f"{label}: assistant starts", "assistant_message_started" in names) else 1
    failures += 0 if expect(f"{label}: live status emitted", "trace_status" in names) else 1
    failures += 0 if expect(f"{label}: answer deltas emitted", bool(nonempty_answer(events))) else 1
    failures += 0 if expect(f"{label}: final trace emitted", "trace_final" in names) else 1
    failures += 0 if expect(f"{label}: done emitted", "done" in names) else 1
    message_ids = {str(event.data.get("message_id")) for event in events if event.data.get("message_id")}
    session_ids = {str(event.data.get("session_id")) for event in events if event.data.get("session_id")}
    failures += 0 if expect(f"{label}: stable message id", len(message_ids) == 1, str(message_ids)) else 1
    failures += 0 if expect(f"{label}: stable session id", len(session_ids) == 1, str(session_ids)) else 1
    return failures


def check_admin_config(token: str) -> int:
    events = parse_sse(
        post_stream(
            token,
            {
                "message": "In one short sentence, summarize the current admin configuration shape.",
                "tools": ["admin-config"],
            },
        )
    )
    failures = check_common("admin-config stream", events)
    trace = final_trace(events)
    tools = trace.get("tools") if isinstance(trace, dict) else []
    done = done_payload(events)
    tool_names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    done_tool_ids = {
        tool.get("tool_id")
        for tool in done.get("tools_used", [])
        if isinstance(tool, dict)
    }
    failures += 0 if expect("admin-config trace names tool", "Admin Config" in tool_names) else 1
    failures += 0 if expect("admin-config done includes tool metadata", "admin-config" in done_tool_ids) else 1
    return failures


def check_db_query(token: str) -> int:
    events = parse_sse(
        post_stream(
            token,
            {
                "message": "SELECT 1 AS one",
                "tools": ["db-query"],
            },
        )
    )
    failures = check_common("db-query stream", events)
    trace = final_trace(events)
    rendered_trace = json.dumps(trace, sort_keys=True)
    tools = trace.get("tools") if isinstance(trace, dict) else []
    db_tool = next(
        (tool for tool in tools if isinstance(tool, dict) and tool.get("id") == "db-query"),
        {},
    )
    failures += 0 if expect("db-query trace marks results redacted", db_tool.get("metadata", {}).get("redacted") is True) else 1
    failures += 0 if expect("db-query trace uses safe input summary", db_tool.get("input_summary") == "Read-only database query.") else 1
    failures += 0 if expect("db-query trace omits raw SQL", "SELECT 1 AS one" not in rendered_trace) else 1
    failures += 0 if expect("db-query trace omits raw row value", '"one"' not in rendered_trace and "**1**" not in rendered_trace) else 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5C: Assistant chat streaming transport")
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="Accepted for compatibility with run_all_be_tests.py; this test intentionally uses the Docker gateway container.",
    )
    parser.parse_args()

    print("=" * 72)
    print("TEST 5C: ASSISTANT CHAT STREAMING TRANSPORT")
    print("=" * 72)
    try:
        token = mint_admin_token()
        failures = check_admin_config(token)
        failures += check_db_query(token)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 2

    if failures:
        print(f"\n[FAIL] {failures} checks failed")
        return 1
    print("\n[PASS] Streaming transport checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
