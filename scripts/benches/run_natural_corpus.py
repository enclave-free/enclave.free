#!/usr/bin/env python3
"""Run the natural corpus through one isolated synthetic local lifecycle.

This is the supported entry point for a grounded natural-corpus run. It creates
the temporary benchmark identity and fixtures, delegates requests and evidence
capture to ``run_benchmark.py``, and always attempts fixture cleanup.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import run_benchmark
from scripts.benches.conversation_model_bench import LocalComposeEnvironment
from scripts.benches.synthetic_environment import (
    validate_loopback_api_base,
    verify_http_target,
    verify_synthetic_environment,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    config = run_benchmark.load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        default=config.get("backend_url", "http://localhost:18000"),
        help="loopback backend origin",
    )
    parser.add_argument(
        "--model",
        default=config.get("model") or "glm-5-3-flash",
        help="expected model identity",
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def _safe_error(kind: str, exc: BaseException) -> dict[str, str]:
    """Keep lifecycle reports free of arbitrary subprocess or HTTP bodies."""

    return {"kind": kind, "message": f"{kind} failed ({type(exc).__name__})"}


def _single_seed_value(fixture: dict[str, Any], key: str, plural_key: str) -> Any:
    value = fixture.get(key)
    if value is not None:
        return value
    values = fixture.get(plural_key)
    if isinstance(values, list) and len(values) == 1:
        return values[0]
    raise ValueError(f"seed fixture did not return one {key}")


def build_fixture_manifest(
    knowledge_fixture: dict[str, Any] | None,
    resource_fixture: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Reduce seed returns to the exact synthetic facts visible to retrieval."""

    if knowledge_fixture is None and resource_fixture is None:
        return None
    knowledge: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    fixture_version = None
    if knowledge_fixture is not None:
        knowledge.append(
            {
                "job_id": _single_seed_value(knowledge_fixture, "job_id", "job_ids"),
                "source_file": _single_seed_value(knowledge_fixture, "source_file", "sources"),
                "chunk_id": knowledge_fixture["chunk_id"],
                "source_text": knowledge_fixture["source_text"],
            }
        )
        fixture_version = knowledge_fixture.get("fixture_version")
    if resource_fixture is not None:
        values = resource_fixture.get("resources")
        if not isinstance(values, list) or not values or not all(isinstance(value, dict) for value in values):
            raise ValueError("seed fixture did not return complete resource rows")
        resources = values
    return {
        "schema_version": run_benchmark.SYNTHETIC_FIXTURE_SCHEMA,
        "fixture_version": fixture_version or "post-release-v2",
        "knowledge": knowledge,
        "resources": resources,
    }


def _empty_initial_preflight(result: dict[str, Any]) -> bool:
    counts = result.get("counts")
    return bool(
        result.get("eligible") is True
        and isinstance(counts, dict)
        and all(counts.get(key) == 0 for key in ("users", "resources", "documents"))
    )


def _planned_runs(corpus: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    """Represent every planned turn when setup fails before the runner starts."""

    runs: list[dict[str, Any]] = []
    for repeat in range(1, args.repeat + 1):
        for key, session in corpus.get("sessions", {}).items():
            turns = [
                {
                    "turn": turn.get("turn"),
                    "request": {"message": turn.get("user_message", "")},
                    "rubric": turn.get("rubric", {}),
                    "coverage": turn.get("coverage", {}),
                    "history": [],
                    "status": "not_run",
                    "answer": "",
                    "tool_evidence": [],
                    "elapsed_seconds": 0,
                }
                for turn in session.get("turns", [])
            ]
            runs.append(
                {
                    "session_key": key,
                    "session_id": None,
                    "scenario": {
                        "id": session.get("id", key),
                        "name": session.get("name", key),
                        "scenario_type": session.get("scenario_type", "natural"),
                        "review_status": session.get("review_status", "expert_review_pending"),
                        "scenario_hash": run_benchmark.canonical_hash(session),
                        "fixture_version": None,
                    },
                    "requested_tools": run_benchmark.configured_tools(corpus),
                    "model": args.model,
                    "turns": turns,
                    "errors": [{"kind": "not_run", "message": "lifecycle setup failed"}],
                    "counts": {"expected_turns": len(turns), "completed_turns": 0},
                    "completed": False,
                    "semantic_outcome": {"status": "unreviewed"},
                    "elapsed_seconds": 0,
                    "repeat": repeat,
                }
            )
    return runs


def _write_lifecycle_report(
    output: Path,
    *,
    args: argparse.Namespace,
    fixture_manifest: dict[str, Any] | None,
    initial_preflight: dict[str, Any] | None,
    target_verified: bool | None,
    runner_exit_code: int,
    harness_errors: list[dict[str, str]],
) -> None:
    """Persist lifecycle failures beside the canonical runner artifact."""

    try:
        report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    except (OSError, json.JSONDecodeError):
        report = None
    if not isinstance(report, dict) or not isinstance(report.get("artifact"), dict):
        corpus = run_benchmark.load_corpus()
        report = run_benchmark.build_report(
            _planned_runs(corpus, args),
            corpus=corpus,
            metadata={
                "api_base": args.api_base,
                "model_expected": args.model,
                "repeat": args.repeat,
                "tools": run_benchmark.configured_tools(corpus),
            },
            fixture_manifest=fixture_manifest,
        )
    artifact = report["artifact"]
    if harness_errors:
        report["harness_errors"] = list(harness_errors)
        report.setdefault("run", {})["harness_errors"] = list(harness_errors)
        artifact.setdefault("run", {})["harness_errors"] = list(harness_errors)
    report["lifecycle"] = {
        "status": "failed" if harness_errors or runner_exit_code else "passed",
        "initial_preflight": initial_preflight,
        "http_target_verified": target_verified,
        "runner_exit_code": runner_exit_code,
        "harness_errors": list(harness_errors),
    }
    measurements = run_benchmark.measure_artifact(artifact)
    if harness_errors:
        measurements["release_gate"] = "blocked"
    report["measurements"] = measurements
    summary = report.setdefault("summary", {})
    summary["measurements"] = measurements
    if harness_errors:
        summary["harness_errors"] = list(harness_errors)
        summary["transport_errors"] = int(summary.get("transport_errors", 0)) + len(harness_errors)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_lifecycle(
    argv: list[str] | None = None,
    *,
    environment_factory: Callable[[], Any] = LocalComposeEnvironment,
    runner: Callable[[list[str]], int] = run_benchmark.main,
) -> int:
    args = parse_args(argv)
    try:
        args.api_base = validate_loopback_api_base(args.api_base)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.repeat < 1:
        print("--repeat must be at least 1", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"refusing to overwrite existing output: {args.output}", file=sys.stderr)
        return 2

    environment = None
    token_env = "BENCHMARK_AUTH_TOKEN"
    previous_token = os.environ.get(token_env)
    had_previous_token = token_env in os.environ
    token = None
    fixture_manifest = None
    manifest_path: Path | None = None
    initial_preflight = None
    target_verified = None
    runner_exit_code = 1
    harness_errors: list[dict[str, str]] = []
    try:
        environment = environment_factory()
        initial_preflight = verify_synthetic_environment(environment)
        if not _empty_initial_preflight(initial_preflight):
            raise RuntimeError("initial synthetic environment was not empty and eligible")
        target_verified = verify_http_target(environment, args.api_base)
        if not target_verified:
            raise RuntimeError("HTTP target did not bind to the verified local backend")

        corpus = run_benchmark.load_corpus()
        tools = tuple(run_benchmark.configured_tools(corpus))
        token = environment.user_token(tools)
        knowledge_fixture = environment.seed_knowledge() if "knowledge-search" in tools else None
        resource_fixture = environment.seed_resources() if "curated-resources" in tools else None
        fixture_manifest = build_fixture_manifest(knowledge_fixture, resource_fixture)
        if tools and fixture_manifest is None:
            raise RuntimeError("configured source tools did not produce a fixture manifest")
        if fixture_manifest is not None:
            validated = run_benchmark.load_fixture_manifest
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
                manifest_path = Path(handle.name)
                json.dump(fixture_manifest, handle, ensure_ascii=False)
            fixture_manifest = validated(manifest_path)

        os.environ[token_env] = token
        runner_args = [
            "--api-base",
            args.api_base,
            "--model",
            args.model,
            "--repeat",
            str(args.repeat),
            "--output",
            str(args.output),
        ]
        if manifest_path is not None:
            runner_args.extend(["--fixture-manifest", str(manifest_path)])
        runner_exit_code = int(runner(runner_args))
    except Exception as exc:
        harness_errors.append(_safe_error("lifecycle", exc))
    finally:
        if had_previous_token:
            os.environ[token_env] = previous_token or ""
        else:
            os.environ.pop(token_env, None)
        if environment is not None:
            try:
                environment.cleanup_scenario()
            except Exception as exc:
                harness_errors.append(_safe_error("cleanup", exc))
        if manifest_path is not None:
            try:
                manifest_path.unlink(missing_ok=True)
            except OSError:
                pass
        _write_lifecycle_report(
            args.output,
            args=args,
            fixture_manifest=fixture_manifest,
            initial_preflight=initial_preflight,
            target_verified=target_verified,
            runner_exit_code=runner_exit_code,
            harness_errors=harness_errors,
        )

    if harness_errors:
        return 1
    return runner_exit_code


def main(argv: list[str] | None = None) -> int:
    return run_lifecycle(argv)


if __name__ == "__main__":
    raise SystemExit(main())
