#!/usr/bin/env python3
"""Executable, model-backed issue #535 evaluation (requires Compose + provider)."""
from __future__ import annotations
import argparse, json, subprocess, time, uuid
from pathlib import Path
from typing import Any
import requests

ROOT = Path(__file__).parents[3]
COMPOSE = ["docker", "compose", "-f", "docker-compose.infra.yml", "-f", "docker-compose.app.yml"]
ORG_NAME = "Issue 535 Legal Aid"
CASES = [
    ("en", "email", "What is the email address?", "Can you give me the email?", 0),
    ("es", "email", "¿Cuál es el correo electrónico?", "¿Me puedes dar el email?", 1),
    ("en", "phone", "What is the phone number?", "Can you give me the phone number?", 0),
    ("es", "phone", "¿Cuál es el teléfono?", "¿Me das el número de teléfono?", 1),
    ("en", "url", "What is the website?", "Can you give me the website?", 0),
    ("es", "url", "¿Cuál es el sitio web?", "¿Me das el sitio web?", 1),
    ("en", "address", "What is the address?", "Can you give me the address?", 0),
    ("es", "address", "¿Cuál es la dirección?", "¿Me das la dirección?", 1),
    ("en", "secure_channel", "What secure channel is listed?", "Can you give me the secure channel?", 0),
    ("es", "secure_channel", "¿Cuál es el canal seguro?", "¿Me das el canal seguro?", 1),
]


def initial_message(language: str, initial: str) -> str:
    if language == "es":
        return f"{ORG_NAME} está en México y ofrece ayuda legal. {initial} Responde en español."
    return f"{ORG_NAME} is in Mexico and provides legal help. {initial} Answer in English."


def context_free_followup(text: str) -> bool:
    forbidden = (ORG_NAME, "Acme Legal Aid", "Mexico", "legal help", "legal aid")
    return not any(term.casefold() in text.casefold() for term in forbidden)

def expect(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{': ' + detail if detail and not ok else ''}")
    return ok

def backend_python(source: str) -> list[str]:
    p = subprocess.run([*COMPOSE, "exec", "-T", "core-backend", "python", "-c", source], cwd=ROOT, capture_output=True, text=True, timeout=45)
    if p.returncode: raise RuntimeError(p.stderr.strip() or "backend helper failed")
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]

def mint() -> dict[str, str]:
    rows = backend_python(r'''import auth, database, json, time
a = database.list_admins()[0]
suffix = str(int(time.time() * 1000)); email = "issue-535-eval-" + suffix + "@example.test"
uid = database.create_user(email=email, name="Issue 535 Eval"); database.update_user_approval(uid, True)
print(json.dumps({"admin": auth.create_admin_session_token(a["id"], a["pubkey"], int(a.get("session_nonce", 0) or 0)), "user": auth.create_session_token(uid, email), "user_id": str(uid)}))''')
    return json.loads(rows[-1])

def req(base: str, token: str, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 180) -> requests.Response:
    return requests.request(method, base.rstrip("/") + path, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=timeout)

def parse_sse(raw: str) -> list[dict[str, Any]]:
    out = []
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        name, data = None, []
        for line in block.splitlines():
            if line.startswith("event:"): name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"): data.append(line.split(":", 1)[1].lstrip())
        if name:
            out.append({"event": name, "data": json.loads("\n".join(data) or "{}")})
    return out

def answer_json(value: Any) -> str:
    if not isinstance(value, dict): return ""
    return next((value[k] for k in ("answer", "content", "message") if isinstance(value.get(k), str)), "")

def score_contact_turn(answer: str, trace: Any, fresh: str, stale: str, tool_enabled: bool = True) -> tuple[bool, str]:
    text = json.dumps(trace, sort_keys=True, ensure_ascii=False)
    fresh_ok, stale_ok = fresh in answer, stale not in answer
    tool_ok = ("find_resources" in text or "curated-resources" in text) if tool_enabled else not ("find_resources" in text or "curated-resources" in text)
    answer_ok = fresh_ok if tool_enabled else not fresh_ok
    return answer_ok and stale_ok and tool_ok, f"fresh={fresh_ok} stale_absent={stale_ok} tool={tool_ok}"

def run_turn(base: str, token: str, payload: dict[str, Any], stream: bool, timeout: float) -> tuple[str, Any, str | None]:
    response = req(base, token, "POST", "/llm/chat/stream" if stream else "/llm/chat", payload, timeout)
    if response.status_code != 200: raise RuntimeError(f"chat returned {response.status_code}: {response.text[:400]}")
    if not stream:
        body = response.json(); return answer_json(body), (body.get("trace") or body), body.get("session_id")
    events = parse_sse(response.text)
    answer = "".join(str(e["data"].get("delta") or "") for e in events if e["event"] == "answer_delta").strip()
    trace = next((e["data"].get("trace", {}) for e in events if e["event"] == "trace_final"), {})
    sid = next((e["data"].get("session_id") for e in events if e["data"].get("session_id")), None)
    return answer, trace, sid

def resource(base: str, token: str, rid: str, contact: dict[str, str], method: str = "POST") -> None:
    body = {"resource_id": rid, "name": ORG_NAME, "resource_type": "legal", "description": "Synthetic evaluation fixture; do not contact.", "contact": contact, "languages": ["en", "es"], "scope_level": "country", "scope_code": "MX", "help_types": ["legal"], "verified": True, "vetted_by": "issue-535-eval"}
    path = "/admin/resources" if method == "POST" else f"/admin/resources/{rid}"
    r = req(base, token, method, path, body)
    if r.status_code not in ({200, 201} if method == "POST" else {200}): raise RuntimeError(f"resource {method}: {r.status_code} {r.text[:400]}")


def cleanup_session(base: str, token: str, session_id: str) -> bool:
    response = req(base, token, "DELETE", f"/query/session/{session_id}", timeout=30)
    try:
        body = response.json()
    except ValueError:
        body = {}
    return session_cleanup_ok(response.status_code, body)


def session_cleanup_ok(status_code: int, body: Any) -> bool:
    deletion = body.get("deletion", {}) if isinstance(body, dict) else {}
    return status_code == 200 and body.get("status") == "deleted" and deletion.get("status") == "succeeded"


def cleanup_resource(base: str, token: str, resource_id: str) -> bool:
    deleted = req(base, token, "DELETE", f"/admin/resources/{resource_id}", timeout=30)
    try:
        body = deleted.json()
    except ValueError:
        body = {}
    if not resource_delete_ok(deleted.status_code, body):
        return False
    listing = req(base, token, "GET", "/admin/resources", timeout=30)
    if listing.status_code != 200:
        return False
    try:
        resources = listing.json().get("resources", [])
    except (TypeError, ValueError):
        return False
    return not any(isinstance(item, dict) and item.get("resource_id") == resource_id for item in resources)


def resource_delete_ok(status_code: int, body: Any) -> bool:
    return status_code == 200 and isinstance(body, dict) and body.get("success") is True


def cleanup_user(user_id: str) -> bool:
    rows = backend_python(f"import database, json; deleted = database.delete_user({int(user_id)}); print(json.dumps({{'deleted': deleted, 'exists': database.get_user({int(user_id)}) is not None}}))")
    result = json.loads(rows[-1]) if rows else {}
    return result.get("deleted") is True and result.get("exists") is False

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--api-base", default="http://localhost:18000"); ap.add_argument("--timeout", type=float, default=180); args = ap.parse_args()
    stale = {"email": "stale-535@example.test", "phone": "+52-555-0100", "url": "https://stale.example.test", "address": "Stale office, Mexico", "secure_channel": "stale-secure-535"}
    fresh = {"email": "fresh-535@example.test", "phone": "+52-555-0199", "url": "https://fresh.example.test", "address": "Fresh office, Mexico", "secure_channel": "fresh-secure-535"}
    fixtures = None; sessions: list[str] = []; rid = f"issue-535-eval-{int(time.time() * 1000)}"; failures = 0; cleanup_failures = 0; fatal = False
    try:
        fixtures = mint(); resource(args.api_base, fixtures["admin"], rid, stale)
        for language, key, initial, followup, stream in CASES:
            # Every scenario starts from the same stale directory state; no prior
            # case's fresh update is allowed to leak into the next initial turn.
            resource(args.api_base, fixtures["admin"], rid, stale, "PUT")
            sid = str(uuid.uuid4())
            sessions.append(sid)
            first, _, returned_sid = run_turn(args.api_base, fixtures["user"], {"message": initial_message(language, initial), "tools": ["curated-resources"], "session_id": sid}, False, args.timeout)
            if returned_sid != sid:
                raise RuntimeError(f"initial session id mismatch: expected {sid}, got {returned_sid}")
            failures += 0 if expect(f"{language} {key}: stale initial", stale[key] in first, first[:240]) else 1
            resource(args.api_base, fixtures["admin"], rid, fresh, "PUT")
            answer, trace, followup_sid = run_turn(args.api_base, fixtures["user"], {"message": followup, "tools": ["curated-resources"], "session_id": sid}, bool(stream), args.timeout)
            if followup_sid != sid:
                raise RuntimeError(f"follow-up session id mismatch: expected {sid}, got {followup_sid}")
            ok, detail = score_contact_turn(answer, trace, fresh[key], stale[key]); failures += 0 if expect(f"{language} {key}: fresh follow-up", ok, detail) else 1
        disabled_sid = str(uuid.uuid4())
        sessions.append(disabled_sid)
        answer, trace, returned_disabled_sid = run_turn(args.api_base, fixtures["user"], {"message": "Do not use tools. What is the email address?", "tools": [], "session_id": disabled_sid}, False, args.timeout)
        if returned_disabled_sid != disabled_sid:
            raise RuntimeError(f"disabled session id mismatch: expected {disabled_sid}, got {returned_disabled_sid}")
        ok, detail = score_contact_turn(answer, trace, fresh["email"], stale["email"], False); failures += 0 if expect("disabled tools: no invented contact", ok, detail) else 1
    except Exception as exc:
        print(f"[ERROR] {exc}"); fatal = True
    finally:
        if fixtures:
            for sid in sessions:
                try:
                    if not cleanup_session(args.api_base, fixtures["user"], sid):
                        cleanup_failures += 1; print(f"[FAIL] cleanup session {sid}")
                except Exception as exc:
                    cleanup_failures += 1; print(f"[FAIL] cleanup session {sid}: {exc}")
            try:
                if not cleanup_resource(args.api_base, fixtures["admin"], rid):
                    cleanup_failures += 1; print("[FAIL] cleanup resource verification")
            except Exception as exc:
                cleanup_failures += 1; print(f"[FAIL] cleanup resource: {exc}")
            try:
                if not cleanup_user(fixtures["user_id"]):
                    cleanup_failures += 1; print("[FAIL] cleanup user verification")
            except Exception as exc:
                cleanup_failures += 1; print(f"[FAIL] cleanup user: {exc}")
    return 2 if fatal else (1 if failures or cleanup_failures else 0)

if __name__ == "__main__": raise SystemExit(main())
