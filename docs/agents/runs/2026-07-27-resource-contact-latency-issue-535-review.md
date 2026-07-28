# Review Packet

## Issue

- Issue: #535 — Ground contact follow-ups in a fresh Curated Resources call
- Slice type: Sage model-planning and final-answer contract
- Acceptance criteria: fresh `find_resources` decision for enabled contact follow-ups; recent-context carry-forward; fresh-result-only final contact details; English/Spanish contact cues; disabled Tool Set boundary; public Conversation seam coverage
- Baseline: Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`; parent `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0`
- Current diff: `git -C runtime/sage diff 14de20d2c378ac9af91e26378bd2c488a9b54faa...72a766db998971aa62975624203f1c76cf7e0061`

## Implementation Summary

When Curated Resources is enabled, Sage now receives an explicit model-planning policy requiring a fresh `find_resources` decision for current email, phone, URL/website, address, secure-channel, and equivalent contact requests—including Spanish follow-ups. The policy tells the model to carry organization, jurisdiction, language, and help type from recent Conversation context into the Tool arguments. Final-answer mode is explicitly restricted to contact details returned by the fresh Tool result and must honestly report a missing contact. The policy is omitted when the Tool Set is disabled, preserving authorization.

## Implementation Evidence

- `implement` session: yes
- `tdd` used: yes
- Red test, if applicable: `curated_resources_contact_followups_require_fresh_grounding_in_both_modes` initially failed on the missing fresh-call policy text
- Green implementation, if applicable: same test and full Sage suite pass after adding the policy
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
STANDARDS_STATUS: pass with residual test-environment limitation
STANDARDS_FINDINGS:
- Fixed: expanded the runtime-profile test to cover English and Spanish email, phone, website/URL, address, secure-channel cues and disabled-policy absence.
- Judgment call retained: the fresh-call/context sentence appears in both the model-visible Tool description and runtime policy because those are separate authorization/planning scopes.

SPEC_STATUS: pass with residual test-environment limitation
SPEC_FINDINGS:
- Fixed: strengthened planning and final-answer policy for all required contact modalities, recent Conversation context, fresh-result-only grounding, honest no-match wording, and no deterministic router.
- Residual: this isolated run cannot execute live `/llm/chat` or `/llm/chat/stream` with a real provider and Postgres; existing Sage Tool-loop and Resource Tool tests pass, but route-level multi-turn replay remains for an environment with those services.
```
