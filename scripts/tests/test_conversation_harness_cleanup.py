#!/usr/bin/env python3
"""Lifecycle cleanup regressions for local conversation evidence harnesses."""

from __future__ import annotations

import json
import sys
import unittest
from typing import NoReturn
from unittest.mock import patch

from scripts.tests.TOOLS import measure_admin_conversation_timing as timing
from scripts.tests.TOOLS import test_5d_chunk_retrieval_gateway_smoke as retrieval


class _ConnectionLostResponse:
    def __enter__(self) -> "_ConnectionLostResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        raise ConnectionResetError("connection lost after dispatch")


class _JsonResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_JsonResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        return self._body


class ConversationHarnessCleanupTest(unittest.TestCase):
    def test_retrieval_policy_cleanup_restores_original_sage_timestamp(self) -> None:
        previous = {
            "id": "11111111-1111-1111-1111-111111111111",
            "value": "all",
            "updated_at": "2026-07-14 10:11:12+00",
        }
        with patch.object(retrieval, "run_sage_postgres") as run_postgres:
            retrieval.cleanup_sage_knowledge_scope(7, previous)

        sql = run_postgres.call_args.args[0]
        self.assertIn("SET value = 'all'", sql)
        self.assertIn("updated_at = '2026-07-14 10:11:12+00'", sql)

    def test_retrieval_cleanup_retains_core_principals_when_sage_cleanup_fails(self) -> None:
        seed = {
            "job_id": "job",
            "point_id": None,
            "source_file": "fixture.md",
            "file_path": None,
            "user_id": 42,
            "user_type_id": 7,
            "owns_user_fixture": True,
            "previous_core_knowledge_scope": None,
            "previous_sage_knowledge_scope": None,
        }
        with patch.object(retrieval, "cleanup_sage_knowledge_scope"), patch.object(
            retrieval,
            "cleanup_sage_ephemeral_identity",
            side_effect=RuntimeError("identity still has a session"),
        ), patch.object(retrieval, "run_backend_python", return_value={}) as run_backend:
            with self.assertRaisesRegex(RuntimeError, "Sage identity cleanup failed"):
                retrieval.cleanup_seed(seed)

        cleanup_script = run_backend.call_args.args[0]
        self.assertIn("owns_user_fixture = False", cleanup_script)
        self.assertIn('Path(os.getenv("UPLOADS_DIR", "/uploads")) / source_file', cleanup_script)

    def test_timing_harness_deletes_requested_session_after_connection_loss(self) -> None:
        requests = []

        def urlopen(request: object, timeout: float) -> object:
            requests.append((request, timeout))
            if request.get_method() == "POST":
                return _ConnectionLostResponse()
            return _JsonResponse(
                {
                    "status": "deleted",
                    "deletion": {"status": "succeeded"},
                }
            )

        scenario = timing.Scenario("connection_loss", "hello", [])
        with patch.object(timing.urllib.request, "urlopen", side_effect=urlopen):
            with self.assertRaisesRegex(ConnectionResetError, "connection lost"):
                timing.measure_stream("http://gateway.test", "admin-token", scenario)

        self.assertEqual([request.get_method() for request, _ in requests], ["POST", "DELETE"])
        request_payload = json.loads(requests[0][0].data)
        requested_session_id = request_payload["session_id"]
        self.assertTrue(requested_session_id)
        self.assertTrue(requests[1][0].full_url.endswith(f"/{requested_session_id}"))

    def test_timing_cleanup_failure_does_not_mask_stream_failure(self) -> None:
        def urlopen(request: object, timeout: float) -> object:
            if request.get_method() == "POST":
                return _ConnectionLostResponse()
            raise RuntimeError("cleanup also failed")

        scenario = timing.Scenario("connection_loss", "hello", [])
        with patch.object(timing.urllib.request, "urlopen", side_effect=urlopen):
            with self.assertRaisesRegex(ConnectionResetError, "connection lost"):
                timing.measure_stream("http://gateway.test", "admin-token", scenario)

    def test_retrieval_smoke_deletes_requested_session_after_connection_loss(self) -> None:
        post_payload: dict[str, object] = {}
        deleted: list[tuple[str, str, str, float]] = []

        def fail_post(_url: str, **kwargs: object) -> NoReturn:
            payload = kwargs["json"]
            self.assertIsInstance(payload, dict)
            post_payload.update(payload)
            raise ConnectionError("connection lost after dispatch")

        def record_delete(
            api_base: str, token: str, session_id: str, timeout: float
        ) -> None:
            deleted.append((api_base, token, session_id, timeout))

        seed = {
            "job_id": "job",
            "chunk_id": "chunk",
            "source_file": "source.md",
            "point_id": "00000000-0000-0000-0000-000000000001",
            "upload_paths": [],
        }
        argv = [
            "test_5d_chunk_retrieval_gateway_smoke.py",
            "--token",
            "user-token",
            "--user-type-id",
            "7",
        ]
        with patch.object(sys, "argv", argv):
            with patch.object(retrieval, "seed_chunk", return_value=seed), patch.object(
                retrieval.requests, "post", side_effect=fail_post
            ), patch.object(
                retrieval, "delete_query_session", side_effect=record_delete
            ), patch.object(retrieval, "cleanup_seed"):
                self.assertEqual(retrieval.main(), 2)

        requested_session_id = str(post_payload["session_id"])
        self.assertTrue(requested_session_id)
        self.assertEqual(
            deleted,
            [("http://127.0.0.1:18000", "user-token", requested_session_id, 180.0)],
        )


if __name__ == "__main__":
    unittest.main()
