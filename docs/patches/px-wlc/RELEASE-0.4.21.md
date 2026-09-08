# LIBERATOR / 0.4.21 rollout

## Scope and review

The release inventory on 2026-09-08 found no unreleased staging commits and one open PR: #669, removing the three-paragraph sign-in disclaimer panel. Other actual worktrees had no staged changes. The bare repository index is historical state, not a release candidate.

Generic release 0.4.21 contains the copy cleanup. The WLC-inspired LIBERATOR visuals remain on `temp/px-demo-wlc-visual-only`; they are not merged into generic main. Instance name remains the stored `LIBERATOR` and tagline remains `Empowering Families of Political Prisoners`.

Standards review: one heuristic robustness finding resolved by making the Vite transform reject changed HTML root/title markers. The repeated identity constants remain a documented temporary maintenance tradeoff. Spec review: one verification gap resolved by rebuilding the combined copy + branded frontend and running all 14 browser checks. No outstanding code findings on either axis.

## Verification

- Combined branch: all 490 tests / 82 files pass through the real pre-commit hook.
- Generic frontend: all 488 tests / 81 files pass; production build passes.
- Combined branded frontend: enabled and disabled production builds pass; all 14 fixture browser checks pass, including desktop/mobile, light/dark, Arabic RTL, auth states, User Approval, profile completion, and same-browser rollback. Updated screenshots are under `screenshots/liberator/`.
- Malformed HTML root and title each reject with the intended build error; normal branded build passes.
- Semgrep: 80 rules on 12 changed frontend files, zero findings.
- Frontend dependency audit: no unaccepted high/critical advisories.
- Backend CI security regressions, frontend security regressions, localization, production runtime, and PDF drift checks passed on #669.
- Python dependency scan remains failed for pre-existing accelerate 1.14.0 / CVE-2026-69112, tracked in [#670](https://github.com/enclave-free/enclave.free/issues/670). No suppression added. Upstream has no fixed published version at release preparation. The deployed backend also has 1.14.0; the rollout preserves that image and does not resolve this advisory.

## Rollout status

Prepared; deployment completion will be recorded here after live verification. The deployed source was verified as `063e132ce0b77a238cd8bccdd4f36cfd38369eae` / 0.4.20 before any change. A frontend rollback image tag and exported archive have been created on the server; operational paths and container evidence are retained in the local operator record outside the repository.

Only the frontend service will be recreated, using the existing Compose project, environment and demo port bindings. Backend, Sage, infrastructure, volumes and persisted Instance Settings remain in place.

## Rollback and removal

For immediate full frontend rollback, use the saved pre-release frontend image with the original Compose files and a frontend-image override, then `up -d --no-deps --no-build frontend`. For branding-only rollback while retaining the copy cleanup, build generic v0.4.21 without `VITE_DEMO_BRAND` and replace only frontend. Neither operation requires a database restore or clearing browser storage.

For source removal, retain the release/copy merge and documentation. Revert the later Vite guard commit `6eda1de` first, then the LIBERATOR rename `574179a`, then the original visual patch `8889acc`. The final deployed revision will be recorded after live verification. Historical PX paths and symbols identify this temporary patch; visible name is LIBERATOR.
