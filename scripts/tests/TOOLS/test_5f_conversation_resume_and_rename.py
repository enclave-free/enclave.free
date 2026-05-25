#!/usr/bin/env python3
"""
Test 5F: Conversation Resume and Rename

Verifies saved Conversation resume metadata and title-only rename behavior
through the Docker gateway container.
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
import auth, database, sqlite3

pub = "a" * 64
admin = database.get_admin_by_pubkey(pub)
if not admin:
    conn = sqlite3.connect("/data/enclave.db")
    cur = conn.cursor()
    cur.execute("insert into admins(pubkey) values(?)", (pub,))
    conn.commit()
    conn.close()
    admin = database.get_admin_by_pubkey(pub)
if not admin:
    try:
        database.add_admin(pub)
    except Exception:
        conn = sqlite3.connect("/data/enclave.db")
        cur = conn.cursor()
        cur.execute("insert into admins(pubkey) values(?)", (pub,))
        conn.commit()
    conn.close()
    admin = database.get_admin_by_pubkey(pub)

def user_token(email, name):
    user = database.get_user_by_email(email)
    if not user:
        user_id = database.create_user(email=email, name=name)
        database.update_user_approval(user_id, True)
        user = database.get_user(user_id)
    return auth.create_session_token(user["id"], email)

print(auth.create_admin_session_token(admin["id"], pub, int(admin.get("session_nonce", 0) or 0)))
print(user_token("resume-rename-smoke@example.test", "Resume Rename Smoke"))
print(user_token("resume-rename-other@example.test", "Resume Rename Other"))
"""
    lines = [
        line.strip()
        for line in run_compose_exec("core-backend", "python", "-c", script).splitlines()
        if line.strip()
    ]
    if len(lines) < 3:
        raise RuntimeError("failed to mint smoke auth tokens")
    return {"admin": lines[0], "user": lines[1], "other_user": lines[2]}


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
    if result.returncode != 0:
        raise RuntimeError(
            "gateway request failed "
            f"with {result.returncode}: stderr={result.stderr.strip()} stdout={result.stdout.strip()}"
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5F: Conversation Resume and Rename")
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="Accepted for compatibility with run_all_be_tests.py; this test intentionally uses the Docker gateway container.",
    )
    parser.parse_args()

    print("=" * 72)
    print("TEST 5F: CONVERSATION RESUME AND RENAME")
    print("=" * 72)

    failures = 0
    tokens = mint_smoke_tokens()
    create_status, created = gateway_request(
        tokens["user"],
        "POST",
        "/llm/chat",
        {"message": "Resume rename smoke title", "tools": []},
    )
    session_id = created.get("session_id")
    failures += 0 if expect("user conversation created", create_status == 200 and isinstance(session_id, str)) else 1
    if create_status != 200 or not isinstance(session_id, str):
        return 1

    history_status, history_before = gateway_request(tokens["user"], "GET", "/query/sessions")
    before_item = next(
        (
            item
            for item in history_before.get("conversations", [])
            if isinstance(item, dict) and item.get("id") == session_id
        ),
        {},
    )
    before_updated_at = before_item.get("updated_at")
    resume_status, resumed = gateway_request(tokens["user"], "GET", f"/query/session/{session_id}")
    messages = resumed.get("messages", [])
    history_after_status, history_after = gateway_request(tokens["user"], "GET", "/query/sessions")
    after_item = next(
        (
            item
            for item in history_after.get("conversations", [])
            if isinstance(item, dict) and item.get("id") == session_id
        ),
        {},
    )
    failures += 0 if expect("resume returns 200", resume_status == 200) else 1
    failures += 0 if expect("resume includes title", resumed.get("title") == "Resume rename smoke title") else 1
    failures += 0 if expect(
        "resume exposes stable message ids",
        isinstance(messages, list)
        and len(messages) >= 2
        and all(isinstance(item.get("id"), str) for item in messages if isinstance(item, dict)),
    ) else 1
    failures += 0 if expect(
        "viewing does not update history activity timestamp",
        history_status == 200
        and history_after_status == 200
        and isinstance(before_updated_at, str)
        and after_item.get("updated_at") == before_updated_at,
    ) else 1

    other_status, _ = gateway_request(
        tokens["other_user"],
        "PATCH",
        f"/query/session/{session_id}",
        {"title": "Other user rename"},
    )
    failures += 0 if expect("unauthorized user rename is forbidden", other_status == 403) else 1

    rename_status, renamed = gateway_request(
        tokens["user"],
        "PATCH",
        f"/query/session/{session_id}",
        {"title": "Renamed smoke conversation"},
    )
    failures += 0 if expect("owner rename succeeds", rename_status == 200) else 1
    failures += 0 if expect("rename returns confirmed title", renamed.get("title") == "Renamed smoke conversation") else 1

    _, resumed_after_rename = gateway_request(tokens["user"], "GET", f"/query/session/{session_id}")
    failures += 0 if expect(
        "rename updates title metadata only",
        resumed_after_rename.get("title") == "Renamed smoke conversation"
        and resumed_after_rename.get("messages") == messages,
    ) else 1

    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nAll conversation resume and rename checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
