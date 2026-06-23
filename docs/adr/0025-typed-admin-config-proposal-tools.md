# Typed Admin Config Proposal Tools

Admin Config write intent should prefer Typed Proposal Tools over model-authored raw change-set JSON. Sage still owns the Model-Driven Tool Loop and Change Confirmation, but models should express product-level intent while deterministic code builds canonical Enclave Control Plane request shapes, validates them, and returns an Executable Change Set for the existing Apply flow.

## Considered Options

- Keep only `propose_config_change_set` with raw `requests_json`. Rejected because it makes the model hand-author exact control-plane paths, nested JSON string values, and request grouping; this is slow and brittle for Kimi on bootstrap setup.
- Convert every Tool Set at once. Rejected because DB Query, Knowledge Search, Curated Resources, Web Search, and Admin Config read Tools already have small typed contracts. The observed performance problem is proposal serialization for Admin Config writes.
- Use provider-native function calling. Rejected because ADR-0023 keeps Tool orchestration Sage-owned and provider-portable.

## Consequences

`propose_config_change_set` may remain as a compatibility and low-level escape hatch, but primary Admin Config write flows should move to typed proposal Tools backed by deterministic proposal builders. The UI continues to apply only after explicit Change Confirmation.
