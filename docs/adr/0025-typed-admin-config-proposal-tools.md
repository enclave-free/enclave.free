# Typed Admin Config Proposal Tools

Status: Superseded for Admin Config writes by [ADR-0028](0028-sage-owns-direct-admin-config-writes.md). Typed summary reads remain active guidance.

Admin Config write intent should prefer Typed Proposal Tools over model-authored raw change-set JSON. Sage still owns the Model-Driven Tool Loop and Change Confirmation, but models should express product-level intent while deterministic code builds canonical Enclave Control Plane request shapes, validates them, and returns an Executable Change Set for the existing Apply flow.

The same product-level contract shape should apply to common read-heavy Admin Config status flows once benchmark evidence shows that raw read-tool fanout makes models slow or brittle. For broad setup, status, or readiness questions, models should prefer compact typed summary Tools such as `read_admin_setup_summary`; low-level read Tools remain available for narrow follow-up inspection.

For guided Admin Config bootstrap, the model-visible contract should stay small: call the bootstrap proposal Tool with empty args or a short summary. Sage supplies the current Admin message to the deterministic planner, normalizes the numbered setup answers, and stages the reviewable change set without requiring Kimi to copy long setup notes or decompose every field by deduction.

## Considered Options

- Keep only `propose_config_change_set` with raw `requests_json`. Rejected because it makes the model hand-author exact control-plane paths, nested JSON string values, and request grouping; this is slow and brittle for Kimi on bootstrap setup.
- Convert every Tool Set at once. Rejected because DB Query, Knowledge Search, Curated Resources, Web Search, and Admin Config read Tools can remain lower-level escape hatches. The observed performance problems were first Admin Config proposal serialization, then broad Admin Config status fanout after live Kimi benchmark evidence.
- Use provider-native function calling. Rejected because ADR-0023 keeps Tool orchestration Sage-owned and provider-portable.

## Consequences

`propose_config_change_set` may remain as a compatibility and low-level escape hatch, but primary Admin Config write flows should move to typed proposal Tools backed by deterministic proposal builders. Broad Admin Config setup/status reads should move to typed summary Tools backed by deterministic aggregation. The UI continues to apply only after explicit Change Confirmation.
