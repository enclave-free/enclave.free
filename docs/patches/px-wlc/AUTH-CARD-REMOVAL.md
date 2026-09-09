# Remove the sign-in data protection card

Requested on 2026-09-08 after the LIBERATOR rollout. The signup and login form now ends with the short magic-link explanation. The entire “How Enclave protects your data” card and its three unused icon imports are removed from `frontend/src/pages/UserAuth.tsx`.

This presentation-only follow-up lives on `temp/px-demo-wlc-visual-only`. Email submission, link expiry, encryption, administrator access and Instance Settings are unchanged. Existing translation keys remain available. No backend or data migration is involved.

## Rollback

Revert the commit introducing this document to restore the card in source. Deployment retains the previous frontend image and a Compose rollback override; recreate only `frontend` with that image to restore the previous live screen. The v0.4.22 backend security fix must remain deployed.

This follow-up is independent of the original three branding commits. When removing the entire temporary patch, decide explicitly whether to retain this form simplification in the generic frontend.
