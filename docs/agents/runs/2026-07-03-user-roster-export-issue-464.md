# Slice Issue: Export User Roster Workbook from User Management

## Parent

Parent: #463

## What to build

Add an Admin-facing **User Roster Export** action to User management. The action should generate an `.xlsx` workbook that gives Admins a clean, spreadsheet-friendly roster of Users instead of requiring them to inspect raw database tables.

The workbook should include a primary `Users` worksheet, a `Pending Approval` worksheet, `User Types`, `Field Dictionary`, and `Export Notes`. It should use the Admin browser's existing locally decrypted identity/profile values when available, clearly mark locked encrypted values when they are not available, and avoid exporting raw ciphertext.

The export should also record a backend Audit Log event identifying the action as a copied User Roster Export without storing exported plaintext workbook contents.

## Acceptance criteria

- [x] User management exposes a clear User Roster Export action separate from the database export.
- [x] The export creates an `.xlsx` workbook with `Users`, `Pending Approval`, `User Types`, `Field Dictionary`, and `Export Notes` worksheets.
- [x] The `Users` worksheet has one row per User and includes User ID, User Approval status, name, email, User Type, created date, Nostr pubkey, identity status, and available User Profile columns.
- [x] The `Pending Approval` worksheet includes only Users whose User Approval status is pending.
- [x] The workbook does not include raw encrypted ciphertext; locked encrypted values are labeled as locked or unavailable.
- [x] Locally decrypted identity/profile values are included when available in the Admin browser.
- [x] The workbook includes copied-export notes so Admins know downloaded spreadsheets are operator/device controlled records after creation.
- [x] A backend Audit Log event records the copied User Roster Export without receiving or persisting exported workbook contents.
- [x] Frontend tests cover workbook creation/download behavior from the User management seam.
- [x] Backend tests cover copied-export audit event recording.

## Blocked by

- None - can start immediately.
