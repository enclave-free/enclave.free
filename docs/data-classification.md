# Data Classification

This document summarizes the operator-visible classifications exposed through
Data Lifecycle Status. These are domain categories, not table names.

| Classification item | Domain term | Classification |
| --- | --- | --- |
| PII Fields | User Profiles | sensitive Instance data |
| Uploaded Documents | Document Library | sensitive Instance content |
| Derived Chunks and Embeddings | Retrieval Index | derived Instance content |
| Secrets and Credentials | Deployment Settings | Deployment secret |
| Audit Log Evidence | Audit Log | governance evidence |
| Inference Verification Records | Inference Verification Record | governance evidence |
| User Memory | User Memory | Sage context |
| Session Memory | Sage Session Memory | Conversation state |
| Copied Exports | Copied Export | Deployment Surface |

Classification does not itself create a deletion guarantee. Active product
storage lifecycle behavior remains governed by Data Lifecycle Status, while
Copied Exports and other Deployment Surfaces remain operator responsibilities.
