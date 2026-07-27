# Issue

- Issue: #534 — Find precise Curated Resources with honest bounded results
- Fixed point before session: `133ca477e17d19ce8637a043fdec147f1a200a7e`
- Worker session: `/root/ticket_534`
- Commit: parent `698a021192acdf9f1aa4855292034989e2e6b55e`; Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa`; ledger closeout `d37097f00db833ff15a00bd27f8ff1ca2e544c45`
- Status: complete; review findings fixed and verification green

## Inputs

- Spec issue: #533 and PRD `docs/agents/runs/2026-07-27-curated-resource-contact-latency-prd.md`
- Ticket: #534
- Relevant glossary terms: Curated Resource, Resource Directory, Tool, User Conversation
- Relevant ADRs: 0023, 0024, 0027
- Prototype answer and source branch, if any: None

## Implementation

- Private contract seams used: Enclave Control Plane Resource Directory `/internal/agent/resources/search`; Sage `find_resources` Tool execution
- Behaviors covered: normalized exact/hybrid query matching; curation-preserving ranking; offset pagination; count/page metadata; query/offset forwarding; bounded-result and completeness-safe wording
- `tdd` used: yes — backend and Sage public-contract tests were red before implementation, then greened one vertical slice at a time
- Commands run during implementation:
  - `/Users/plebdev/Desktop/Projects/enclave-free/enclave.free/.venv/bin/python -m unittest backend.tests.test_resource_directory`
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib web_runtime::tests`
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo check -p sage-core --bin enclave_web`
  - `cargo fmt --all -- --check`
- Full suite commands:
  - `/Users/plebdev/Desktop/Projects/enclave-free/enclave.free/.venv/bin/python -m unittest discover -s backend/tests -p 'test_*.py'` (423 tests, OK)
  - `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib` (118 tests, OK)

## Review

- Review fixed point: parent `133ca477e17d19ce8637a043fdec147f1a200a7e`; Sage `a33e5903f775e5da627eac4269371622a2f1bf99`
- Standards findings: stale private-contract docs, obsolete compatibility fallback, and terminology corrected
- Spec findings: field-specific exact matching, fresh-call Tool wording, strict metadata contract, and expanded contract tests corrected
- Worthy fixes applied: all hard and medium findings
- Findings ignored with reasons: baseline typed metadata/data-clump smells retained as out-of-scope cleanup; behavior is covered

## Risks

- No ticket-blocking risk remains. A typed page-metadata value object and query-candidate extraction remain optional structural cleanup outside #534; current behavior is covered through the accepted private contract seams.
