> Release follow-up: see [RELEASE-0.4.21.md](RELEASE-0.4.21.md) for the combined copy review, final rollout status, and rollback record. The preparation notes below are historical.

# LIBERATOR release preparation

Status: prepared locally; not deployed. The Instance name is **LIBERATOR**, all caps. The live public Instance Settings already report that name. The existing tagline remains “Empowering Families of Political Prisoners.”

Keep using `temp/px-demo-wlc-visual-only`. The internal `px` file names, CSS classes, fixture variables, and Compose override name are historical identifiers, not displayed product names. Renaming those interfaces would add churn to a temporary patch and its rollback procedure.

## Changes in this revision

| Before | After |
| --- | --- |
| PX brand label and browser title | LIBERATOR in all caps, including initial HTML and cached-settings initialization |
| PX favicon | Local LIBERATOR “L” favicon at `/demo-branding/liberator.svg`; old PX SVG removed |
| Large two-letter name sizing | Responsive sizing for the longer name; explicit left-to-right wordmark in RTL interfaces |
| Header expected to fit on one line | Branded header controls can wrap at narrow widths; verified at 320px |
| Fixture used PX Instance Settings | Fixture now uses LIBERATOR, matching current live public settings |
| PX screenshots and verification | New evidence under `screenshots/liberator/`; original screenshots retained as history |

The signup page's subtitle reads the actual Instance name through the existing configuration. No changes to `UserAuth.tsx`, security/privacy notices, translation files, email templates, backend behavior, or stored Instance Settings are part of this rename.

## Sign-in copy checkpoint

The user is revising the intimidating security copy separately. No such edits were present in this worktree when preparation began. Before deployment:

1. Identify the final copy commit/worktree and bring it into the intended release only when available.
2. Review the combined sign-in page and translations, including mobile layout.
3. Rebuild the final frontend image and record its immutable image ID. The currently prepared image predates those copy changes.

Do not mark the content checkpoint complete from these screenshots: they intentionally show the existing copy. This is a readiness record, not a request to rewrite the user's copy.

## Verification

- Enabled and disabled Vite/TypeScript builds pass.
- Title/favicon tests pass and confirm the display name does not overwrite cached Instance Settings.
- Browser verification covers the full existing flow, LIBERATOR header at 320px, mobile and RTL layouts, and disabled/original-baseline rollback with the current LIBERATOR Instance name.
- The production Docker image is built as `enclave-frontend:liberator-wlc-prepared`, image ID `sha256:af0fc6ae40f411f56e808b80e472e492e34a78ac40a293211d6f5f2a64ccac7e`.
- All 82 files / 490 frontend tests passed. The local production container passed its health check and served LIBERATOR HTML and the new favicon. The local image is ARM64; build on the deployment host or target its architecture for rollout. The repository's full pre-commit checks run using the documented Git-environment isolation wrapper; see [the original hook issue](VERIFICATION.md#commit-hook-environment-issue).

Current screenshots: [signup desktop](screenshots/liberator/after-signup-desktop.png), [signup mobile](screenshots/liberator/after-signup-mobile-light.png), [320px chat header](screenshots/liberator/after-chat-mobile-320.png), [Arabic RTL](screenshots/liberator/after-signup-mobile-rtl.png). [Structured browser results](screenshots/liberator/browser-results.json).

## Rollback after the rename

The [deployment/rollback runbook](README.md) still applies. Retain the actual frontend image running immediately before deployment; the earlier PX baseline is not a substitute for that host-specific capture.

Operational rollback restores the generic frontend appearance and removes the temporary favicon. **LIBERATOR remains the name**, because the name is already in live Instance Settings. This visual patch does not restore the old PX name or alter email identity. Any future copy commit must be included explicitly in the deployment record so the chosen rollback image's copy is clear.

For source removal, revert the rename application commit `574179a` first, then `8889acc`. Keep the documentation commits as the historical reference. The original [application manifest](application-manifest.json) describes `8889acc`; the rename commit provides its small follow-up delta.

The current live host image, deployment time, and live rollback test remain unrecorded because no deployment was performed. Record them at activation, after the copy checkpoint and final visual review.
