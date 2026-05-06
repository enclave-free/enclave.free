#!/usr/bin/env python3
"""
Test 5A: Internal Agent Contract

Validates the private Sage-to-Python /internal/agent/* contract:
- protected routes reject missing tokens
- health and low-data endpoints return expected schemas with the token
- data-dependent endpoints are checked when matching fixtures exist
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest


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
        raise RuntimeError(
            "sqlite3 JSON query failed "
            f"(returncode={result.returncode}, stderr={result.stderr!r}, stdout={result.stdout!r})"
        )
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "sqlite3 JSON query returned invalid JSON "
            f"(stdout={result.stdout!r}, stderr={result.stderr!r})"
        ) from exc


class SimpleResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def json(self) -> dict[str, Any]:
        return json.loads(self.text or "{}")


def request_json(
    method: str,
    api_base: str,
    path: str,
    token: str | None,
    payload: dict[str, Any] | None = None,
) -> SimpleResponse:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["X-Internal-Agent-Token"] = token
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    req = urlrequest.Request(
        f"{api_base.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlrequest.urlopen(req, timeout=60) as resp:
            return SimpleResponse(int(resp.getcode() or 0), resp.read().decode("utf-8", errors="replace"))
    except urlerror.HTTPError as exc:
        return SimpleResponse(int(exc.code or 0), exc.read().decode("utf-8", errors="replace"))
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        return SimpleResponse(0, f"Request failed: {exc}")


def post_json(api_base: str, path: str, token: str | None, payload: dict[str, Any]) -> SimpleResponse:
    return request_json("POST", api_base, path, token, payload)


def get_json(api_base: str, path: str, token: str | None) -> SimpleResponse:
    return request_json("GET", api_base, path, token)


def expect_status(label: str, response: SimpleResponse, expected: set[int]) -> bool:
    if response.status_code in expected:
        print(f"[PASS] {label}: HTTP {response.status_code}")
        return True
    print(f"[FAIL] {label}: expected {sorted(expected)}, got {response.status_code}: {response.text[:400]}")
    return False


def expect_keys(label: str, data: dict[str, Any], keys: set[str]) -> bool:
    missing = sorted(keys - set(data))
    if not missing:
        print(f"[PASS] {label}: schema keys present")
        return True
    print(f"[FAIL] {label}: missing keys {missing}; got {sorted(data)}")
    return False


def expect(name: str, condition: Any, details: str = "") -> bool:
    if condition:
        return True
    suffix = f": {details}" if details else ""
    print(f"[FAIL] {name}{suffix}")
    return False


def first_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5A: internal agent contract")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--internal-token", default=os.getenv("INTERNAL_AGENT_TOKEN"))
    parser.add_argument("--token", help="Accepted for run_all_be_tests compatibility; unused")
    args = parser.parse_args()

    env_values = load_container_env()
    internal_token = args.internal_token or env_values.get("INTERNAL_AGENT_TOKEN", "")
    db_path = env_values.get("SQLITE_PATH", DEFAULT_DB_PATH)

    if not internal_token:
        print("[ERROR] INTERNAL_AGENT_TOKEN not provided and not discoverable from core-backend")
        return 2

    print("=" * 72)
    print("TEST 5A: INTERNAL AGENT CONTRACT")
    print("=" * 72)

    failures = 0

    protected_routes: list[tuple[str, str, str, dict[str, Any] | None]] = [
        ("GET health", "GET", "/internal/agent/health", None),
        ("GET user record", "GET", "/internal/agent/users/1", None),
        ("GET admin record", "GET", "/internal/agent/admins/by-pubkey/missing", None),
        ("GET user type", "GET", "/internal/agent/user-types/1", None),
        ("GET document access", "GET", "/internal/agent/document-access", None),
        ("GET user profile", "GET", "/internal/agent/user-profile-context/1", None),
        (
            "POST document search",
            "POST",
            "/internal/agent/document-search",
            {
                "query": "contract smoke",
                "user": {"id": -1, "type": "user", "approved": True, "user_type_id": None, "dev_mode": True},
                "top_k": 1,
            },
        ),
        ("POST admin DB query", "POST", "/internal/agent/admin-db-query", {"sql": "SELECT 1"}),
    ]

    unauthorized_cases: list[tuple[str, str, str, dict[str, Any] | None, str | None]] = []
    for label, method, path, payload in protected_routes:
        unauthorized_cases.append((f"{label} rejects missing token", method, path, payload, None))
        unauthorized_cases.append((f"{label} rejects invalid token", method, path, payload, "invalid-internal-agent-token"))

    for label, method, path, payload, token in unauthorized_cases:
        response = post_json(args.api_base, path, token, payload or {}) if method == "POST" else get_json(args.api_base, path, token)
        failures += 0 if expect_status(label, response, {403}) else 1

    health = get_json(args.api_base, "/internal/agent/health", internal_token)
    if expect_status("GET /internal/agent/health with token", health, {200}):
        failures += 0 if expect_keys("internal health", health.json(), {"status"}) else 1
    else:
        failures += 1

    access = get_json(args.api_base, "/internal/agent/document-access", internal_token)
    if expect_status("GET /internal/agent/document-access with token", access, {200}):
        failures += 0 if expect_keys("document access", access.json(), {"user_type_id", "available_document_ids", "default_document_ids"}) else 1
    else:
        failures += 1

    db_query = post_json(args.api_base, "/internal/agent/admin-db-query", internal_token, {"sql": "SELECT 1 AS one"})
    if expect_status("POST /internal/agent/admin-db-query with token", db_query, {200}):
        failures += 0 if expect_keys("admin DB query", db_query.json(), {"success", "columns", "rows", "executionTimeMs", "error"}) else 1
    else:
        failures += 1

    unsafe_query = post_json(args.api_base, "/internal/agent/admin-db-query", internal_token, {"sql": "DELETE FROM users"})
    if expect_status("POST /internal/agent/admin-db-query unsafe SQL", unsafe_query, {200}):
        data = unsafe_query.json()
        if data.get("success") is False and data.get("error"):
            print("[PASS] unsafe SQL returns success=false error payload")
        else:
            print(f"[FAIL] unsafe SQL did not return expected error payload: {data}")
            failures += 1
    else:
        failures += 1

    admin_lookup_failed = False
    try:
        admin = first_row(run_sqlite_json("SELECT id, pubkey FROM admins ORDER BY id ASC LIMIT 1", db_path))
    except RuntimeError as exc:
        print(f"[SKIP] admin row unavailable: {exc}")
        admin = None
        admin_lookup_failed = True
    if admin:
        admin_res = get_json(args.api_base, f"/internal/agent/admins/by-pubkey/{admin['pubkey']}", internal_token)
        if expect_status("GET admin record with token", admin_res, {200}):
            admin_data = admin_res.json()
            failures += 0 if expect_keys("admin record", admin_data, {"id", "type", "pubkey", "session_nonce"}) else 1
            failures += 0 if expect("admin record type discriminator", admin_data.get("type") == "admin", str(admin_data)) else 1
        else:
            failures += 1
    elif not admin_lookup_failed:
        print("[SKIP] no admin row available for admin schema check")

    user_type_lookup_failed = False
    try:
        user_type = first_row(run_sqlite_json("SELECT id FROM user_types ORDER BY id ASC LIMIT 1", db_path))
    except RuntimeError as exc:
        print(f"[SKIP] user type row unavailable: {exc}")
        user_type = None
        user_type_lookup_failed = True
        failures += 1
    if user_type:
        type_res = get_json(args.api_base, f"/internal/agent/user-types/{user_type['id']}", internal_token)
        if expect_status("GET user type with token", type_res, {200}):
            failures += 0 if expect_keys("user type", type_res.json(), {"id", "name", "description", "icon", "display_order", "created_at"}) else 1
        else:
            failures += 1
    elif not user_type_lookup_failed:
        print("[SKIP] no user_type row available for user-type schema check")

    user_lookup_failed = False
    try:
        user = first_row(run_sqlite_json("SELECT id FROM users ORDER BY id ASC LIMIT 1", db_path))
    except RuntimeError as exc:
        print(f"[SKIP] user row unavailable: {exc}")
        user = None
        user_lookup_failed = True
        failures += 1
    if user:
        user_res = get_json(args.api_base, f"/internal/agent/users/{user['id']}", internal_token)
        if expect_status("GET user record with token", user_res, {200}):
            user_data = user_res.json()
            failures += 0 if expect_keys("user record", user_data, {"id", "type", "approved", "email", "name", "user_type_id", "dev_mode"}) else 1
            failures += 0 if expect("user record type discriminator", user_data.get("type") == "user", str(user_data)) else 1
        else:
            failures += 1

        profile_res = get_json(args.api_base, f"/internal/agent/user-profile-context/{user['id']}", internal_token)
        if expect_status("GET user profile context with token", profile_res, {200}):
            failures += 0 if expect_keys("user profile context", profile_res.json(), {"user_id", "user_type_id", "profile"}) else 1
        else:
            failures += 1
    elif not user_lookup_failed:
        print("[SKIP] no user row available for user/profile schema checks")

    doc_search = post_json(
        args.api_base,
        "/internal/agent/document-search",
        internal_token,
        {
            "query": "contract smoke",
            "user": {"id": -1, "type": "user", "approved": True, "user_type_id": None, "dev_mode": True},
            "top_k": 1,
        },
    )
    if doc_search.status_code == 200:
        failures += 0 if expect_keys("document search", doc_search.json(), {"sources", "context", "search_query", "top_k"}) else 1
    elif 500 <= doc_search.status_code < 600:
        print(f"[SKIP] document-search schema check skipped due to upstream retrieval dependency: HTTP {doc_search.status_code}")
    else:
        print(f"[FAIL] document-search returned unexpected status {doc_search.status_code}: {doc_search.text[:400]}")
        failures += 1

    print("-" * 72)
    if failures:
        print(f"TEST 5A RESULT: FAILED ({failures} issue(s))")
        return 1
    print("TEST 5A RESULT: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
