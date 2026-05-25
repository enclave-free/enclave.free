#!/usr/bin/env python3
"""
Test 5E: Conversation Sidebar History

Verifies Sage-owned /query/sessions through the Docker gateway container so
the Conversation Sidebar has a durable, role-aware history source.
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

email = "sidebar-history-smoke@example.test"
user = database.get_user_by_email(email)
if not user:
    user_id = database.create_user(email=email, name="Sidebar History Smoke")
    database.update_user_approval(user_id, True)
    user = database.get_user(user_id)

print(auth.create_admin_session_token(admin["id"], pub, int(admin.get("session_nonce", 0) or 0)))
print(auth.create_session_token(user["id"], email))
"""
    lines = [
        line.strip()
        for line in run_compose_exec("core-backend", "python", "-c", script).splitlines()
        if line.strip()
    ]
    if len(lines) < 2:
        raise RuntimeError("failed to mint smoke auth tokens")
    return {"admin": lines[0], "user": lines[1]}


def gateway_post(token: str, path: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    raw = run_compose_exec(
        "backend",
        "wget",
        "-qO-",
        f"--timeout={timeout}",
        f"--header=Authorization: Bearer {token}",
        "--header=Content-Type: application/json",
        f"--post-data={json.dumps(payload)}",
        f"http://127.0.0.1:8000{path}",
        timeout=timeout + 10,
    )
    return json.loads(raw)


def gateway_get(token: str, path: str, timeout: int = 60) -> dict[str, Any]:
    raw = run_compose_exec(
        "backend",
        "wget",
        "-qO-",
        f"--timeout={timeout}",
        f"--header=Authorization: Bearer {token}",
        f"http://127.0.0.1:8000{path}",
        timeout=timeout + 10,
    )
    return json.loads(raw)


def expect(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"[PASS] {label}")
        return True
    print(f"[FAIL] {label}{': ' + detail if detail else ''}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5E: Conversation Sidebar History")
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="Accepted for compatibility with run_all_be_tests.py; this test intentionally uses the Docker gateway container.",
    )
    parser.parse_args()

    print("=" * 72)
    print("TEST 5E: CONVERSATION SIDEBAR HISTORY")
    print("=" * 72)

    failures = 0
    tokens = mint_smoke_tokens()
    user_response = gateway_post(
        tokens["user"],
        "/llm/chat",
        {"message": "Sidebar history smoke user title", "tools": []},
    )
    admin_response = gateway_post(
        tokens["admin"],
        "/llm/chat",
        {"message": "Sidebar history smoke admin title", "tools": []},
    )

    user_history = gateway_get(tokens["user"], "/query/sessions")
    admin_history = gateway_get(tokens["admin"], "/query/sessions")
    user_conversations = user_history.get("conversations", [])
    admin_conversations = admin_history.get("conversations", [])

    failures += (
        0 if expect("user conversation created", "session_id" in user_response) else 1
    )
    failures += (
        0 if expect("admin conversation created", "session_id" in admin_response) else 1
    )
    failures += (
        0 if expect("user history is a list", isinstance(user_conversations, list)) else 1
    )
    failures += (
        0
        if expect("admin history is a list", isinstance(admin_conversations, list))
        else 1
    )
    failures += 0 if expect(
        "user history includes safe title",
        any(
            item.get("title") == "Sidebar history smoke user title"
            and (item.get("session_id") or item.get("id"))
            == user_response.get("session_id")
            for item in user_conversations
            if isinstance(item, dict)
        ),
    ) else 1
    failures += 0 if expect(
        "admin history includes safe title",
        any(
            item.get("title") == "Sidebar history smoke admin title"
            and (item.get("session_id") or item.get("id"))
            == admin_response.get("session_id")
            for item in admin_conversations
            if isinstance(item, dict)
        ),
    ) else 1
    failures += 0 if expect(
        "user history excludes admin-owned conversation",
        all(
            item.get("owner_type") == "user"
            for item in user_conversations
            if isinstance(item, dict)
        ),
    ) else 1
    failures += 0 if expect(
        "admin history excludes user-owned conversation",
        all(
            item.get("owner_type") == "admin"
            for item in admin_conversations
            if isinstance(item, dict)
        ),
    ) else 1
    failures += 0 if expect(
        "history exposes message counts",
        all(
            isinstance(item.get("message_count"), int)
            for item in user_conversations + admin_conversations
            if isinstance(item, dict)
        ),
    ) else 1

    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nAll conversation sidebar history checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
