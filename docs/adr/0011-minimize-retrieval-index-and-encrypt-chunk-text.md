# Minimize Retrieval Index And Encrypt Chunk Text

The Enclave Free Prototype will treat Qdrant as a minimized Retrieval Index rather than active content storage. Retrieved points should carry vector data and minimal metadata such as `chunk_id`, `job_id`, and source labels; chunk text should live in product-owned encrypted active storage, initially SQLite, protected by a deployment-held Content Encryption Key so backend retrieval workflows can hydrate context without storing plaintext document excerpts in Qdrant payloads.

## Considered Options

- Store plaintext chunk text in Qdrant payloads. Rejected because it makes the Retrieval Index a plaintext content store and weakens the Document Library confidentiality posture.
- Store encrypted chunk text directly in Qdrant payloads. Rejected because payload minimization gives a clearer boundary: Qdrant indexes retrieval metadata while the Enclave Control Plane owns encrypted chunk content and lifecycle deletion.
- Store encrypted chunk text as files under `uploads/chunks`. Deferred because SQLite already owns ingest metadata and gives a simpler first implementation and test surface for the prototype.

## Consequences

Retrieval must hydrate chunk text after vector search by resolving returned `chunk_id`s through the encrypted chunk store. Document deletion and Retention Execution must remove encrypted chunk rows as an explicit lifecycle target alongside uploaded artifacts and Retrieval Index points. This is active storage confidentiality, not Secure Erase and not end-to-end encryption from backend workflows.
