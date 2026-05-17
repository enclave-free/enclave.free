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


def mint_admin_token() -> str:
    script = """
import json
import auth, database
admin = database.list_admins()[0]
token = auth.create_admin_session_token(admin["id"], admin["pubkey"], int(admin.get("session_nonce", 0) or 0))
print(json.dumps({"token": token}))
"""
    payload = run_backend_python(script, timeout=30)
    token = str(payload.get("token") or "")
    if not token:
        raise RuntimeError("failed to mint admin token")
    return token


def seed_chunk() -> dict[str, Any]:
    script = f"""
import json
import os
import time
import uuid
from pathlib import Path

from qdrant_client.models import PointStruct

import database
import ingest_db
import store

job_id = "gateway-smoke-" + str(int(time.time() * 1000))
chunk_id = job_id + "_chunk_0000"
source_file = "Gateway Retrieval Smoke.md"
text = "Gateway retrieval smoke fixture. The required marker phrase is: {EXPECTED_PHRASE}."
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
ingest_db.upsert_retrieval_chunk(
    chunk_id=chunk_id,
    job_id=job_id,
    chunk_index=0,
    source_file=source_file,
    text=text,
)

store.ensure_qdrant_collection()
vector = store.embed_texts(["query: {QUESTION}"])[0]
point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"chunk:{{chunk_id}}"))
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

print(json.dumps({{"job_id": job_id, "chunk_id": chunk_id, "point_id": point_id, "source_file": source_file}}))
"""
    return run_backend_python(script, timeout=180)


def cleanup_seed(seed: dict[str, Any]) -> None:
    script = f"""
import json

from qdrant_client.models import PointIdsList

import database
import ingest_db
import store

job_id = {json.dumps(seed.get("job_id"))}
point_id = {json.dumps(seed.get("point_id"))}
database.init_schema()
ingest_db.init_ingest_schema()
with database.get_write_cursor() as cursor:
    cursor.execute("DELETE FROM document_defaults WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM retrieval_chunks WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM ingest_jobs WHERE job_id = ?", (job_id,))
try:
    store.get_qdrant_client().delete(
        collection_name=store.COLLECTION_NAME,
        points_selector=PointIdsList(points=[point_id]),
    )
except Exception:
    pass
print(json.dumps({{"cleaned": True}}))
"""
    try:
        run_backend_python(script, timeout=60)
    except Exception as exc:
        print(f"[WARN] cleanup failed: {exc}")


def expect(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"[PASS] {label}")
        return True
    print(f"[FAIL] {label}{': ' + detail if detail else ''}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 5D: chunk Retrieval through public /query")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--token", help="Optional admin bearer token")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    print("=" * 72)
    print("TEST 5D: CHUNK RETRIEVAL GATEWAY SMOKE")
    print("=" * 72)

    seed: dict[str, Any] | None = None
    try:
        token = args.token or mint_admin_token()
        seed = seed_chunk()
        response = requests.post(
            f"{args.api_base.rstrip('/')}/query",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "question": QUESTION,
                "job_ids": [seed["job_id"]],
                "top_k": 1,
                "tools": [],
            },
            timeout=args.timeout,
        )

        failures = 0
        failures += 0 if expect("/query status", response.status_code == 200, f"{response.status_code}: {response.text[:500]}") else 1
        payload = response.json() if response.status_code == 200 else {}
        sources = payload.get("sources") if isinstance(payload, dict) else []
        first_source = sources[0] if isinstance(sources, list) and sources else {}
        context_used = payload.get("context_used") or payload.get("context") or ""
        rendered_payload = json.dumps(payload, sort_keys=True)

        failures += 0 if expect("source returned", bool(first_source), rendered_payload[:500]) else 1
        failures += 0 if expect("selected job_id preserved", first_source.get("job_id") == seed["job_id"], str(first_source)) else 1
        failures += 0 if expect("chunk_id preserved", first_source.get("chunk_id") == seed["chunk_id"], str(first_source)) else 1
        failures += 0 if expect("source file preserved", first_source.get("source_file") == seed["source_file"], str(first_source)) else 1
        failures += 0 if expect("hydrated context includes marker", EXPECTED_PHRASE in str(context_used) or EXPECTED_PHRASE in rendered_payload) else 1

        if failures:
            print(f"\n[FAIL] {failures} checks failed")
            return 1
        print("\n[PASS] Chunk Retrieval gateway smoke passed")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 2
    finally:
        if seed:
            cleanup_seed(seed)


if __name__ == "__main__":
    sys.exit(main())
