# Active Content Encryption Posture

This document distinguishes active content confidentiality from Secure Erase and unsupported Deployment Surfaces.

## Artifact Encryption Posture

Uploaded Document artifacts are written through `backend/app/content_artifacts.py`.

When `CONTENT_ENCRYPTION_KEY` is configured and `DOCUMENT_ARTIFACT_ENCRYPTION` is `auto` or `required`, new uploaded artifacts are encrypted in active storage. Operators may explicitly set `DOCUMENT_ARTIFACT_ENCRYPTION=disabled`; that is reported as plaintext by operator choice.

Changing the posture affects future writes. Existing plaintext artifacts require Confidentiality Migration before lifecycle status can report verified encrypted active artifacts.

## Retrieval Content Posture

Current Retrieval Index writes keep Qdrant payloads minimized. Qdrant receives vectors and metadata such as chunk id, job id, and source file. Chunk text is stored separately in SQLite `retrieval_chunks.encrypted_text` and hydrated by backend workflows when needed.

## Confidentiality Migration

The lifecycle Confidentiality Migration preview and execute endpoints report eligible legacy plaintext active artifacts and can rewrite them when a Content Encryption Key is configured.

Confidentiality Migration does not claim Secure Erase. It rewrites active product storage only; it does not control backups, snapshots, WAL files, logs, copied exports, browser caches, or provider traces.

## Evidence Surfaces

- `GET /admin/lifecycle/status` reports `active_content_encryption`.
- `GET /admin/lifecycle/confidentiality-migration/preview` reports eligible legacy active content.
- Tests cover encrypted artifact writes, minimized Qdrant payloads, encrypted retrieval chunk hydration, and migration boundaries.

