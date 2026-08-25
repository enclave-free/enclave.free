# Present Conversation Activity for its audience

Status: Accepted. This supersedes ADR-0024 only where that decision required identical visible Activity detail for Admin and User Conversations.

Enclave Free retains the same guarded Conversation Trace with both Admin and User assistant turns, including persistence and export, but presents that trace differently by audience. Admin Activity keeps provider, model-request, retry, timing, and usage diagnostics because Admins diagnose the system; User Activity keeps product-meaningful actions and outcomes such as Tool use, search, and retrieval while omitting those operational internals. Test User Sessions use the User presentation because their purpose is to reproduce the User Conversation experience. This preserves one trace contract and transparent evidence without turning the User experience into an operations console.
