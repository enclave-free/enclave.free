# CodeRabbit Round: Local Branch Diff

## Round

- Scope: local
- Round number: 1
- Command or trigger: `coderabbit review --agent --type all --base staging`
- Started: 2026-07-03 15:37 CDT
- Completed: 2026-07-03 15:43 CDT
- Availability: completed
- Fallback review thread: Not needed.

## Findings To Address

| Finding | Severity | Decision | Notes |
| --- | --- | --- | --- |
| `frontend/src/utils/userRosterExport.ts` allowed XML 1.0 illegal control bytes through `xmlEscape`. | minor | Fixed | Added localized control-character stripping in `xmlEscape` and a workbook regression assertion. |

## Findings Not Addressed

| Finding | Reason |
| --- | --- |
| `backend/app/ai_config.py` duplicated JSON string-array validation. | Out of scope; file was not touched by the User Roster Export slice. |
| `frontend/src/pages/AdminAIConfig.tsx` drops unknown/legacy user default Tool IDs on save. | Out of scope; file was not touched by the User Roster Export slice. |

## Result

- Continue: Yes.
- Escalate: No.
- Notes: One in-scope workbook XML hardening finding fixed and rechecked. Two unrelated AI config findings recorded for future work rather than expanding this feature PR.
