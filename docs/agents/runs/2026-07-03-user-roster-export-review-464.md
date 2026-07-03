# Review Packet: #464 User Roster Export

## Issue

- Issue: #464 Export User Roster workbook from User management
- Slice type: AFK
- Acceptance criteria: See `docs/agents/runs/2026-07-03-user-roster-export-issue-464.md`
- Baseline: origin/staging
- Current diff: working tree before commit on `feature/user-roster-export`

## Implementation Summary

Admins now have an `Export users` action in User management that downloads an `.xlsx` User Roster Export. The workbook is organized for non-technical roster auditing, keeps raw ciphertext out of the file, marks locked encrypted values, includes browser-local decrypted values when available, and records copied-export audit metadata on the backend without posting workbook contents.

## Implementation Evidence

- `implement` session: Current Codex thread.
- `tdd` used: Yes.
- Red test, if applicable: Added workbook and Admin user-management tests before final implementation hardening.
- Green implementation, if applicable:
  - Workbook utility creates the expected sheets and avoids ciphertext.
  - Admin page test verifies download and copied-export audit metadata.
  - Backend test verifies copied-export audit event metadata.
- Refactor, if applicable:
  - Browser workbook writer split into `frontend/src/utils/userRosterExport.ts`.
  - Admin page export code keeps decryption and audit/download sequencing local to User management.
- Commands run:
  - `cd frontend && npm run test -- userRosterExport.test.ts AdminUserConfig.test.tsx` -> 2 files, 5 tests passed.
  - `cd frontend && npm run test -- --reporter=dot` -> 69 files, 356 tests passed.
  - `cd frontend && npm run build` -> passed with existing large chunk warnings.
  - `uv run --python /Users/plebdev/.local/bin/python3.12 --with fastapi --with qdrant-client --with pydantic --with pycryptodome --with coincurve --with bech32 --with python-multipart --with itsdangerous --with httpx --with redis --with requests --with python-dotenv --with openai --with urllib3 --with filelock --with Pillow --with numpy python -m unittest backend.tests.test_admin_db_query_endpoint` -> 7 tests passed.
  - `PYTHONWARNINGS=ignore uv run --python /Users/plebdev/.local/bin/python3.12 --with fastapi --with qdrant-client --with pydantic --with pycryptodome --with coincurve --with bech32 --with python-multipart --with itsdangerous --with httpx --with redis --with requests --with python-dotenv --with openai --with urllib3 --with filelock --with Pillow --with numpy python -m unittest discover -q backend/tests` -> 380 tests passed.
  - `git diff --check` -> passed.

## Reviewer Output

```text
STANDARDS_STATUS: pass
STANDARDS_FINDINGS:
- Fixed before final review: hard-coded Admin pubkey storage key replaced with STORAGE_KEYS.ADMIN_PUBKEY.
- Fixed before final review: generated frontend/dist/index.html build churn removed from the source diff.
- Fixed before final review: existing admin assistant docs wording synced so the full backend docs compatibility suite passes.
- Fixed after local CodeRabbit: workbook XML escaping now strips XML 1.0 illegal control bytes from user-supplied text.

SPEC_STATUS: pass
SPEC_FINDINGS:
- Fixed before final review: Created At is a spreadsheet date/time cell instead of plain text.
- Fixed before final review: repeated Onboarding Question names scoped to different User Types no longer duplicate values into non-applicable columns.
```
