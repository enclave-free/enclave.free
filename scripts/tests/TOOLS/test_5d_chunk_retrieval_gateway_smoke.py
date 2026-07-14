#!/usr/bin/env python3
"""
Test 5D: Chunk Retrieval Gateway Smoke

Seeds one current Document Library chunk in the running Docker stack, then
verifies the public /query route can retrieve it as selected Required Context
through Sage and expose source metadata in the response.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import requests


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
QUESTION = "What phrase marks the gateway retrieval smoke fixture?"
EXPECTED_PHRASE = "crimson context handshake"


def run_backend_python(script: str, timeout: int = 120) -> dict[str, Any]:
    result = subprocess.run(
        [*COMPOSE_ARGS, "exec", "-T", "core-backend", "python", "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"core-backend python failed: {result.stderr.strip()} {result.stdout[:400]}")
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"core-backend python did not return JSON: {result.stdout[:400]}") from exc


def run_sage_postgres(sql: str, *, tuples_only: bool = False) -> str:
    command = [
        *COMPOSE_ARGS,
        "exec",
        "-T",
        "postgres",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "sage",
        "-d",
        "sage",
    ]
    if tuples_only:
        command.extend(["-t", "-A"])
    command.extend(["-c", sql])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Sage Postgres command failed: {result.stderr.strip()}")
    return result.stdout.strip()


def read_sage_knowledge_scope(user_type_id: int) -> dict[str, str] | None:
    rendered = run_sage_postgres(
        "SELECT json_build_object("
        "'id', id::text, 'value', value, 'updated_at', updated_at::text)::text "
        "FROM ai_config_user_type_overrides "
        f"WHERE ai_config_key = 'knowledge_source_default' AND user_type_id = {user_type_id};",
        tuples_only=True,
    )
    return json.loads(rendered) if rendered else None


def configure_sage_knowledge_scope(user_type_id: int) -> dict[str, str] | None:
    previous = read_sage_knowledge_scope(user_type_id)
    override_id = uuid.uuid4()
    sql = f"""
INSERT INTO ai_config_user_type_overrides (
    id, ai_config_key, user_type_id, value, updated_at
) VALUES (
    '{override_id}', 'knowledge_source_default', {user_type_id}, 'selected', NOW()
)
ON CONFLICT (ai_config_key, user_type_id) DO UPDATE SET
    value = EXCLUDED.value,
    updated_at = NOW();
"""
    run_sage_postgres(sql)
    return previous


def cleanup_sage_knowledge_scope(
    user_type_id: int | None,
    previous: dict[str, str] | None,
) -> None:
    if user_type_id is None:
        return
    if previous is None:
        sql = (
            "DELETE FROM ai_config_user_type_overrides "
            f"WHERE ai_config_key = 'knowledge_source_default' AND user_type_id = {user_type_id};"
        )
    else:
        escaped_value = str(previous.get("value") or "").replace("'", "''")
        escaped_updated_at = str(previous.get("updated_at") or "").replace("'", "''")
        if not escaped_updated_at:
            raise RuntimeError("previous Sage knowledge policy is missing updated_at")
        sql = (
            "UPDATE ai_config_user_type_overrides "
            f"SET value = '{escaped_value}', updated_at = '{escaped_updated_at}' "
            "WHERE ai_config_key = 'knowledge_source_default' "
            f"AND user_type_id = {user_type_id};"
        )
    run_sage_postgres(sql)


def cleanup_sage_ephemeral_identity(user_id: int) -> None:
    memory_user_id = f"user:{user_id}"
    sql = f"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM web_sessions
        WHERE owner_type = 'user' AND owner_id = '{user_id}'
    ) OR EXISTS (
        SELECT 1 FROM messages WHERE user_id = '{memory_user_id}'
    ) THEN
        RAISE EXCEPTION 'query session lifecycle cleanup is incomplete for user {user_id}';
    END IF;
END $$;
DELETE FROM external_identities
WHERE identity_type = 'user' AND external_id = '{user_id}';
"""
    run_sage_postgres(sql)


def read_core_knowledge_scope(user_type_id: int) -> dict[str, Any] | None:
    script = f"""
import json
import database
database.init_schema()
print(json.dumps({{
    "override": database.get_ai_config_override(
        "knowledge_source_default",
        {user_type_id},
    )
}}))
"""
    return run_backend_python(script, timeout=30).get("override")


def seed_user_token() -> dict[str, Any]:
    script = """
import json
import time

import auth
import database

database.init_schema()
suffix = str(int(time.time() * 1000))
email = "gateway-smoke-" + suffix + "@example.test"
user_type_id = database.create_user_type("Gateway Smoke Users " + suffix, description="Temporary smoke-test users")
with database.get_write_cursor() as cursor:
    cursor.execute(
        "INSERT INTO users (email, name, user_type_id, approved, created_at) VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)",
        (email, "Gateway Smoke User", user_type_id),
    )
    user_id = cursor.lastrowid
token = auth.create_session_token(user_id, email)
print(json.dumps({"token": token, "user_id": user_id, "user_type_id": user_type_id}))
"""
    payload = run_backend_python(script, timeout=60)
    token = str(payload.get("token") or "")
    if not token:
        raise RuntimeError("failed to mint user token")
    return payload


def seed_chunk(user_type_id: int | None) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:12]
    job_id = f"gateway-smoke-{suffix}"
    chunk_id = f"{job_id}_chunk_0000"
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"chunk:{chunk_id}"))
    source_file = f"Gateway Retrieval Smoke {suffix}.md"
    previous_core_scope = (
        read_core_knowledge_scope(user_type_id) if user_type_id is not None else None
    )
    previous_sage_scope = (
        read_sage_knowledge_scope(user_type_id) if user_type_id is not None else None
    )
    seed: dict[str, Any] = {
        "job_id": job_id,
        "chunk_id": chunk_id,
        "point_id": point_id,
        "source_file": source_file,
        "file_path": None,
        "user_type_id": user_type_id,
        "owns_user_fixture": False,
        "previous_core_knowledge_scope": previous_core_scope,
        "previous_sage_knowledge_scope": previous_sage_scope,
    }
    script = f"""
import json
import os
from pathlib import Path

from qdrant_client.models import PointStruct

import database
import ingest_db
import store

job_id = {job_id!r}
chunk_id = {chunk_id!r}
point_id = {point_id!r}
source_file = {source_file!r}
text = "Gateway retrieval smoke fixture. The required marker phrase is: {EXPECTED_PHRASE}."
user_type_id = {repr(user_type_id)}
upload_dir = Path(os.getenv("UPLOADS_DIR", "/uploads"))
upload_dir.mkdir(parents=True, exist_ok=True)
file_path = upload_dir / source_file
file_path.write_text(text, encoding="utf-8")

database.init_schema()
ingest_db.init_ingest_schema()
ingest_db.create_job(
    job_id=job_id,
    filename=source_file,
    file_path=str(file_path),
    ontology_id="default",
    canonical_name=source_file,
    is_current=True,
)
ingest_db.update_job_status(job_id, "completed", total_chunks=1, processed_chunks=1)
database.upsert_document_defaults(job_id, is_available=True, is_default_active=False, display_order=0)
if user_type_id is not None:
    database.upsert_document_defaults_override(
        job_id,
        user_type_id,
        is_available=True,
        is_default_active=True,
        changed_by="",
    )
    database.upsert_ai_config_override(
        "knowledge_source_default",
        user_type_id,
        "selected",
        changed_by="",
    )
ingest_db.upsert_retrieval_chunk(
    chunk_id=chunk_id,
    job_id=job_id,
    chunk_index=0,
    source_file=source_file,
    text=text,
)

store.ensure_qdrant_collection()
vector = store.embed_texts(["query: {QUESTION}"])[0]
store.get_qdrant_client().upsert(
    collection_name=store.COLLECTION_NAME,
    points=[
        PointStruct(
            id=point_id,
            vector=vector,
            payload={{
                "type": "chunk",
                "chunk_id": chunk_id,
                "job_id": job_id,
                "source_file": source_file,
                "content_ref": "retrieval_chunk:" + chunk_id,
            }},
        )
    ],
)

print(json.dumps({{
    "job_id": job_id,
    "chunk_id": chunk_id,
    "point_id": point_id,
    "source_file": source_file,
    "file_path": str(file_path),
}}))
"""
    try:
        seed.update(run_backend_python(script, timeout=180))
        if user_type_id is not None:
            seed["previous_sage_knowledge_scope"] = configure_sage_knowledge_scope(user_type_id)
    except Exception:
        cleanup_seed(seed)
        raise
    return seed


def cleanup_seed(seed: dict[str, Any]) -> None:
    script = f"""
import json
import os
from pathlib import Path

from qdrant_client.models import PointIdsList

import database
import ingest_db
import store

job_id = {repr(seed.get("job_id"))}
point_id = {repr(seed.get("point_id"))}
user_id = {repr(seed.get("user_id"))}
user_type_id = {repr(seed.get("user_type_id"))}
owns_user_fixture = __DELETE_OWNED_PRINCIPALS__
file_path = {repr(seed.get("file_path"))}
source_file = {repr(seed.get("source_file"))}
previous_core_scope = {repr(seed.get("previous_core_knowledge_scope"))}
if not file_path and source_file:
    file_path = str(Path(os.getenv("UPLOADS_DIR", "/uploads")) / source_file)
database.init_schema()
ingest_db.init_ingest_schema()
errors = []
with database.get_write_cursor() as cursor:
    if user_type_id is not None:
        if previous_core_scope is None:
            cursor.execute(
                "DELETE FROM ai_config_user_type_overrides WHERE ai_config_key = ? AND user_type_id = ?",
                ("knowledge_source_default", user_type_id),
            )
        else:
            cursor.execute(
                "UPDATE ai_config_user_type_overrides SET value = ?, updated_at = ? WHERE ai_config_key = ? AND user_type_id = ?",
                (
                    previous_core_scope.get("value"),
                    previous_core_scope.get("updated_at"),
                    "knowledge_source_default",
                    user_type_id,
                ),
            )
        cursor.execute(
            "DELETE FROM document_defaults_user_type_overrides WHERE job_id = ? AND user_type_id = ?",
            (job_id, user_type_id),
        )
    cursor.execute("DELETE FROM document_defaults WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM retrieval_chunks WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM ingest_jobs WHERE job_id = ?", (job_id,))
    if owns_user_fixture and user_id is not None:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    if owns_user_fixture and user_type_id is not None:
        cursor.execute("DELETE FROM user_types WHERE id = ?", (user_type_id,))
if file_path:
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception as exc:
        errors.append("upload cleanup failed: " + str(exc))
if point_id:
    try:
        store.get_qdrant_client().delete(
            collection_name=store.COLLECTION_NAME,
            points_selector=PointIdsList(points=[point_id]),
            wait=True,
        )
    except Exception as exc:
        errors.append("Qdrant cleanup failed: " + str(exc))
if errors:
    raise RuntimeError(" | ".join(errors))
print(json.dumps({{"cleaned": True}}))
"""
    errors: list[str] = []
    sage_principal_cleanup_succeeded = True
    try:
        cleanup_sage_knowledge_scope(
            seed.get("user_type_id"),
            seed.get("previous_sage_knowledge_scope"),
        )
    except Exception as exc:
        errors.append(f"Sage policy cleanup failed: {exc}")
        sage_principal_cleanup_succeeded = False
    if seed.get("owns_user_fixture") and seed.get("user_id") is not None:
        if sage_principal_cleanup_succeeded:
            try:
                cleanup_sage_ephemeral_identity(int(seed["user_id"]))
            except Exception as exc:
                errors.append(f"Sage identity cleanup failed: {exc}")
                sage_principal_cleanup_succeeded = False
    delete_owned_principals = bool(
        seed.get("owns_user_fixture") and sage_principal_cleanup_succeeded
    )
    script = script.replace(
        "__DELETE_OWNED_PRINCIPALS__",
        repr(delete_owned_principals),
    )
    try:
        run_backend_python(script, timeout=60)
    except Exception as exc:
        errors.append(f"backend fixture cleanup failed: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))


def delete_query_session(
    api_base: str,
    token: str,
    session_id: str,
    timeout: float,
) -> None:
    response = requests.delete(
        f"{api_base.rstrip('/')}/query/session/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(
            "query session cleanup failed: "
            f"{response.status_code}: {response.text[:500]}"
        )
    payload = response.json()
    deletion = payload.get("deletion") if isinstance(payload, dict) else None
    if payload.get("status") != "deleted" or not isinstance(deletion, dict):
        raise RuntimeError(f"query session cleanup returned an unexpected payload: {payload}")
    if deletion.get("status") != "succeeded":
        raise RuntimeError(f"query session cleanup did not succeed: {payload}")


def expect(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"[PASS] {label}")
        return True
    print(f"[FAIL] {label}{': ' + detail if detail else ''}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5D: chunk Retrieval through public /query")
    parser.add_argument("--api-base", default="http://127.0.0.1:18000")
    parser.add_argument("--token", help="Optional approved user bearer token")
    parser.add_argument(
        "--user-type-id",
        type=int,
        help="Required with --token so the smoke can configure authoritative knowledge policy",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.token and not args.user_type_id:
        parser.error("--user-type-id is required when --token is provided")

    print("=" * 72)
    print("TEST 5D: CHUNK RETRIEVAL GATEWAY SMOKE")
    print("=" * 72)

    seed: dict[str, Any] | None = None
    seeded_user: dict[str, Any] | None = None
    token: str | None = None
    requested_session_id = str(uuid.uuid4())
    response_session_id: str | None = None
    request_dispatched = False
    response_succeeded = False
    result = 2
    try:
        if not args.token:
            seeded_user = seed_user_token()
        token = args.token or seeded_user["token"]
        user_type_id = (
            int(seeded_user["user_type_id"])
            if seeded_user
            else int(args.user_type_id)
        )
        seed = seed_chunk(user_type_id)
        seed.update({
            "user_id": seeded_user.get("user_id") if seeded_user else None,
            "user_type_id": user_type_id,
            "owns_user_fixture": seeded_user is not None,
        })
        request_dispatched = True
        response = requests.post(
            f"{args.api_base.rstrip('/')}/query",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "question": QUESTION,
                "session_id": requested_session_id,
                "job_ids": [seed["job_id"]],
                "top_k": 1,
                "tools": [],
            },
            timeout=args.timeout,
        )

        failures = 0
        failures += 0 if expect("/query status", response.status_code == 200, f"{response.status_code}: {response.text[:500]}") else 1
        response_succeeded = response.status_code == 200
        payload = response.json() if response.status_code == 200 else {}
        response_session_id = str(payload.get("session_id") or "").strip() or None
        sources = payload.get("sources") if isinstance(payload, dict) else []
        first_source = sources[0] if isinstance(sources, list) and sources else {}
        context_used = payload.get("context_used") or payload.get("context") or ""
        rendered_payload = json.dumps(payload, sort_keys=True)

        failures += 0 if expect(
            "requested session_id preserved",
            response_session_id == requested_session_id,
            rendered_payload[:500],
        ) else 1
        failures += 0 if expect("source returned", bool(first_source), rendered_payload[:500]) else 1
        failures += 0 if expect("selected job_id preserved", first_source.get("job_id") == seed["job_id"], str(first_source)) else 1
        failures += 0 if expect("chunk_id preserved", first_source.get("chunk_id") == seed["chunk_id"], str(first_source)) else 1
        failures += 0 if expect("source file preserved", first_source.get("source_file") == seed["source_file"], str(first_source)) else 1
        failures += 0 if expect("hydrated context includes marker", EXPECTED_PHRASE in str(context_used) or EXPECTED_PHRASE in rendered_payload) else 1

        if failures:
            print(f"\n[FAIL] {failures} checks failed")
            result = 1
        else:
            print("\n[PASS] Chunk Retrieval gateway smoke passed")
            result = 0
    except Exception as exc:
        print(f"[ERROR] {exc}")
        result = 2
    finally:
        cleanup_errors: list[str] = []
        if request_dispatched and token:
            try:
                delete_query_session(
                    args.api_base,
                    token,
                    requested_session_id,
                    args.timeout,
                )
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if response_succeeded and response_session_id != requested_session_id:
            cleanup_errors.append(
                "successful /query response did not preserve the requested session_id"
            )
        if seed:
            try:
                cleanup_seed(seed)
            except Exception as exc:
                cleanup_errors.append(str(exc))
        elif seeded_user:
            try:
                cleanup_seed({
                    "job_id": None,
                    "point_id": None,
                    "user_id": seeded_user.get("user_id"),
                    "user_type_id": seeded_user.get("user_type_id"),
                    "owns_user_fixture": True,
                })
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if cleanup_errors:
            print("[ERROR] Cleanup failed: " + "; ".join(cleanup_errors))
            result = 2
    return result


if __name__ == "__main__":
    sys.exit(main())
