# PRD: User Roster Export

## Problem Statement

Admins can download a raw database backup and inspect database tables, but that is a technical workflow. Non-technical Admins primarily need a clean, spreadsheet-friendly roster of Users so they can audit who exists in an Instance, who is pending User Approval, which User Type each User belongs to, and what User Profile information is available.

The current database export framing makes this feel like a database operation instead of an Admin operations task. It also risks conflating a technical backup with a human-readable Copied Export.

## Solution

Add a **User Roster Export** action to User management. The export creates an `.xlsx` workbook designed around Admin auditing, not raw tables. The primary worksheet is a readable User list with one row per User. Supporting worksheets explain User Types, Onboarding Questions, and export metadata.

Encrypted identity and User Profile values should only be included when they are already available in the Admin browser through the existing local NIP-04 decryption flow. The backend must not gain plaintext access to encrypted User Profile data just to build the spreadsheet. A backend audit event records that a User Roster Export was created without storing exported plaintext contents.

## User Stories

1. As an Admin, I want to download a User spreadsheet from User management, so that I do not need to use the database explorer for ordinary roster auditing.
2. As an Admin, I want one row per User, so that I can scan, sort, and filter the Instance's Users.
3. As an Admin, I want to see User Approval status, so that I can identify pending Users quickly.
4. As an Admin, I want a dedicated pending-approval worksheet, so that approval review is easy for a non-technical operator.
5. As an Admin, I want to see each User's User Type, so that I can audit onboarding segmentation.
6. As an Admin, I want to see User creation dates as spreadsheet dates, so that I can sort by signup/onboarding time.
7. As an Admin, I want decrypted name and email included only when my browser has unlocked them locally, so that the export matches the privacy posture of the admin UI.
8. As an Admin, I want locked encrypted fields to be clearly labeled, so that I know whether the export is incomplete because decryption was unavailable.
9. As an Admin, I want User Profile answers in columns when available, so that I can audit onboarding information without writing SQL.
10. As an Admin, I want the spreadsheet to include a field dictionary, so that I understand which columns are required, scoped to a User Type, encrypted, or included in chat context.
11. As an Admin, I want the spreadsheet to include User Type counts, so that I can audit the shape of my User population.
12. As an Admin, I want an export notes worksheet, so that I can see when the file was created and understand it is a Copied Export.
13. As an Operator, I want copied roster exports to be recorded in the Audit Log, so that export actions remain visible without storing exported plaintext.
14. As an Operator, I want the raw database backup export to remain separate, so that technical restore workflows are not confused with roster auditing.
15. As a developer, I want this behavior covered through existing Admin user-management seams, so that the feature stays local to the Enclave Control Plane user-management surface.

## Implementation Decisions

- Add the export action to User management rather than the database explorer.
- The workbook should be generated in the browser from already-authorized Admin API data plus any identity/profile values decrypted locally through the existing admin NIP-04 flow.
- Add a small backend endpoint that records a copied-export Audit Log event for User Roster Export creation. It should not receive or persist exported spreadsheet contents.
- The workbook should contain these sheets:
  - `Users`: primary roster, one row per User.
  - `Pending Approval`: Users whose User Approval status is pending.
  - `User Types`: User Type metadata and roster counts.
  - `Field Dictionary`: Onboarding Question metadata used to interpret dynamic User Profile columns.
  - `Export Notes`: timestamp, export mode, privacy/lifecycle warning, and copied-export language.
- The `Users` sheet should include stable core columns first: User ID, approval status, name, email, User Type, created date, Nostr pubkey, identity status, and User Profile availability/completeness.
- Dynamic User Profile columns should be prefixed consistently so they read as profile data rather than database fields.
- The spreadsheet must avoid raw ciphertext. Locked encrypted values should be represented by clear status text.
- The raw SQLite export remains available and should not be renamed into the User Roster workflow.
- No database schema change is required.

## Testing Decisions

- Test the backend audit endpoint through the existing FastAPI test style used for Admin database export audit evidence.
- Test the frontend export behavior through the Admin User management page seam, mocking Admin API data and browser download creation.
- Unit-test workbook construction as a pure frontend utility where possible, inspecting workbook sheet names and representative cell values rather than implementation details.
- Verify that locked encrypted values do not write ciphertext into the workbook.
- Verify that User Approval and User Type values are represented in the exported workbook.
- Run targeted tests first, then the relevant full frontend suite/build and targeted backend test file.

## Out of Scope

- Full database spreadsheet export.
- Backend decryption of User identity or User Profile values.
- Exporting raw ciphertext.
- Replacing the raw SQLite backup export.
- Production deployment or production data operations.
- Google Sheets integration.

## Further Notes

Downloaded User Roster Export files are Copied Exports and become operator/device controlled records after creation. The feature should make this visible in the workbook and Audit Log without pretending copied files remain inside Active Storage Lifecycle.
