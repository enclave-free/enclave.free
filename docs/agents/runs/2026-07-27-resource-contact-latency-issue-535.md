# Issue

- Issue: #535 — Ground contact follow-ups in a fresh Curated Resources call
- Fixed point before session: parent `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0`; Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`
- Worker session: `/root/ticket_535`
- Commit: Sage `829c8df311dc6bc5da34250959b33e6d3d885ab3`; parent `6fa1da3bfe224f34869b68916a1a5e94e2ba0fed` (pointer/records)
- Status: complete; review findings resolved at the accepted shared orchestration seam

## Inputs

- Spec issue: #535, parent #533, and PRD `docs/agents/runs/2026-07-27-curated-resource-contact-latency-prd.md`
- Ticket: #535
- Relevant glossary terms: User Conversation, Curated Resource, Resource Directory, Tool Set, Tool
- Relevant ADRs: 0023, 0024, 0027
- Prototype answer and source branch, if any: None

## Implementation

- Public interface used: Sage's shared `run_turn_with_adapters` Conversation orchestration seam directly beneath `/llm/chat` and `/llm/chat/stream`; `find_resources` Tool contract
- Behaviors covered: typed fresh contact lookup decision with organization/jurisdiction/language/help-type context; fresh-result-only final contact grounding against deliberately stale prose; honest no-match wording; disabled Curated Resources authorization boundary; batch/stream answer parity; English and Spanish contact cues
- `tdd` used: yes — a red runtime-profile contract test was added before the policy implementation, then greened in one vertical slice
- Commands run during implementation:
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib curated_resources_contact_followups_require_fresh_grounding_in_both_modes -- --nocapture`
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib`
  - `cargo check -p sage-core --bin enclave_web`
  - `cargo fmt --all -- --check`
- Full suite command: Sage full library suite above (122 tests, passing). Parent Python/frontend suites were not rerun because this slice changes only Sage prompt/Tool contract text and its Sage tests.

## Review

- Review fixed point: Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`; parent `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0`
- Standards findings: behavioral eval concern resolved with four shared-seam tests; the fresh policy is repeated in the Tool description and runtime instruction as deliberate model-visible contract reinforcement (judgment-call duplication retained)
- Spec findings: route-level test request superseded by the agreed seam: `run_turn_with_adapters` is the shared orchestration directly beneath `/llm/chat` and `/llm/chat/stream`; tests now validate follow-up input/context, typed selection, fresh grounding, empty results, disabled authorization, and stream/batch parity
- Worthy fixes applied: added behavior tests through the shared Conversation orchestration seam and made the planner fake validate the actual follow-up/context input before selecting `find_resources`
- Findings ignored with reasons: direct HTTP handler instantiation would require unavailable Postgres/provider state and would duplicate the accepted shared seam; no production or external state was authorized

## Risks

- The policy guides model Tool planning; it does not add a deterministic classifier or force Tool execution. Tests use deterministic boundary fakes at the shared orchestration seam, so real-provider quality remains an operational concern rather than an untested product path.
