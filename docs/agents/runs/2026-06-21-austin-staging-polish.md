# Austin Staging Polish Run Ledger

## Run

- Run ID: 2026-06-21-austin-staging-polish
- Loop: plebdev feature-dev
- Target repo: enclave-free/enclave.free-prototype
- Base branch: staging
- Feature branch: feature/austin-staging-polish
- Human owner: Austin
- Started: 2026-06-21 17:19:53 CDT
- Current status: implemented locally; verification passed; preparing commit, push, and staging PR
- Skill setup status: present; AGENTS.md points to GitHub Issues, triage labels, and domain docs

## Goal

Turn Austin's working-session notes into clean PRDs and tracer-bullet issues, then implement the Austin-owned executable slices end-to-end on a non-draft PR targeting staging.

## Current Evidence

- origin/staging was fast-forwarded to origin/main at 84a8f7c before the feature branch was created.
- Issues #388 and #389 are open and labeled needs-triage.
- Fresh staging already includes Admin Test & Feedback scaffolding, session logs, per-turn thumbs feedback storage, and test-user/impersonation surfaces from the staging sync.
- Reliability inclusion decision: Issues #388 and #389 are included in the Austin staging work rather than deferred or treated as out-of-band follow-up.
- PRD structure decision: Use one Austin PRD for this staging work, with sections for Admin Experience, Beta Chat Logs, Resource Directory polish, Email identity, and Reliability fixes #388/#389.
- Thumbs feedback decision: Thumbs up/down feedback is existing staging context/background, not a new Austin deliverable. Austin's beta-review scope is encrypted session logging and review/export visibility.
- Austin corrected scope: no curated resource doc dropper/importer for this pass.
- Resource Directory decision: keep the current manual Resource Directory form for now. Do not build PDF, spreadsheet, or candidate-extraction import flows in the Austin PRDs.
- Manual Resource Directory polish decision: include both better Admin Dashboard/navigation entry points and small copy/layout polish on the existing manual form, without changing the Resource Directory data model.
- Admin navigation/dashboard decision: Keep the Admin Dashboard broadly like the current dashboard, but make it much simpler and primarily about navigation options.
- Admin dashboard copy decision: Remove or heavily reduce safety setup, setup notifications, readiness noise, and overly verbose explanatory copy for this pass because onboarding will be white-glove.
- Admin navigation clarity decision: Admin sidebar, admin chat, user chat, and simulated/test-user chat must be explicitly labeled so admins always know where they are and how to get back to the main Admin Dashboard.
- Admin context labels decision: Use `Admin Dashboard`, `Admin Assistant`, `User Preview`, and `Test User Session` as the plain labels for the main admin-side contexts.
- Admin back-navigation decision: Replace generic admin-side `Back to chat` language with destination- or mode-specific navigation. Use `Back to Admin Dashboard` for admin pages and reserve chat language only for literal chat destinations such as `Admin Assistant`.
- Refresh/no-refresh decision: After onboarding/admin setup applies changes, the admin should land in or remain on the dashboard with the new state visible without needing a manual browser refresh or seeing `refresh recommended` copy.
- Email identity decision: Magic-link emails should use the instance's real public name instead of hardcoded `Enclave`. Default to `instance_name`, and allow a configurable public email display name through Instance Settings/admin configuration when different wording is needed.
- Onboarding assistant tool decision: During onboarding/setup, the Admin Assistant should only use the narrow admin-configuration toolset. Broader tools belong in the full Admin Assistant after setup.
- Onboarding assistant UI decision: The onboarding/setup chat should hide or remove advanced admin-chat controls such as the environment checkbox and tool selection so it feels like a seamless setup chat rather than the full admin console.
- Beta chat-log decision: `Dump encrypted chat logs` is not merely an export/navigation affordance. The beta requirement is that user chat sessions are saved to the SQLite database and encrypted to the admin Nostr key.
- Beta chat-log coverage decision: Save both real beta user chat sessions and admin-created `Test User Session` chats, but mark test/admin-generated sessions clearly so they are not confused with real beta-user evidence.
- Beta chat-log access decision: Include a minimal in-app list/export surface for beta review, and ensure the encrypted saved records are also visible in their stored form through Database Explorer.
- Existing docs define Resources as structured SQLite Resource Directory records, separate from uploaded Document Library Retrieval.
- Implementation completed on feature/austin-staging-polish:
  - Simplified Admin Dashboard into navigation-first Admin Workflows, Settings, Data & Content, and Operations sections.
  - Made admin return links explicit with `Back to Admin Dashboard` and kept chat wording only for actual chat contexts.
  - Hid onboarding setup chat refresh/tool/secret controls and suppressed refresh-recommended copy after onboarding Apply.
  - Added magic-link email identity resolution: optional `public_email_display_name`, falling back to `instance_name`, with Instance Settings control.
  - Persisted encrypted session-log ciphertext in SQLite, deduplicated real user logs by Sage session id, and allowed session log tables in Database Explorer.
  - Added Sage user-session log posting for user chat/query paths and marked Test/User sources in the beta-log UI.
  - Fixed #388 by replacing the false empty-response apology with a reviewable-change-set confirmation.
  - Fixed #389 by serializing Qdrant collection creation and treating benign already-exists races as success.

## Verification

- Backend focused unittests: `.venv/bin/python -m unittest backend.tests.test_session_logs backend.tests.test_internal_session_logs backend.tests.test_magic_link_enumeration backend.tests.test_sql_safety backend.tests.test_store_minimized_payload backend.tests.test_user_audit_coverage` — 30 passed.
- Sage runtime tests: `cargo test -p sage-core --lib` — 68 passed.
- Frontend focused tests: `npm run test -- AdminSetup.test.tsx AdminInstanceConfig.test.tsx AdminResourcesDirectory.test.tsx FeedbackView.test.tsx` — 9 passed.
- Frontend production build: `npm run build` — passed; Vite emitted the existing large-chunk warning.
- Frontend dev smoke: `curl -I http://127.0.0.1:5174/` — 200 OK.

## Durable Artifacts

- CONTEXT updates: none yet
- ADRs: none yet
- PRD issue: #407
- Slice issues: #408, #409, #410, #411, #412, #388, #389
- Issue sessions: pending
- Agent briefs: pending
- Review packets: pending
- Local CodeRabbit report: pending
- PR URL: pending

## Commands

- Install: frontend: npm install; backend dependencies are container/runtime managed
- Typecheck: frontend: npm run build
- Test: backend: python3 -m pytest backend/tests; frontend: npm run verify:pre-commit
- Build: docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build
- Visual verification: local frontend at http://localhost:5173 or Compose-served app, with browser checks for touched admin/user flows

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #408 Simplify Admin Dashboard and admin-side navigation | AFK | implemented | pending | none known | yes |
| #409 Focused onboarding setup chat and no-refresh Apply | AFK | implemented | pending | none known | yes |
| #410 Magic-link email identity from Instance Settings | AFK | implemented | pending | none known | yes |
| #411 Encrypted beta Conversation logs | AFK | implemented | pending | none known | yes |
| #412 Manual Resource Directory discoverability/form polish | AFK | implemented | pending | none known | yes |
| #388 Sage false apology after successful Admin Change Confirmation | AFK | implemented | pending | none known | yes |
| #389 Document Ingestion Qdrant collection race | AFK | implemented | pending | none known | yes |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| none yet | | | | |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| pending | pending | pending | pending | pending | pending |

## Open Questions

- Austin work is captured in one PRD issue (#407) with implementation slices #408, #409, #410, #411, #412, #388, and #389.
- Austin scope excludes curated resource doc dropper/import. Resource Directory remains manual-form only for now.
- Austin scope includes small Resource Directory navigation/copy/form polish only; no Resource Directory importer or data-model changes.
- Austin scope includes simplifying the current Admin Dashboard, making admin-side navigation state explicit, and ensuring every admin destination has an obvious path back to the main Admin Dashboard.
- Austin scope includes using the agreed context labels: `Admin Dashboard`, `Admin Assistant`, `User Preview`, and `Test User Session`.
- Austin scope includes replacing confusing generic `Back to chat` affordances with explicit admin-context navigation.
- Austin scope includes removing the onboarding/setup manual-refresh step and making the dashboard reflect applied setup state directly.
- Austin scope includes correcting magic-link email identity so emails no longer hardcode `Enclave` and can use a configurable public name.
- Austin scope includes simplifying the onboarding/setup assistant UI by hiding full-admin controls and keeping only the focused setup chat experience.
- Austin scope includes durable encrypted beta chat-session logging: save user chat sessions in SQLite encrypted to the admin Nostr key.
- Austin scope includes encrypted logging for both real user chats and marked `Test User Session` chats.
- Austin scope includes minimal encrypted chat-log review/export plus Database Explorer visibility for the saved encrypted records.
- Austin scope does not include new thumbs up/down feedback work beyond ensuring beta chat-session logs carry enough context for review.
- Current staging already contains the ninth onboarding question, config-only onboarding assistant tools, Test & Feedback scaffolding, session logs, per-turn thumbs feedback, test users, and encrypted session-log export.

## Escalations

- None.
