#!/usr/bin/env python3
"""
Test 5B: Sage-Owned Route Smoke

Exercises the public routes that nginx forwards to Sage and checks key
auth/CSRF/admin-user boundaries.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from itsdangerous import URLSafeTimedSerializer


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
DEFAULT_DB_PATH = "/data/sanctum.db"


def load_container_env(service: str = "core-backend") -> dict[str, str]:
    try:
        result = subprocess.run(
            [*COMPOSE_ARGS, "exec", "-T", service, "env"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=20,
        )
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def require_env(values: dict[str, str], key: str, service: str) -> str:
    value = values.get(key)
    if not value:
        raise RuntimeError(f"{service} did not expose required {key}; smoke test cannot mint matching auth cookies")
    return value


def run_sqlite_json(sql: str, db_path: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [*COMPOSE_ARGS, "exec", "-T", "core-backend", "sqlite3", "-readonly", "-json", db_path],
        input=sql.strip().rstrip(";"),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []


def first_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def normalize_origin(raw: str) -> str:
    parsed = urlparse(raw or "")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return (raw or "").rstrip("/") or "http://localhost:5173"


def resolve_origin(env_values: dict[str, str]) -> str:
    configured = env_values.get("CORS_ORIGINS") or env_values.get("CORS_ALLOW_ORIGINS") or ""
    for part in configured.split(","):
        origin = normalize_origin(part.strip())
        if origin and origin != "*":
            return origin
    return normalize_origin(env_values.get("FRONTEND_URL", "http://localhost:5173"))


def admin_token(secret_key: str, admin: dict[str, Any]) -> str:
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(
        {
            "admin_id": int(admin["id"]),
            "pubkey": admin["pubkey"],
            "type": "admin",
            "session_nonce": int(admin.get("session_nonce") or 0),
        },
        salt="admin-session",
    )


def user_token(secret_key: str, user: dict[str, Any]) -> str:
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(
        {
            "user_id": int(user["id"]),
            "email": user.get("email") or f"test-user-{user['id']}@example.test",
        },
        salt="session",
    )


def ensure_user(db_path: str) -> dict[str, Any] | None:
    return first_row(
        run_sqlite_json(
            "SELECT id, COALESCE(email, '') AS email, user_type_id FROM users WHERE approved = 1 ORDER BY id ASC LIMIT 1",
            db_path,
        )
    )


def expect(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"[PASS] {label}")
        return True
    print(f"[FAIL] {label}{': ' + detail if detail else ''}")
    return False


def expect_status(label: str, response: requests.Response, expected: set[int]) -> bool:
    return expect(label, response.status_code in expected, f"expected {sorted(expected)}, got {response.status_code}: {response.text[:400]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5B: Sage-owned route smoke")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--token", help="Optional admin bearer token")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    backend_env_values = load_container_env("core-backend")
    sage_env_values = load_container_env("sage")
    db_path = backend_env_values.get("SQLITE_PATH", DEFAULT_DB_PATH)
    try:
        secret_key = require_env(sage_env_values, "SECRET_KEY", "sage")
        csrf_cookie_name = require_env(sage_env_values, "CSRF_COOKIE_NAME", "sage")
        admin_cookie_name = require_env(sage_env_values, "ADMIN_SESSION_COOKIE_NAME", "sage")
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 2
    origin = resolve_origin(sage_env_values)

    admin = first_row(
        run_sqlite_json(
            "SELECT id, pubkey, COALESCE(session_nonce, 0) AS session_nonce FROM admins ORDER BY id ASC LIMIT 1",
            db_path,
        )
    )
    if not admin and not args.token:
        print("[ERROR] No admin token provided and no admin row found")
        return 2
    active_admin_token = args.token or admin_token(secret_key, admin)

    user = ensure_user(db_path)
    active_user_token = user_token(secret_key, user) if user else None

    print("=" * 72)
    print("TEST 5B: SAGE-OWNED ROUTE SMOKE")
    print("=" * 72)

    failures = 0

    defaults = requests.get(f"{args.api_base.rstrip('/')}/session-defaults", timeout=30)
    failures += 0 if expect_status("GET /session-defaults", defaults, {200}) else 1
    if defaults.status_code == 200:
        data = defaults.json()
        failures += 0 if expect("session-defaults schema", {"web_search_enabled", "default_document_ids"} <= set(data)) else 1

    chat_payload = {"message": "Reply with OK.", "tools": []}
    bearer_chat = requests.post(
        f"{args.api_base.rstrip('/')}/llm/chat",
        headers={"Authorization": f"Bearer {active_admin_token}", "Content-Type": "application/json"},
        json=chat_payload,
        timeout=args.timeout,
    )
    failures += 0 if expect_status("POST /llm/chat admin bearer", bearer_chat, {200}) else 1

    csrf_token = secrets.token_urlsafe(32)
    cookie_session = requests.Session()
    cookie_session.cookies.set(admin_cookie_name, active_admin_token)
    cookie_session.cookies.set(csrf_cookie_name, csrf_token)

    cookie_chat = cookie_session.post(
        f"{args.api_base.rstrip('/')}/llm/chat",
        headers={"Origin": origin, "X-CSRF-Token": csrf_token, "Content-Type": "application/json"},
        json=chat_payload,
        timeout=args.timeout,
    )
    failures += 0 if expect_status("POST /llm/chat admin cookie + valid CSRF", cookie_chat, {200}) else 1

    missing_csrf = cookie_session.post(
        f"{args.api_base.rstrip('/')}/llm/chat",
        headers={"Origin": origin, "Content-Type": "application/json"},
        json=chat_payload,
        timeout=30,
    )
    failures += 0 if expect_status("POST /llm/chat admin cookie + missing CSRF", missing_csrf, {403}) else 1

    bad_csrf = cookie_session.post(
        f"{args.api_base.rstrip('/')}/llm/chat",
        headers={"Origin": origin, "X-CSRF-Token": "bad-token", "Content-Type": "application/json"},
        json=chat_payload,
        timeout=30,
    )
    failures += 0 if expect_status("POST /llm/chat admin cookie + bad CSRF", bad_csrf, {403}) else 1

    ai_config = requests.get(
        f"{args.api_base.rstrip('/')}/admin/ai-config",
        headers={"Authorization": f"Bearer {active_admin_token}"},
        timeout=30,
    )
    failures += 0 if expect_status("GET /admin/ai-config admin bearer", ai_config, {200}) else 1

    tool_exec = requests.post(
        f"{args.api_base.rstrip('/')}/admin/tools/execute",
        headers={"Authorization": f"Bearer {active_admin_token}", "Content-Type": "application/json"},
        json={"tool_id": "db-query", "query": "SELECT 1 AS one"},
        timeout=30,
    )
    failures += 0 if expect_status("POST /admin/tools/execute admin bearer", tool_exec, {200}) else 1

    if active_user_token:
        user_tool_exec = requests.post(
            f"{args.api_base.rstrip('/')}/admin/tools/execute",
            headers={"Authorization": f"Bearer {active_user_token}", "Content-Type": "application/json"},
            json={"tool_id": "db-query", "query": "SELECT 1 AS one"},
            timeout=30,
        )
        failures += 0 if expect_status("POST /admin/tools/execute non-admin rejection", user_tool_exec, {403}) else 1

        query_res = requests.post(
            f"{args.api_base.rstrip('/')}/query",
            headers={"Authorization": f"Bearer {active_user_token}", "Content-Type": "application/json"},
            json={"question": "Reply with OK using available context.", "top_k": 1, "tools": []},
            timeout=args.timeout,
        )
        if expect_status("POST /query user bearer", query_res, {200}):
            data = query_res.json()
            session_id = data.get("session_id")
            failures += 0 if expect("/query returns session_id", bool(session_id)) else 1
            if session_id:
                own_session = requests.get(
                    f"{args.api_base.rstrip('/')}/query/session/{session_id}",
                    headers={"Authorization": f"Bearer {active_user_token}"},
                    timeout=30,
                )
                failures += 0 if expect_status("GET /query/session owner access", own_session, {200}) else 1

                admin_session = requests.get(
                    f"{args.api_base.rstrip('/')}/query/session/{session_id}",
                    headers={"Authorization": f"Bearer {active_admin_token}"},
                    timeout=30,
                )
                failures += 0 if expect_status("GET /query/session admin access", admin_session, {200}) else 1
        else:
            failures += 1
    else:
        print("[SKIP] user-token checks skipped; no approved user fixture exists")

    print("-" * 72)
    if failures:
        print(f"TEST 5B RESULT: FAILED ({failures} issue(s))")
        return 1
    print("TEST 5B RESULT: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
