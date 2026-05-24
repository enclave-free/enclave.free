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


def measure_stream(api_base: str, token: str, scenario: Scenario) -> dict[str, Any]:
    started = time.perf_counter()
    first_event_ms: float | None = None
    first_delta_ms: float | None = None
    done_ms: float | None = None
    timing_phases: list[dict[str, Any]] = []
    tool_statuses: list[dict[str, Any]] = []
    answer_chars = 0

    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/llm/chat/stream",
        data=json.dumps({"message": scenario.message, "tools": scenario.tools}).encode(
            "utf-8"
        ),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

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
                elif event_name == "answer_delta":
                    delta = str(data.get("delta") or "")
                    answer_chars += len(delta)
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

    if first_delta_ms is None:
        raise RuntimeError(f"{scenario.name}: stream completed without an answer_delta")
    if done_ms is None:
        done_ms = (time.perf_counter() - started) * 1000

    return {
        "scenario": scenario.name,
        "tools": scenario.tools,
        "first_event_ms": round(first_event_ms or 0, 1),
        "first_visible_assistant_token_ms": round(first_delta_ms, 1),
        "done_ms": round(done_ms, 1),
        "answer_chars": answer_chars,
        "timing_phases": timing_phases,
        "tool_statuses": tool_statuses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure streamed Admin Conversation timing through Compose"
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
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
