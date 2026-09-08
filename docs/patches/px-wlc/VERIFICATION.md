# Verification record

Date: 2026-09-08. Scope: local production bundles, isolated synthetic browser flow, frontend tests, and production Docker image. Live demo access was read-only.

## Baseline

Preparation base: `063e132ce0b77a238cd8bccdd4f36cfd38369eae` (release 0.4.20). All five JavaScript/CSS assets referenced by the live demo's index matched the unmodified local build byte for byte. The exact paths and SHA-256 hashes are in [baseline-assets.json](baseline-assets.json). This verifies public entry assets, not the complete host source tree or running Docker image ID.

Read-only live screenshots: [desktop](screenshots/live-before-desktop.png), [mobile](screenshots/live-before-mobile.png). The local fixture uses a deliberately different purple custom accent to stress the non-persistent override; use rollback screenshots for controlled comparisons rather than expecting its generic color to match the blue live demo.

## Automated results

| Check | Result |
| --- | --- |
| Full default-mode frontend suite, `npm run test` | 82 files, 490 tests passed |
| Enabled-mode auth/onboarding/verification/pending/profile/User Type tests | 6 files, 19 tests passed |
| New display-only title/favicon tests | 2 passed; included in full suite |
| TypeScript + Vite enabled build | Passed |
| TypeScript + Vite disabled build | Passed |
| Unknown non-empty selector | Rejected with explicit configuration error |
| Production Docker frontend build with WLC argument | Passed |
| Compose override resolution | Correct production target, WLC build argument, explicit image tag |
| Production container health and deep-link HTML | Healthy; `/auth` returns PX HTML inside verified container |
| Browser flow and same-browser rollback | Passed; [structured results](browser-results.json) |

The full suite emits expected test-fixture errors/warnings, including intentionally failed routes and a missing Compose secret fixture message, but exits successfully. Builds retain the baseline large-chunk warning; this patch does not address existing bundle size. No runtime dependency or lockfile change was made.

## Browser flow

The repeatable script uses the actual compiled app and a local synthetic API. It covers keyboard focus, initial language selection, saved-language redirect, signup/login tabs, request failure/retry, email sent state, expired/valid verification, pending approval, approved chat, theme toggle, settings access, User Type selection, profile completion, mobile light/dark, Arabic RTL, and Admin entry.

Rollback uses the same browser and origin. It swaps the server to a disabled build and then the original baseline build. It checks the temporary layout/HTML marker/favicon are absent, PX remains the name, the original custom accent returns, and original cached config, User session markers, language, and theme remain. No uncaught browser exceptions occurred. The final disabled-build and original-baseline mobile rollback screenshots were also pixel-identical (390 × 1258).

Screenshot capture waits for fonts and settled rendering. The script checks horizontal overflow at desktop/mobile signup. It uses reduced-motion emulation; the new patch introduces no continuous animation. Visual review confirmed legible focus treatment on the profile field and preserved form labels/data notices.

## Contrast and production image

Calculated contrast for the selected token pairs (WCAG relative luminance): light body text 15.85:1, light muted text on overlay 4.86:1, light link text 6.08:1, light button text 15.85:1, dark muted text on overlay 5.85:1, dark button text 9.44:1. These checks cover key token pairs, not a complete accessibility audit. The four bright decorative colors do not carry text meaning.

Final local production image ID: `sha256:61bff6bd2972e63d33cbe6a16b9e244d0be4e7708f3ca9e1e8cefeb345a3c392`. The named verification container reported healthy and served PX deep-link HTML and the SVG favicon through nginx. It was stopped and removed after verification. No production app services were recreated.

## Commit-hook environment issue

The first commit attempt ran the real repository hook and failed one existing test: `scripts/preCommitHooks.test.ts` inherits Git's hook environment into temporary Git repositories. Its `git add sample.ts` affected this checkout's index instead of the intended fixture. The generated index entry was removed; no fixture file was committed. The same full suite had already passed outside the hook.

For the commit, a temporary hook wrapper under `/tmp/px-wlc-isolated-hooks` unsets `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_PREFIX`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`, and `GIT_ALTERNATE_OBJECT_DIRECTORIES`, then executes the actual `frontend/.husky/pre-commit`. The wrapper is selected only for that `git commit` invocation using `-c core.hooksPath=...`; repository hook configuration is not changed. This runs lint-staged and the full test suite rather than skipping them. The isolated commit hook passed all 82 files / 490 tests. The unrelated test harness is not modified in this visual patch.

## Visual evidence

| Surface | Evidence |
| --- | --- |
| Language / welcome | [Desktop](screenshots/after-language-desktop.png) |
| Signup | [Desktop](screenshots/after-signup-desktop.png), [mobile light](screenshots/after-signup-mobile-light.png), [mobile dark](screenshots/after-signup-mobile-dark.png) |
| Arabic RTL | [Mobile](screenshots/after-signup-mobile-rtl.png) |
| Email states | [Sent](screenshots/after-email-sent.png), [expired](screenshots/after-expired-link.png) |
| Approval | [Pending](screenshots/after-pending.png) |
| User Onboarding | [User Type](screenshots/after-user-type.png), [profile](screenshots/after-profile.png) |
| Conversations | [Light](screenshots/after-chat-light.png), [dark](screenshots/after-chat-dark.png) |
| Settings and Admin | [Settings](screenshots/after-settings-dark.png), [Admin entry](screenshots/after-admin-mobile.png) |
| Rollback | [Disabled build](screenshots/rollback-disabled-mobile.png), [original baseline](screenshots/rollback-baseline-mobile.png) |

## Limits and remaining deployment work

- No live deployment, real email, real account mutation, or Admin signature was performed.
- Browser flow uses synthetic API responses and account details, so it is not server-side authorization or email-delivery verification.
- Chat verification covers layout, entry, settings, and theme; it does not invoke a model or assert generated responses.
- Host Compose project/configuration, current image ID, retained rollback image, and activation time must be recorded before deploying. Follow [the runbook](README.md).
- Existing external font requests remain. New PX artwork and favicon are local; no WLC website dependency was added.
- The configured English tagline stays English in Arabic UI; this is operator content, not a new untranslated control.

## Commit ledger

Plan: `306ce15`. Application patch: `8889acc` (16 application/build files). The following documentation-only commit closes out this verification record; locate it with `git log --oneline 8889acc..HEAD`. Revert `8889acc` to remove the application patch while retaining these records. No changes are pushed or merged by this local implementation task.
