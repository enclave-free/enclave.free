# Remove Prototype Compatibility Debt After Sage Hard Cut

The Enclave Free Prototype will remove Prototype Compatibility Debt that preserves obsolete behavior after Sage became the source of truth for the Agent Runtime. Sage-owned public Agent Runtime routes must not keep duplicate Python behavior as a rollback path; direct calls to obsolete Python public Agent Runtime routes should fail clearly. Maple-era Model Provider labels, aliases, imports, and admin-facing copy should be removed rather than silently honored. Generic `LLM_*` settings may remain temporarily as Python-side Deployment Settings for diagnostics, verification metadata, and remaining deployment surfaces, but they should not be described as live Sage Agent Settings until runtime configuration is unified.

## Considered Options

- Keep all compatibility behavior until the prototype becomes a product release. Rejected because silent fallback paths blur the Sage and Enclave Control Plane boundary and make regressions harder to detect.
- Delete obsolete public Python routes outright. Deferred in favor of explicit tombstone responses where useful, because clear failures help local developers and tests discover the correct Gateway-to-Sage path.
- Treat plaintext and encryption fallbacks as part of the same cleanup. Rejected because those fallbacks are Confidentiality Migration concerns tied to existing storage state, not obsolete route or provider behavior.

## Consequences

The supported local development path is the Compose topology where the Gateway routes public Agent Runtime requests to Sage. Python remains the Enclave Control Plane and should expose only active public product routes plus the active private Sage-to-Python contract. Obsolete internal compatibility endpoints should fail clearly or be removed so future Sage work does not accidentally depend on old ownership boundaries. Admin UI and docs should stop teaching Maple-era provider names and should make the split between Sage runtime environment and Python-side Deployment Settings explicit until configuration is unified.
