# Rollback and permanent removal

Audited 2026-09-17 against deployed application source `b8f1625` and generic base `v0.4.25` (commit `5dbd822f02dd0694a5178ef9001b93eb12f8e9a9`). This runbook supersedes rollback sections in historical patch documents.

## Choose the intended result

| Operation | Result | Does it remove the entire patch? |
| --- | --- | --- |
| Color-only rollback | Accepted blue entry layout remains; application returns to the preceding teal palette | No |
| Restore generic 0.4.25 frontend | All generic frontend behavior/appearance, including the original protection card | Yes, operationally |
| Rebuild patch with empty `VITE_DEMO_BRAND` | Generic identity/layout/colors; protection-card removal remains | No, only disables gated branding |
| Revert all application patch commits | Application/build tree exactly matches generic 0.4.25; historical docs may remain | Yes, in source; deploy afterward |

Saved Instance Settings are never restored or overwritten by these operations. Generic presentation uses the currently saved Instance name, logo, theme and colors; the saved name may still be LIBERATOR. Removing source branding does not rename customer settings or email identity.

## Prepared operational restores

The authorized demo host is `root@137.184.21.75`, project `enclave-free`, application directory `/opt/enclave-free`. Run these **only when rollback is requested**, not during documentation checks. No live rollback was performed during closeout.

First inspect the current frontend image/health and compare with [the manifest](current-manifest.json). If the deployment has advanced since this audit, prepare rollback against its new generic base and actual ordered Compose files instead of reusing these commands blindly.

### Undo only the latest color alignment

```bash
ssh -o BatchMode=yes root@137.184.21.75 \
  bash /opt/enclave-free/backups/pre-colors-b8f1625/rollback.sh
```

Expected frontend image: `sha256:86524c1e9a5ba930cc9138c9ca6ff5a5378159f7fbc98f7a9958584eed7fca41` (`enclave-frontend:liberator-entry-v2-c9199c8`). The original ordered Compose invocation and image archive are retained in that backup directory. This older script has no current-image guard; manually verify the starting image first.

### Remove all temporary frontend branding

```bash
ssh -o BatchMode=yes root@137.184.21.75 \
  bash /opt/enclave-free/backups/wlc-accepted-b8f1625/restore-generic.sh
```

Expected frontend image: `sha256:6045a956b0ad9bdf0d62f546078647c3371036640d3d0bce018b3b717dd7341c` (`enclave-frontend:generic-rollback-0.4.25`). Built from the exact generic release, not from an older generic 0.4.21 image.

The guarded script starts only from the accepted `b8f1625` image. Its final override pins both generic image and generic build context with an empty selector, preserving all existing release overrides. It uses `up -d --no-deps --no-build frontend`. Backend, Sage, database and volumes are not recreated. The inverse `restore-accepted.sh` in the same directory is guarded to start only from this generic image and restores the accepted frontend if the rollback must be undone.

Retained archive: `/opt/enclave-free/backups/wlc-accepted-b8f1625/frontend-images.tar.gz` contains both generic and accepted images. If tags/images were pruned, load this archive before restore:

```bash
ssh -o BatchMode=yes root@137.184.21.75 \
  'gzip -dc /opt/enclave-free/backups/wlc-accepted-b8f1625/frontend-images.tar.gz | docker load'
```

Keep that backup directory, its Compose files, the current environment file and both source checkouts until retirement. The scripts refer to existing absolute paths. Rebuild/re-audit them if moving hosts or consolidating Compose files. Treat environment files as secrets; never commit a fully rendered Compose configuration.

### Verify after either restore

1. Confirm frontend image ID and healthy status. Compare non-frontend container IDs/images with a pre-restore inventory.
2. Refresh an already-open browser and open a fresh one. Old lazy-loaded chunks may require a reload after an image switch.
3. Check language selection, signup/login, favicon/title, light/dark preferences, mobile layout and public admin entry. Full generic restore should have no `data-demo-brand="wlc"` marker or promotional side panel.
4. Check saved public settings are unchanged. Check an authorized existing authenticated session when available; do not send real emails or create accounts merely to test visual rollback.
5. Record image/source/time/results and any session-verification limitation. If unsuccessful, restore the retained accepted image with the same frontend-only procedure.

Do not restore a database, delete volumes, clear localStorage, run `down -v`, use the local reset script, or roll back the backend for this visual patch.

## Permanent source removal

The owner authorized main integration on 2026-09-17. The application removal patch below also applies on main while its application tree matches `b8f1625`; do not reset main or revert unrelated release history.

Preferred removal keeps all patch documentation/evidence and reverses only the recorded application/build difference. From a clean dedicated removal branch/worktree based on this accepted patch:

```bash
git diff --binary v0.4.25 b8f1625 -- frontend docker-compose.px-wlc.yml > /tmp/enclave-wlc-application.patch
git apply --check --reverse --index /tmp/enclave-wlc-application.patch
git apply --reverse --index /tmp/enclave-wlc-application.patch
git diff --exit-code v0.4.25 -- frontend docker-compose.px-wlc.yml
```

The check-only application passed against the accepted checkout including the documentation closeout. Review the staged removal, run required checks/build, and commit. Do not force application over conflicts after later application edits; reconcile those edits first. This method preserves the documentation added after the accepted application revision.

For a commit-by-commit audit, use a clean dedicated branch/worktree from the accepted patch. The following exact newest-first sequence was rehearsed with `--no-commit` in an isolated worktree on 2026-09-17. It applied without conflicts and left zero application/build difference from generic 0.4.25:

```bash
git revert --no-commit \
  b8f1625 8e5a2ce c9199c8 4e0df74 c04120d 2c043d9 \
  b28eb21 2e68f04 6eda1de 574179a 8889acc
git diff --exit-code v0.4.25 -- frontend docker-compose.px-wlc.yml
```

The first command stages changes but does not commit or deploy. Review the staged diff, run the required checks/build, and commit the removal. Documentation hunks are also reverted; preserve the accepted documentation/evidence if retaining the customization reference. Do not revert merge commits that brought generic releases/security fixes into this branch. Do not reset to the original 0.4.20 preparation base.

This proof is specific to application revision `b8f1625`; later documentation-only closeout changes may need documentation conflict resolution when reverting historical commits. Later application changes must be reviewed and preserved individually. Use [the inventory](current-manifest.json) to confirm every temporary source/build hook was removed. Retire `docker-compose.px-wlc.yml` and host branding overrides after replacing their frontend selection with the generic release configuration, keeping unrelated release overrides intact.

Rebuild/deploy the generic frontend after source removal; a Git revert alone does not alter a running container. Generic mode restores the verbose protection card as part of this exact removal. If its simplification is desired in the generic product, make that a separate reviewed change after proving removal parity.
