# Tinfoil Proxy Integrity — Issue Session #487

## Issue

- Issue: [#487](https://github.com/enclave-free/enclave.free/issues/487)
- Fixed point before session: `67d36eb`
- Worker session: `/root/ticket_487`
- Commit: `d5f323729d99d0102d7fab0aabe76dc1b78486c0`
- Status: complete

## Inputs

- Spec issue: [#486](https://github.com/enclave-free/enclave.free/issues/486)
- Ticket: supported standalone Tinfoil proxy and strict response-integrity smoke
- Relevant glossary terms: Tinfoil, Model Provider, Encrypted Inference, Verifiable Inference
- Relevant ADRs: ADR-0003, ADR-0019, ADR-0027
- Prototype answer and source branch, if any: none; the 2026-07-11 investigation supplied direct failing/passing transport evidence

## Implementation

- Public interface used: default Docker Compose topology and `scripts/smoke_test.sh`
- Behaviors covered: supported pinned proxy image, explicit Docker host allowlist, strict non-stream response framing/JSON/message validation, existing gateway health, real provider streaming
- `tdd` used: yes; Compose contract, truncated-response fixture, and reset-flow tests were red before implementation
- Commands run during implementation: targeted unittest, Python compilation, shell syntax, merged Compose config, real GLM 5.2 non-stream completion, real streaming SSE probe
- Full suite command: parent full-stack suite deferred to blocked integration issue #490; all #487 operator seams passed

## Review

- Review fixed point: `67d36eb`
- Standards findings: stale gateway-port instructions, incomplete `--skip-smoke` help, and duplicated subprocess setup
- Spec findings: none
- Worthy fixes applied: all three standards findings
- Findings ignored with reasons: none

## Risks

- The full fresh-stack Sage/gateway E2E is owned by #490 after all runtime changes land.
