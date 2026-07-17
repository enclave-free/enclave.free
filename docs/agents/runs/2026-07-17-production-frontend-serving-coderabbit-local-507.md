# Local CodeRabbit Round — Issue #507

## Round

- Scope: local
- Round number: 1
- Command or trigger: primary-session local CodeRabbit review against the issue #507 branch diff
- Started: 2026-07-17
- Completed: 2026-07-17
- Availability: completed
- Fallback review thread: two-axis Standards and Spec review recorded in `docs/agents/runs/2026-07-17-production-frontend-serving-review-507.md`

## Findings To Address

| Finding                                                                                        | Severity | Decision  | Notes                                                                                                                                                                          |
| ---------------------------------------------------------------------------------------------- | -------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Production frontend health probes used BusyBox-unsupported `wget --no-verbose --tries=1` flags | major    | addressed | Replaced frontend image, production/development Compose, and runtime probes with `wget -q --spider`; rebuilt through Apple Containers and passed the exact in-container probe. |
| Immutable asset cache header used `always`, applying it to missing-asset errors                | minor    | addressed | Removed `always` from the `/assets/` header and added a live HTTP regression proving asset 404s are not immutable.                                                             |
| Development Compose contract asserted only the command prefix                                  | minor    | addressed | The contract now asserts the complete `npm run dev -- --host 0.0.0.0` command.                                                                                                 |
| Frontend guide said “this directory” for the development bind mount                            | minor    | addressed | Documentation now names the `frontend/` bind-mount source explicitly.                                                                                                          |

## Findings Not Addressed

| Finding | Reason                                                |
| ------- | ----------------------------------------------------- |
| None    | All four verified findings were worthy and addressed. |

## Result

- Continue: yes; local CodeRabbit issues are resolved and affected checks pass
- Escalate: no
- Notes: Compose contracts passed 2/2; Apple production HTTP contracts passed 5/5; the rebuilt image passed the BusyBox-compatible in-container health probe; `git diff --check` passed. The full frontend suite was not repeated because these fixes affect packaging, deployment checks, and documentation rather than application code.
