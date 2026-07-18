# CPU-Only Core Backend Image — Issue Session #509

## Issue

- Issue: [#509](https://github.com/enclave-free/enclave.free/issues/509)
- Fixed point before session: `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500`
- Worker session: `/root/backend_cpu_worker`
- Commit: `f29e0b6`
- Status: complete

## Inputs

- Spec issue: [#508](https://github.com/enclave-free/enclave.free/issues/508)
- Ticket: build and verify a CPU-only core backend image
- Relevant glossary terms: Single-Instance Deployment, Deployment, Document Ingestion
- Relevant ADRs: none
- Prototype answer and source branch, if any: none

## Implementation

- Public interface used: built core image executed through its container command interface
- Behaviors covered: official CPU wheel provenance; pinned Torch/torchvision compatibility; no CUDA runtime or NVIDIA/CUDA distributions; embedding, Transformers, Docling PDF, ingestion, and application imports; unchanged non-root startup; health/Qdrant/Valkey/vector behavior; complete-dependency CI alignment
- `tdd` used: yes; the verifier failed against the existing image before dependency changes and passed against the optimized image
- Red evidence: Torch 2.13.0 exposed CUDA 13.0 and 18 CUDA/NVIDIA distributions
- Green evidence: Torch 2.8.0+cpu, torchvision 0.23.0, no CUDA runtime/distributions, required imports, `pip check`, security audit, health, shared store, and 768-dimension vector smoke passed
- Full suite command: Apple Container execution of `python -m unittest discover -s backend/tests` (387 tests passed)
- Image evidence: the `variants[].size` field from `container image list --format json` reduced from 3,300,590,209 bytes for prior Apple image `apple/enclavefree-core-backend:dev` (`e84b6c0f5a70b564b388c851b4bf1b933bbf658a0b80295016c7ed868078dac0`) to 526,230,016 bytes for the round-1 image `enclavefree-core-backend:cpu` (`a59fd5f8bebddbe86cf998a685f75451de7049c99fe41b7d67a9783435de123f`), an 84.1% like-for-like reduction; the separately observed 9.4 GB v0.4.0 release image is context, not the percentage denominator

## Review

- Review fixed point: `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500`
- Standards findings: none; pass
- Spec findings: none; pass
- Worthy fixes applied: none requested by reviewers
- Findings ignored with reasons: none

## Risks

- `pip-audit` cannot map the official local-version `torch==2.8.0+cpu` distribution to PyPI and reports that package as skipped; the artifact verifier independently enforces the approved exact CPU version and the CI log makes the audit limitation explicit.
