#!/usr/bin/env python3
"""Create/apply full-context reviews; optionally calibrate a Tinfoil judge first."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.benches.quality_measurements import (
    JUDGE_INSTRUCTION,
    RUBRIC,
    blind_evidence,
    build_review_packet,
    fingerprint,
    load_calibration_fixture,
    measure_artifact,
    resource_artifact,
)


def judge_packet(packet: dict[str, Any], call: Callable[[dict[str, Any]], dict[str, Any]], *, model: str, reasoning_effort: str) -> dict[str, Any]:
    calibration = load_calibration_fixture()
    results = []
    for case in calibration["cases"]:
        dimensions = call(case["evidence"])
        passed = isinstance(dimensions, dict) and all(
            isinstance(dimensions.get(name), dict) and dimensions[name].get("status") == expected
            for name, expected in case["expected"].items()
        )
        results.append({"id": case["id"], "passed": passed, "dimensions": dimensions})
        if not passed:
            raise ValueError(f"judge calibration failed: {case['id']}; no run reviews accepted")
    calibration_record = {
        "fixture_hash": fingerprint(calibration), "rubric_hash": packet["rubric_hash"],
        "instruction_hash": fingerprint(JUDGE_INSTRUCTION), "model": model,
        "reasoning_effort": reasoning_effort, "cases": results,
        "limitation": "Passing these adversarial controls does not establish expert validity or judge independence.",
    }
    reviewed = copy.deepcopy(packet)
    reviewed["calibration"] = calibration_record
    for entry in reviewed["entries"]:
        entry["dimensions"] = call(blind_evidence(entry["evidence"]))
        entry.update(reviewer=model, method="calibrated_model", reviewed_at=datetime.now(timezone.utc).isoformat(), calibration_hash=fingerprint(calibration_record))
    return reviewed


def tinfoil_judge(base: str, model: str, effort: str, timeout: float) -> Callable[[dict[str, Any]], dict[str, Any]]:
    parsed = urlsplit(base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("judge URL must be a loopback HTTP endpoint for your verified Tinfoil proxy")
    import httpx
    token = os.environ.get("LLM_API_KEY") or os.environ.get("TINFOIL_API_KEY")
    if not token:
        raise ValueError("LLM_API_KEY or TINFOIL_API_KEY is required for opt-in judging")
    def call(evidence: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(base.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {token}"}, json={
                "model": model, "reasoning_effort": effort, "temperature": 0,
                "max_tokens": 4096, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": JUDGE_INSTRUCTION + "\n" + json.dumps(RUBRIC)}, {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}],
            }, timeout=timeout, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise ValueError(f"judge request failed: {type(exc).__name__}") from None
        if response.status_code != 200:
            raise ValueError(f"judge returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except (TypeError, ValueError):
            raise ValueError("judge returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise ValueError("judge returned a non-object response")
        choices = payload.get("choices") or []
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) or choices[0].get("finish_reason") != "stop":
            raise ValueError("judge did not complete a JSON verdict")
        try:
            content = choices[0]["message"]["content"]
            verdict = json.loads(content)
        except (KeyError, TypeError, ValueError):
            raise ValueError("judge returned an invalid JSON verdict") from None
        if not isinstance(verdict, dict):
            raise ValueError("judge returned a non-object verdict")
        return verdict
    return call


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("template", "apply", "judge"))
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-api-base", default="http://127.0.0.1:18089/v1")
    parser.add_argument("--reasoning-effort", choices=("low", "high", "max"), default="low")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        artifact = json.loads(args.artifact.read_text())
        if artifact.get("schema") == "curated-resource-contact-evidence-v3":
            artifact = resource_artifact(artifact)
        if not artifact.get("candidates"):
            raise ValueError("expected a modern Conversation artifact with candidates; historical evidence needs explicit adaptation")
        if args.output.resolve() in {args.artifact.resolve(), args.review.resolve() if args.review else args.artifact.resolve()}:
            raise ValueError("write a new output file; never overwrite original evidence/review")
        if args.action == "template":
            result = build_review_packet(artifact)
            status = "unreviewed"
        elif args.action == "judge":
            if not args.judge_model:
                raise ValueError("--judge-model is required; no external judge runs by default")
            if args.judge_model in {c.get("model") for c in artifact["candidates"]}:
                raise ValueError("select a judge model different from all evaluated models")
            result = judge_packet(build_review_packet(artifact), tinfoil_judge(args.judge_api_base, args.judge_model, args.reasoning_effort, args.timeout), model=args.judge_model, reasoning_effort=args.reasoning_effort)
            status = measure_artifact(artifact, result)["semantic_review"]["status"]
        else:
            if not args.review:
                raise ValueError("--review is required")
            result = {**artifact, "measurements": measure_artifact(artifact, json.loads(args.review.read_text()))}
            status = result["measurements"]["release_gate"]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        print(f"Review status: {status}; output: {args.output}")
        return 0 if args.action == "template" or status == "passed" else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
