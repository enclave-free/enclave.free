# Temporary LIBERATOR / WLC visual patch

Status: implemented and locally verified; **not deployed**. Branch: `temp/px-demo-wlc-visual-only`.

**LIBERATOR** is now the Instance name (formerly PX). The branch, module names, CSS prefix, and Compose variable names retain `px` so the existing patch history remains stable. WLC supplies the visual reference. This branch is a temporary, organization-specific frontend patch, not a generic Enclave release. Do not merge it into `main` or `staging` as a product-wide branding change.

Current preparation status and renamed screenshots: [LIBERATOR release preparation](LIBERATOR.md). The sign-in security-copy revision is being handled separately by the user and must be reviewed before the live update.

## Documents and evidence

- [Original research and scope](../../wlc-demo-branding-plan.md)
- [Implementation analysis and future customization requirements](ANALYSIS.md)
- [Original PX verification record](VERIFICATION.md)
- [Exact application commit/file manifest](application-manifest.json)
- [Baseline asset fingerprints](baseline-assets.json)
- [Browser verification results](browser-results.json)
- [Screenshots](screenshots/)
- [Local fixture server](fixture-server.mjs) and [repeatable browser checks](verify-browser.mjs)

## Change inventory

Paths below are relative to the repository root. Every application/build file in the patch is listed here.

| File | Change | Removal |
| --- | --- | --- |
| `frontend/src/branding/pxDemo.ts` | Build selector, LIBERATOR name, favicon path | Delete with patch |
| `frontend/src/branding/PxBrand.tsx` | LIBERATOR wordmark treatment with four decorative colors | Delete with patch |
| `frontend/src/branding/PxWelcome.tsx` | Welcome panel with existing Instance tagline, responsive artwork, and form area | Delete with patch |
| `frontend/src/branding/pxDemo.css` | Scoped palette, font stack, navy buttons, welcome layout, dark/mobile/contrast variants | Delete and remove import |
| `frontend/src/branding/pxDocument.ts` | Display-only title/favicon wrappers around existing helpers | Delete; restore original provider imports |
| `frontend/src/branding/pxDemo.test.ts` | Checks temporary metadata does not overwrite config and disabled metadata restores | Delete with patch |
| `frontend/public/demo-branding/liberator.svg` | Original local LIBERATOR favicon | Delete with patch |
| `frontend/src/components/onboarding/OnboardingCard.tsx` | Optional PX welcome shell; existing form children remain intact | Restore baseline component |
| `frontend/src/components/shared/InstanceLogo.tsx` | Optional PX brand treatment | Restore baseline component |
| `frontend/src/components/shared/AppHeader.tsx` | LIBERATOR identity in compact shared header; existing controls retained | Restore baseline component |
| `frontend/src/context/InstanceConfigContext.tsx` | Import display-only title/favicon wrappers; config values and saving remain unchanged | Restore original two imports |
| `frontend/src/main.tsx` | Import scoped stylesheet | Remove added import |
| `frontend/index.html` | LIBERATOR title/favicon first-paint handling when HTML carries explicit demo attribute | Remove temporary block |
| `frontend/vite.config.ts` | Validate build option; set HTML demo attribute/title before render | Remove plugin/selector logic |
| `frontend/Dockerfile` | Build-stage argument/environment for selector | Remove added ARG/ENV |
| `docker-compose.px-wlc.yml` | Explicit frontend-only build override and required image tag | Remove from invocation and delete |

`docs/patches/px-wlc/` holds patch-only records, synthetic verification tools, results, and screenshots. These may be retained as historical/reference material after source removal. `docs/wlc-demo-branding-plan.md` links research to the implemented result. No dependency or lockfile change is required. No backend, authentication, User Approval, database, email, or Conversation logic changed.

## Activation behavior

The build option is `VITE_DEMO_BRAND=wlc`. An empty/unset value is generic mode. Unknown non-empty values fail at Vite startup rather than silently selecting another appearance.

The Vite HTML transform sets `data-demo-brand="wlc"` before the app renders. React selects PX presentation using the same build option. CSS tokens live on `body`, which overrides inherited custom accent values from `html` without changing them. The provider still reads and saves original Instance Settings. The temporary display name and favicon are never written to localStorage or the server.

Changing an environment variable on a running nginx container cannot switch the branding. It is compiled into the frontend. Build/redeploy or restore the retained image, then reload the browser. Already-open tabs retain their loaded version until reload; old lazy-loaded asset URLs may fail if the serving image changed, so refresh after either switch.

The patch does not force a theme, rename email identity, translate the Instance tagline, add membership questions, or change security notices. It preserves the current system/light/dark behavior. Disabled builds may still contain inert scoped CSS and the local favicon file; disabling is an operational rollback, while reverting the source patch removes those files completely.

## Reproduce local verification

From the repository root, install frontend dependencies with `npm ci --prefix frontend`.

```bash
(cd frontend && VITE_DEMO_BRAND=wlc npm run build -- --outDir /tmp/px-wlc-enabled-dist --emptyOutDir)
(cd frontend && VITE_DEMO_BRAND= npm run build -- --outDir /tmp/px-wlc-disabled-dist --emptyOutDir)
```

The original baseline was built from `063e132ce0b77a238cd8bccdd4f36cfd38369eae` into `/tmp/px-wlc-baseline-dist`. To recreate it later, make a separate detached worktree at that commit, install its frontend dependencies, and build to that path. Do not check out the baseline over uncommitted patch work.

Install isolated browser tools (no application dependency changes):

```bash
npm install --prefix /tmp/px-wlc-browser-tools playwright@1.63.0
npx --prefix /tmp/px-wlc-browser-tools playwright install chromium
node docs/patches/px-wlc/fixture-server.mjs
```

In a second terminal, from the repo root:

```bash
node docs/patches/px-wlc/verify-browser.mjs
```

The fixture binds only to `127.0.0.1:4178`. It serves the actual production frontend bundles with synthetic API responses and `example.test` account details. It does not proxy to the live demo or send emails. Stop it with Ctrl-C when done. Never deploy this fixture. It intentionally uses a purple custom Instance color to test that the PX appearance overrides display without overwriting cached settings.

Run `npm run test --prefix frontend` for the default-mode suite. The verification record includes enabled-mode targeted tests. Docker build verification uses:

```bash
docker build --target production --build-arg VITE_DEMO_BRAND=wlc \
  -t enclave-frontend:px-wlc-local-verification frontend
```

## Demo deployment procedure — not yet executed

These commands are a runbook template, not a claim of deployment. Before activation, record the actual host, Compose project, complete base Compose file list, source commit, and current image in the deployment record below. Use the existing project's identity; a different project name can create a parallel stack or conflict with fixed container names.

1. Verify the reviewed patch commit and compare the running demo baseline. All five entry assets matched the preparation base during this task; host image identity is still unverified.
2. Retain the running frontend image by immutable ID. On the demo host:

```bash
PX_ROLLBACK_ID=$(docker inspect --format '{{.Image}}' enclave-frontend)
docker image tag "$PX_ROLLBACK_ID" enclave-frontend:px-before-wlc
```

Save the ID and tag in an operator-local deployment record. Do not prune this image while the patch is in use. For resilience against host image cleanup, save it with `docker image save` to an operator-managed backup location before rollout.

3. In Bash, define `PX_BASE` as an array containing the **verified existing** Compose invocation, including its `-p` project and all its base `-f` files. Use absolute file paths if the patch source checkout is separate. Do not print a complete rendered Compose config because it may contain secrets. For example, the invocation shape is:

```bash
PX_BASE=(docker compose -p "$PX_COMPOSE_PROJECT" -f "$PX_INFRA_FILE" -f "$PX_APP_FILE")
```

Add all actual host overrides to that array, in their original order. Ensure the resolved frontend build context points at the reviewed patch checkout. Reuse the deployment's existing environment mechanism.

4. Give the reviewed patch a unique tag and build only the frontend:

```bash
export PX_DEMO_FRONTEND_IMAGE="enclave-frontend:px-wlc-$(git rev-parse --short HEAD)"
"${PX_BASE[@]}" -f "$PX_PATCH_CHECKOUT/docker-compose.px-wlc.yml" build frontend
"${PX_BASE[@]}" -f "$PX_PATCH_CHECKOUT/docker-compose.px-wlc.yml" up -d --no-deps --no-build frontend
```

5. Verify container health, `/auth`, `/verify`, favicon delivery, cached-browser reload, theme switching, and the visible LIBERATOR identity. Record the actual image ID, time, operator, and checks. Review synthetic/local screenshots before this step. Live email checks require an explicitly selected test account.

## Operational rollback — preferred

Use the retained old image, without rebuilding and without changing data. Create a small operator-local override:

```yaml
services:
  frontend:
    image: enclave-frontend:px-before-wlc
```

Run the same verified base invocation, excluding the WLC override and applying the rollback override last:

```bash
"${PX_BASE[@]}" -f "$PX_ROLLBACK_OVERRIDE" up -d --no-deps --no-build frontend
```

Check the running image ID equals `PX_ROLLBACK_ID`. Reload a browser that used the patch. Confirm the generic Instance styling, original favicon behavior, language/theme choice, and authenticated access. No database restore, volume removal, localStorage clearing, or logout is needed. Do not run `down -v` or the local reset script.

Alternative: build with an empty selector and deploy that image. The browser verification covers both this path and the original unmodified baseline. Runtime health and image rollback on the actual host still need to be exercised at deployment.

## Source removal and commit record

- Preparation base: `063e132ce0b77a238cd8bccdd4f36cfd38369eae`.
- Plan commit: `306ce15`.
- Application implementation: `8889acc`; LIBERATOR rename: `574179a`. Final documentation: the following commit, listed by `git log --oneline 8889acc..HEAD`.

Keep application changes in one patch commit, with final verification/docs in a following commit. To remove source changes from a later descendant, revert the LIBERATOR rename commit first and then `8889acc` and resolve any intervening frontend conflicts, then rebuild in generic mode. Retain this documentation as the customization reference. A Git revert alone does not replace a running image.

## Deployment record

| Field | Current value |
| --- | --- |
| Live activation | Not performed |
| Host/source commit | Not inspected |
| Retained live rollback image ID | To record before activation |
| Live patch image ID | Not deployed |
| Local verification image | `enclave-frontend:liberator-wlc-prepared` |
| Live rollback exercise | Not performed |
| Local same-browser rollback | Passed for disabled and original builds |
