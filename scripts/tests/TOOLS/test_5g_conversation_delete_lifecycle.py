#!/usr/bin/env python3
"""
Test 5G: Conversation Delete Lifecycle

Verifies authorized saved Conversation deletion through the Docker gateway
container and confirms the deleted Conversation disappears from resume/history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def run_compose_exec(service: str, *args: str, timeout: int = 60) -> str:
    result = subprocess.run(
        [*COMPOSE_ARGS, "exec", "-T", service, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{service} exec failed with {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def mint_smoke_tokens() -> dict[str, str]:
    script = r"""
import auth, database

def user_token(email, name):
    user = database.get_user_by_email(email)
    if not user:
        user_id = database.create_user(email=email, name=name)
        database.update_user_approval(user_id, True)
        user = database.get_user(user_id)
    return auth.create_session_token(user["id"], email)

print(user_token("delete-lifecycle-smoke@example.test", "Delete Lifecycle Smoke"))
print(user_token("delete-lifecycle-other@example.test", "Delete Lifecycle Other"))
"""
    lines = [
        line.strip()
        for line in run_compose_exec("core-backend", "python", "-c", script).splitlines()
        if line.strip()
    ]
    if len(lines) < 2:
        raise RuntimeError("failed to mint smoke auth tokens")
    return {"user": lines[0], "other_user": lines[1]}


def gateway_request(
    token: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> tuple[int, dict[str, Any]]:
    args = [
        "curl",
        "-sS",
        "-w",
        "\n%{http_code}",
        "-X",
        method,
        "-H",
        f"Authorization: Bearer {token}",
    ]
    if payload is not None:
        args.extend(
            [
                "-H",
                "Content-Type: application/json",
                "--data",
                json.dumps(payload),
            ]
        )
    args.append(f"http://127.0.0.1:8000{path}")
    result = subprocess.run(
        [*COMPOSE_ARGS, "exec", "-T", "backend", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=timeout + 10,
    )
    raw = result.stdout
    body, _, status_text = raw.rpartition("\n")
    status = int(status_text) if status_text.isdigit() else 0
    data = json.loads(body) if body else {}
    return status, data


def expect(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"[PASS] {label}")
        return True
    print(f"[FAIL] {label}{': ' + detail if detail else ''}")
    return False


def history_contains_session(history: dict[str, Any], session_id: str) -> bool:
    return any(
        isinstance(item, dict) and item.get("id") == session_id
        for item in history.get("conversations", [])
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5G: Conversation Delete Lifecycle")
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="Accepted for compatibility with run_all_be_tests.py; this test intentionally uses the Docker gateway container.",
    )
    parser.parse_args()

    print("=" * 72)
    print("TEST 5G: CONVERSATION DELETE LIFECYCLE")
    print("=" * 72)

    failures = 0
    tokens = mint_smoke_tokens()
    create_status, created = gateway_request(
        tokens["user"],
        "POST",
        "/llm/chat",
        {"message": "Delete lifecycle smoke title", "tools": []},
    )
    session_id = created.get("session_id")
    failures += 0 if expect("user conversation created", create_status == 200 and isinstance(session_id, str)) else 1
    if not isinstance(session_id, str):
        return 1

    history_status, history_before = gateway_request(tokens["user"], "GET", "/query/sessions")
    failures += 0 if expect(
        "history includes created conversation",
        history_status == 200 and history_contains_session(history_before, session_id),
    ) else 1

    other_status, _ = gateway_request(
        tokens["other_user"],
        "DELETE",
        f"/query/session/{session_id}",
    )
    failures += 0 if expect("unauthorized user delete is forbidden", other_status == 403) else 1

    owner_status, deleted = gateway_request(
        tokens["user"],
        "DELETE",
        f"/query/session/{session_id}",
    )
    deletion = deleted.get("deletion", {})
    failures += 0 if expect("owner delete succeeds", owner_status == 200) else 1
    failures += 0 if expect(
        "delete returns sanitized lifecycle summary",
        deleted.get("status") == "deleted"
        and isinstance(deletion, dict)
        and deletion.get("status") == "succeeded"
        and isinstance(deletion.get("counts"), dict)
        and "messages" not in deleted
        and "content" not in deleted,
    ) else 1

    resume_status, _ = gateway_request(tokens["user"], "GET", f"/query/session/{session_id}")
    failures += 0 if expect("deleted conversation cannot be resumed", resume_status == 404) else 1

    history_after_status, history_after = gateway_request(tokens["user"], "GET", "/query/sessions")
    failures += 0 if expect(
        "history no longer includes deleted conversation",
        history_after_status == 200 and not history_contains_session(history_after, session_id),
    ) else 1

    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nAll conversation delete lifecycle checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
