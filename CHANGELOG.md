# Changelog

## 0.4.2 - 2026-07-18

- Prevented GLM internal planning and serialized Tool transcripts from spilling into visible assistant answers by quarantining suspicious final-answer openings and retrying once through the clean-answer path.
- Preserved normal direct-answer streaming and kept provider reasoning available only through the separate Conversation Trace UI.

## 0.4.1 - 2026-07-18

- Replaced the Admin Config proposal/Apply-card workflow with direct Sage-owned configuration tools that write after natural conversational confirmation and return authoritative refresh metadata.
- Simplified guided onboarding and Admin Config tool contracts with native objects and arrays, structured backend validation feedback, and clearer model guidance for reliable one-pass setup.
- Hardened direct configuration writes with complete-call validation, atomic persistence, authorization, audit provenance, and safe handling of secrets and user-type deletion.
- Switched the default frontend runtime to compiled production assets with SPA fallback, explicit cache behavior, stable health probes, and a separate opt-in development override.
- Reduced the backend production image with CPU-only inference dependencies and fixed reasoning-trace disclosure so provider reasoning remains controlled trace data rather than visible answer text.

## 0.4.0 - 2026-07-17

- Reduced Admin Conversation latency by streaming plain final answers, deferring Session Memory embeddings, bounding typed Tool planning, and preserving provider reasoning as guarded trace data instead of visible answer text.
- Expanded Admin Config, Database Query, Knowledge Search, curated-resource, and web-search tool routing with clearer progress, trace, retry, and failure behavior.
- Added and hardened Admin User Manager workflows for searchable roster review, user details, approvals, encrypted identity unlock, and audited roster export.
- Added audited plaintext session-log export, removed duplicate trial logs, and replaced free-text curated-resource coverage entry with a searchable region picker.
- Completed and enforced interface-key parity for the six priority locales, improved language ordering and preference migration, and kept the remaining locale sweep tracked separately.
- Aligned the Qdrant Python client and server minor versions and strengthened Tinfoil proxy integrity, gateway, security, and deployment smoke coverage.

## 0.3.0 - 2026-07-06

- Added a dedicated Admin User Manager detail screen so admins can open a user from the roster and review identity, approval, user type, public key, joined date, and all applicable profile fields.
- Kept the detail view accessible for non-technical admins with a clear back path, status summaries, and the same approve, refresh, and encrypted-detail unlock actions as the roster.
- Released the User Manager detail workflow to the demo release train.

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
