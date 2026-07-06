# Issue Session: User Manager Dashboard (#478, #479)

## Scope

- Base: `origin/staging` at `8965caa`.
- Branch: `feature/user-manager-dashboard`.
- Issues: #478 route/table and #479 approval/export actions.
- Rationale for combined session: the table, filters, approve action, roster export, and admin entry point are one end-to-end admin workflow and share one route-level state model.

## Implementation

- Added `/admin/user-manager` as an admin-guarded lazy route.
- Added a User Manager entry on the Admin Setup page.
- Added a new dashboard page backed by existing `/admin/users`, `/admin/user-types`, `/admin/user-fields`, `/users/{id}`, and `/admin/users/roster-export` contracts.
- Added visible metrics, search, approval and User Type filters, profile completion cues, encrypted identity helper states, refresh, approve, and visible-roster export.
- Added English i18n keys; other locales rely on the existing `fallbackLng: 'en'` behavior until real translations exist.

## Verification

- `cd frontend && npm run test -- AdminUserManager App.routing AdminSetup` passed 15 tests.
- `cd frontend && npm run test` passed 72 files / 378 tests.
- `cd frontend && npx prettier --check src/pages/AdminUserManager.tsx src/pages/AdminUserManager.test.tsx src/App.tsx src/App.routing.test.tsx src/pages/AdminSetup.tsx src/pages/AdminSetup.test.tsx src/i18n/locales/en.json` passed.
- `cd frontend && npm run build` passed; generated `frontend/dist/index.html` churn was reverted.
- Browser harness verified desktop table layout and approve interaction against a mock API.

## Review

- Composer review sidecar findings addressed: npub search, live callouts, badge icon hiding, export failure coverage, filtered export assertions, profile cues, and non-English locale cleanup.
- CodeRabbit local: `coderabbit review --agent --type all --base staging` completed with 0 findings.
