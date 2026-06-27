#!/usr/bin/env python3

from __future__ import annotations

import http.client
import inspect
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.benches.conversation_model_bench import (
    BenchOptions,
    HttpConversationClient,
    LocalComposeEnvironment,
    SCENARIOS,
    StreamResult,
    parse_args,
    run_bench,
    run_command,
    runtime_config_fingerprint_command,
)


class FakeEnvironment:
    def __init__(self) -> None:
        self.verified_models: list[str | None] = []
        self.seeded_knowledge = False
        self.seeded_resources = False
        self.switched_models: list[str] = []
        self.restored_models: list[str] = []
        self.health_waits = 0
        self.reset_count = 0
        self.operations: list[str] = []

    def run_metadata(self) -> dict:
        return {"repo": "test-repo", "git": {"prototype": "abc123"}}

    def current_model(self) -> str:
        return "kimi-k2-6"

    def verify_runtime_model(self, expected_model: str | None = None) -> dict:
        self.verified_models.append(expected_model)
        return {
            "service": "sage",
            "runtime_config": {
                "TINFOIL_MODEL": expected_model or "kimi-k2-6",
                "TINFOIL_API_KEY": {"configured": True, "fingerprint": "abc"},
            },
        }

    def admin_token(self) -> str:
        return "admin-token"

    def user_token(self) -> str:
        return "user-token"

    def seed_knowledge(self) -> dict:
        self.seeded_knowledge = True
        return {
            "job_ids": ["bench-knowledge-fixture"],
            "sources": ["Post-Release First Day Safety.md"],
        }

    def seed_resources(self) -> dict:
        self.seeded_resources = True
        return {
            "resource_ids": ["conversation-bench-global-legal"],
            "resources": [
                {
                    "resource_id": "conversation-bench-global-legal",
                    "name": "Bench Liberty Legal Hotline",
                }
            ],
        }

    def switch_model(self, model: str) -> None:
        self.switched_models.append(model)

    def wait_for_health(self) -> None:
        self.health_waits += 1

    def restore_model(self, model: str) -> None:
        self.restored_models.append(model)

    def reset_state(self) -> None:
        self.operations.append("reset_state")
        self.reset_count += 1


class FakeConversationClient:
    def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
        self.last_token = token
        self.last_payload = payload
        message = payload["message"]
        if message.strip().upper().startswith("SELECT "):
            return StreamResult(
                answer=(
                    "The selected settings include instance_name, assistant_name, "
                    "and default_language."
                ),
                events=[
                    {
                        "event": "activity_step",
                        "elapsed_ms": 20.0,
                        "data": {
                            "activity_step": {
                                "id": "db-query",
                                "title": "Database Query",
                                "status": "completed",
                            }
                        },
                    },
                    {
                        "event": "answer_delta",
                        "elapsed_ms": 90.0,
                        "data": {"delta": "The selected settings include instance_name."},
                    },
                    {
                        "event": "done",
                        "elapsed_ms": 110.0,
                        "data": {
                            "model": "kimi-k2-6",
                            "provider": "sage",
                            "tools_used": [
                                {
                                    "tool_id": "db-query",
                                    "tool_name": "Database Query",
                                    "query": message,
                                    "output_summary": "Database results were redacted from the trace.",
                                    "warnings": ["raw_results_redacted"],
                                }
                            ],
                        },
                    },
                ],
                done={
                    "model": "kimi-k2-6",
                    "provider": "sage",
                    "tools_used": [
                        {
                            "tool_id": "db-query",
                            "tool_name": "Database Query",
                            "query": message,
                            "output_summary": "Database results were redacted from the trace.",
                            "warnings": ["raw_results_redacted"],
                        }
                    ],
                },
                trace={
                    "tools": [
                        {
                            "id": "db-query",
                            "name": "Database Query",
                            "query": message,
                            "warnings": ["raw_results_redacted"],
                        }
                    ]
                },
                admin_change_set=None,
                timings={
                    "first_event_ms": 20.0,
                    "first_trace_or_tool_feedback_ms": 20.0,
                    "first_visible_assistant_token_ms": 90.0,
                    "done_ms": 110.0,
                },
            )
        if "do not make me write SQL" in message:
            return StreamResult(
                answer=(
                    "The Database Query tool only runs direct read-only SELECT "
                    "statements. Submit a SELECT query to inspect database counts."
                ),
                events=[
                    {
                        "event": "activity_step",
                        "elapsed_ms": 20.0,
                        "data": {
                            "activity_step": {
                                "id": "db-query",
                                "title": "Database Query",
                                "status": "guarded",
                                "warnings": ["direct_select_required"],
                            }
                        },
                    },
                    {
                        "event": "answer_delta",
                        "elapsed_ms": 90.0,
                        "data": {"delta": "The Database Query tool only runs SELECT."},
                    },
                    {
                        "event": "done",
                        "elapsed_ms": 110.0,
                        "data": {
                            "model": "kimi-k2-6",
                            "provider": "sage",
                            "tools_used": [
                                {
                                    "tool_id": "db-query",
                                    "tool_name": "Database Query",
                                    "output_summary": "Submit a direct read-only SELECT to run it.",
                                    "warnings": ["direct_select_required"],
                                    "guarded": True,
                                }
                            ],
                        },
                    },
                ],
                done={
                    "model": "kimi-k2-6",
                    "provider": "sage",
                    "tools_used": [
                        {
                            "tool_id": "db-query",
                            "tool_name": "Database Query",
                            "output_summary": "Submit a direct read-only SELECT to run it.",
                            "warnings": ["direct_select_required"],
                            "guarded": True,
                        }
                    ],
                },
                trace={
                    "tools": [
                        {
                            "id": "db-query",
                            "name": "Database Query",
                            "warnings": ["direct_select_required"],
                            "guarded": True,
                        }
                    ]
                },
                admin_change_set=None,
                timings={
                    "first_event_ms": 20.0,
                    "first_trace_or_tool_feedback_ms": 20.0,
                    "first_visible_assistant_token_ms": 90.0,
                    "done_ms": 110.0,
                },
            )
        if "loved one was just released" in message and "curated resources" in message:
            return StreamResult(
                answer=(
                    "First, get to a physically safe place, contact trusted people, "
                    "and document urgent needs. For vetted help, use Bench Liberty "
                    "Legal Hotline at bench-legal@example.test for legal triage."
                ),
                events=[
                    {
                        "event": "activity_step",
                        "elapsed_ms": 20.0,
                        "data": {
                            "activity_step": {
                                "id": "knowledge-search",
                                "title": "Knowledge Search",
                                "status": "completed",
                            }
                        },
                    },
                    {
                        "event": "activity_step",
                        "elapsed_ms": 40.0,
                        "data": {
                            "activity_step": {
                                "id": "curated-resources",
                                "title": "Curated Resources",
                                "status": "completed",
                            }
                        },
                    },
                    {
                        "event": "answer_delta",
                        "elapsed_ms": 90.0,
                        "data": {"delta": "First, get to a physically safe place."},
                    },
                    {
                        "event": "done",
                        "elapsed_ms": 120.0,
                        "data": {
                            "model": "kimi-k2-6",
                            "provider": "sage",
                            "tools_used": [
                                {
                                    "tool_id": "knowledge-search",
                                    "tool_name": "Knowledge Search",
                                    "output_summary": "Found 1 relevant source.",
                                },
                                {
                                    "tool_id": "curated-resources",
                                    "tool_name": "Curated Resources",
                                    "output_summary": "Found vetted curated resources for the answer.",
                                },
                            ],
                        },
                    },
                ],
                done={
                    "model": "kimi-k2-6",
                    "provider": "sage",
                    "tools_used": [
                        {
                            "tool_id": "knowledge-search",
                            "tool_name": "Knowledge Search",
                            "output_summary": "Found 1 relevant source.",
                        },
                        {
                            "tool_id": "curated-resources",
                            "tool_name": "Curated Resources",
                            "output_summary": "Found vetted curated resources for the answer.",
                        },
                    ],
                },
                trace={
                    "tools": [
                        {"id": "knowledge-search", "name": "Knowledge Search"},
                        {"id": "curated-resources", "name": "Curated Resources"},
                    ],
                    "retrieval": [
                        {
                            "source_type": "document",
                            "title": "Post-Release First Day Safety.md",
                            "summary": "Immediate first-day safety steps.",
                        }
                    ],
                },
                admin_change_set=None,
                timings={
                    "first_event_ms": 20.0,
                    "first_trace_or_tool_feedback_ms": 20.0,
                    "first_visible_assistant_token_ms": 90.0,
                    "done_ms": 120.0,
                },
            )
        if "vetted legal referral" in message:
            return StreamResult(
                answer=(
                    "Use the Bench Liberty Legal Hotline at bench-legal@example.test. "
                    "Only use the listed contact details and verify before acting."
                ),
                events=[
                    {
                        "event": "activity_step",
                        "elapsed_ms": 20.0,
                        "data": {
                            "activity_step": {
                                "id": "curated-resources",
                                "title": "Curated Resources",
                                "status": "completed",
                            }
                        },
                    },
                    {
                        "event": "answer_delta",
                        "elapsed_ms": 90.0,
                        "data": {"delta": "Use the Bench Liberty Legal Hotline."},
                    },
                    {
                        "event": "done",
                        "elapsed_ms": 110.0,
                        "data": {
                            "model": "kimi-k2-6",
                            "provider": "sage",
                            "tools_used": [
                                {
                                    "tool_id": "curated-resources",
                                    "tool_name": "Curated Resources",
                                    "output_summary": "Found vetted curated resources for the answer.",
                                }
                            ],
                        },
                    },
                ],
                done={
                    "model": "kimi-k2-6",
                    "provider": "sage",
                    "tools_used": [
                        {
                            "tool_id": "curated-resources",
                            "tool_name": "Curated Resources",
                            "output_summary": "Found vetted curated resources for the answer.",
                        }
                    ],
                },
                trace={"tools": [{"id": "curated-resources", "name": "Curated Resources"}]},
                admin_change_set=None,
                timings={
                    "first_event_ms": 20.0,
                    "first_trace_or_tool_feedback_ms": 20.0,
                    "first_visible_assistant_token_ms": 90.0,
                    "done_ms": 110.0,
                },
            )
        if "political imprisonment" in message:
            return StreamResult(
                answer=(
                    "First today, get to a physically safe place, contact trusted "
                    "people, document urgent needs, and seek local professional help "
                    "for legal, medical, or safety questions."
                ),
                events=[
                    {
                        "event": "activity_step",
                        "elapsed_ms": 20.0,
                        "data": {
                            "activity_step": {
                                "id": "knowledge-search",
                                "title": "Knowledge Search",
                                "status": "completed",
                            }
                        },
                    },
                    {
                        "event": "answer_delta",
                        "elapsed_ms": 80.0,
                        "data": {"delta": "First today, get to a physically safe place."},
                    },
                    {
                        "event": "done",
                        "elapsed_ms": 100.0,
                        "data": {
                            "model": "kimi-k2-6",
                            "provider": "sage",
                            "tools_used": [
                                {
                                    "tool_id": "knowledge-search",
                                    "tool_name": "Knowledge Search",
                                    "output_summary": "Found 1 relevant source.",
                                }
                            ],
                        },
                    },
                ],
                done={
                    "model": "kimi-k2-6",
                    "provider": "sage",
                    "tools_used": [
                        {
                            "tool_id": "knowledge-search",
                            "tool_name": "Knowledge Search",
                            "output_summary": "Found 1 relevant source.",
                        }
                    ],
                },
                trace={
                    "tools": [{"id": "knowledge-search", "name": "Knowledge Search"}],
                    "retrieval": [
                        {
                            "source_type": "document",
                            "title": "Post-Release First Day Safety.md",
                            "summary": "Immediate first-day safety steps.",
                        }
                    ],
                },
                admin_change_set=None,
                timings={
                    "first_event_ms": 20.0,
                    "first_trace_or_tool_feedback_ms": 20.0,
                    "first_visible_assistant_token_ms": 80.0,
                    "done_ms": 100.0,
                },
            )
        if "there are two kinds of users" in message:
            admin_change_set = {
                "version": 1,
                "summary": "Bootstrap FreeThem",
                "requests": [
                    {
                        "method": "PUT",
                        "path": "/admin/settings",
                        "body": {
                            "instance_name": "FreeThem",
                            "assistant_name": "Liberty",
                            "header_tagline": "political prisoners support team",
                            "description": (
                                "We are the political prisoners support team an arm "
                                "of the World Liberty Congress"
                            ),
                            "primary_color": "#2563EB",
                            "default_theme": "dark",
                            "default_language": "en",
                            "auto_approve_users": True,
                        },
                    },
                    {
                        "method": "POST",
                        "path": "/admin/user-types",
                        "body": {
                            "name": "Families and Friends of Current Political Prisoners",
                            "description": (
                                "Support for people with loved ones currently in the situation."
                            ),
                        },
                    },
                    {
                        "method": "POST",
                        "path": "/admin/user-types",
                        "body": {
                            "name": "Friends, Family, and Former Political Prisoners",
                            "description": (
                                "Support for former political prisoners and people "
                                "helping after the situation."
                            ),
                        },
                    },
                ],
            }
            return StreamResult(
                answer="I prepared these setup changes for review. Use Apply to confirm.",
                events=[],
                done={
                    "model": "kimi-k2-6",
                    "provider": "sage",
                    "tools_used": [
                        {
                            "tool_id": "admin-config:propose_admin_config_bootstrap",
                            "tool_name": "Admin Config",
                            "status": "completed",
                            "output_summary": "Prepared bootstrap change set: Bootstrap FreeThem",
                        }
                    ],
                    "admin_change_set": admin_change_set,
                },
                trace={
                    "tools": [
                        {
                            "id": "admin-config:propose_admin_config_bootstrap",
                            "name": "Admin Config",
                            "status": "completed",
                        },
                    ]
                },
                admin_change_set=admin_change_set,
                timings={
                    "first_event_ms": 10.0,
                    "first_trace_or_tool_feedback_ms": 10.0,
                    "first_visible_assistant_token_ms": 90.0,
                    "done_ms": 110.0,
                },
            )
        if "FreeThem" in payload["message"]:
            return StreamResult(
                answer="I prepared these changes for review. Use Apply to confirm.",
                events=[],
                done={
                    "model": "kimi-k2-6",
                    "provider": "sage",
                    "tools_used": [
                        {
                            "tool_id": "admin-config:read_instance_settings",
                            "tool_name": "Admin Config",
                            "output_summary": "Read read_instance_settings.",
                        },
                        {
                            "tool_id": "admin-config:propose_admin_config_bootstrap",
                            "tool_name": "Admin Config",
                            "output_summary": "Prepared bootstrap change set: Bootstrap FreeThem",
                        }
                    ],
                    "admin_change_set": {
                        "version": 1,
                        "summary": "Bootstrap FreeThem",
                        "requests": [
                            {
                                "method": "PUT",
                                "path": "/admin/settings",
                                "body": {
                                    "instance_name": "FreeThem",
                                    "assistant_name": "Ally",
                                    "header_tagline": "Political prisoner support team.",
                                    "description": "We are the Political Prisoners Support Team.",
                                    "primary_color": "#4F46E5",
                                    "default_theme": "dark",
                                    "default_language": "en",
                                    "auto_approve_users": True,
                                },
                            },
                            {
                                "method": "POST",
                                "path": "/admin/user-types",
                                "body": {
                                    "name": "Family and Friends of Current Prisoners",
                                    "description": "For loved ones of people currently imprisoned for political reasons.",
                                },
                            },
                            {
                                "method": "POST",
                                "path": "/admin/user-types",
                                "body": {
                                    "name": "Former Prisoners and Supporters",
                                    "description": "For former political prisoners and supporters seeking post-release resources.",
                                },
                            },
                            {
                                "method": "POST",
                                "path": "/admin/user-fields",
                                "body": {
                                    "field_name": "What country are you in?",
                                    "field_type": "text",
                                    "display_order": 1,
                                    "include_in_chat": True,
                                },
                            },
                            {
                                "method": "POST",
                                "path": "/admin/user-fields",
                                "body": {
                                    "field_name": "What kind of support do you need?",
                                    "field_type": "select",
                                    "display_order": 2,
                                    "include_in_chat": True,
                                    "options": [
                                        "Current prisoner support",
                                        "Post-release support",
                                    ],
                                },
                            },
                            {
                                "method": "PUT",
                                "path": "/admin/ai-config/prompt_rules",
                                "body": {
                                    "value": json.dumps(
                                        [
                                            "Ask where users are before giving location-specific guidance."
                                        ]
                                    )
                                },
                            },
                        ],
                    },
                },
                trace={
                    "tools": [
                        {"id": "admin-config:read_instance_settings", "name": "Admin Config"},
                        {
                            "id": "admin-config:propose_admin_config_bootstrap",
                            "name": "Admin Config",
                        },
                    ]
                },
                admin_change_set={
                    "version": 1,
                    "summary": "Bootstrap FreeThem",
                    "requests": [
                        {
                            "method": "PUT",
                            "path": "/admin/settings",
                            "body": {
                                "instance_name": "FreeThem",
                                "assistant_name": "Ally",
                                "header_tagline": "Political prisoner support team.",
                                "description": "We are the Political Prisoners Support Team.",
                                "primary_color": "#4F46E5",
                                "default_theme": "dark",
                                "default_language": "en",
                                "auto_approve_users": True,
                            },
                        },
                        {
                            "method": "POST",
                            "path": "/admin/user-types",
                            "body": {
                                "name": "Family and Friends of Current Prisoners",
                                "description": "For loved ones of people currently imprisoned for political reasons.",
                            },
                        },
                        {
                            "method": "POST",
                            "path": "/admin/user-types",
                            "body": {
                                "name": "Former Prisoners and Supporters",
                                "description": "For former political prisoners and supporters seeking post-release resources.",
                            },
                        },
                        {
                            "method": "POST",
                            "path": "/admin/user-fields",
                            "body": {
                                "field_name": "What country are you in?",
                                "field_type": "text",
                                "display_order": 1,
                                "include_in_chat": True,
                            },
                        },
                        {
                            "method": "POST",
                            "path": "/admin/user-fields",
                            "body": {
                                "field_name": "What kind of support do you need?",
                                "field_type": "select",
                                "display_order": 2,
                                "include_in_chat": True,
                                "options": [
                                    "Current prisoner support",
                                    "Post-release support",
                                ],
                            },
                        },
                        {
                            "method": "PUT",
                            "path": "/admin/ai-config/prompt_rules",
                            "body": {
                                "value": json.dumps(
                                    [
                                        "Ask where users are before giving location-specific guidance."
                                    ]
                                )
                            },
                        },
                    ],
                },
                timings={
                    "first_event_ms": 10.0,
                    "first_trace_or_tool_feedback_ms": 10.0,
                    "first_visible_assistant_token_ms": 90.0,
                    "done_ms": 110.0,
                },
            )
        return StreamResult(
            answer=(
                "FreeThem is mostly configured. I checked the available Admin "
                "Config setup summary and model keys remain redacted."
            ),
            events=[
                {
                    "event": "trace_status",
                    "elapsed_ms": 10.0,
                    "data": {"timing": {"phase": "preparing_tools", "elapsed_ms": 10}},
                },
                {
                    "event": "activity_step",
                    "elapsed_ms": 25.0,
                    "data": {
                        "activity_step": {
                            "id": "admin-config:read_admin_setup_summary",
                            "title": "Admin Config",
                            "status": "completed",
                        }
                    },
                },
                {
                    "event": "answer_delta",
                    "elapsed_ms": 100.0,
                    "data": {"delta": "FreeThem is mostly configured."},
                },
                {
                    "event": "done",
                    "elapsed_ms": 120.0,
                    "data": {
                        "model": "kimi-k2-6",
                        "provider": "sage",
                        "tools_used": [
                            {
                                "tool_id": "admin-config:read_admin_setup_summary",
                                "tool_name": "Admin Config",
                                "output_summary": (
                                    "Read Admin Config setup summary: warnings, "
                                    "2 item(s) need attention."
                                ),
                            }
                        ],
                    },
                },
            ],
            done={
                "model": "kimi-k2-6",
                "provider": "sage",
                "tools_used": [
                    {
                        "tool_id": "admin-config:read_admin_setup_summary",
                        "tool_name": "Admin Config",
                        "output_summary": (
                            "Read Admin Config setup summary: warnings, "
                            "2 item(s) need attention."
                        ),
                    }
                ],
            },
            trace={
                "tools": [
                    {
                        "id": "admin-config:read_admin_setup_summary",
                        "name": "Admin Config",
                    }
                ]
            },
            admin_change_set=None,
            timings={
                "first_event_ms": 10.0,
                "first_trace_or_tool_feedback_ms": 25.0,
                "first_visible_assistant_token_ms": 100.0,
                "done_ms": 120.0,
            },
        )


class FakeWarningOnlyClient:
    def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
        return StreamResult(
            answer="They should make a simple plan today and stay calm.",
            events=[
                {
                    "event": "answer_delta",
                    "elapsed_ms": 80.0,
                    "data": {"delta": "They should make a simple plan today."},
                },
                {
                    "event": "done",
                    "elapsed_ms": 100.0,
                    "data": {"model": "kimi-k2-6", "provider": "sage", "tools_used": []},
                },
            ],
            done={"model": "kimi-k2-6", "provider": "sage", "tools_used": []},
            trace={"tools": [], "retrieval": []},
            admin_change_set=None,
            timings={
                "first_event_ms": 80.0,
                "first_trace_or_tool_feedback_ms": None,
                "first_visible_assistant_token_ms": 80.0,
                "done_ms": 100.0,
            },
        )


class FakeGenericFailureAnswerClient(FakeConversationClient):
    def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
        result = super().stream_chat(token, payload, timeout)
        return StreamResult(
            answer="I apologize, but I wasn't able to generate a response.",
            events=result.events,
            done=result.done,
            trace=result.trace,
            admin_change_set=result.admin_change_set,
            timings=result.timings,
        )


class FakeSlowFirstAnswerClient(FakeConversationClient):
    def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
        result = super().stream_chat(token, payload, timeout)
        return StreamResult(
            answer=result.answer,
            events=result.events,
            done=result.done,
            trace=result.trace,
            admin_change_set=result.admin_change_set,
            timings={
                "first_event_ms": 10.0,
                "first_trace_or_tool_feedback_ms": 10.0,
                "first_visible_assistant_token_ms": 45_000.0,
                "done_ms": 50_000.0,
            },
        )


class FakeSlowTraceFeedbackClient(FakeConversationClient):
    def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
        result = super().stream_chat(token, payload, timeout)
        return StreamResult(
            answer=result.answer,
            events=result.events,
            done=result.done,
            trace=result.trace,
            admin_change_set=result.admin_change_set,
            timings={
                **result.timings,
                "first_trace_or_tool_feedback_ms": 15_000.0,
            },
        )


class FakeFailingClient:
    def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
        raise RuntimeError("connection closed")


class IncompleteStreamResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.offset = 0

    def __enter__(self) -> "IncompleteStreamResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        if self.offset < len(self.body):
            chunk = self.body[self.offset : self.offset + size]
            self.offset += len(chunk)
            return chunk
        raise http.client.IncompleteRead(b"")


class ConversationModelBenchTest(unittest.TestCase):
    def test_bench_docs_match_v0_runner_contract(self) -> None:
        docs = (REPO_ROOT / "docs" / "conversation-model-bench.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("python scripts/benches/conversation_model_bench.py", docs)
        self.assertIn("--models gpt-oss-120b,kimi-k2-6", docs)
        self.assertIn("--no-restore-model", docs)
        self.assertIn("Hard failures", docs)
        self.assertIn("Evidence-only warnings", docs)
        self.assertIn("Browser Apply-Panel Smoke Follow-Up", docs)
        self.assertNotIn("Open Decisions", docs)

    def test_cli_defaults_to_all_v0_scenarios(self) -> None:
        options = parse_args([])

        self.assertEqual(
            options.scenarios,
            (
                "admin_config_bootstrap",
                "admin_config_live_onboarding_prompt",
                "admin_deployment_readiness",
                "admin_database_direct_select",
                "admin_database_natural_language_guardrail",
                "user_knowledge_assistance",
                "user_curated_resource_referral",
                "user_knowledge_and_resource_assistance",
            ),
        )

    def test_cli_parses_explicit_models_and_no_restore(self) -> None:
        options = parse_args(
            ["--models", "gpt-oss-120b, gemma4-31b", "--seed-resources", "--no-restore-model"]
        )

        self.assertEqual(options.models, ("gpt-oss-120b", "gemma4-31b"))
        self.assertTrue(options.seed_resources)
        self.assertFalse(options.restore_model)

    def test_runtime_config_fingerprint_uses_internal_agent_token_header(self) -> None:
        command = runtime_config_fingerprint_command("test-token")

        self.assertIn("X-Internal-Agent-Token: test-token", command)
        self.assertNotIn("Authorization: Bearer test-token", command)

    def test_run_command_redacts_internal_agent_token_on_failure(self) -> None:
        with patch(
            "scripts.benches.conversation_model_bench.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="request failed",
            ),
        ):
            with self.assertRaises(RuntimeError) as raised:
                run_command(
                    [
                        "curl",
                        "-H",
                        "X-Internal-Agent-Token: secret-token",
                        "http://example.test",
                    ],
                    timeout=1,
                )

        message = str(raised.exception)
        self.assertIn("X-Internal-Agent-Token: <redacted>", message)
        self.assertNotIn("secret-token", message)

    def test_run_command_redacts_internal_agent_token_on_timeout(self) -> None:
        with patch(
            "scripts.benches.conversation_model_bench.subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=["curl", "-H", "X-Internal-Agent-Token: secret-token"],
                timeout=1,
            ),
        ):
            with self.assertRaises(RuntimeError) as raised:
                run_command(
                    [
                        "curl",
                        "-H",
                        "X-Internal-Agent-Token: secret-token",
                        "http://example.test",
                    ],
                    timeout=1,
                )

        message = str(raised.exception)
        self.assertIn("X-Internal-Agent-Token: <redacted>", message)
        self.assertNotIn("secret-token", message)

    def test_fresh_reset_admin_helper_uses_existing_admin_creation_api(self) -> None:
        source = inspect.getsource(LocalComposeEnvironment.admin_token)

        self.assertIn("database.add_admin", source)
        self.assertNotIn("database.create_admin", source)

    def test_wait_for_health_retries_after_probe_timeout(self) -> None:
        with (
            patch(
                "scripts.benches.conversation_model_bench.subprocess.run",
                side_effect=[
                    subprocess.TimeoutExpired(cmd="curl", timeout=10),
                    subprocess.CompletedProcess(
                        args=[],
                        returncode=0,
                        stdout="",
                        stderr="",
                    ),
                ],
            ) as run_probe,
            patch(
                "scripts.benches.conversation_model_bench.time.time",
                side_effect=[0, 1, 2],
            ),
            patch("scripts.benches.conversation_model_bench.time.sleep") as sleep,
        ):
            LocalComposeEnvironment().wait_for_health()

        self.assertEqual(run_probe.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_stream_client_artifacts_incomplete_stream_before_done(self) -> None:
        body = (
            b'event: assistant_message_started\ndata: {"message_id":"msg_1"}\n\n'
            b'event: trace_status\ndata: {"status":"Running enabled tools..."}\n\n'
        )

        with patch(
            "urllib.request.urlopen",
            return_value=IncompleteStreamResponse(body),
        ):
            result = HttpConversationClient("http://example.test").stream_chat(
                "token",
                {"message": "hello"},
                timeout=1,
            )

        self.assertEqual(
            [event["event"] for event in result.events],
            [
                "assistant_message_started",
                "trace_status",
            ],
        )
        self.assertEqual(result.done, {})
        self.assertIn("stream closed before done", result.error or "")

    def test_stream_client_preserves_multibyte_answer_text(self) -> None:
        answer_data = json.dumps({"delta": "Get safe — today."}, ensure_ascii=False)
        done_data = json.dumps({"model": "kimi-k2-6", "provider": "sage"})
        body = (
            f"event: answer_delta\ndata: {answer_data}\n\n"
            f"event: done\ndata: {done_data}\n\n"
        ).encode("utf-8")

        with patch(
            "urllib.request.urlopen",
            return_value=IncompleteStreamResponse(body),
        ):
            result = HttpConversationClient("http://example.test").stream_chat(
                "token",
                {"message": "hello"},
                timeout=1,
            )

        self.assertEqual(result.answer, "Get safe — today.")
        self.assertIsNone(result.error)

    def test_stream_client_records_first_trace_or_tool_feedback_latency(self) -> None:
        body = (
            b'event: trace_delta\ndata: {"trace_delta":{"id":"trace-1","kind":"tool_call","title":"Admin Config","status":"running"}}\n\n'
            b'event: answer_delta\ndata: {"delta":"Ready"}\n\n'
            b'event: done\ndata: {"model":"kimi-k2-6","provider":"sage"}\n\n'
        )

        with (
            patch(
                "urllib.request.urlopen",
                return_value=IncompleteStreamResponse(body),
            ),
            patch(
                "scripts.benches.conversation_model_bench.time.perf_counter",
                side_effect=[100.0, 100.015, 100.055, 100.090],
            ),
        ):
            result = HttpConversationClient("http://example.test").stream_chat(
                "token",
                {"message": "hello"},
                timeout=1,
            )

        self.assertEqual(result.timings["first_event_ms"], 15.0)
        self.assertEqual(result.timings["first_trace_or_tool_feedback_ms"], 15.0)
        self.assertEqual(result.timings["first_visible_assistant_token_ms"], 55.0)
        self.assertEqual(result.timings["done_ms"], 90.0)

    def test_reset_option_invokes_local_state_reset_before_scenarios(self) -> None:
        env = FakeEnvironment()

        class RecordingScenarioClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                env.operations.append("scenario_started")
                return super().stream_chat(token, payload, timeout)

        run_bench(
            BenchOptions(
                scenarios=("admin_deployment_readiness",),
                reset=True,
            ),
            environment=env,
            client=RecordingScenarioClient(),
        )

        self.assertEqual(env.reset_count, 1)
        self.assertEqual(env.verified_models, ["kimi-k2-6"])
        self.assertLess(
            env.operations.index("reset_state"),
            env.operations.index("scenario_started"),
        )

    def test_current_model_admin_readiness_bench_produces_passing_artifact(self) -> None:
        env = FakeEnvironment()
        client = FakeConversationClient()

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_deployment_readiness",),
            ),
            environment=env,
            client=client,
        )

        self.assertEqual(artifact["schema_version"], 1)
        self.assertEqual(artifact["candidates"][0]["model"], "kimi-k2-6")
        self.assertEqual(
            artifact["candidates"][0]["scenarios"][0]["id"],
            "admin_deployment_readiness",
        )
        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertEqual(env.verified_models, ["kimi-k2-6"])
        self.assertEqual(client.last_token, "admin-token")
        self.assertEqual(client.last_payload["tools"], ["admin-config"])
        self.assertEqual(
            artifact["candidates"][0]["scenarios"][0]["timing"][
                "first_trace_or_tool_feedback_ms"
            ],
            25.0,
        )

    def test_admin_readiness_fails_when_change_set_tool_is_staged(self) -> None:
        class FakeStagedChangeSetClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                return StreamResult(
                    answer=result.answer,
                    events=result.events,
                    done={
                        **result.done,
                        "tools_used": [
                            *result.done.get("tools_used", []),
                            {
                                "tool_id": "admin_change_set",
                                "tool_name": "Admin Change Set",
                            },
                        ],
                    },
                    trace=result.trace,
                    admin_change_set=result.admin_change_set,
                    timings=result.timings,
                    error=result.error,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_deployment_readiness",),
            ),
            environment=FakeEnvironment(),
            client=FakeStagedChangeSetClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check for check in scenario["checks"]}

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(checks["admin_change_set_not_staged"]["severity"], "hard")
        self.assertEqual(checks["admin_change_set_not_staged"]["status"], "failed")

    def test_admin_readiness_requires_setup_summary_tool(self) -> None:
        class FakeLowLevelReadFanoutClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                low_level_tools = [
                    {
                        "tool_id": "admin-config:read_deployment_readiness",
                        "tool_name": "Admin Config",
                        "output_summary": "Read read_deployment_readiness.",
                    },
                    {
                        "tool_id": "admin-config:read_instance_settings",
                        "tool_name": "Admin Config",
                        "output_summary": "Read read_instance_settings.",
                    },
                    {
                        "tool_id": "admin-config:read_user_types",
                        "tool_name": "Admin Config",
                        "output_summary": "Read read_user_types.",
                    },
                ]
                return StreamResult(
                    answer=result.answer,
                    events=[
                        {
                            "event": "activity_step",
                            "elapsed_ms": 25.0,
                            "data": {
                                "activity_step": {
                                    "id": "admin-config:read_deployment_readiness",
                                    "title": "Admin Config",
                                    "status": "completed",
                                }
                            },
                        },
                        {
                            "event": "answer_delta",
                            "elapsed_ms": 100.0,
                            "data": {"delta": "FreeThem is mostly configured."},
                        },
                        {
                            "event": "done",
                            "elapsed_ms": 120.0,
                            "data": {
                                "model": "kimi-k2-6",
                                "provider": "sage",
                                "tools_used": low_level_tools,
                            },
                        },
                    ],
                    done={**result.done, "tools_used": low_level_tools},
                    trace={
                        "tools": [
                            {"id": tool["tool_id"], "name": "Admin Config"}
                            for tool in low_level_tools
                        ]
                    },
                    admin_change_set=result.admin_change_set,
                    timings=result.timings,
                    error=result.error,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_deployment_readiness",),
            ),
            environment=FakeEnvironment(),
            client=FakeLowLevelReadFanoutClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check for check in scenario["checks"]}

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(checks["admin_setup_summary_tool_used"]["severity"], "hard")
        self.assertEqual(checks["admin_setup_summary_tool_used"]["status"], "failed")
        self.assertEqual(
            checks["broad_status_avoids_low_level_read_fanout"]["status"],
            "failed",
        )

    def test_admin_readiness_fails_when_stream_change_set_payload_is_staged(self) -> None:
        class FakeStagedChangeSetClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                return StreamResult(
                    answer=result.answer,
                    events=result.events,
                    done=result.done,
                    trace=result.trace,
                    admin_change_set={"requests": [{"path": "/admin/settings"}]},
                    timings=result.timings,
                    error=result.error,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_deployment_readiness",),
            ),
            environment=FakeEnvironment(),
            client=FakeStagedChangeSetClient(),
        )

        checks = {
            check["name"]: check
            for check in artifact["candidates"][0]["scenarios"][0]["checks"]
        }

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(checks["admin_change_set_not_staged"]["status"], "failed")

    def test_admin_readiness_fails_when_done_change_set_payload_is_staged(self) -> None:
        class FakeStagedChangeSetClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                return StreamResult(
                    answer=result.answer,
                    events=result.events,
                    done={
                        **result.done,
                        "admin_change_set": {"requests": [{"path": "/admin/settings"}]},
                    },
                    trace=result.trace,
                    admin_change_set=result.admin_change_set,
                    timings=result.timings,
                    error=result.error,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_deployment_readiness",),
            ),
            environment=FakeEnvironment(),
            client=FakeStagedChangeSetClient(),
        )

        checks = {
            check["name"]: check
            for check in artifact["candidates"][0]["scenarios"][0]["checks"]
        }

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(checks["admin_change_set_not_staged"]["status"], "failed")

    def test_admin_config_bootstrap_scenario_requires_canonical_change_set(self) -> None:
        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_config_bootstrap",),
            ),
            environment=FakeEnvironment(),
            client=FakeConversationClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}
        scenario_prompt = SCENARIOS["admin_config_bootstrap"].message

        self.assertEqual(scenario["id"], "admin_config_bootstrap")
        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertIn("propose_admin_config_bootstrap directly", scenario_prompt)
        self.assertNotIn("Read the current Admin Config first", scenario_prompt)
        self.assertEqual(checks["admin_change_set_present"], "passed")
        self.assertEqual(checks["admin_change_set_uses_canonical_paths"], "passed")
        self.assertEqual(checks["baseline_settings_present"], "passed")
        self.assertEqual(checks["user_types_present"], "passed")
        self.assertEqual(checks["typed_bootstrap_tool_used"], "passed")
        self.assertEqual(checks["onboarding_fields_present"], "passed")
        self.assertEqual(checks["behavior_rules_present"], "passed")
        self.assertEqual(
            scenario["response"]["admin_change_set"]["requests"][1]["path"],
            "/admin/user-types",
        )

    def test_admin_config_live_onboarding_prompt_accepts_current_ui_answer_format(self) -> None:
        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_config_live_onboarding_prompt",),
            ),
            environment=FakeEnvironment(),
            client=FakeConversationClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}
        severities = {check["name"]: check["severity"] for check in scenario["checks"]}
        requests = scenario["response"]["admin_change_set"]["requests"]

        self.assertEqual(scenario["id"], "admin_config_live_onboarding_prompt")
        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertIn("- 1. FreeThem", scenario["request"]["message_preview"])
        self.assertEqual(
            [request["path"] for request in requests],
            ["/admin/settings", "/admin/user-types", "/admin/user-types"],
        )
        self.assertEqual(checks["typed_bootstrap_tool_used"], "passed")
        self.assertEqual(checks["live_onboarding_bootstrap_not_rejected"], "passed")
        self.assertEqual(checks["live_onboarding_baseline_settings_present"], "passed")
        self.assertEqual(checks["live_onboarding_instance_name_preserved"], "passed")
        self.assertEqual(checks["live_onboarding_dark_theme_preserved"], "passed")
        self.assertEqual(checks["live_onboarding_auto_approval_enabled"], "passed")
        self.assertEqual(checks["live_onboarding_user_types_present"], "passed")
        self.assertEqual(severities["live_onboarding_user_type_content_present"], "hard")
        self.assertEqual(checks["live_onboarding_does_not_create_user_fields"], "passed")
        self.assertEqual(checks["live_onboarding_does_not_create_behavior_rules"], "passed")

    def test_admin_config_live_onboarding_prompt_rejects_forbidden_agent_config_writes(
        self,
    ) -> None:
        class FakeForbiddenRulesClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                admin_change_set = dict(result.admin_change_set or {})
                admin_change_set["requests"] = [
                    *(admin_change_set.get("requests") or []),
                    {
                        "method": "PUT",
                        "path": "/admin/ai-config/prompt_forbidden",
                        "body": {"value": json.dumps(["Never discuss legal help."])},
                    },
                ]
                done = dict(result.done)
                done["admin_change_set"] = admin_change_set
                return StreamResult(
                    answer=result.answer,
                    events=result.events,
                    done=done,
                    trace=result.trace,
                    admin_change_set=admin_change_set,
                    timings=result.timings,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_config_live_onboarding_prompt",),
            ),
            environment=FakeEnvironment(),
            client=FakeForbiddenRulesClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(
            checks["live_onboarding_does_not_create_behavior_rules"], "failed"
        )

    def test_admin_config_live_onboarding_prompt_requires_separate_user_type_entries(
        self,
    ) -> None:
        class FakeCombinedUserTypeClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                admin_change_set = dict(result.admin_change_set or {})
                admin_change_set["requests"] = [
                    {
                        "method": "PUT",
                        "path": "/admin/settings",
                        "body": {
                            "instance_name": "FreeThem",
                            "assistant_name": "Liberty",
                            "header_tagline": "political prisoners support team",
                            "description": "World Liberty Congress support team",
                            "primary_color": "#2563EB",
                            "default_theme": "dark",
                            "default_language": "en",
                            "auto_approve_users": True,
                        },
                    },
                    {
                        "method": "POST",
                        "path": "/admin/user-types",
                        "body": {
                            "name": "Families, current prisoners, former prisoners, and aftercare",
                            "description": "Combined malformed catch-all type.",
                        },
                    },
                    {
                        "method": "POST",
                        "path": "/admin/user-types",
                        "body": {
                            "name": "General Supporter",
                            "description": "Unrelated second type.",
                        },
                    },
                ]
                done = dict(result.done)
                done["admin_change_set"] = admin_change_set
                return StreamResult(
                    answer=result.answer,
                    events=result.events,
                    done=done,
                    trace=result.trace,
                    admin_change_set=admin_change_set,
                    timings=result.timings,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_config_live_onboarding_prompt",),
            ),
            environment=FakeEnvironment(),
            client=FakeCombinedUserTypeClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(checks["live_onboarding_user_type_content_present"], "failed")

    def test_admin_config_live_onboarding_prompt_fails_when_bootstrap_is_rejected(self) -> None:
        class FakeRejectedBootstrapClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                return StreamResult(
                    answer="I apologize, but I wasn't able to generate a response.",
                    events=result.events,
                    done={
                        "model": "kimi-k2-6",
                        "provider": "sage",
                        "tools_used": [
                            {
                                "tool_id": "admin-config:propose_admin_config_bootstrap",
                                "tool_name": "Admin Config",
                                "status": "guarded",
                                "output_summary": (
                                    "Invalid bootstrap proposal: setup_notes must "
                                    "include numbered setup answer 1."
                                ),
                                "warnings": ["invalid_admin_config_bootstrap"],
                                "guarded": True,
                            }
                        ],
                    },
                    trace={
                        "tools": [
                            {
                                "id": "admin-config:propose_admin_config_bootstrap",
                                "name": "Admin Config",
                                "status": "guarded",
                                "warnings": ["invalid_admin_config_bootstrap"],
                                "guarded": True,
                            }
                        ]
                    },
                    admin_change_set=None,
                    timings=result.timings,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_config_live_onboarding_prompt",),
            ),
            environment=FakeEnvironment(),
            client=FakeRejectedBootstrapClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(checks["live_onboarding_bootstrap_not_rejected"], "failed")
        self.assertEqual(checks["admin_change_set_present"], "failed")

    def test_admin_config_bootstrap_scenario_fails_without_typed_bootstrap_tool(self) -> None:
        class FakeGenericBootstrapClient(FakeConversationClient):
            def stream_chat(self, token: str, payload: dict, timeout: float) -> StreamResult:
                result = super().stream_chat(token, payload, timeout)
                done = dict(result.done)
                done["tools_used"] = [
                    {
                        "tool_id": "admin-config:propose_config_change_set",
                        "tool_name": "Admin Config",
                        "output_summary": "Proposed change set: Bootstrap FreeThem",
                    }
                ]
                trace = {
                    "tools": [
                        {
                            "id": "admin-config:propose_config_change_set",
                            "name": "Admin Config",
                        }
                    ]
                }
                return StreamResult(
                    answer=result.answer,
                    events=result.events,
                    done=done,
                    trace=trace,
                    admin_change_set=result.admin_change_set,
                    timings=result.timings,
                )

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_config_bootstrap",),
            ),
            environment=FakeEnvironment(),
            client=FakeGenericBootstrapClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertEqual(checks["typed_bootstrap_tool_used"], "failed")
        self.assertEqual(
            checks["generic_change_set_tool_not_used_for_bootstrap"], "failed"
        )

    def test_user_knowledge_assistance_records_retrieval_evidence(self) -> None:
        env = FakeEnvironment()
        client = FakeConversationClient()

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("user_knowledge_assistance",),
                seed_knowledge=True,
            ),
            environment=env,
            client=client,
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertTrue(env.seeded_knowledge)
        self.assertEqual(client.last_token, "user-token")
        self.assertEqual(client.last_payload["tools"], ["knowledge-search"])
        self.assertEqual(client.last_payload["job_ids"], ["bench-knowledge-fixture"])
        self.assertEqual(scenario["id"], "user_knowledge_assistance")
        self.assertEqual(scenario["actor"], "user")
        self.assertEqual(checks["knowledge_search_behavior_recorded"], "passed")
        self.assertEqual(checks["retrieval_evidence_recorded"], "passed")
        self.assertEqual(scenario["retrieval_evidence"][0]["title"], "Post-Release First Day Safety.md")

    def test_admin_database_direct_select_requires_executed_redacted_query(self) -> None:
        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_database_direct_select",),
            ),
            environment=FakeEnvironment(),
            client=FakeConversationClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertEqual(scenario["id"], "admin_database_direct_select")
        self.assertEqual(scenario["actor"], "admin")
        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertEqual(checks["db_query_tool_used"], "passed")
        self.assertEqual(checks["db_query_was_executed"], "passed")
        self.assertEqual(checks["db_query_results_redacted_from_trace"], "passed")

    def test_admin_database_natural_language_request_records_guardrail(self) -> None:
        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("admin_database_natural_language_guardrail",),
            ),
            environment=FakeEnvironment(),
            client=FakeConversationClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertEqual(scenario["id"], "admin_database_natural_language_guardrail")
        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertEqual(checks["db_query_guardrail_recorded"], "passed")
        self.assertEqual(checks["db_query_not_executed_from_natural_language"], "passed")

    def test_curated_resource_referral_seeds_resource_fixture(self) -> None:
        env = FakeEnvironment()
        client = FakeConversationClient()

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("user_curated_resource_referral",),
                seed_resources=True,
            ),
            environment=env,
            client=client,
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertTrue(env.seeded_resources)
        self.assertEqual(client.last_token, "user-token")
        self.assertEqual(client.last_payload["tools"], ["curated-resources"])
        self.assertEqual(
            scenario["fixtures"]["resources"]["resource_ids"],
            ["conversation-bench-global-legal"],
        )
        self.assertEqual(checks["curated_resources_tool_used"], "passed")
        self.assertEqual(checks["curated_resource_found"], "passed")
        self.assertEqual(checks["answer_surfaces_vetted_resource"], "passed")

    def test_combined_assistance_records_knowledge_and_curated_resources(self) -> None:
        env = FakeEnvironment()
        client = FakeConversationClient()

        artifact = run_bench(
            BenchOptions(
                api_base="http://127.0.0.1:18000",
                scenarios=("user_knowledge_and_resource_assistance",),
                seed_knowledge=True,
                seed_resources=True,
            ),
            environment=env,
            client=client,
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        checks = {check["name"]: check["status"] for check in scenario["checks"]}

        self.assertTrue(env.seeded_knowledge)
        self.assertTrue(env.seeded_resources)
        self.assertEqual(
            client.last_payload["tools"],
            ["knowledge-search", "curated-resources"],
        )
        self.assertEqual(client.last_payload["job_ids"], ["bench-knowledge-fixture"])
        self.assertEqual(checks["knowledge_search_behavior_recorded"], "passed")
        self.assertEqual(checks["curated_resources_tool_used"], "passed")
        self.assertEqual(checks["answer_combines_safety_and_referral"], "passed")

    def test_warning_only_user_findings_do_not_fail_the_run(self) -> None:
        artifact = run_bench(
            BenchOptions(
                scenarios=("user_knowledge_assistance",),
                seed_knowledge=False,
            ),
            environment=FakeEnvironment(),
            client=FakeWarningOnlyClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]

        self.assertEqual(scenario["summary"]["status"], "passed")
        self.assertEqual(artifact["candidates"][0]["summary"]["status"], "passed")
        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertEqual(
            {warning["name"] for warning in artifact["summary"]["warnings"]},
            {
                "first_trace_or_tool_feedback_present",
                "knowledge_search_behavior_recorded",
                "retrieval_evidence_recorded",
                "answer_present_with_practical_guidance",
            },
        )

    def test_scenario_stream_errors_are_recorded_as_hard_failures(self) -> None:
        artifact = run_bench(
            BenchOptions(scenarios=("admin_deployment_readiness",)),
            environment=FakeEnvironment(),
            client=FakeFailingClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertIn("connection closed", scenario["response"]["stream_error"])
        self.assertEqual(
            scenario["summary"]["hard_failures"][0]["name"],
            "stream_completed_without_error",
        )

    def test_generic_generation_failure_answer_fails_even_with_valid_payload(self) -> None:
        artifact = run_bench(
            BenchOptions(scenarios=("admin_config_bootstrap",)),
            environment=FakeEnvironment(),
            client=FakeGenericFailureAnswerClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]
        hard_failures = {failure["name"] for failure in scenario["summary"]["hard_failures"]}

        self.assertEqual(artifact["summary"]["status"], "failed")
        self.assertIn("does_not_emit_generic_generation_failure", hard_failures)
        self.assertTrue(scenario["response"]["admin_change_set"])

    def test_slow_first_answer_is_warning_only(self) -> None:
        artifact = run_bench(
            BenchOptions(scenarios=("admin_deployment_readiness",)),
            environment=FakeEnvironment(),
            client=FakeSlowFirstAnswerClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]

        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertEqual(
            {warning["name"] for warning in scenario["summary"]["warnings"]},
            {"first_answer_under_30s"},
        )

    def test_slow_trace_feedback_is_warning_only(self) -> None:
        artifact = run_bench(
            BenchOptions(scenarios=("admin_deployment_readiness",)),
            environment=FakeEnvironment(),
            client=FakeSlowTraceFeedbackClient(),
        )

        scenario = artifact["candidates"][0]["scenarios"][0]

        self.assertEqual(artifact["summary"]["status"], "passed")
        self.assertEqual(
            {warning["name"] for warning in scenario["summary"]["warnings"]},
            {"first_trace_or_tool_feedback_under_10s"},
        )

    def test_explicit_model_candidates_switch_verify_and_restore_local_sage(self) -> None:
        env = FakeEnvironment()

        artifact = run_bench(
            BenchOptions(
                scenarios=("admin_deployment_readiness",),
                models=("gpt-oss-120b", "gemma4-31b"),
            ),
            environment=env,
            client=FakeConversationClient(),
        )

        self.assertEqual(
            [candidate["model"] for candidate in artifact["candidates"]],
            ["gpt-oss-120b", "gemma4-31b"],
        )
        self.assertEqual(env.switched_models, ["gpt-oss-120b", "gemma4-31b"])
        self.assertEqual(env.verified_models, ["gpt-oss-120b", "gemma4-31b"])
        self.assertEqual(env.health_waits, 2)
        self.assertEqual(env.restored_models, ["kimi-k2-6"])


if __name__ == "__main__":
    unittest.main()
