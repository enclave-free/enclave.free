#!/usr/bin/env python3
"""Fail closed on npm audit findings except narrowly documented exceptions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}

# EX-024: Enclave is a browser-only Vite SPA and does not use React Router's
# React Server Components / Framework action path. GitHub lists 8.3.0 as the
# first patched version, but that version is not published as of 2026-07-28.
# Remove this entry when https://github.com/enclave-free/enclave.free/issues/541
# is resolved.
ALLOWED_ADVISORIES = {
    ("react-router", "GHSA-qwww-vcr4-c8h2", 1124282),
}


def _at_or_above_threshold(severity: object, threshold: str) -> bool:
    rank = SEVERITY_RANK.get(str(severity).casefold())
    if rank is None:
        return True
    return rank >= SEVERITY_RANK[threshold]


def _advisory_id(url: object) -> str:
    value = str(url or "").rstrip("/")
    return value.rsplit("/", 1)[-1] if value else ""


def evaluate_audit(
    report: object, threshold: str = "high"
) -> tuple[list[str], list[str]]:
    """Return (unexpected findings, accepted exceptions) for an npm v2 report."""
    if not isinstance(report, dict):
        return ["npm audit report is not a JSON object"], []
    if report.get("error"):
        return [f"npm audit error: {report['error']}"], []

    vulnerabilities = report.get("vulnerabilities")
    if not isinstance(vulnerabilities, dict):
        return ["npm audit report is missing the vulnerabilities object"], []

    unexpected: list[str] = []
    accepted: list[str] = []
    unexpected_packages: set[str] = set()
    wrappers: list[tuple[str, list[str], str]] = []

    for package, raw_vulnerability in vulnerabilities.items():
        if not isinstance(raw_vulnerability, dict):
            unexpected.append(f"{package}: malformed vulnerability entry")
            unexpected_packages.add(package)
            continue

        severity = str(raw_vulnerability.get("severity", "unknown")).casefold()
        via = raw_vulnerability.get("via", [])
        if not isinstance(via, list):
            unexpected.append(f"{package}: malformed via list")
            unexpected_packages.add(package)
            continue

        leaf_findings = [item for item in via if isinstance(item, dict)]
        references = [item for item in via if isinstance(item, str)]

        for finding in leaf_findings:
            finding_severity = str(finding.get("severity", severity)).casefold()
            if not _at_or_above_threshold(finding_severity, threshold):
                continue

            dependency = str(finding.get("dependency") or package)
            identifier = _advisory_id(finding.get("url"))
            source = finding.get("source")
            key = (dependency, identifier, source)
            label = f"{dependency} {identifier or source} ({finding_severity})"
            if key in ALLOWED_ADVISORIES:
                accepted.append(label)
            else:
                unexpected.append(label)
                unexpected_packages.add(package)

        if references and _at_or_above_threshold(severity, threshold):
            wrappers.append((package, references, severity))
        elif not via and _at_or_above_threshold(severity, threshold):
            unexpected.append(f"{package}: unclassified {severity} vulnerability")
            unexpected_packages.add(package)

    changed = True
    while changed:
        changed = False
        for package, references, severity in wrappers:
            if package in unexpected_packages:
                continue
            missing_reference = any(reference not in vulnerabilities for reference in references)
            if missing_reference or any(reference in unexpected_packages for reference in references):
                unexpected.append(
                    f"{package}: {severity} vulnerability via {', '.join(references)}"
                )
                unexpected_packages.add(package)
                changed = True

    return sorted(set(unexpected)), sorted(set(accepted))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path, help="npm audit --json output")
    parser.add_argument(
        "--threshold", choices=tuple(SEVERITY_RANK), default="high"
    )
    args = parser.parse_args()

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Frontend dependency audit could not be read: {exc}")
        return 2

    unexpected, accepted = evaluate_audit(report, args.threshold)
    for finding in accepted:
        print(f"Accepted documented exception: {finding}")
    if unexpected:
        print("Unexpected frontend dependency audit findings:")
        for finding in unexpected:
            print(f"- {finding}")
        return 1

    print(f"No unaccepted {args.threshold} or critical frontend advisories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
