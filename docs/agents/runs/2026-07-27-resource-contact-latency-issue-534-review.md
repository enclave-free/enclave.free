# Review Packet

## Issue

- Issue: #534 — Find precise Curated Resources with honest bounded results
- Slice type: backend + Sage public contract
- Acceptance criteria: query/offset request and response metadata; exact/hybrid matching and ranking; ready/scope/help/language/curation filters; honest bounded Tool output; completeness-safe final-answer instructions; public seam tests
- Baseline: parent `133ca477e17d19ce8637a043fdec147f1a200a7e`; Sage `a33e5903f775e5da627eac4269371622a2f1bf99`
- Current diff: `git diff 133ca477e17d19ce8637a043fdec147f1a200a7e...HEAD`

## Implementation Summary

The Enclave Control Plane Resource Directory lookup now accepts a free-text query and continuation offset, ranks exact normalized IDs/names/contact values ahead of partial and description matches, and returns complete page metadata while preserving existing curation filters. Sage forwards the new arguments and tells the model when a page is partial or complete, with final-answer instructions that prohibit unsupported exhaustive claims.

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
STANDARDS_STATUS: changes_requested
STANDARDS_FINDINGS:
- Fixed: updated `docs/internal-agent-contract.md`, `docs/tools.md`, and Sage architecture contract notes for query/offset and metadata semantics.
- Fixed: removed obsolete list-response compatibility fallback and required Sage page metadata fields so stale contracts fail clearly.
- Fixed: corrected issue-session terminology to private contract / Enclave Control Plane.
- Judgement calls retained: typed metadata value object and extracting query candidate fields are future cleanup opportunities; no behavior risk in this slice.

SPEC_STATUS: changes_requested
SPEC_FINDINGS:
- Fixed: scoped phone-digit exact matching to phone fields, organization punctuation normalization to names, and removed partial resource-ID matching.
- Fixed: stated fresh contact lookup requirement directly in the `find_resources` Tool contract.
- Fixed: required metadata fields so completeness cannot silently default to complete.
- Added public-contract coverage for exact ID/name/phone/URL/secure-channel/address, description fallback, pagination, and final pages.
```
