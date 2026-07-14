# CodeRabbit Rounds: Admin Agent Latency Critical Path

## Round 1

- Scope: local branch diff against `staging`
- Command: `coderabbit review --agent --type all --base staging`
- Availability: completed
- Findings: 18

### Addressed

- Clarified the `:8000` to `:18000` public-port change and strengthened reset/docs port regressions.
- Scoped benchmark policy-cleanup evidence and date-scoped the historical proxy override with its immutable digest.
- Handled unknown-length chunked `IncompleteRead` failures and added a regression.
- Replaced fabricated fake answer deltas with ordered segments of the real answer.
- Preserved fractional Tool durations until report serialization.
- Derived partial-seed upload cleanup from the container `UPLOADS_DIR`.
- Restored exact Core/Sage policy values and timestamps and retained Core principals if Sage cleanup fails.
- Preserved partial stream evidence on transport loss and converted setup failures into failed artifacts with cleanup.
- Added a zero-retry hard gate for deterministic bootstrap and documented the diagnostics schema.
- Updated the goal ledger and #490 evidence/review records.

### Not Applicable or Not Changed

- The supported proxy image does accept `--allowed-host`; live `0.1.6 --help` and the healthy local service verify it.
- Curated Resources have no User Type scope in the product contract. The benchmark instead uses a unique resource ID and email and hard-requires the run-specific email, preventing another global fixture from producing a false green result. Documentation now states that boundary accurately.

## Result

- Continue: yes
- Escalate: no
- Next: rerun after corrections

## Round 2

- Scope: local branch diff against `staging`
- Command: `coderabbit review --agent --type all --base staging`
- Availability: completed
- Findings: 0
- Result: clean
