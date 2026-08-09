# Changelog

## 0.4.17 - 2026-08-09

- Kept Admin Test User conversations within a responsive, viewport-bounded workspace so long answers and expanded Activity scroll inside the shared message thread.
- Kept the composer, persona controls, Reset, Exit, and encrypted trial saving visible outside the conversation scroll without changing canonical User Conversation behavior.
- Added focused regressions for the Admin adapter height boundary, shared thread scroll ownership, and control placement.

## 0.4.16 - 2026-08-09

- Kept prose emitted before a later native Tool call private while preserving it in model continuity, so users receive only the grounded post-Tool answer.
- Buffered Tool-capable direct answers until model-led Tool selection completes, without adding classifiers, forced Tools, rewrites, fallback answers, or post-event retries.
- Added provider-level regressions for split content/Tool-call streams and synchronized the no-leak assertion with actual provider progress.

## 0.4.15 - 2026-08-09

- Made Admin Test-as-User sessions use the same canonical Conversation component and behavior as logged-in User chat while preserving persona selection, feedback, reset, exit, and trial saving.
- Reduced the model-facing Curated Resources contract to precise resource, region, language, and pagination hints so GLM can discover valid Admin-curated referrals without guessing restrictive search facets.
- Gave generic consent, concise-answer, Tool-stopping, and silent Tool-selection requirements precedence over Agent Settings without adding intent classifiers, forced Tool calls, fallback retrieval, answer rewriting, or reasoning escalation.
- Strengthened customer-conversation benchmarks for consent, safe database execution evidence, model-request boundaries, and the exact customer replay suite.

## 0.4.14 - 2026-08-08

- Replaced heavy-handed Tool routing and answer correction with a bounded, model-driven native Tool loop that preserves same-model continuity and generic Resource Directory lookups.
- Added privacy-safe model, Tool, Retrieval, first-event, usage, and total-turn observations plus repeatable conversation benchmarks.
- Measured GLM 5.2 reasoning levels and selected `none` as the demo default for lower latency without prompt-specific routing.
- Increased the pre-first-event provider window to 30 seconds and allowed two identical same-model retries without replaying executed Tools.
- Refreshed compatible frontend dependency resolutions to patched Nano ID and React Router releases.

## 0.4.13 - 2026-07-29

- Quarantined multiline `Tool calls` / `Function call` / `Arguments` transcripts across streaming boundaries while preserving benign explanatory prose.

## 0.4.12 - 2026-07-29

- Quarantined final answers that begin with a serialized plural `Tool calls:` invocation so internal Tool syntax is never exposed and the existing safe inventory fallback can run.

## 0.4.11 - 2026-07-29

- Preserved successful curated-resource inventory answers when both final-answer generation attempts are safely quarantined before any text is exposed.
- Restricted the deterministic fallback to an explicitly user-safe inventory rendering; contact lookups, multi-Tool turns, partial streams, and ordinary provider failures remain fail-closed.

## 0.4.10 - 2026-07-28

- Required fresh, exact Curated Resources lookups for contact-detail follow-ups while preserving the user's jurisdiction even when the prior help category is unavailable.
- Preserved contact and inventory scope across pages, rejected inconsistent counts and cursors, and prevented partial Resource Directory results from being described as exhaustive.
- Expanded English and Spanish inventory-region matching and added bounded lookup retries plus attributable Tool-selection and latency diagnostics.

## 0.4.9 - 2026-07-28

- Normalized case, accents, and whitespace in country names and aliases so variants such as `México` and `Türkiye` resolve to their ISO codes and no longer exclude otherwise-matching country-scoped Curated Resources from exact contact searches.

## 0.4.8 - 2026-07-28

- Quarantined capitalized `Tool:` and `Tool decision:` labels joined directly to a preceding sentence period, including same-line contact lookup arguments, before any answer text is exposed.
- Preserved lowercase embedded identifiers such as `namespace.tool:build` and `devtool:build`, with exhaustive streamed split coverage for the customer-observed output shape.

## 0.4.7 - 2026-07-28

- Prevented period-joined `Tool:` envelopes and lookup-only process narration from being released as final answers when the Tool phase had already completed.
- Added one bounded clean-answer retry for those responses while preserving explanatory Tool prose, search-related explanations, and embedded identifiers across arbitrary provider chunk boundaries.

## 0.4.6 - 2026-07-28

- Closed the remaining streamed Tool-decision leak across arbitrary provider chunk boundaries, including JSON, Markdown, bullet-form, and inline argument variants, while preserving ordinary explanatory Tool prose.
- Tightened the four-persona customer replay verifier so terminal Resource pages are accepted only when the answer clearly states that no additional pages remain.

## 0.4.5 - 2026-07-28

- Prevented provider-generated lookup narration and Tool-decision syntax from reaching visible final answers, including English and Spanish output with Markdown prefixes or spaced arguments.
- Added one bounded clean-answer retry with fail-closed handling for repeated unsafe output while preserving Resource Directory results and attempt-specific timing.

## 0.4.4 - 2026-07-28

- Re-ran Curated Resources for contact follow-ups and added exact or hybrid matching for organization names, emails, phone numbers, websites, addresses, and secure channels.
- Added bounded result counts, continuation metadata, truncation warnings, and scoped completeness wording so partial Resource Directory pages are not presented as exhaustive.
- Added content-free Tool-selection and omission observations, attributable Conversation timing, and bounded timeout/retry behavior for read-only Resource and Knowledge lookups.
- Hardened final-answer Tool-transcript quarantine and added customer-prompt replay coverage across the four demo personas, including Spanish contact follow-up and inventory continuation.
- Patched available frontend dependency advisories and kept the remaining React Router RSC-only advisory as one exact, tracked, fail-closed security exception.

## 0.4.3 - 2026-07-18

- Prevented runaway search/process narration and provider-token-limit truncation from being accepted or persisted as successful final answers.
- Bounded and de-duplicated current-turn Tool context, preferred the newest results under pressure, and made the planner's replan hint optional to avoid unnecessary planning retries.

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
