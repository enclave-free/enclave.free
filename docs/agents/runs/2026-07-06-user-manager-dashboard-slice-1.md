# Slice 1: Add the User Manager Dashboard route and table

## Parent

#477

## What to build

Create a dedicated admin **User Manager Dashboard** that lists **Users** in an accessible table with readable identity, **User Approval**, **User Type**, **User Profile**, and joined-at information. Add a clear admin entry point and routing for `/admin/user-manager`.

## Acceptance criteria

- [ ] `/admin/user-manager` is protected by the existing admin route guard.
- [ ] The admin setup/home surface links to the dashboard with non-technical copy.
- [ ] The dashboard fetches **Users**, **User Types**, and **Onboarding Questions** through existing admin APIs.
- [ ] The roster renders in a semantic table with clear column headers.
- [ ] The table includes loading, empty, and error states.
- [ ] The dashboard includes status summary counts for total, pending, approved, and incomplete-profile **Users**.
- [ ] Search and filters update the visible table rows without a full page reload.
- [ ] Frontend tests cover route registration and table/filter behavior.

## Blocked by

None - can start immediately.
