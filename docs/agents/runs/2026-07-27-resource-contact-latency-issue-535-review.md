# Review Packet

## Issue

- Issue: #535 — Ground contact follow-ups in a fresh Curated Resources call
- Slice type: Sage model-planning and final-answer contract
- Acceptance criteria: fresh `find_resources` decision for enabled contact follow-ups; recent-context carry-forward; fresh-result-only final contact details; English/Spanish contact cues; disabled Tool Set boundary; public Conversation seam coverage
- Baseline: Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`; parent eval `2e3db4ac53aae31f36350b72957c80a5ee46c7b4`; Sage final `6a7cde839e55d283fa02a033e90fe8f708f34d7b`
- Current diff: `git -C runtime/sage diff 14de20d2c378ac9af91e26378bd2c488a9b54faa...6a7cde839e55d283fa02a033e90fe8f708f34d7b`

## Implementation Summary

When Curated Resources is enabled, Sage now receives an explicit model-planning policy requiring a fresh `find_resources` decision for current email, phone, URL/website, address, secure-channel, and equivalent contact requests—including Spanish follow-ups. The policy tells the model to carry organization, jurisdiction, language, and help type from recent Conversation context into the Tool arguments. Final-answer mode is explicitly restricted to contact details returned by the fresh Tool result and must honestly report a missing contact. The policy is omitted when the Tool Set is disabled, preserving authorization.

## Implementation Evidence

- `implement` session: yes
- `tdd` used: yes — the policy contract and real replay tests were red before implementation, then green
- Red test, if applicable: the focused contact replay initially failed until independent language/context, modality, stale→fresh, and empty/disabled assertions were added
- Green implementation, if applicable: real Sage replay tests and full 121-test Sage suite pass; the Compose model-backed eval is implemented for #539 execution
- Refactor, if applicable: no unrelated refactor
- Commands run: focused and full `cargo test -p sage-core --lib` (121); `cargo check -p sage-core --bin enclave_web`; `cargo fmt --all -- --check`; `git -C runtime/sage diff --check`; `python3 -m unittest scripts/tests/test_curated_resource_contact_model_eval.py` (5/5); `python3 -m py_compile scripts/tests/TOOLS/test_5h_curated_resource_contact_model_eval.py`; eval `--help`

## Review Instructions

Review only issue #535's Sage slice against the issue, PRD, ADR-0023/0024/0027, and Sage/parent repository standards. Keep standards and spec findings separate.

Check:

- Acceptance criteria are met without a deterministic intent router.
- Tests verify the enabled/disabled policy through the real Sage Conversation seam; the durable Compose asset exercises public `/llm/chat` and `/llm/chat/stream` when the configured stack/provider is available.
- Final-answer instructions prevent stale assistant prose from supplying current contacts.
- English and Spanish follow-up wording and context carry-forward are explicit, with five contact modalities and per-case stale resets.
- No incomplete work, TODO placeholders, or unrelated changes.
- Relevant Sage verification commands pass.

## Reviewer Output

```text
STANDARDS_STATUS: pass
STANDARDS_FINDINGS:
- Fixed: replaced boundary-only evidence with real Sage planner/parser/tool/final-answer replay and added the executable model-backed Compose eval asset.
- Judgment call retained: the fresh-call/context wording is intentionally reinforced in both the Tool description and runtime instruction because they are separate model-visible scopes.

SPEC_STATUS: pass
SPEC_FINDINGS:
- Fixed: real Sage tests prove typed `find_resources` args, independent language/context carry-forward, stale-vs-fresh grounding, honest empty results, disabled authorization, and streaming/non-streaming parity. The Compose asset drives both public routes with ephemeral fixtures and verified cleanup.
- The model-backed Compose run is scheduled for #539 because it requires the completed local stack and configured provider; no live run is claimed here.
```
