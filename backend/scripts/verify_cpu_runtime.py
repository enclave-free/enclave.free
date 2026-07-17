#!/usr/bin/env python3
"""Verify the installed backend runtime is the supported CPU-only artifact."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

from packaging.version import Version


EXPECTED_VERSIONS = {
    "torch": Version("2.8.0"),
    "torchvision": Version("0.23.0"),
}
REQUIRED_IMPORTS = (
    "torchvision",
    "sentence_transformers",
    "transformers",
    "docling",
    "docling.document_converter",
    "docling.datamodel.pipeline_options",
    "docling.datamodel.base_models",
    "ingest",
    "main",
)


def normalized_distribution_name(distribution: importlib.metadata.Distribution) -> str:
    name = distribution.metadata.get("Name", "")
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> int:
    app_path = Path("/app")
    if app_path.is_dir():
        sys.path.insert(0, str(app_path))

    torch = importlib.import_module("torch")
    failures: list[str] = []

    installed_versions = {
        package: Version(importlib.metadata.version(package))
        for package in EXPECTED_VERSIONS
    }
    for package, expected in EXPECTED_VERSIONS.items():
        if Version(installed_versions[package].public) != expected:
            failures.append(
                f"{package} must be {expected}, found {installed_versions[package]}"
            )

    cuda_runtime = torch.version.cuda
    cuda_available = torch.cuda.is_available()
    if cuda_runtime is not None:
        failures.append(f"torch exposes CUDA runtime {cuda_runtime}")
    if cuda_available:
        failures.append("torch reports CUDA is available")

    runtime_distributions = sorted(
        {
            name
            for distribution in importlib.metadata.distributions()
            if (name := normalized_distribution_name(distribution)).startswith(
                "nvidia-"
            )
            or name == "cuda-python"
            or name.startswith("cuda-")
        }
    )
    if runtime_distributions:
        failures.append(
            "CUDA/NVIDIA runtime distributions are installed: "
            + ", ".join(runtime_distributions)
        )

    imported = []
    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
            imported.append(module_name)
        except Exception as error:  # pragma: no cover - exercised in built artifact
            failures.append(f"failed to import {module_name}: {error}")

    evidence = {
        "cuda_available": cuda_available,
        "cuda_runtime": cuda_runtime,
        "forbidden_distributions": runtime_distributions,
        "imports": imported,
        "torch": str(installed_versions["torch"]),
        "torchvision": str(installed_versions["torchvision"]),
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))

    if failures:
        for failure in failures:
            print(f"CPU runtime verification failed: {failure}", file=sys.stderr)
        return 1

    print("CPU runtime verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
