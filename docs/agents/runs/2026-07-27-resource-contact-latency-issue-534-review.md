# Review Packet

## Issue

- Issue: #534 — Find precise Curated Resources with honest bounded results
- Slice type: backend + Sage public contract
- Acceptance criteria: query/offset request and response metadata; exact/hybrid matching and ranking; ready/scope/help/language/curation filters; honest bounded Tool output; completeness-safe final-answer instructions; public seam tests
- Baseline: parent `133ca477e17d19ce8637a043fdec147f1a200a7e`; Sage `a33e5903f775e5da627eac4269371622a2f1bf99`
- Current diff: `git diff 133ca477e17d19ce8637a043fdec147f1a200a7e...HEAD`

## Implementation Summary

Resource Directory lookup now accepts a free-text query and continuation offset, ranks exact normalized IDs/names/contact values ahead of partial and description matches, and returns complete page metadata while preserving existing curation filters. Sage forwards the new arguments and tells the model when a page is partial or complete, with final-answer instructions that prohibit unsupported exhaustive claims.

## Implementation Evidence

- `implement` session: yes
- `tdd` used: yes
- Red test, if applicable: backend metadata/query contract and Sage forwarding/partial-page assertions initially failed
- Green implementation, if applicable: targeted backend and Sage tests pass
- Refactor, if applicable: no unrelated refactor
- Commands run: targeted backend test file; targeted Sage web runtime tests; Sage cargo check; cargo fmt check; git diff checks

## Review Instructions

Review only issue #534's slice against the issue and PRD. Keep standards and spec findings separate. Apply repository standards in `AGENTS.md`, `CONTEXT.md`, and the documented smell baseline from `code-review`.

## Reviewer Output

```text
STANDARDS_STATUS: pending
STANDARDS_FINDINGS:
- pending

SPEC_STATUS: pending
SPEC_FINDINGS:
- pending
```
