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
- Green implementation, if applicable: both rendered Compose contracts pass; five live HTTP contract checks pass against the Apple-built production image; the BusyBox-compatible health probe passes in-container; user and admin routes render without overlays, Vite/HMR scripts, or matching console messages
- Refactor, if applicable: none beyond the deployment packaging required by the ticket
- Commands run: `python3 scripts/tests/DEPLOYMENT/test_frontend_compose_contract.py`; `scripts/test_frontend_runtime.sh apple`; `cd frontend && npx tsc --noEmit`; `cd frontend && npm run build`; `cd frontend && npm test` (76 files, 419 tests); `git diff --check`

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
STANDARDS_STATUS: pass
STANDARDS_FINDINGS:
- None after fixes. The frontend guide now identifies the repository-root working directory, and the runtime script validates once before installing one runtime adapter.

SPEC_STATUS: pass
SPEC_FINDINGS:
- None after fixes and primary-session browser verification. The smoke executes the configured probe, verifies Apple running state, and waits for Docker healthy state.
- Against `enclave-frontend-ticket-507:local`, the language-selection and Admin Setup/Nostr interfaces rendered with no overlay, no `/@vite/client`, one hashed production script, and zero Vite/WebSocket/HMR console messages.
```

## Local CodeRabbit

- Round: `docs/agents/runs/2026-07-17-production-frontend-serving-coderabbit-local-507.md`
- Result: four findings addressed; none dismissed
- Major fix: all frontend health paths now use the BusyBox-compatible `wget -q --spider` probe and the rebuilt Apple image passes it in-container
- Minor fixes: asset 404s no longer receive immutable caching; the dev command contract is exact; the bind-mount documentation names `frontend/`
