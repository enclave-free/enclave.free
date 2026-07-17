# PRD: User Manager Dashboard

## Problem Statement

The **Admin** currently has no focused, non-technical view for managing **Users**. User operations are mixed into User Settings alongside **User Type**, **Onboarding Question**, migration, reachout, and export configuration. That makes it hard for an **Admin** to quickly answer basic operational questions: who is waiting for **User Approval**, what **User Type** each **User** belongs to, whether their **User Profile** looks complete, and what simple action should happen next.

## Solution

Create a dedicated admin **User Manager Dashboard** on staging. The dashboard gives the **Admin** a readable table of **Users**, concise status summaries, filters for common operational states, and simple actions such as approving a pending **User**. It reuses existing **Enclave Control Plane** APIs and keeps User Settings focused on schema/setup work.

## User Stories

1. As an **Admin**, I want a dedicated User Manager entry point, so that I do not need to hunt through User Settings for user operations.
2. As an **Admin**, I want to see all **Users** in a simple formatted table, so that I can scan the current roster.
3. As an **Admin**, I want each row to show the best available identity, so that encrypted or locked identity data is still understandable.
4. As an **Admin**, I want to see **User Approval** status, so that I can identify pending **Users**.
5. As an **Admin**, I want to approve a pending **User** from the table, so that they can enter normal user-facing product flows.
6. As an **Admin**, I want approved **Users** to have a clear status, so that I do not accidentally act on them again.
7. As an **Admin**, I want to filter pending and approved **Users**, so that urgent approval work is easy to find.
8. As an **Admin**, I want to filter by **User Type**, so that I can review a segment of the **Instance** roster.
9. As an **Admin**, I want to search by visible identity, email, user number, or public key, so that I can find a specific **User** quickly.
10. As an **Admin**, I want to see **User Profile** completion cues, so that I can tell whether a **User** has shared onboarding information.
11. As an **Admin**, I want to refresh the roster, so that I can confirm whether recent approvals or signups are visible.
12. As an **Admin**, I want loading, empty, and error states to be written plainly, so that I know what is happening without technical interpretation.
13. As an **Admin**, I want keyboard-accessible controls and semantic table markup, so that the dashboard works with assistive technology.
14. As an **Admin**, I want to export the visible roster, so that I can keep an operational **User Roster Export** when needed.
15. As an **Admin**, I want encrypted identity limitations to be explained without alarm, so that I know when local signer access affects display.

## Implementation Decisions

- Add a focused `/admin/user-manager` route protected by the existing admin route guard.
- Add the User Manager entry to the admin setup/home surface as an operational dashboard separate from User Settings.
- Keep `/admin/users` as the User Settings route for **User Type**, **Onboarding Question**, migration, reachout, and existing detailed configuration workflows.
- Reuse existing **Enclave Control Plane** APIs: list **Users**, update **User Approval**, list **User Types**, and record **User Roster Export** metadata.
- Keep approval as an explicit row action; do not add destructive delete controls in this feature.
- Decrypt identity and **User Profile** values in the browser using the same local signer pattern as the current User Settings export flow. Do not post decrypted plaintext back to the backend.
- Derive dashboard metrics and profile completion cues client-side from the listed **Users** and known **Onboarding Questions**.
- Favor a semantic table with stable controls over card-heavy presentation.

## Testing Decisions

- Add frontend component tests that exercise the public dashboard behavior through rendered UI, not implementation internals.
- Add a routing test proving `/admin/user-manager` loads behind admin protection.
- Verify approval uses `PUT /users/{id}` with `{ approved: true }` and updates the visible roster state.
- Verify filtering/searching changes the visible table rows in a way a screen reader can observe through row text.
- Verify copied export uses existing workbook generation and audit metadata path.
- Run targeted Vitest tests first, then the frontend test suite and build.
- Perform browser visual verification of `/admin/user-manager` for layout, readability, and non-overlap.

## Out of Scope

- Production deployment or production-only verification.
- User deletion or data deletion workflows.
- Editing **User Profile** values.
- **User Type** migration from the new dashboard.
- New backend pagination, sorting, or query filters.
- Multi-admin permission models.
- Direct admin-to-user messaging.

## Further Notes

This PRD intentionally treats the dashboard as an **Ordinary Product Flow** owned by the **Admin**, not as a Sage tool or **Admin Conversation** feature. Existing audit behavior for **User Approval** and **User Roster Export** remains the source of truth.
