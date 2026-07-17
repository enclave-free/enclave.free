# Review Packet — Issue #507

## Issue

- Issue: [#507](https://github.com/enclave-free/enclave.free/issues/507)
- Slice type: AFK tracer bullet
- Acceptance criteria: production static image; stable port and HTTP health; SPA fallback; immutable hashed assets; refreshable entry document without Vite; explicit development override; automated HTTP and Compose checks; frontend regressions green; Apple Containers verification; deployment documentation
- Baseline: `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500`
- Current diff: `git diff 55e5ef4fb1aa3379cedb3923e8480fadb2e6e500...HEAD`

## Implementation Summary

The default frontend now runs a compiled Vite bundle from a small Nginx runtime image. Host port 5173 and direct SPA navigation remain stable, production cache headers distinguish immutable hashed assets from the refreshable entry document, and `/api` stays under the deployment reverse proxy's authority. Contributors opt into Vite, hot reload, and the frontend source mount through a separate Compose override.

## Implementation Evidence

- `implement` session: `/root/frontend_prod_worker`
- `tdd` used: yes, at the pre-agreed built-container HTTP and rendered Compose seams
- Red test, if applicable: the old default lacked the production build target and development override; its live Apple Container response injected `/@vite/client`, exposed no compiled assets, and proxied `/api`
- Green implementation, if applicable: both rendered Compose contracts pass; four live HTTP contract checks pass against the Apple-built production image
- Refactor, if applicable: none beyond the deployment packaging required by the ticket
- Commands run: `python3 scripts/tests/DEPLOYMENT/test_frontend_compose_contract.py`; `scripts/test_frontend_runtime.sh apple`; `cd frontend && npx tsc --noEmit`; `cd frontend && npm run build`; `git diff --check`

## Review Instructions

Review only this issue's slice unless you find a severe cross-slice regression. Keep standards and spec findings separate.

Check:

- Acceptance criteria are met.
- Tests verify behavior through public interfaces.
- No implementation-only tests are masquerading as behavior tests.
- No obvious incomplete work, TODO placeholders, or unrelated changes.
- Relevant test, typecheck, build, or visual verification commands pass.

## Reviewer Output

```text
STANDARDS_STATUS: pending
STANDARDS_FINDINGS:
- Pending the required two-axis review.

SPEC_STATUS: pending
SPEC_FINDINGS:
- Pending the required two-axis review.
```
