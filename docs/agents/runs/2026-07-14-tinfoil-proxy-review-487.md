# Review Packet — Issue #487

## Issue

- Issue: [#487](https://github.com/enclave-free/enclave.free/issues/487)
- Slice type: AFK tracer bullet
- Acceptance criteria: supported standalone proxy, preserved internal contract, explicit host validation, strict non-stream integrity, existing health/stream behavior, aligned docs/env
- Baseline: `67d36eb`
- Current diff: `git diff 67d36eb...d5f3237`

## Implementation Summary

Operators now get the supported pinned standalone Tinfoil proxy by default, and the normal reset/smoke flow rejects truncated or structurally invalid non-streaming completions while retaining gateway and streaming verification.

## Implementation Evidence

- `implement` session: `/root/ticket_487`
- `tdd` used: yes
- Red test: deprecated Compose image, no truncation detector, and no provider-integrity reset step were each observed before implementation
- Green implementation: four focused tests, strict Python/shell checks, Compose config, real GLM 5.2 non-streaming integrity, and 17-event SSE stream passed
- Refactor: repeated test runner extracted; smoke entry point centralized
- Commands run: recorded in the issue session artifact

## Reviewer Output

```text
STANDARDS_STATUS: pass
STANDARDS_FINDINGS:
- Fixed stale gateway port documentation.
- Fixed incomplete skip-smoke help.
- Removed duplicated test subprocess setup.

SPEC_STATUS: pass
SPEC_FINDINGS:
- None.
```
