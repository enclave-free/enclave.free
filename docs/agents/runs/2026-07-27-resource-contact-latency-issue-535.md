# Issue

- Issue: #535 — Ground contact follow-ups in a fresh Curated Resources call
- Fixed point before session: parent `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0`; Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`
- Worker session: `/root/ticket_535_model_eval`
- Commit: Sage `6a7cde839e55d283fa02a033e90fe8f708f34d7b`; parent eval `2e3db4ac53aae31f36350b72957c80a5ee46c7b4`; parent pointer/records are the closeout commit for this ticket
- Status: complete; fresh standards/spec review findings resolved

## Inputs

- Spec issue: #535, parent #533, and PRD `docs/agents/runs/2026-07-27-curated-resource-contact-latency-prd.md`
- Ticket: #535
- Relevant glossary terms: User Conversation, Curated Resource, Resource Directory, Tool Set, Tool
- Relevant ADRs: 0023, 0024, 0027
- Prototype answer and source branch, if any: None

## Implementation

- Public interface used: Sage's real `SageAgent`/`run_agent_turn` Conversation seam with the real `FindResourcesTool`, local OpenAI-compatible provider boundary, and local Resource Directory stub; the durable Compose eval exercises `/llm/chat` and `/llm/chat/stream`
- Behaviors covered: typed fresh contact lookup decision with organization/jurisdiction/language/help-type context; fresh-result-only final contact grounding against deliberately stale prose; honest no-match wording; disabled Curated Resources authorization boundary; batch/stream answer parity; English and Spanish contact cues
- `tdd` used: yes — a red runtime-profile contract test was added before the policy implementation, then greened in one vertical slice
- Commands run during implementation:
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib curated_resources_contact_followups_require_fresh_grounding_in_both_modes -- --nocapture`
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib`
  - `cargo check -p sage-core --bin enclave_web`
  - `cargo fmt --all -- --check`
- Full suite command: `cargo test -p sage-core --lib` (121 tests, passing); `cargo check -p sage-core --bin enclave_web`; `cargo fmt --all -- --check`; `git -C runtime/sage diff --check`. Eval asset checks: `python3 -m unittest scripts/tests/test_curated_resource_contact_model_eval.py` (5/5), `python3 -m py_compile scripts/tests/TOOLS/test_5h_curated_resource_contact_model_eval.py`, and `--help`. The model-backed Compose run is implemented and scheduled for #539 on the completed local stack.

## Review

- Review fixed point: Sage `6a7cde839e55d283fa02a033e90fe8f708f34d7b`; parent eval `2e3db4ac53aae31f36350b72957c80a5ee46c7b4`
- Standards status: pass after fresh review; shared Tool-description/runtime wording is deliberate model-visible contract reinforcement.
- Spec status: pass after fresh review; the real replay covers independent English/Spanish contexts, five modalities, stale→fresh grounding, empty/disabled boundaries, sender modes, and stream/batch deltas. The Compose asset covers the public routes and ephemeral fixture cleanup.
- Worthy fixes applied: replaced the initial boundary-only evidence with a real Sage planner/parser/tool/final-answer replay; added a durable model-backed Compose eval with per-case stale resets, context-free followups, pre-registered session IDs, and verified cleanup.
- Accepted boundary: the local replay provider is a deterministic boundary mock permitted by the issue; live provider quality and full-stack execution are tracked for #539 rather than claimed as run here.

## Risks

- The policy guides model Tool planning; it does not add a deterministic classifier or force Tool execution. The model-backed Compose eval is executable but requires the configured provider and completed local stack; it is scheduled for #539.
