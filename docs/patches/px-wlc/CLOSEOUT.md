# Accepted patch closeout — 2026-09-17

The customer accepted the entry design and the application color alignment. Application source remains `b8f1625`; this closeout changes documentation/evidence only. The live frontend was re-inspected as healthy at its recorded immutable image. No running service, saved setting or account was changed during documentation cleanup.

## Verification retained

- Frontend production build and 493 tests across 83 files passed for the deployed application revision.
- Entry iteration: 14 synthetic browser flows, enabled/disabled builds, RTL/mobile, task-page layout and same-browser disabled-brand switching passed.
- Color follow-up: shared light palette, dark adaptation, text/link/action contrast, actual dark-action edge, admin/chat/settings, 320px fit and no uncaught browser errors passed using isolated fixtures.
- Keyboard checks cover eight auth controls, focus visibility and the language menu.
- Seven read-only live browser checks passed; 61 public build files matched the deployed container by SHA-256.
- Desktop language selection, desktop signup, mobile signup and dark-preference mobile signup screenshots were pixel-identical before/after color alignment.
- A generic 0.4.25 frontend image was built and checked healthy in a separate container; HTTP delivery and absence of demo marker/assets passed. Both generic and accepted images are archived with verified gzip integrity. Guarded restore scripts passed shell syntax and resolved-image/build-selector checks. The check container was removed.
- Full source-removal sequence applied without conflicts in an isolated checkout, with zero difference from generic 0.4.25 across all application/build patch paths.

Machine-readable color/live/assets/pixel evidence and the reusable color-check script are in [evidence/accepted](evidence/accepted/). Entry screenshots are in [screenshots/iteration-2](screenshots/iteration-2/). Full operator logs and before/after screenshots remain in the workspace `docs/releases/wlc-color-alignment/`; deployment backups and restore scripts also live on the server as recorded in [ROLLBACK.md](ROLLBACK.md).

Authenticated admin/chat/settings checks used synthetic fixture data. Live browser checks did not send email, sign Nostr challenges, create users or exercise authenticated production flows. No live rollback was performed; source reversal, retained images/archive integrity and rollback configuration were checked without changing the accepted site.

## What was cleaned up

The patch index now names the accepted deployed source and generic base. Earlier plans, preparation notes and release manifests are explicitly historical. The file inventory includes the second iteration assets, entry callers and tests. Rollback distinguishes the previous color palette from full generic restoration. The whole removal sequence includes all follow-ups, preserves generic release merges, and documents that an empty build selector leaves the independent protection-card removal in place.

## Lessons for the configurable frontend

| Observation | Capability to carry forward |
| --- | --- |
| A shared onboarding wrapper leaked the large hero onto admin/task pages. | Explicit entry-layout selection with standard task layouts as the default. |
| Independent landing/application palettes drifted. | Shared semantic color roles, with scoped entry theme and coordinated dark adaptation. |
| Product, team and organization are different credits. | Separate product wordmark, team attribution and organization-logo fields. |
| Shadow removal suppressed focus; dark navy buttons needed a visible edge. | Focus and contrast checks that inspect actual rendered controls in both themes. |
| Build-time branding requires redeployment; saved settings remain generic. | Preview/publish/versioned restore for appearance settings, with clear ownership of theme/language preferences. |
| Historical rollback notes became misleading after follow-ups. | One authoritative current manifest and runbook, with immutable source/image identities and dated historical records. |

The patch remains a reference implementation, not the future configuration system. No extra dependencies, database migration, backend changes or runtime WLC asset requests were introduced. Retain the design/evidence after retiring source customization.

## Main integration — 2026-09-17

The owner subsequently requested that the accepted patch and documentation be integrated into `main` and local/remote branches synchronized. This supersedes the original requirement to keep the patch off main. Main integration preserves the accepted application tree and the opt-in build selector. The independent protection-card removal also becomes part of default builds; all other branding remains gated. No release tag or deployment is required for this source synchronization. The immutable `b8f1625` application revision, v0.4.25 rollback base and retained images remain the rollback reference.
