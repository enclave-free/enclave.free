# Typed Tool Decisions and Plain Streaming — Issue Session #488

## Issue

- Issue: [#488](https://github.com/enclave-free/enclave.free/issues/488)
- Fixed point before session: Sage `782aaa7`
- Worker session: `/root/ticket_488`, with root integration and review fixes
- Sage commit: `9664b38bbda23315cc3229f5a87740c9eab8af45`
- Status: complete

## Inputs

- Spec issue: [#486](https://github.com/enclave-free/enclave.free/issues/486)
- ADR: `docs/adr/0027-separate-tool-decisions-from-final-answer-delivery.md`
- Ticket: typed, bounded Tool planning followed by plain final-answer generation and real provider deltas
- Relevant glossary terms: Agent Runtime, Tool Set, Conversation Streaming Transport, Conversation Trace, Change Confirmation

## Implementation

- Typed prediction now returns only `ToolDecision` (`tool_calls` plus explicit replan intent).
- The common path plans once, runs all immediately useful Tools, then uses provider-neutral plain generation.
- Tool-free turns skip typed planning; deterministic successful proposal Tools finish without another model call.
- Public streaming uses real provider answer chunks and one ordered trace/answer signal channel.
- Textual and provider-native Tool envelopes are rejected without exposing their structured content; benign JSON, code, citations, and explanatory protocol prose remain streamable.
- Streaming and non-streaming routes share the same bounded turn runner and preserve Tool metadata, trace, persistence, fallback, and Change Confirmation behavior.
- `tdd` used: yes; parser, state-transition, transport ordering, fallback, malformed-output, deterministic-terminal, parity, and provider-stream tests were added before final acceptance.

## Verification

- `cargo test -p sage-core --lib`: 137 passed
- `cargo check -p sage-core --bin enclave_web`: passed
- `cargo fmt --all -- --check`: passed
- `git diff --check`: passed
- Changed-code clippy passed with the repository's six unrelated baseline lints explicitly allowed.

## Review

- Spec and standards reviewers ran repeatedly against the fixed Sage commit.
- Findings fixed: nested Tool text in legacy recovery; textual Tool envelopes split across chunks; conflicting stage prompts; Tool activity ordering; public emission coverage; single/unquoted and args-first envelopes; null optional Tool fields; fallback emission semantics; unified trace/answer ordering; benign structured-prose latency; and incomplete code-fence recursion.
- Final review result: clean; no remaining P0–P2 findings.

## Risks

- Real GLM 5.2 behavior, full public handler `done`/error ordering, and before/after latency evidence remain integration gates in issue #490.
