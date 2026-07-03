# Knowledge and Curated Resources E2E Run

## Run

- Run ID: 2026-07-03-knowledge-resources-e2e
- Loop: Local verification / exploratory QA
- Target repo: enclave-free/enclave.free
- Local frontend: http://127.0.0.1:5173
- Local gateway: http://127.0.0.1:18000
- Human owner: Austin
- Started: 2026-07-03
- Current status: Passed with one product caveat documented below.

## Goal

Set up a local Enclave Free instance, upload knowledge documents, create curated resources, and verify Sage can list, suggest, and retrieve needle-in-haystack facts through the Knowledge and Curated Resources tools. Exercise both direct API contracts and the browser chat UI.

## Local Setup

- Started from the existing Docker Compose local stack. The app services were healthy: frontend, gateway, core backend, Sage web runtime, Qdrant, Sage Postgres, SearxNG, Tinfoil proxy, and Valkey.
- Claimed the local instance through the browser first-admin flow at `/admin?dev_nostr=1`.
- Created a test user type: `Families and Advocates`.
- Created an approved test user assigned to that user type.
- Verified the chat UI as that user through the browser at `/chat`.

## Seed Data

Knowledge documents uploaded through the ingest endpoint and processed to completion:

| Job ID | File | Status | Notes |
| --- | --- | --- | --- |
| `5039110e3321a53b` | `Harbor-Release-Protocol.md` | completed, default-active | Includes `HARBOR-77-ALPHA`, `harbor sunrise`, `+1-555-0142` extension `77`, and `Mira Calder`. |
| `15a20add96ce11fa` | `Family-Support-Field-Manual.md` | completed, default-active | Includes `river lantern`, `LANTERN-CHECK-204`, and `Aunt Sofia`. |

Curated resources created through `/admin/resources`:

| Resource ID | Name | Scope | Help Types | Needle Facts |
| --- | --- | --- | --- | --- |
| `e2e-nicaragua-legal-harbor` | Harbor Rights Legal Collective | Nicaragua | legal, humanitarian | `MARLIN-42`, blue-folder intake packet, `intake@harbor-rights.example.test`, `Signal +505-0000-4242`. |
| `e2e-global-family-support` | Lantern Family Support Desk | Global | legal, humanitarian | `LANTERN-CHECK-204`, Aunt Sofia backup guidance, `support@lantern-desk.example.test`. |

Fixture and result artifacts:

- `/Users/plebdev/Desktop/Projects/enclave-free/output/e2e-fixtures/Harbor-Release-Protocol.md`
- `/Users/plebdev/Desktop/Projects/enclave-free/output/e2e-fixtures/Family-Support-Field-Manual.md`
- `/Users/plebdev/Desktop/Projects/enclave-free/output/e2e-agent-results.json`

## Verification Evidence

Direct contract checks:

- `/internal/agent/resources/search` for legal help in Nicaragua returned Harbor Rights Legal Collective first, followed by the global Lantern Family Support Desk.
- `/vector-search` against collection `enclave_knowledge` retrieved both uploaded chunks for a Harbor-specific query.
- `/internal/agent/document-search` returned both uploaded sources with hydrated context after the approved user was assigned to the `Families and Advocates` user type.

Live Sage streaming checks through `/llm/chat/stream`:

| Scenario | Tools Used | Elapsed | Result |
| --- | --- | ---: | --- |
| List uploaded documents | Knowledge Search | 4.96s | Correctly listed and summarized both uploaded documents. |
| Retrieve Harbor needle facts | Knowledge Search | 4.10s | Returned `HARBOR-77-ALPHA`, `+1-555-0142` extension `77`, and `Mira Calder`. |
| Suggest Nicaragua legal referral | Curated Resources | 4.28s | Returned Harbor Rights Legal Collective, `MARLIN-42`, email, URL, and Signal contact. |
| Combined safety and referral answer | Knowledge Search, Curated Resources | 9.15s | Combined first-day safety steps with Harbor and Lantern referral details. |

Browser UI check:

- The chat UI showed both uploaded documents in the `Documents` area.
- `Knowledge` and `Resources` tools were both selected in the `Tools` area.
- A combined user query triggered both tool activity steps:
  - `Knowledge Search`: succeeded, "Retrieved uploaded-document passages for the answer."
  - `Curated Resources`: succeeded, "Found vetted curated resources for the answer."
- The final answer included safety steps, `harbor sunrise`, `river lantern`, `HARBOR-77-ALPHA`, `MARLIN-42`, Harbor Rights Legal Collective contact details, Lantern Family Support Desk details, and the private legal triage contact.

## Issue Log

### P2: Users without a user type cannot access global default Knowledge documents

Evidence:

- A direct `/internal/agent/document-search` call with an approved user actor but no `user_type_id` returned empty `sources` and empty `context`, even when explicit uploaded `job_ids` were requested and the documents were global defaults.
- After creating a user type and assigning the same test user to it, the same document-search path returned the expected sources and Sage answered correctly.
- The current implementation returns no accessible jobs when the actor is a non-admin user without a type:
  - `backend/app/internal_agent.py:245`

Impact:

- If a real user can reach chat before being assigned a user type, Knowledge Search silently behaves as if no documents are available, even when global default documents exist.
- This may be intended if every non-admin user must always have a user type before chat. If not, no-user-type users probably should inherit the global/default document-access set instead of getting an empty list.

Suggested fix if this is not intentional:

- Update `_build_accessible_job_ids` so `user.user_type_id is None` consults `database.get_available_documents_for_user_type(None)` or another explicit global-default access rule, then keep filtering requested `job_ids` through that allow-list.
- Add a regression test covering approved users with `user_type_id=None` and default-active documents.

## Result

Knowledge and Curated Resources passed the local end-to-end test. Sage can list uploaded documents, retrieve exact needle facts, suggest vetted curated resources, and combine both tool outputs in the browser UI. The only caveat found is the no-user-type Knowledge access behavior above.
