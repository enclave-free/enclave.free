#!/usr/bin/env python3
"""Executable, model-backed issue #539 evaluation (requires Compose + provider)."""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, time, uuid
from collections import namedtuple
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
import requests

ROOT = Path(__file__).parents[3]
COMPOSE = ["docker", "compose"]
if os.environ.get("ENCLAVE_EVAL_COMPOSE_ENV_FILE"):
    COMPOSE.extend(["--env-file", os.environ["ENCLAVE_EVAL_COMPOSE_ENV_FILE"]])
COMPOSE.extend(["-f", "docker-compose.infra.yml", "-f", "docker-compose.app.yml"])
ORG_NAME = "Issue 539 Legal Aid"


PersonaSpec = namedtuple(
    "PersonaSpec",
    ("key", "name", "user_type_id", "create_user_type"),
    defaults=(None, True),
)


PERSONAS = (
    PersonaSpec("generic_user", "Global / no User Type", create_user_type=False),
    PersonaSpec("family_member", "Family member"),
    PersonaSpec("former_political_prisoner", "Former Political Prisoner"),
    PersonaSpec(
        "solidarity_networks_for_political_prisoners",
        "Solidarity Networks for Political Prisoners",
    ),
)
REPLAY_LANGUAGES = ("en", "es")
DEMO_EFFECTIVE_DEFAULT_TOOL_IDS = ("curated-resources", "knowledge-search")
CONTACT_FOLLOWUPS = {
    "en": {
        "email": "Can you give me the email?",
        "phone": "Can you give me the phone number?",
        "url": "Can you give me the website?",
        "address": "Can you give me the address?",
        "secure_channel": "Can you give me the secure channel?",
    },
    "es": {
        "email": "¿Me puedes dar el email?",
        "phone": "¿Me das el número de teléfono?",
        "url": "¿Me das el sitio web?",
        "address": "¿Me das la dirección?",
        "secure_channel": "¿Me das el canal seguro?",
    },
}
CONTACT_REPLAY_CASES = {
    "en": tuple(CONTACT_FOLLOWUPS["en"].items()),
    # Spanish is an explicit replay dimension, not a claim about any live
    # customer's configured language. Keep the reported exact prompt stable.
    "es": (("email", "¿Me puedes dar el email?"),),
}
INVENTORY_LIMIT = 10
INVENTORY_NAMES = tuple(
    f"Issue 539 Inventory {index:02d}"
    for index in range(1, INVENTORY_LIMIT + 2)
)
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

def derive_ephemeral_admin_pubkey(suffix: str) -> str:
    """Derive a deterministic valid secp256k1 x-only public key marker."""
    field_prime = (1 << 256) - (1 << 32) - 977
    counter = 0
    while True:
        candidate = hashlib.sha256(
            f"issue-539-ephemeral-local-admin-{suffix}-{counter}".encode()
        ).digest()
        x_coordinate = int.from_bytes(candidate, "big")
        if x_coordinate < field_prime:
            y_squared = (pow(x_coordinate, 3, field_prime) + 7) % field_prime
            if y_squared == 0 or pow(y_squared, (field_prime - 1) // 2, field_prime) == 1:
                return candidate.hex()
        counter += 1


def new_fixture_journal(suffix: str) -> dict[str, Any]:
    """Create the cleanup journal before any fixture mutation can occur."""
    ephemeral_pubkey = derive_ephemeral_admin_pubkey(suffix)
    return {
        "suffix": suffix,
        "ephemeral_admin_pubkey": ephemeral_pubkey,
        "admin": None,
        "admin_pubkey": ephemeral_pubkey,
        "owns_admin": None,
        "users": [],
        "configured_type_ids": [],
        "global_tool_ids_original": None,
        "global_tools_restore_required": False,
        "resource_ids": [],
    }


def mint(
    fixtures: dict[str, Any] | None = None,
    *,
    backend_runner=backend_python,
) -> dict[str, Any]:
    """Mint fixtures stepwise, persisting every cleanup identity as soon as known."""
    if fixtures is None:
        fixtures = new_fixture_journal(str(int(time.time() * 1000)))
    suffix = str(fixtures["suffix"])
    ephemeral_pubkey = str(fixtures["ephemeral_admin_pubkey"])
    rows = backend_runner(
        f'''import auth, database, json
admins = database.list_admins()
owns_admin = not admins
ephemeral_pubkey = {ephemeral_pubkey!r}
if owns_admin:
    database.add_admin(ephemeral_pubkey)
    a = database.get_admin_by_pubkey(ephemeral_pubkey)
else:
    a = admins[0]
print(json.dumps({{"admin": auth.create_admin_session_token(a["id"], a["pubkey"], int(a.get("session_nonce", 0) or 0)), "admin_pubkey": a["pubkey"], "owns_admin": owns_admin}}))'''
    )
    admin = json.loads(rows[-1])
    fixtures.update(admin)

    for index, spec in enumerate(PERSONAS):
        entry: dict[str, Any] = {
            "key": spec.key,
            "name": spec.name,
            "user_type_id": None,
            "email": f"issue-539-{spec.key}-{suffix}@example.test",
        }
        fixtures["users"].append(entry)
        if spec.create_user_type:
            type_name = f"{spec.name} {suffix}"
            rows = backend_runner(
                f'''import database, json
type_id = database.create_user_type({type_name!r}, description="Temporary issue #539 local replay persona", display_order={index})
print(json.dumps({{"user_type_id": type_id}}))'''
            )
            entry["user_type_id"] = int(json.loads(rows[-1])["user_type_id"])
        rows = backend_runner(
            f'''import auth, database, json
email = {entry["email"]!r}
user_id = database.create_user(email=email, name={spec.name!r}, user_type_id={entry["user_type_id"]!r})
database.update_user_approval(user_id, True)
print(json.dumps({{"token": auth.create_session_token(user_id, email), "user_id": user_id}}))'''
        )
        entry.update(
            {
                **json.loads(rows[-1]),
            }
        )
    return fixtures

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

def executed_tool_ids(trace: Any) -> list[str]:
    if not isinstance(trace, dict):
        return []
    ids: list[str] = []
    for tool in trace.get("tools", []):
        if not isinstance(tool, dict):
            continue
        tool_id = tool.get("id")
        if isinstance(tool_id, str) and tool.get("status") in ("completed", "succeeded"):
            ids.append(tool_id)
    for delta in trace.get("trace_deltas", []):
        if not isinstance(delta, dict) or delta.get("kind") != "tool_result":
            continue
        tool_name = delta.get("tool_name")
        if isinstance(tool_name, str) and delta.get("status") in ("completed", "succeeded"):
            ids.append(tool_name)
    return sorted(set(ids))


def used_curated_resources(trace: Any) -> bool:
    return any(
        tool_id in {"curated-resources", "find_resources", "Curated Resources"}
        for tool_id in executed_tool_ids(trace)
    )


def tool_lifecycle_events(trace: Any) -> list[dict[str, str]]:
    """Keep lifecycle identity/status only; omit arguments, results, and prompts."""
    if not isinstance(trace, dict):
        return []
    events: list[dict[str, str]] = []
    for tool in trace.get("tools", []):
        if not isinstance(tool, dict):
            continue
        tool_name = tool.get("id") or tool.get("name")
        status = tool.get("status")
        if isinstance(tool_name, str) and isinstance(status, str):
            events.append(
                {"kind": "tool_summary", "tool": tool_name, "status": status}
            )
    lifecycle_kinds = {"tool_call", "tool_result", "tool_retry", "timeout"}
    for delta in trace.get("trace_deltas", []):
        if not isinstance(delta, dict) or delta.get("kind") not in lifecycle_kinds:
            continue
        tool_name = delta.get("tool_name")
        status = delta.get("status")
        if not isinstance(tool_name, str) or not isinstance(status, str):
            continue
        event = {"kind": str(delta["kind"]), "tool": tool_name, "status": status}
        metadata = delta.get("metadata")
        call_id = metadata.get("call_id") if isinstance(metadata, dict) else None
        if isinstance(call_id, str):
            event["call_id"] = call_id
        events.append(event)
    return events


def resource_tool_metadata(trace: Any) -> list[dict[str, Any]]:
    """Allowlist count/pagination metadata from successful Curated Resource Tools."""
    if not isinstance(trace, dict):
        return []
    records: list[dict[str, Any]] = []
    for tool in trace.get("tools", []):
        if not isinstance(tool, dict):
            continue
        tool_name = tool.get("id") or tool.get("name")
        if tool_name not in {"curated-resources", "find_resources", "Curated Resources"}:
            continue
        if tool.get("status") not in {"completed", "succeeded"}:
            continue
        metadata = tool.get("metadata")
        if not isinstance(metadata, dict):
            continue
        returned = metadata.get("returned_count")
        total = metadata.get("total_count")
        has_more = metadata.get("has_more")
        next_offset = metadata.get("next_offset")
        valid_integer = lambda value: isinstance(value, int) and not isinstance(value, bool) and value >= 0
        if not valid_integer(returned) or not valid_integer(total) or not isinstance(has_more, bool):
            continue
        if next_offset is not None and not valid_integer(next_offset):
            continue
        records.append(
            {
                "returned_count": returned,
                "total_count": total,
                "has_more": has_more,
                "next_offset": next_offset,
            }
        )
    return records


def evidence_entry(
    *,
    persona: str,
    case: str,
    answer: str,
    trace: Any,
    passed: bool,
    detail: str,
) -> dict[str, Any]:
    """Return a privacy-safe model-evaluation record without prompts or raw traces."""
    return {
        "persona": persona,
        "case": case,
        "answer": answer,
        "elapsed_ms": trace.get("_evaluation_elapsed_ms") if isinstance(trace, dict) else None,
        "answer_chars": len(answer),
        "answer_words": len(answer.split()),
        "executed_tools": executed_tool_ids(trace),
        "tool_lifecycle": tool_lifecycle_events(trace),
        "resource_tool_metadata": resource_tool_metadata(trace),
        "passed": passed,
        "detail": detail,
    }


def score_contact_turn(
    answer: str,
    trace: Any,
    fresh: str,
    stale_contacts: dict[str, str],
    tool_enabled: bool = True,
) -> tuple[bool, str]:
    fresh_ok = fresh in answer
    stale_ok = all(value not in answer for value in stale_contacts.values())
    tool_ok = used_curated_resources(trace) if tool_enabled else not used_curated_resources(trace)
    answer_ok = fresh_ok if tool_enabled else not fresh_ok
    return answer_ok and stale_ok and tool_ok, f"fresh={fresh_ok} stale_absent={stale_ok} tool={tool_ok}"


def score_inventory_turn(
    answer: str,
    trace: Any,
    *,
    final_name: str,
    continuation: bool,
    previous_answer: str = "",
    previous_trace: Any = None,
) -> tuple[bool, str]:
    metadata = resource_tool_metadata(trace)
    previous_metadata = resource_tool_metadata(previous_trace)
    tool_ok = used_curated_resources(trace) and bool(metadata)
    normalized = answer.casefold()

    def has(*patterns: str) -> bool:
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    no_more_claim = has(
        r"\bno\s+(?:more|additional)\s+(?:matching\s+)?(?:results?|resources?)\b",
        r"\bno\s+additional\s+pages?\b",
        r"\bno\s+remaining\s+(?:matching\s+)?(?:results?|resources?)\b",
        r"\bno\s+quedan\b",
        r"\bno\s+hay\s+m[aá]s\s+(?:resultados?|recursos?)\b",
        r"\bsin\s+m[aá]s\s+(?:resultados?|recursos?)\b",
        r"\bno\s+(?:next|further)\s+pages?\b",
        r"\bno\s+hay\s+(?:otra|siguiente)\s+p[aá]gina\b",
    )
    positive_more = not no_more_claim and has(
        r"\bmore\s+(?:matching\s+)?(?:results?|resources?|pages?)\b",
        r"\badditional\s+(?:matching\s+)?(?:results?|resources?)\b",
        r"\bnext\s+page\b",
        r"\bremaining\s+(?:matching\s+)?(?:results?|resources?)\b",
        r"\bm[aá]s\s+(?:resultados?|recursos?)\b",
        r"\bsiguiente\s+p[aá]gina\b",
        r"\brecursos?\s+restantes\b",
    )
    complete_claim = has(
        r"\ball\b",
        r"\bevery\b",
        r"\bcomplete\b",
        r"\btod[oa]s\b",
        r"\bcomplet[oa]s?\b",
        r"\bconjunto\s+completo\b",
    )
    qualified_or_negated = has(
        r"\bnot\s+all\b",
        r"\bnot\s+(?:a\s+)?complete\b",
        r"\bmay\s+not\s+be\s+(?:all|complete)\b",
        r"\b(?:cannot|can\s+not|can['’]t|unable\s+to)\s+(?:confirm|verify)[^.]{0,80}\b(?:no\s+more|no\s+additional\s+pages?|all|complete)\b",
        r"\bno\s+puedo\s+(?:confirmar|verificar)[^.]{0,80}\b(?:no\s+hay\s+m[aá]s|tod[oa]s|complet[oa])\b",
        r"\bno\s+son\s+tod[oa]s\b",
    )

    def mentioned_names(value: str) -> set[str]:
        return {
            name
            for name in INVENTORY_NAMES
            if re.search(
                rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])",
                value,
                flags=re.IGNORECASE,
            )
        }

    answer_names = mentioned_names(answer)
    previous_names = mentioned_names(previous_answer)
    combined_names = answer_names | previous_names
    expected_names = set(INVENTORY_NAMES)
    expected_first_page = set(INVENTORY_NAMES[:INVENTORY_LIMIT])
    expected_last_page = {final_name}
    count = len(INVENTORY_NAMES)
    scoped = has(
        r"\bmatching\b",
        r"\bsupplied\s+filters?\b",
        r"\bnames?\s+start",
        r"\bcoinciden\b",
        r"\bfiltros?\b",
        r"\bnombres?\s+empiezan\b",
        r"\bque\s+empiezan\b",
    )
    bounded_metadata = {
        "returned_count": INVENTORY_LIMIT,
        "total_count": count,
        "has_more": True,
        "next_offset": INVENTORY_LIMIT,
    }
    terminal_one_metadata = {
        "returned_count": 1,
        "total_count": count,
        "has_more": False,
        "next_offset": None,
    }
    terminal_zero_metadata = {
        "returned_count": 0,
        "total_count": count,
        "has_more": False,
        "next_offset": None,
    }

    def contains_sequence(records: list[dict[str, Any]], expected: list[dict[str, Any]]) -> bool:
        position = 0
        for record in records:
            if position < len(expected) and record == expected[position]:
                position += 1
        return position == len(expected)

    all_metadata = [*previous_metadata, *metadata]
    authoritative_counts = {count}
    authoritative_pairs: set[tuple[int, int]] = set()
    authoritative_offsets: set[int] = set()
    authoritative_remaining_counts: set[int] = set()
    for record in all_metadata:
        authoritative_counts.add(record["returned_count"])
        authoritative_counts.add(record["total_count"])
        authoritative_pairs.add((record["returned_count"], record["total_count"]))
        if record["next_offset"] is not None:
            authoritative_offsets.add(record["next_offset"])
        if record["has_more"]:
            consumed = record["next_offset"]
            if consumed is None:
                consumed = record["returned_count"]
            authoritative_remaining_counts.add(max(record["total_count"] - consumed, 0))
        else:
            authoritative_remaining_counts.add(0)
    if contains_sequence(metadata, [bounded_metadata, terminal_one_metadata]) or contains_sequence(
        previous_metadata, [bounded_metadata, terminal_one_metadata]
    ):
        authoritative_pairs.add((count, count))
    if terminal_zero_metadata in metadata and contains_sequence(
        previous_metadata, [bounded_metadata, terminal_one_metadata]
    ):
        authoritative_offsets.add(count)

    claimed_pairs = {
        (int(returned), int(total))
        for pattern in (
            r"\b(\d+)\s*/\s*(\d+)\b",
            r"\b(\d+)\s+(?:of|de)\s+(\d+)\b",
        )
        for returned, total in re.findall(pattern, normalized)
    }
    claimed_offsets = {
        int(offset)
        for offset in re.findall(
            r"\b(?:next\s+)?(?:offset|desplazamiento)(?:\s+(?:is|es|at|en))?\s*[:=]?\s*(\d+)\b",
            normalized,
        )
    }
    claimed_counts = {
        int(value)
        for value in re.findall(
            r"\b(\d+)\s+(?:matching\s+|coincidentes?\s+)?(?:ready\s+)?(?:resources?|recursos?)\b",
            normalized,
        )
    }
    claimed_remaining_counts = {
        int(value)
        for value in re.findall(
            r"\b(\d+)\s+(?:more\s+(?:matching\s+)?(?:resources?|results?)|(?:recursos?|resultados?)\s+m[aá]s)\b",
            normalized,
        )
    }
    wrong_numeric_claim = (
        not claimed_pairs.issubset(authoritative_pairs)
        or not claimed_offsets.issubset(authoritative_offsets)
        or not claimed_counts.issubset(authoritative_counts)
        or not claimed_remaining_counts.issubset(authoritative_remaining_counts)
    )

    if continuation:
        if previous_names == expected_first_page:
            page_ok = (
                answer_names == expected_last_page
                and no_more_claim
                and bounded_metadata in previous_metadata
                and terminal_one_metadata in metadata
            )
        elif previous_names == expected_names:
            page_ok = (
                not answer_names
                and no_more_claim
                and contains_sequence(
                    previous_metadata,
                    [bounded_metadata, terminal_one_metadata],
                )
                and terminal_zero_metadata in metadata
            )
        else:
            page_ok = False
    else:
        exact_bounded_page = (
            answer_names == expected_first_page
            and final_name not in answer_names
            and positive_more
            and bounded_metadata in metadata
        )
        scoped_complete = (
            answer_names == expected_names
            and final_name in answer_names
            and scoped
            and complete_claim
            and contains_sequence(metadata, [bounded_metadata, terminal_one_metadata])
        )
        page_ok = exact_bounded_page or scoped_complete
    unsupported_complete_claim = complete_claim and combined_names != expected_names
    passed = (
        tool_ok
        and page_ok
        and not unsupported_complete_claim
        and not qualified_or_negated
        and not wrong_numeric_claim
    )
    return passed, f"tool={tool_ok} metadata={len(metadata)} previous_metadata={len(previous_metadata)} page={page_ok} names={len(answer_names)} new_names={len(answer_names - previous_names)} combined_names={len(combined_names)} unsupported_complete={unsupported_complete_claim} qualified={qualified_or_negated} wrong_numeric={wrong_numeric_claim}"


def expected_case_count(
    persona_filter: str | None,
    inventory_only: bool,
    contact_only: bool,
    language_filter: str | None = None,
) -> int:
    selected = [
        persona for persona in PERSONAS if persona_filter is None or persona.key == persona_filter
    ]
    languages = [
        language
        for language in REPLAY_LANGUAGES
        if language_filter is None or language == language_filter
    ]
    contact_cases = 0 if inventory_only else len(selected) * sum(
        1 + len(CONTACT_REPLAY_CASES[language]) for language in languages
    )
    inventory_cases = 0 if contact_only else len(selected) * 2
    disabled_control = (
        1
        if not inventory_only
        and any(persona.key == "generic_user" for persona in selected)
        else 0
    )
    return contact_cases + inventory_cases + disabled_control


def evaluation_summary(
    *,
    expected_case_count: int,
    evidence: list[dict[str, Any]],
    failures: int,
    cleanup_failures: int,
    fatal: bool,
) -> dict[str, Any]:
    completed = len(evidence)
    passed_cases = sum(item.get("passed") is True for item in evidence)
    failed_cases = completed - passed_cases
    passed = (
        not fatal
        and failures == 0
        and cleanup_failures == 0
        and completed == expected_case_count
        and failed_cases == 0
    )
    status = "fatal" if fatal else ("passed" if passed else "failed")
    return {
        "status": status,
        "passed": passed,
        "fatal": fatal,
        "failure_count": failures,
        "cleanup_failure_count": cleanup_failures,
        "expected_case_count": expected_case_count,
        "completed_case_count": completed,
        "passed_case_count": passed_cases,
        "failed_case_count": failed_cases,
    }


def persist_evaluation_evidence(
    path: Path,
    *,
    payload: dict[str, Any],
    expected_case_count: int,
    evidence: list[dict[str, Any]],
    failures: int,
    cleanup_failures: int,
    fatal: bool,
) -> tuple[dict[str, Any], int, Exception | None]:
    summary = evaluation_summary(
        expected_case_count=expected_case_count,
        evidence=evidence,
        failures=failures,
        cleanup_failures=cleanup_failures,
        fatal=fatal,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema": "issue-539-model-eval-evidence-v2",
                    **payload,
                    **summary,
                    "cases": evidence,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return summary, cleanup_failures, None
    except Exception as exc:
        cleanup_failures += 1
        summary = evaluation_summary(
            expected_case_count=expected_case_count,
            evidence=evidence,
            failures=failures,
            cleanup_failures=cleanup_failures,
            fatal=fatal,
        )
        return summary, cleanup_failures, exc


def audit_contains_fine_timing(value: Any) -> bool:
    rendered = json.dumps(value, sort_keys=True, ensure_ascii=False).casefold()
    return any(
        phase in rendered
        for phase in (
            "tool_planning_model_duration",
            "final_answer_model_duration",
            "final_answer_response_header_wait",
            "final_answer_first_provider_event_wait",
            "tool_execution",
            "resource_directory_lookup",
            "retrieval",
            "retry_delay",
            "total_turn",
        )
    )

def run_turn(base: str, token: str, payload: dict[str, Any], stream: bool, timeout: float) -> tuple[str, Any, str | None]:
    started = time.perf_counter()
    response = req(base, token, "POST", "/llm/chat/stream" if stream else "/llm/chat", payload, timeout)
    if response.status_code != 200: raise RuntimeError(f"chat returned {response.status_code}: {response.text[:400]}")
    if not stream:
        body = response.json(); trace = dict(body.get("trace") or body); trace["_evaluation_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1); return answer_json(body), trace, body.get("session_id")
    response.encoding = "utf-8"
    events = parse_sse(response.text)
    answer = "".join(str(e["data"].get("delta") or "") for e in events if e["event"] == "answer_delta").strip()
    trace = next((e["data"].get("trace", {}) for e in events if e["event"] == "trace_final"), {})
    trace = dict(trace); trace["_evaluation_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    sid = next((e["data"].get("session_id") for e in events if e["data"].get("session_id")), None)
    return answer, trace, sid

def resource(
    base: str,
    token: str,
    rid: str,
    contact: dict[str, str],
    method: str = "POST",
    *,
    name: str = ORG_NAME,
    display_order: int = 0,
) -> None:
    body = {
        "name": name,
        "kind": "organization",
        "description": "Synthetic issue #539 evaluation fixture; do not contact.",
        "pointers": [
            {"type": pointer_type, "value": value}
            for pointer_type, value in contact.items()
        ],
        "languages": ["en", "es"],
        "regions": [{"level": "country", "code": "MX"}],
        "tags": ["legal"],
        "provenance": {"vetted_by": "issue-539-eval"},
        "verified": True,
        "display_order": display_order,
    }
    if method == "POST":
        body["resource_id"] = rid
    path = "/admin/resources" if method == "POST" else f"/admin/resources/{rid}"
    r = req(base, token, method, path, body)
    if r.status_code not in ({200, 201} if method == "POST" else {200}): raise RuntimeError(f"resource {method}: {r.status_code} {r.text[:400]}")


def configure_persona_tools(
    base: str,
    admin_token: str,
    user_type_id: int | None,
    tool_ids: list[str] | None = None,
    *,
    journal: dict[str, Any] | None = None,
) -> None:
    if tool_ids is None:
        tool_ids = list(DEMO_EFFECTIVE_DEFAULT_TOOL_IDS)
    if user_type_id is None:
        if journal is None:
            raise ValueError("global Tool configuration requires a cleanup journal")
        if not journal.get("global_tools_restore_required"):
            original = req(
                base,
                admin_token,
                "GET",
                "/admin/ai-config/user_default_tool_ids",
                timeout=30,
            )
            if original.status_code != 200:
                raise RuntimeError(
                    f"read global tools: {original.status_code} {original.text[:300]}"
                )
            original_value = original.json().get("value")
            if not isinstance(original_value, str):
                raise RuntimeError("global Tool default did not return a string value")
            journal["global_tool_ids_original"] = original_value
            # Mark restoration required before the mutating request so a lost
            # response cannot strand the global configuration.
            journal["global_tools_restore_required"] = True
        path = "/admin/ai-config/user_default_tool_ids"
        label = "global tools"
    else:
        path = f"/admin/ai-config/user-type/{user_type_id}/user_default_tool_ids"
        label = f"User Type {user_type_id} tools"
    response = req(
        base,
        admin_token,
        "PUT",
        path,
        {"value": json.dumps(tool_ids, separators=(",", ":"))},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"configure {label}: {response.status_code} {response.text[:300]}")


def cleanup_persona_tools(base: str, admin_token: str, user_type_id: int) -> bool:
    response = req(
        base,
        admin_token,
        "DELETE",
        f"/admin/ai-config/user-type/{user_type_id}/user_default_tool_ids",
        timeout=30,
    )
    return response.status_code == 200


def restore_global_tools(
    base: str,
    admin_token: str,
    journal: dict[str, Any],
) -> bool:
    if not journal.get("global_tools_restore_required"):
        return True
    original = journal.get("global_tool_ids_original")
    if not isinstance(original, str):
        return False
    response = req(
        base,
        admin_token,
        "PUT",
        "/admin/ai-config/user_default_tool_ids",
        {"value": original},
        timeout=30,
    )
    if response.status_code == 200:
        journal["global_tools_restore_required"] = False
    return response.status_code == 200


def persona_tools_effective(base: str, user_token: str, user_type_id: int | None) -> bool:
    path = (
        "/session-defaults"
        if user_type_id is None
        else f"/session-defaults?user_type_id={user_type_id}"
    )
    response = req(
        base,
        user_token,
        "GET",
        path,
        timeout=30,
    )
    if response.status_code != 200:
        return False
    try:
        default_tool_ids = set(response.json().get("default_tool_ids", []))
        # The server correctly omits Knowledge Search when this synthetic replay
        # has no active documents. Curated Resources must still be effective.
        return "curated-resources" in default_tool_ids
    except (AttributeError, TypeError, ValueError):
        return False


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
    if deleted.status_code != 404 and not resource_delete_ok(deleted.status_code, body):
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


def reconcile_fixture_journal(fixtures: dict[str, Any]) -> None:
    """Recover exact marker-owned IDs if a create succeeded before its call failed."""
    suffix = str(fixtures["suffix"])
    rows = backend_python(f'''import database, json
suffix = {suffix!r}
users = []
for user in database.list_users():
    email = str(user.get("email") or "")
    if email.startswith("issue-539-") and email.endswith("-" + suffix + "@example.test"):
        users.append({{"user_id": user["id"], "user_type_id": user.get("user_type_id"), "email": email}})
types = [{{"user_type_id": item["id"]}} for item in database.list_user_types() if str(item.get("name") or "").endswith(" " + suffix) and item.get("description") == "Temporary issue #539 local replay persona"]
print(json.dumps({{"users": users, "types": types}}))''')
    recovered = json.loads(rows[-1]) if rows else {"users": [], "types": []}
    by_type = {
        int(item["user_type_id"]): item
        for item in fixtures["users"]
        if item.get("user_type_id") is not None
    }
    for item in recovered.get("types", []):
        type_id = int(item["user_type_id"])
        if type_id not in by_type:
            entry = {"key": f"recovered_type_{type_id}", "user_type_id": type_id}
            fixtures["users"].append(entry)
            by_type[type_id] = entry
    for item in recovered.get("users", []):
        raw_type_id = item.get("user_type_id")
        if raw_type_id is None:
            entry = next(
                (
                    candidate
                    for candidate in fixtures["users"]
                    if candidate.get("email") == item.get("email")
                ),
                None,
            )
            if entry is None:
                entry = {
                    "key": "recovered_global_user",
                    "email": item.get("email"),
                    "user_type_id": None,
                }
        else:
            type_id = int(raw_type_id)
            entry = by_type.setdefault(
                type_id,
                {"key": f"recovered_type_{type_id}", "user_type_id": type_id},
            )
        if entry not in fixtures["users"]:
            fixtures["users"].append(entry)
        entry["user_id"] = int(item["user_id"])


def cleanup_personas(users: list[dict[str, Any]], suffix: str | None = None) -> bool:
    user_ids = sorted({int(user["user_id"]) for user in users if user.get("user_id") is not None})
    type_ids = sorted({int(user["user_type_id"]) for user in users if user.get("user_type_id") is not None})
    rows = backend_python(f"""import database, json
from pathlib import Path
user_ids = {user_ids!r}
type_ids = {type_ids!r}
suffix = {suffix!r}
if suffix:
    for user in database.list_users():
        email = str(user.get("email") or "")
        if email.startswith("issue-539-") and email.endswith("-" + suffix + "@example.test"):
            user_ids.append(int(user["id"]))
    for item in database.list_user_types():
        if str(item.get("name") or "").endswith(" " + suffix) and item.get("description") == "Temporary issue #539 local replay persona":
            type_ids.append(int(item["id"]))
user_ids = sorted(set(user_ids))
type_ids = sorted(set(type_ids))
with database.get_cursor() as cursor:
    placeholders = ",".join("?" for _ in user_ids) or "NULL"
    cursor.execute("SELECT transcript_path FROM session_logs WHERE subject_user_id IN (" + placeholders + ")", user_ids)
    transcript_paths = [row[0] for row in cursor.fetchall() if row[0]]
    cursor.execute("DELETE FROM session_logs WHERE subject_user_id IN (" + placeholders + ")", user_ids)
for value in transcript_paths:
    path = Path(value)
    if path.is_file():
        path.unlink()
deleted_users = [database.delete_user(user_id) for user_id in user_ids if database.get_user(user_id) is not None]
deleted_types = [database.delete_user_type(type_id) for type_id in type_ids if database.get_user_type(type_id) is not None]
print(json.dumps({{"deleted_users": deleted_users, "deleted_types": deleted_types, "deleted_transcripts": len(transcript_paths), "users_exist": [database.get_user(user_id) is not None for user_id in user_ids], "types_exist": [database.get_user_type(type_id) is not None for type_id in type_ids]}}))
""")
    result = json.loads(rows[-1]) if rows else {}
    return (
        all(result.get("deleted_users", []))
        and all(result.get("deleted_types", []))
        and not any(result.get("users_exist", [True]))
        and not any(result.get("types_exist", [True]))
    )


def sage_identity_cleanup_sql(users: list[dict[str, Any]]) -> str:
    external_ids = ",".join(
        f"'{int(user['user_id'])}'" for user in users if user.get("user_id") is not None
    )
    if not external_ids:
        return "SELECT 0;"
    return (
        "DELETE FROM external_identities "
        "WHERE identity_type = 'user' AND external_id IN ("
        + external_ids
        + "); SELECT count(*) FROM external_identities "
        "WHERE identity_type = 'user' AND external_id IN ("
        + external_ids
        + ");"
    )


def cleanup_sage_identities(users: list[dict[str, Any]]) -> bool:
    if not any(user.get("user_id") is not None for user in users):
        return True
    process = subprocess.run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "sage",
            "-d",
            "sage",
            "-Atc",
            sage_identity_cleanup_sql(users),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )
    if process.returncode:
        return False
    lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    return bool(lines) and lines[-1] == "0"


def cleanup_admin(
    pubkey: str,
    owned: bool | None,
    *,
    backend_runner=backend_python,
) -> bool:
    if owned is False:
        return True
    rows = backend_runner(
        f"import database, json; existed = database.get_admin_by_pubkey({pubkey!r}) is not None; removed = database.remove_admin({pubkey!r}) if existed else False; print(json.dumps({{'existed': existed, 'removed': removed, 'exists': database.get_admin_by_pubkey({pubkey!r}) is not None}}))"
    )
    result = json.loads(rows[-1]) if rows else {}
    return result.get("exists") is False and (
        result.get("existed") is False or result.get("removed") is True
    )


def initial_all_contacts_message(language: str) -> str:
    if language == "es":
        return (
            f"{ORG_NAME} está en México y ofrece ayuda legal. "
            "Dame su email, teléfono, sitio web, dirección y canal seguro. Responde en español."
        )
    return (
        f"{ORG_NAME} is in Mexico and provides legal help. "
        "Give me its email, phone, website, address, and secure channel. Answer in English."
    )


def exit_code_for_summary(summary: dict[str, Any]) -> int:
    if summary.get("fatal") is True:
        return 2
    return 0 if summary.get("passed") is True else 1


def validate_loopback_api_base(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--api-base must be an HTTP(S) loopback origin")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("--api-base must not contain credentials")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("--api-base is restricted to localhost, 127.0.0.1, or [::1]")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid --api-base port: {exc}") from exc
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("--api-base must be an origin without a path, query, or fragment")
    return f"{parsed.scheme.casefold()}://{parsed.netloc}".rstrip("/")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--api-base", default="http://localhost:18000"); ap.add_argument("--timeout", type=float, default=180); ap.add_argument("--persona", choices=[persona.key for persona in PERSONAS]); ap.add_argument("--language", choices=REPLAY_LANGUAGES); mode = ap.add_mutually_exclusive_group(); mode.add_argument("--inventory-only", action="store_true"); mode.add_argument("--contact-only", action="store_true"); ap.add_argument("--evidence-file", type=Path, default=Path("/tmp/issue539-model-eval-evidence.json")); args = ap.parse_args()
    try:
        args.api_base = validate_loopback_api_base(args.api_base)
    except ValueError as exc:
        ap.error(str(exc))
    stale = {"email": "stale-539@example.test", "phone": "+52-555-0100", "url": "https://stale-539.example.test", "address": "Stale issue 539 office, Mexico", "secure_channel": "stale-secure-539"}
    fresh = {"email": "fresh-539@example.test", "phone": "+52-555-0199", "url": "https://fresh-539.example.test", "address": "Fresh issue 539 office, Mexico", "secure_channel": "fresh-secure-539"}
    sessions: list[tuple[str, str]] = []
    suffix = str(int(time.time() * 1000))
    rid = f"issue-539-contact-{suffix}"
    inventory_ids = [f"issue-539-inventory-{index}-{suffix}" for index in range(len(INVENTORY_NAMES))]
    fixtures = new_fixture_journal(suffix)
    fixtures["resource_ids"] = [rid, *([] if args.contact_only else inventory_ids)]
    expected_cases = expected_case_count(
        args.persona,
        args.inventory_only,
        args.contact_only,
        language_filter=args.language,
    )
    failures = 0
    cleanup_failures = 0
    fatal = False
    fatal_error_type: str | None = None
    evidence: list[dict[str, Any]] = []
    try:
        mint(fixtures)
        for persona in fixtures["users"]:
            user_type_id = persona.get("user_type_id")
            if user_type_id is not None:
                # Journal the override target before mutation so a lost response
                # is still cleanup-safe.
                fixtures["configured_type_ids"].append(int(user_type_id))
            configure_persona_tools(
                args.api_base,
                fixtures["admin"],
                None if user_type_id is None else int(user_type_id),
                journal=fixtures,
            )
            effective = persona_tools_effective(
                args.api_base,
                str(persona["token"]),
                None if user_type_id is None else int(user_type_id),
            )
            failures += 0 if expect(f"{persona['key']}: effective Curated Resources enabled", effective) else 1
        resource(args.api_base, fixtures["admin"], rid, stale)
        if not args.contact_only:
            for index, inventory_id in enumerate(inventory_ids):
                resource(
                    args.api_base,
                    fixtures["admin"],
                    inventory_id,
                    {"email": f"inventory-{index}@example.test"},
                    name=INVENTORY_NAMES[index],
                    display_order=index,
                )

        replay_users = [
            persona
            for persona in fixtures["users"]
            if args.persona is None or persona["key"] == args.persona
        ]
        for persona_index, persona in enumerate(replay_users):
            key = str(persona["key"])
            token = str(persona["token"])
            if not args.inventory_only:
                replay_languages = [
                    language
                    for language in REPLAY_LANGUAGES
                    if args.language is None or language == args.language
                ]
                for language_index, language in enumerate(replay_languages):
                    resource(args.api_base, fixtures["admin"], rid, stale, "PUT")
                    sid = str(uuid.uuid4())
                    sessions.append((token, sid))
                    first, first_trace, returned_sid = run_turn(
                        args.api_base,
                        token,
                        {"message": initial_all_contacts_message(language), "tools": ["curated-resources"], "session_id": sid},
                        bool((persona_index + language_index) % 2),
                        args.timeout,
                    )
                    if returned_sid != sid:
                        raise RuntimeError(f"initial session id mismatch: expected {sid}, got {returned_sid}")
                    initial_ok = all(value in first for value in stale.values())
                    failures += 0 if expect(f"{key}/{language}: stale contact authority", initial_ok, first[:400]) else 1
                    evidence.append(
                        evidence_entry(
                            persona=key,
                            case=f"{language}_stale_contact_authority",
                            answer=first,
                            trace=first_trace,
                            passed=initial_ok,
                            detail="all_stale_contacts_present=" + str(initial_ok),
                        )
                    )
                    resource(args.api_base, fixtures["admin"], rid, fresh, "PUT")
                    for contact_index, (contact_key, followup) in enumerate(CONTACT_REPLAY_CASES[language]):
                        answer, trace, followup_sid = run_turn(
                            args.api_base,
                            token,
                            {"message": followup, "tools": ["curated-resources"], "session_id": sid},
                            bool((persona_index + language_index + contact_index) % 2),
                            args.timeout,
                        )
                        if followup_sid != sid:
                            raise RuntimeError(f"follow-up session id mismatch: expected {sid}, got {followup_sid}")
                        ok, detail = score_contact_turn(answer, trace, fresh[contact_key], stale)
                        failures += 0 if expect(f"{key}/{language}: fresh {contact_key}", ok, f"{detail}; answer={answer[:300]}") else 1
                        evidence.append(
                            evidence_entry(
                                persona=key,
                                case=f"{language}_fresh_{contact_key}",
                                answer=answer,
                                trace=trace,
                                passed=ok,
                                detail=detail,
                            )
                        )

            if args.contact_only:
                continue

            inventory_sid = str(uuid.uuid4())
            sessions.append((token, inventory_sid))
            inventory_language = args.language or "en"
            inventory_prompt = (
                "Lista los recursos curados listos cuyos nombres empiezan con 'Issue 539 Inventory'. "
                "Esta es una solicitud de inventario: no filtres por tipo de ayuda y no supongas que la primera página limitada está completa. Responde en español."
                if inventory_language == "es"
                else "List the ready Curated Resources whose names start with 'Issue 539 Inventory'. This is an inventory request: do not filter by help type and do not assume the first bounded page is complete."
            )
            first_page, first_trace, inventory_returned_sid = run_turn(
                args.api_base,
                token,
                {"message": inventory_prompt, "tools": ["curated-resources"], "session_id": inventory_sid},
                bool(persona_index % 2),
                args.timeout,
            )
            if inventory_returned_sid != inventory_sid:
                raise RuntimeError(f"inventory session id mismatch: expected {inventory_sid}, got {inventory_returned_sid}")
            ok, detail = score_inventory_turn(first_page, first_trace, final_name=INVENTORY_NAMES[-1], continuation=False)
            failures += 0 if expect(f"{key}: bounded inventory", ok, f"{detail}; answer={first_page[:500]}") else 1
            evidence.append(
                evidence_entry(
                    persona=key,
                    case="bounded_inventory",
                    answer=first_page,
                    trace=first_trace,
                    passed=ok,
                    detail=detail,
                )
            )
            continuation_prompt = "Muestra la siguiente página de esos recursos coincidentes." if inventory_language == "es" else "Show the next page of those matching resources."
            next_page, next_trace, continuation_sid = run_turn(
                args.api_base,
                token,
                {"message": continuation_prompt, "tools": ["curated-resources"], "session_id": inventory_sid},
                not bool(persona_index % 2),
                args.timeout,
            )
            if continuation_sid != inventory_sid:
                raise RuntimeError(f"continuation session id mismatch: expected {inventory_sid}, got {continuation_sid}")
            ok, detail = score_inventory_turn(next_page, next_trace, final_name=INVENTORY_NAMES[-1], continuation=True, previous_answer=first_page, previous_trace=first_trace)
            failures += 0 if expect(f"{key}: inventory continuation", ok, f"{detail}; answer={next_page[:500]}") else 1
            evidence.append(
                evidence_entry(
                    persona=key,
                    case="inventory_continuation",
                    answer=next_page,
                    trace=next_trace,
                    passed=ok,
                    detail=detail,
                )
            )

        if not args.inventory_only and (args.persona is None or args.persona == "generic_user"):
            generic = fixtures["users"][0]
            configure_persona_tools(
                args.api_base,
                fixtures["admin"],
                None,
                [],
                journal=fixtures,
            )
            disabled_effective = not persona_tools_effective(
                args.api_base,
                str(generic["token"]),
                None,
            )
            failures += 0 if expect("disabled tools: effective policy is disabled", disabled_effective) else 1
            disabled_sid = str(uuid.uuid4())
            sessions.append((str(generic["token"]), disabled_sid))
            answer, trace, returned_disabled_sid = run_turn(args.api_base, str(generic["token"]), {"message": "Do not use tools. What is the email address?", "tools": [], "session_id": disabled_sid}, False, args.timeout)
            if returned_disabled_sid != disabled_sid:
                raise RuntimeError(f"disabled session id mismatch: expected {disabled_sid}, got {returned_disabled_sid}")
            ok, detail = score_contact_turn(answer, trace, fresh["email"], stale, False); failures += 0 if expect("disabled tools: no invented contact", ok, detail) else 1
            evidence.append(
                evidence_entry(
                    persona="generic_user",
                    case="disabled_tools_no_invented_contact",
                    answer=answer,
                    trace=trace,
                    passed=ok,
                    detail=detail,
                )
            )
        audit = req(args.api_base, fixtures["admin"], "GET", "/admin/deployment/audit-log?limit=500", timeout=30)
        if audit.status_code != 200:
            raise RuntimeError(f"audit lookup returned {audit.status_code}: {audit.text[:300]}")
        failures += 0 if expect("Audit Log excludes fine Conversation timing", not audit_contains_fine_timing(audit.json())) else 1
    except Exception as exc:
        print(f"[ERROR] {exc}"); fatal = True; fatal_error_type = type(exc).__name__
    finally:
        if fixtures.get("admin"):
            for token, sid in sessions:
                try:
                    if not cleanup_session(args.api_base, token, sid):
                        cleanup_failures += 1; print(f"[FAIL] cleanup session {sid}")
                except Exception as exc:
                    cleanup_failures += 1; print(f"[FAIL] cleanup session {sid}: {exc}")
            for resource_id in fixtures["resource_ids"]:
                try:
                    if not cleanup_resource(args.api_base, fixtures["admin"], resource_id):
                        cleanup_failures += 1; print(f"[FAIL] cleanup resource {resource_id}")
                except Exception as exc:
                    cleanup_failures += 1; print(f"[FAIL] cleanup resource {resource_id}: {exc}")
            for user_type_id in fixtures["configured_type_ids"]:
                try:
                    if not cleanup_persona_tools(
                        args.api_base,
                        fixtures["admin"],
                        int(user_type_id),
                    ):
                        cleanup_failures += 1; print(f"[FAIL] cleanup User Type policy {user_type_id}")
                except Exception as exc:
                    cleanup_failures += 1; print(f"[FAIL] cleanup User Type policy {user_type_id}: {exc}")
            try:
                if not restore_global_tools(args.api_base, fixtures["admin"], fixtures):
                    cleanup_failures += 1; print("[FAIL] restore global Tool policy")
            except Exception as exc:
                cleanup_failures += 1; print(f"[FAIL] restore global Tool policy: {exc}")
        try:
            reconcile_fixture_journal(fixtures)
        except Exception as exc:
            cleanup_failures += 1; print(f"[FAIL] reconcile fixture journal: {exc}")
        try:
            if not cleanup_sage_identities(fixtures["users"]):
                cleanup_failures += 1; print("[FAIL] cleanup Sage identities verification")
        except Exception as exc:
            cleanup_failures += 1; print(f"[FAIL] cleanup Sage identities: {exc}")
        try:
            if not cleanup_personas(fixtures["users"], str(fixtures["suffix"])):
                cleanup_failures += 1; print("[FAIL] cleanup personas verification")
        except Exception as exc:
            cleanup_failures += 1; print(f"[FAIL] cleanup personas: {exc}")
        try:
            if not cleanup_admin(
                str(fixtures["ephemeral_admin_pubkey"]),
                fixtures.get("owns_admin"),
            ):
                cleanup_failures += 1; print("[FAIL] cleanup ephemeral admin verification")
        except Exception as exc:
            cleanup_failures += 1; print(f"[FAIL] cleanup ephemeral admin: {exc}")
        summary, cleanup_failures, evidence_error = persist_evaluation_evidence(
            args.evidence_file,
            payload={
                "fatal_error_type": fatal_error_type,
                "persona_filter": args.persona,
                "inventory_only": args.inventory_only,
                "contact_only": args.contact_only,
                "language_filter": args.language,
                "inventory_fixture_count": len(INVENTORY_NAMES),
            },
            expected_case_count=expected_cases,
            evidence=evidence,
            failures=failures,
            cleanup_failures=cleanup_failures,
            fatal=fatal,
        )
        if evidence_error is None:
            print(f"[EVIDENCE] {args.evidence_file}")
        else:
            print(f"[FAIL] write evidence: {evidence_error}")
    replay_count = 1 if args.persona else len(PERSONAS)
    selected_languages = [language for language in REPLAY_LANGUAGES if args.language is None or language == args.language]
    contact_count = 0 if args.inventory_only else sum(len(CONTACT_REPLAY_CASES[language]) for language in selected_languages)
    inventory_pages = 0 if args.contact_only else 2
    print(f"[SUMMARY] status={summary['status']} passed={summary['passed']} personas={replay_count} contact_modalities={contact_count} inventory_pages={inventory_pages} expected_cases={summary['expected_case_count']} completed_cases={summary['completed_case_count']} failures={failures} cleanup_failures={cleanup_failures}")
    return exit_code_for_summary(summary)

if __name__ == "__main__": raise SystemExit(main())
