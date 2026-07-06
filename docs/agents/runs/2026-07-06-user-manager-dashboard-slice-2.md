# Slice 2: Add User Approval actions and roster export to the dashboard

## Parent

#477

## What to build

Complete the dashboard operations path by letting an **Admin** approve pending **Users** directly from the table, refresh the roster, and create a **User Roster Export** using the existing browser-side export and backend audit metadata flow.

## Acceptance criteria

- [ ] Pending **Users** have a clear Approve action in the table.
- [ ] Approving a **User** calls the existing user update API with `{ approved: true }`.
- [ ] The row and summary counts update after a successful approval.
- [ ] Approval success and failure messages are visible and accessible.
- [ ] Approved **Users** do not show an active approve action.
- [ ] The dashboard can refresh the roster without a full page reload.
- [ ] The dashboard can download a **User Roster Export** and records export metadata through the existing audit endpoint.
- [ ] Frontend tests cover approval success, approval error, refresh, and export behavior.

## Blocked by

#478
