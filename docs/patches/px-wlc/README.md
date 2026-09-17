# Temporary LIBERATOR / WLC visual patch

Customer accepted; deployed and verified. Main integration authorized **2026-09-17**. Last audited **2026-09-17**. This is the authoritative patch index; earlier release/preparation documents are historical.

| Item | Current state |
| --- | --- |
| Integration | `main`; patch history retained on `temp/px-demo-wlc-visual-only` |
| Deployed application source | `b8f1625da5c1198af2dda52cf19aec083575e363` |
| Generic base | `v0.4.25` (`5dbd822f02dd0694a5178ef9001b93eb12f8e9a9`) |
| Scope | Temporary frontend presentation for the one demo Instance |
| Build selector | `VITE_DEMO_BRAND=wlc` |
| Product / team | **LIBERATOR** / **by Political Prisoners Support Team** |
| Organization credit | Official white World Liberty Congress logo on entry pages |
| Live audit | Current frontend image healthy; approved appearance retained |

The owner explicitly authorized integrating the accepted patch and documentation into `main` on 2026-09-17, superseding the original branch-isolation instruction. Branding remains opt-in through `VITE_DEMO_BRAND=wlc`; default builds do not activate the WLC identity or palette. The protection-card removal is an unconditional presentation change and therefore also reaches default builds. The historical `px` module names, CSS prefix and Compose names deliberately remain stable. No backend, authentication, database schema, email delivery or saved Instance Settings change belongs to this patch.

## Start here

- [Rollback and source removal](ROLLBACK.md): distinguish color-only rollback, full generic restore, and permanent source removal.
- [Current manifest](current-manifest.json): immutable source/base, complete application file inventory, tested revert order and image identities.
- [Closeout and verification](CLOSEOUT.md): acceptance, evidence, limitations, and lessons for configurable branding.
- [Entry redesign](ITERATION-2.md) and [application color alignment](COLOR-ALIGNMENT.md): final implementation rationale.
- [Current verification evidence](evidence/accepted/): palette, public browser, asset fingerprints and pixel comparisons.

## Final behavior

Language selection and signup/login explicitly opt into the blue entry layout. Its pale form card stays light in either theme. Admin, profile, verification, approval and other task pages use standard widths and compact branding; they do not inherit the promotional panel. Application light colors match the entry card; dark colors use coordinated blue surfaces. Theme and language preferences remain functional.

The short magic-link explanation remains. The verbose sign-in protection card is removed on this branch. This removal is independent of the build selector: disabling branding alone does **not** restore that card. Full source removal or the prepared generic image restores the generic 0.4.25 frontend, including that card.

The Vite transform writes the demo marker/title before first paint. Metadata wrappers affect displayed title/favicon without rewriting stored settings. CSS is scoped to `data-demo-brand="wlc"`; unknown nonempty selectors fail the build. A running nginx environment change cannot toggle a compiled frontend. Switching images requires browser reload; open tabs may retain old code or request old lazy chunks until refreshed.

## Complete application inventory

See the manifest for exact paths. Compared with generic 0.4.25, the patch touches 21 application/build files:

| Files | Responsibility |
| --- | --- |
| `frontend/src/branding/{pxDemo.ts,pxDocument.ts,PxBrand.tsx,PxWelcome.tsx,pxDemo.css,pxDemo.test.ts}` | Selector, identity, metadata, entry shell, scoped colors/layout and tests |
| `frontend/public/demo-branding/{liberator.svg,entry-background.svg,wlc-white.svg}` | Local favicon, original decorative background and official WLC logo |
| `frontend/src/components/onboarding/OnboardingCard.tsx` and `.test.tsx` | Explicit entry opt-in, standard task-page layout and scope tests |
| `frontend/src/components/shared/{InstanceLogo.tsx,AppHeader.tsx}` | Compact identity |
| `frontend/src/context/InstanceConfigContext.tsx`, `frontend/src/main.tsx` | Display metadata wrappers and stylesheet import |
| `frontend/src/pages/{UserAuth.tsx,UserOnboarding.tsx}` | Entry opt-in and protection-card removal |
| `frontend/index.html`, `frontend/vite.config.ts`, `frontend/Dockerfile` | First-paint metadata and build selector |
| `docker-compose.px-wlc.yml` | Frontend-only opt-in build override |

No package or lockfile changes. Patch documents and synthetic verification tools are under this directory; original research is in `docs/wlc-demo-branding-plan.md`. Retain these as historical/prototype reference when removing application code.

## Reproduce checks

From the repository root:

```bash
npm ci --prefix frontend
(cd frontend && VITE_DEMO_BRAND=wlc npm run build -- --outDir /tmp/px-wlc-enabled-dist --emptyOutDir)
(cd frontend && VITE_DEMO_BRAND= npm run build -- --outDir /tmp/px-wlc-disabled-dist --emptyOutDir)
npm run test --prefix frontend
npm install --prefix /tmp/px-wlc-browser-tools playwright@1.63.0
npx --prefix /tmp/px-wlc-browser-tools playwright install chromium
node docs/patches/px-wlc/fixture-server.mjs
```

In another terminal:

```bash
node docs/patches/px-wlc/verify-browser-v2.mjs
node docs/patches/px-wlc/verify-keyboard.mjs
node docs/patches/px-wlc/verify-entry-polish.mjs
node docs/patches/px-wlc/evidence/accepted/verify-colors.mjs
```

The fixture binds to localhost port 4178, serves compiled assets with synthetic accounts/API responses, and does not send mail. Never deploy the fixture. Stop it after checks. The older `verify-browser.mjs` and original baseline screenshots describe the first iteration; use v2 for the accepted layout. Generated screenshots/results may change during reruns; review them before committing.

## Future deployments and maintenance

Capture the running frontend image, source, health, exact ordered Compose files and non-frontend container inventory before replacing it. Retain the image and a `docker save` archive. Use the existing Compose project/environment and frontend-only `up -d --no-deps --no-build frontend`; do not recreate the backend. Apply the intended frontend image override last. Record new immutable image/source values and refresh rollback evidence after every deployment.

When advancing releases on main, rerun enabled/disabled checks and review any changes to patch-owned files. Prepare an updated unbranded rollback image from the intended release, explicitly deciding whether to retain the protection-card removal. The 0.4.25 removal proof does not establish compatibility with a future backend. Keep the current release overrides and operator backups until the patch has been retired and verified.

## Historical records

[Original research](../../wlc-demo-branding-plan.md), [initial analysis](ANALYSIS.md), [initial verification](VERIFICATION.md), [rename preparation](LIBERATOR.md), [0.4.21 rollout](RELEASE-0.4.21.md), [0.4.22 backend follow-up](RELEASE-0.4.22.md), [protection-card removal](AUTH-CARD-REMOVAL.md), [earlier attribution](WLC-ATTRIBUTION.md), and [iteration plan](ITERATION-2-PLAN.md) preserve decisions and evidence from their dates. The older `application-manifest.json`, `liberator-rename-manifest.json` and `release-manifest.json` are historical snapshots, not current rollback instructions.
