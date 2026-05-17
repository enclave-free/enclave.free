# Data Classification

This document summarizes the operator-visible classifications exposed through
Data Lifecycle Status. These are domain categories, not table names.

| Classification item | Domain term | Classification |
| --- | --- | --- |
| PII Fields | User Profiles | Sensitive Instance Data |
| Uploaded Documents | Document Library | Sensitive Instance Content |
| Derived Chunks and Embeddings | Retrieval Index | Derived Instance Content |
| Secrets and Credentials | Deployment Settings | Deployment Secret |
| Audit Log Evidence | Audit Log | Governance Evidence |
| Inference Verification Records | Inference Verification Record | Governance Evidence |
| User Memory | User Memory | Sage Context |
| Session Memory | Sage Session Memory | Conversation State |
| Copied Exports | Copied Export | Deployment Surface |

Classification does not itself create a deletion guarantee. Active product
storage lifecycle behavior remains governed by Data Lifecycle Status, while
Copied Exports and other Deployment Surfaces remain operator responsibilities.
