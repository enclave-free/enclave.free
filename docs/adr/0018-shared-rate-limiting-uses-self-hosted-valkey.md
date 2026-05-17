# Shared Rate Limiting Uses Self-Hosted Valkey

The Enclave Free Prototype needs abuse-resistant rate limiting that can coordinate across multiple runtime instances without sending operational security state to an external service. Shared rate limiting uses a self-hosted Valkey service as a **Shared Rate Limit Store**, with in-memory rate limiting reserved for single-process local development. This keeps ephemeral abuse-prevention counters out of the Enclave Control Plane SQLite database and Sage Postgres storage while avoiding a managed API-keyed dependency.
