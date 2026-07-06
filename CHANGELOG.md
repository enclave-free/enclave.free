# Changelog

## 0.2.1 - 2026-07-06

- Added a focused admin User Manager dashboard for reviewing users, statuses, profiles, approval, and roster exports.
- Kept curated resource inventory lookup behavior from staging so Sage can list ready Resource Directory entries without requiring a help type.
- Updated demo deployment handoff guidance for the new User Manager approval path.

## 0.2.0 - 2026-07-05

- Added Admin signer-decrypted context for Database-enabled Admin conversations so Sage can interpret encrypted User identity/profile values during encrypted inference.
- Kept signer-decrypted plaintext browser-delegated, Admin-only, Database-turn-only, and out of Activity/Conversation Trace metadata.
- Documented the Admin Signer-Decrypted Context boundary and updated release/runtime verification evidence.

## 0.1.3 - 2026-07-05

- Allowed approved Admin DB Query turns to translate natural-language prompts into read-only SQLite SELECT tool calls instead of requiring literal SELECT-only messages.
- Updated Sage tool-contract coverage and DB query safety docs to match the delegated read-only SQL execution path.

## 0.1.2 - 2026-07-04

- Hardened Agent Settings validation, roster export audit gating, and document upload polling/show-more behavior.
- Added demo handoff PDF drift checking and deterministic PDF generation.
- Polished Agent Settings labels, modal focus restoration, and run-log portability.

## 0.1.1 - 2026-07-01

- Added admin-facing guides for setup, configuration, launch safety, and common workflows.
- Added onboarding language switching for user auth, type selection, profile onboarding, and admin onboarding.

## 0.1.0 - 2026-07-01

Initial customer-facing demo release checkpoint.

- Admin Nostr setup and dashboard workflows for already-initialized demo instances.
- Guided setup, instance/user/agent configuration surfaces, document upload, and resource directory management.
- Email magic-link user auth with manual approval support.
- User Reachout email flow for authenticated users to contact the operator inbox.
- Sage/Tinfoil-backed chat runtime with deployment diagnostics for model/provider checks.
- Demo deployment handoff guide for operators and customer testers.
