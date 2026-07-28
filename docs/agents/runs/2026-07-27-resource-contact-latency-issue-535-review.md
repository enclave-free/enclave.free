# Review Packet

## Issue

- Issue: #535 — Ground contact follow-ups in a fresh Curated Resources call
- Slice type: Sage model-planning and final-answer contract
- Acceptance criteria: fresh `find_resources` decision for enabled contact follow-ups; recent-context carry-forward; fresh-result-only final contact details; English/Spanish contact cues; disabled Tool Set boundary; public Conversation seam coverage
- Baseline: Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`; parent `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0`
- Current diff: `git -C runtime/sage diff 14de20d2c378ac9af91e26378bd2c488a9b54faa...829c8df311dc6bc5da34250959b33e6d3d885ab3`

## Implementation Summary

When Curated Resources is enabled, Sage now receives an explicit model-planning policy requiring a fresh `find_resources` decision for current email, phone, URL/website, address, secure-channel, and equivalent contact requests—including Spanish follow-ups. The policy tells the model to carry organization, jurisdiction, language, and help type from recent Conversation context into the Tool arguments. Final-answer mode is explicitly restricted to contact details returned by the fresh Tool result and must honestly report a missing contact. The policy is omitted when the Tool Set is disabled, preserving authorization.

## Implementation Evidence

- `implement` session: yes
- `tdd` used: yes — the behavior tests were red before the seam fakes were added, then green
- Red test, if applicable: `curated_resources_contact_followups_require_fresh_grounding_in_both_modes` initially failed on the missing fresh-call policy text
- Green implementation, if applicable: four behavior tests and full Sage suite pass after adding the shared-seam fakes
- Refactor, if applicable: no unrelated refactor
- Commands run: focused Sage test; full `cargo test -p sage-core --lib` (119); `cargo check -p sage-core --bin enclave_web`; `cargo fmt --all -- --check`

## Review Instructions

Review only issue #535's Sage slice against the issue, PRD, ADR-0023/0024/0027, and Sage/parent repository standards. Keep standards and spec findings separate.

Check:

- Acceptance criteria are met without a deterministic intent router.
- Tests verify the enabled/disabled policy through public Conversation instruction seams.
- Final-answer instructions prevent stale assistant prose from supplying current contacts.
- English and Spanish follow-up wording and context carry-forward are explicit.
- No incomplete work, TODO placeholders, or unrelated changes.
- Relevant Sage verification commands pass.

## Reviewer Output

```text
STANDARDS_STATUS: pass
STANDARDS_FINDINGS:
- Fixed: added four behavioral tests through the shared Conversation seam; the planner fake validates the actual follow-up/context input before selecting `find_resources`.
- Judgment call retained: the fresh-call/context wording is intentionally reinforced in both the Tool description and runtime instruction because they are separate model-visible scopes.

SPEC_STATUS: pass
SPEC_FINDINGS:
- Fixed: shared orchestration tests prove typed `find_resources` args retained from the actual follow-up input, stale-vs-fresh contact grounding, honest empty result behavior, disabled authorization, and streaming/non-streaming parity. The seam is directly beneath `/llm/chat` and `/llm/chat/stream`.
- Route-level HTTP tests were not added because the agreed seam avoids unavailable Postgres/provider state without bypassing the Conversation runtime.
```
