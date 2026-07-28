# Issue

- Issue: #535 — Ground contact follow-ups in a fresh Curated Resources call
- Fixed point before session: parent `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0`; Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`
- Worker session: `/root/ticket_535`
- Commit: Sage `72a766db998971aa62975624203f1c76cf7e0061`; parent pointer/records pending
- Status: complete; review findings recorded, with route-level replay residual risk

## Inputs

- Spec issue: #535, parent #533, and PRD `docs/agents/runs/2026-07-27-curated-resource-contact-latency-prd.md`
- Ticket: #535
- Relevant glossary terms: User Conversation, Curated Resource, Resource Directory, Tool Set, Tool
- Relevant ADRs: 0023, 0024, 0027
- Prototype answer and source branch, if any: None

## Implementation

- Public interface used: Sage User Conversation model-planning and plain final-answer prompt seams; `find_resources` Tool contract
- Behaviors covered: fresh contact lookup policy for current requests and follow-ups; organization/jurisdiction/language/help-type context carry-forward; English and Spanish contact cues; fresh-result-only final contact grounding; honest no-match wording; disabled Curated Resources authorization boundary
- `tdd` used: yes — a red runtime-profile contract test was added before the policy implementation, then greened in one vertical slice
- Commands run during implementation:
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib curated_resources_contact_followups_require_fresh_grounding_in_both_modes -- --nocapture`
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib`
  - `cargo check -p sage-core --bin enclave_web`
  - `cargo fmt --all -- --check`
- Full suite command: Sage full library suite above (119 tests, passing). Parent Python/frontend suites were not rerun because this slice changes only Sage prompt/Tool contract text and its Sage tests.

## Review

- Review fixed point: Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`; parent `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0`
- Standards findings: prompt-contract test initially covered only one Spanish email phrase; expanded to cover English/Spanish email, phone, website/URL, address, and secure-channel terms plus disabled-policy absence. A possible duplicated policy wording between the Tool description and runtime instruction is a judgment call because they serve distinct model-visible scopes.
- Spec findings: reviewers noted that local tests do not execute live `/llm/chat` or `/llm/chat/stream` with a provider and Postgres, so they cannot prove model-selected fresh lookup and final-answer value grounding end to end. The test now covers all required modality/language policy terms and the disabled instruction boundary; live route replay remains residual risk.
- Worthy fixes applied: strengthened the shared Curated Resources policy for planning and final-answer modes; added context carry-forward and multilingual modality assertions; preserved the disabled Tool Set boundary.
- Findings ignored with reasons: live route/provider replay was not available in this isolated Sage test environment; no production or external state was authorized. Existing public Tool-loop and `find_resources` contract tests remain green.

## Risks

- The policy guides model Tool planning; it does not add a deterministic classifier or force Tool execution. Real-provider `/llm/chat` and `/llm/chat/stream` replay remains outside this local test environment and is the remaining verification risk.
