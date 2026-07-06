# Enclave Free Prototype

The Enclave Free prototype is the candidate next version of Enclave Free, distinguished from the original product by integrating Sage directly as the agent runtime.

## Language

**Enclave Free**:
The product for private, operator-controlled AI assistance over curated organizational knowledge.
_Avoid_: original app, legacy app

**Operator-Controlled Privacy**:
The product principle that an **Operator** controls the **Instance** data boundary, configuration, document library, and approved external integrations.
_Avoid_: local-only, offline-only

**Operator-Controlled Data Lifecycle**:
The product boundary where the **Operator** can understand, configure or invoke, and review lifecycle handling for each operator-visible class of **Instance** data.
_Avoid_: cleanup, full compliance, guaranteed erasure

**Active Storage Lifecycle**:
The portion of **Operator-Controlled Data Lifecycle** that covers supported **Lifecycle Data Classes** in product-owned active **Storage Targets**.
_Avoid_: secure erase, deployment lifecycle, host compliance

**Lifecycle Data Class**:
An operator-visible category of **Instance** data whose retention, deletion, and audit posture can be described independently.
_Avoid_: table, storage backend, log surface

**Storage Target**:
A technical place where some or all of a **Lifecycle Data Class** is stored.
_Avoid_: lifecycle data class, product category

**Lifecycle Support Status**:
The stated level of retention, deletion, or audit support for a **Lifecycle Data Class** within supported **Storage Targets**.
_Avoid_: compliance status, deployment guarantee

**Deployment Surface**:
A technical runtime or infrastructure surface in a **Deployment** that may contain traces of **Instance** activity but is not currently controlled as a **Lifecycle Data Class**.
_Avoid_: lifecycle data class, product record

**Copied Export**:
An operator- or user-created copy of **Instance** data that leaves active product storage.
_Avoid_: product record, lifecycle-controlled data

**Data Retention**:
The **Operator** controlled rules for how long **Instance** data is kept before deletion or review.
_Avoid_: cleanup, storage duration

**Retention Execution**:
The act of applying **Data Retention** rules to eligible **Instance** data.
_Avoid_: data retention, cleanup job

**Scheduled Retention Policy**:
An **Operator** configured **Data Retention** rule that marks a **Lifecycle Data Class** for scheduled **Retention Execution**.
_Avoid_: retention scheduler, cron job

**Retention Scheduler**:
The technical automation that invokes scheduled **Retention Execution** without a human pressing a product control.
_Avoid_: scheduled retention policy, retention setting

**Retention Scheduler Observation**:
Operator-visible evidence that scheduled **Retention Execution** has run recently and what lifecycle result it produced.
_Avoid_: cron health, scheduler guarantee

**Retention Run Record**:
A metadata-only product record of one **Retention Execution** run used for lifecycle status, scheduler observation, and repair workflows.
_Avoid_: audit log entry, deleted data archive

**Data Deletion**:
The **Operator** controlled action or workflow that removes **Instance** data from active storage according to **Data Retention** rules or a specific deletion request.
_Avoid_: cleanup, hide, archive

**Secure Erase**:
A stronger deletion guarantee that reduces recoverability from underlying storage, logs, backups, or snapshots.
_Avoid_: data deletion, logical deletion

**Content Encryption Key**:
A deployment-held key used to encrypt product-owned active content storage that backend workflows must still read.
_Avoid_: admin key, user key, secure erase

**Artifact Encryption Posture**:
The **Deployment** choice that determines whether uploaded **Document** artifacts are encrypted in active storage or explicitly stored as plaintext.
_Avoid_: secure erase, document access, end-to-end encryption

**Retrieval Content Posture**:
The confidentiality posture for chunk text used to hydrate **Retrieval** context after vector search.
_Avoid_: retrieval index posture, artifact encryption posture

**Confidentiality Migration**:
A repair workflow that brings existing active content storage into the current confidentiality posture.
_Avoid_: retention execution, secure erase, cleanup

**Audit Log**:
An operator-visible record of security-relevant or state-changing actions within an **Instance**.
_Avoid_: debug log, server log

**External Integration**:
A configured service outside the **Instance** data boundary that a **Deployment** uses.
_Avoid_: platform service, hidden dependency

**Enclave Free Prototype**:
The candidate next version of **Enclave Free** where **Sage** is integrated into the product runtime.
_Avoid_: demo, throwaway prototype

**Instance**:
One operator-controlled installation of the **Enclave Free Prototype** with its own admin, users, configuration, document library, and data boundary.
_Avoid_: tenant, workspace, deployment

**Deployment**:
The technical environment that runs an **Instance**.
_Avoid_: instance, tenant

**Single-Instance Deployment**:
A **Deployment** pattern where one **Operator** runs one **Instance** through the supported Compose topology.
_Avoid_: platform deployment, multi-tenant deployment, arbitrary infrastructure

**Deployment Readiness**:
An operator-visible status that summarizes whether a **Single-Instance Deployment** has been configured, verified, and reviewed enough for real use.
_Avoid_: internal checklist, CI status, setup complete

**Deployment Wizard**:
A guided admin flow that helps an **Operator** reach **Deployment Readiness** without becoming a separate source of configuration authority.
_Avoid_: separate setup system, hidden provisioning, infrastructure wizard

**Deployment Automation**:
A deployment-owned machine actor that invokes approved operational workflows for an **Instance**.
_Avoid_: admin user, service account, bot admin

**Shared Rate Limit Store**:
A self-hosted **Deployment** component that coordinates abuse-prevention counters across runtime instances.
_Avoid_: product database, external rate-limit service, audit log

**Prototype Compatibility Debt**:
Transitional code, configuration aliases, documentation, or UI copy that preserves obsolete prototype behavior after the current **Sage** and **Enclave Control Plane** boundary has become the source of truth.
_Avoid_: data migration, confidentiality migration, rollback plan

**Instance Initiation**:
The first-time setup act where the first **Admin** authenticates and makes an **Instance** ready for configuration and user onboarding.
_Avoid_: registration, installation

**User Onboarding**:
The product flow where a **User** selects a **User Type** when needed and answers **Onboarding Questions** to create or update their **User Profile**.
_Avoid_: signup, registration

**User Approval**:
The admin-controlled decision that determines whether an authenticated **User** may enter normal user-facing product flows and **User Conversations**.
_Avoid_: onboarding, authentication

**Auto Approval**:
An **Instance Setting** that automatically grants **User Approval** to newly authenticated **Users**.
_Avoid_: open signup

**User Reachout**:
An authenticated user-facing path for a **User** to contact the **Operator** outside a **Conversation**.
_Avoid_: support ticket, user conversation, Sage tool

**Reachout Message**:
The message a **User** sends to the **Operator** through **User Reachout**.
_Avoid_: conversation content, support ticket

**Gateway**:
The deployment infrastructure that preserves the public API origin and routes requests to **Sage** or the **Enclave Control Plane**.
_Avoid_: API owner, policy engine

**Operator**:
The person or organization responsible for running an **Instance**.
_Avoid_: admin, owner, tenant

**Admin**:
The single operator identity that controls an **Instance**.
_Avoid_: staff user, owner, superuser

**User**:
A non-admin person allowed into an **Instance** to use **Sage** and provide onboarding information.
_Avoid_: customer, tenant, client

**Sage**:
The agent runtime integrated into the **Enclave Free Prototype** to own AI conversation behavior.
_Avoid_: LLM wrapper, chatbot service

**Agent Runtime**:
The part of the product responsible for AI conversation behavior, session memory, prompt assembly, tool selection, and agent-facing AI configuration.
_Avoid_: model adapter, chat endpoint

**Enclave Control Plane**:
The part of the product responsible for operator-owned facts and actions such as users, user types, instance settings, documents, ingestion, and safe database execution.
_Avoid_: backend, Python app

**Instance Settings**:
Operator-visible product settings inside an **Instance**.
_Avoid_: deployment config

**Deployment Settings**:
Operator-controlled desired technical environment settings for the **Deployment**.
_Avoid_: instance settings, live process state

**Agent Settings**:
Settings owned by **Sage** that shape **Conversation** behavior.
_Avoid_: LLM config, deployment config

**Model Provider**:
The configured service or local runtime **Sage** uses for model inference.
_Avoid_: model backend, LLM backend

**Tinfoil**:
The current preferred **Model Provider** because it supports encrypted, verifiable inference through a **Trusted Execution Environment**.
_Avoid_: generic LLM provider

**Encrypted Inference**:
Model inference where conversation content is protected from the surrounding infrastructure while it is sent to, processed by, and returned from the **Model Provider**.
_Avoid_: HTTPS, private API

**Verifiable Inference**:
The ability for the **Operator** to verify meaningful claims about where and how model inference ran.
_Avoid_: trusted API call

**Inference Verification Record**:
Operator-visible evidence, including full provider attestation material, that a **Model Provider** was checked against expected **Verifiable Inference** claims at a point in time.
_Avoid_: raw attestation, provider debug payload

**Trusted Execution Environment**:
A verifiable isolated execution environment used to protect model inference from the surrounding infrastructure.
_Avoid_: secure server, private hosting

**Model Provider Requirement**:
The requirement that a **Model Provider** support encrypted inference and **Verifiable Inference**, preferably through a **Trusted Execution Environment**.
_Avoid_: LLM preference

**Agent Personalization**:
Operator rules that tailor **Sage** conversation behavior for a **User** or **User Type**.
_Avoid_: user-type AI config

**Document Library**:
The operator-controlled collection of uploaded knowledge sources available to the product.
_Avoid_: RAG database, vector store

**Document**:
An operator-provided knowledge source in the **Document Library**.
_Avoid_: file, upload, source

**Document Ingestion**:
The process that turns an uploaded **Document** into searchable knowledge in the **Document Library** after the backend returns a durable job identifier.
_Avoid_: upload, file transfer, import

**Document Batch Ingestion**:
An admin workflow that starts **Document Ingestion** for multiple independent **Documents** in one action.
_Avoid_: folder document, bulk file, import folder

**Document Replacement**:
A **Document Ingestion** workflow where a newly uploaded **Document** supersedes an existing **Document** with the same canonical document name after successful ingestion.
_Avoid_: duplicate upload, overwrite file, reimport

**Document Access**:
Operator rules that determine which **Documents** are available to a **User** or **User Type**.
_Avoid_: permissions, RAG defaults

**Retrieval**:
The act of selecting relevant knowledge from the **Document Library** for use in an agent conversation.
_Avoid_: RAG

**Required Context**:
Operator- or policy-mandated knowledge that must be included in a **Conversation** outside ordinary model discretion.
_Avoid_: forced RAG, selected document scope, hidden retrieval

**User Type**:
An operator-defined user segment that determines which onboarding questions are asked of a user.
_Avoid_: role, permission group, audience segment

**Onboarding Question**:
An operator-defined question used to collect structured information from a user during onboarding.
_Avoid_: custom field

**User Profile**:
The structured information a **User** provides in response to **Onboarding Questions**.
_Avoid_: user fields, profile fields

**User Roster Export**:
A **Copied Export** that gives an **Admin** a spreadsheet-friendly roster of **Users**, their **User Approval** status, **User Type**, and available **User Profile** values for operational auditing.
_Avoid_: database export, backup, raw table dump

**User Manager Dashboard**:
An admin-only **Ordinary Product Flow** where the **Admin** can review **Users**, understand **User Approval**, **User Type**, and **User Profile** status, and perform focused user operations such as approving pending **Users**.
_Avoid_: CRM, staff console, user settings

**User Memory**:
Sage-owned durable context about a specific **User** that supports subtle personalization across **Conversations**.
_Avoid_: user profile, session memory, profile fields, user-facing memory manager

**User Memory Retention Class**:
The lifecycle category that determines whether a **User Memory** item is durable, expirable, or eligible because it has been superseded.
_Avoid_: memory type, importance score

**Session Memory**:
The conversation-specific information **Sage** retains to support an ongoing agent interaction.
_Avoid_: user profile, chat history

**Session Memory Compaction**:
The continuity-preserving summarization of older **Conversation Content** so an active **Conversation** can continue within **Model Provider** limits. It is not itself a user-facing loss of context.
_Avoid_: context loss, deletion, warning

**Reduced Conversation Context**:
A user-visible degradation where relevant **Conversation Content**, **Tool** results, **Retrieval** results, **Required Context**, or other expected context was omitted or materially reduced before inference.
_Avoid_: normal compaction, session memory summary

**Session Memory Deletion**:
**Data Deletion** for **Sage** owned **Session Memory** associated with a **Conversation**.
_Avoid_: delete query session

**Lifecycle Deletion Result**:
The per-target outcome of a **Data Deletion** or **Retention Execution** workflow for a **Lifecycle Data Class**.
_Avoid_: success flag, transaction result

**Lifecycle Error Category**:
A sanitized classification of a lifecycle target failure suitable for **Deletion Tombstones** and **Audit Log** events.
_Avoid_: raw stack trace, provider error dump

**Deletion Tombstone**:
A retained product record that marks a requested deletion and preserves enough lifecycle status to audit or retry incomplete deletion targets.
_Avoid_: deleted record, archive, hidden conversation

**Former Subject Reference**:
A minimal non-profile reference used in lifecycle evidence after a **User** has been deleted.
_Avoid_: deleted user profile, email, name

**Conversation**:
An ongoing interaction between a **User** or **Admin** and **Sage**.
_Avoid_: query session, chat session

**Conversation Content**:
The messages, prompts, retrieved document excerpts, required context, user profile context, tool results, and other content sent to a **Model Provider** for inference.
_Avoid_: user message, prompt text

**Admin Signer-Decrypted Context**:
Plaintext that an **Admin** browser signer decrypts from admin-authorized encrypted **Instance** data and deliberately delegates into one **Admin Conversation** turn protected by **Encrypted Inference**. It is not backend decryption, not backend private-key custody, and should not become **Conversation Trace** or **Audit Log** detail.
_Avoid_: backend decrypt, private-key handoff, trace evidence

**Conversation Trace**:
Operator-configured metadata attached to a **Conversation** response that explains how **Sage** produced the response, such as tool calls, retrieval steps, and reasoning traces when available.
_Avoid_: audit log, server log

**Conversation Activity Step**:
A sanitized user-visible step in a **Conversation** that shows meaningful **Sage** activity during an assistant turn, such as using a tool, retrieving context, checking configuration, or preparing a response.
_Avoid_: trace blob, debug event, raw tool call

**Trace Delta**:
An append-only live **Conversation Streaming Transport** event that carries raw or near-raw trace detail for the current assistant turn, such as reasoning content, model step boundaries, tool calls, tool results, retries, and timing.
_Avoid_: hidden debug event, separate log stream

**Activity**:
The user-facing presentation of live **Conversation Activity Steps** and final **Conversation Trace** metadata for an assistant turn. It is one visible concept even when the **Conversation Streaming Transport** delivers live steps and final trace metadata separately, and it should remain transparent enough for prototype debugging and auditability.
_Avoid_: hidden tool-call UI

**Reasoning Trace**:
Visible model reasoning captured during a **Conversation** turn, including raw provider reasoning content when available. A **Reasoning Trace** is not a post-hoc narration invented by **Sage** when the **Model Provider** does not expose reasoning content. A **Reasoning Trace** is conversation transparency metadata, not **Audit Log** evidence or a source of product authority.
_Avoid_: reasoning summary, server log, audit log

**Conversation Turn Timing**:
Transient user-visible timing information about meaningful phases within one **Conversation** turn, used to make slow turns understandable without becoming durable **Conversation Trace** or **Audit Log** evidence.
_Avoid_: phase timing, performance log, provider trace

**Conversation Model Bench**:
An internal evaluation that exercises real **Sage** **Conversation** paths against one or more **Model Provider** candidates and records timing, tool-use, and answer-quality evidence for comparison.
_Avoid_: CI test, unit test, provider smoke test, raw LLM benchmark

**Conversation Streaming Transport**:
A conversation response path that sends assistant turn, live trace status, answer deltas, and completion events to the client as they become available.
_Avoid_: streaming-shaped response, fake streaming, delayed batch response

**Conversation UI Surface**:
The user-facing interface where **Users** or **Admins** read and send **Conversation** messages, inspect permitted **Conversation Trace** details, and choose visible conversation controls.
_Avoid_: agent runtime, chatbot service, conversation owner

**Conversation Sidebar**:
The session-navigation region of the **Conversation UI Surface**. In the current prototype slice it may establish the ChatGPT-like shell with local current-conversation affordances, while durable history, resume, rename, delete, and cross-device persistence remain future **Sage** session-history work.
_Avoid_: fake persistent history, session memory owner

**Conversation Channel**:
A delivery path through which a **User** or **Admin** participates in a **Conversation** with the same **Sage** inside an **Instance**.
_Avoid_: separate agent, native runtime, alternate Sage

**Conversation UI State**:
Client-owned state needed to operate the **Conversation UI Surface** for the current actor, including visible turns, in-progress turn status, selected controls, transient errors, and pending confirmation prompts.
_Avoid_: session memory, conversation owner, agent state

**Conversation Control Snapshot**:
The selected visible conversation controls captured when a **User** or **Admin** submits a turn, such as enabled **Tool Sets** and **Tool** constraints.
_Avoid_: current controls, session settings, agent settings

**Trace Visibility Posture**:
The prototype product stance that **Conversation Trace** details are visible by default for both **Admin Conversations** and **User Conversations**. It is not a per-actor policy surface in the current transparent prototype phase.
_Avoid_: debug mode, logging level, actor-specific trace policy

**Tool**:
A concrete callable contract that **Sage** exposes to the model during a **Conversation** so the model can request an authorized action or information source.
_Avoid_: endpoint, fuzzy context category, hidden prompt blob

**Typed Proposal Tool**:
A model-callable **Admin Config Tool Set** contract whose arguments describe admin write intent in product terms and whose deterministic implementation returns an **Executable Change Set**. It keeps canonical **Enclave Control Plane** request construction out of model-authored free-form JSON.
_Avoid_: raw change-set JSON tool, request JSON proposal, hidden serializer prompt

**Tool Set**:
A visible **Conversation UI Surface** control that enables a related set of **Tools** for the submitted turn.
_Avoid_: route mode, hidden classifier, prompt context toggle

**Model-Driven Tool Loop**:
The Sage-owned loop where the model sees enabled **Tool** contracts, chooses calls, receives **Tool** results, and continues until it can answer or produce an **Executable Change Set**.
_Avoid_: preselected context pipeline, provider-native function-calling dependency

**Ordinary Product Flow**:
A non-agent UI or API path where a **User** or **Admin** performs an action directly through the product.
_Avoid_: tool, conversation action

**Change Confirmation**:
The explicit **Admin** approval required before state-changing actions proposed during an **Admin Conversation** are applied. Executable approval is represented by **Conversation UI State** for a valid pending change set, not by free-form conversational acknowledgement alone.
_Avoid_: review-only workflow, chat-only confirmation

**Superseded Change Confirmation**:
A prior pending **Change Confirmation** that is no longer actionable because a later assistant turn produced a newer **Executable Change Set**.
_Avoid_: duplicate pending approval, stale apply button

**Executable Change Set**:
A structured state-change proposal from **Sage** that the **Conversation UI Surface** can validate, preview, and place into **Change Confirmation**. Prose-only recommendations are not executable change sets.
_Avoid_: prose proposal, suggested edits, assistant recommendation

**Change Set Recovery Turn**:
An **Admin Conversation** turn where the **Admin** indicates they want to apply prior guidance but no valid pending **Executable Change Set** exists. The turn should continue to **Sage** so Sage can produce an **Executable Change Set** or ask a focused follow-up.
_Avoid_: no pending changes error, frontend apply failure

**User Conversation**:
A **Conversation** between a **User** and **Sage** for assistance inside an **Instance**.
_Avoid_: user query

**Admin Conversation**:
A **Conversation** between the **Admin** and **Sage** for configuring or operating an **Instance**.
_Avoid_: admin query

**Subject User**:
The specific **User** an **Admin Conversation** is currently about.
_Avoid_: current user, target user

**Admin Configuration Assistant**:
An admin-only **Admin Conversation** surface for configuration questions and confirmed **Enclave Control Plane** changes.
_Avoid_: support widget, floating chat bubble

**Admin Config Tool Set**:
The admin-only **Tool Set** that exposes configuration read **Tools** and configuration proposal **Tools** to **Sage** during an **Admin Conversation**.
_Avoid_: scoped config context, config dump, manual context switch

## Relationships

- **Enclave Free Prototype** succeeds the first version of **Enclave Free** if the prototype direction is validated
- **Enclave Free** is guided by **Operator-Controlled Privacy**
- **Operator-Controlled Privacy** allows **External Integrations** when they are visible and configurable by the **Operator**
- **Operator-Controlled Data Lifecycle** is part of **Operator-Controlled Privacy**
- **Operator-Controlled Data Lifecycle** is described through **Lifecycle Data Classes**
- **Inference Verification Records** are a **Lifecycle Data Class**
- **Active Storage Lifecycle** is the first production-readiness target for **Operator-Controlled Data Lifecycle**
- **Active Storage Lifecycle** excludes **Deployment Surfaces** unless a future decision promotes a surface into a supported **Lifecycle Data Class**
- A **Lifecycle Data Class** is grouped by product meaning, not by **Storage Target**
- A **Lifecycle Data Class** may span one or more **Storage Targets**
- A **Lifecycle Data Class** has its own lifecycle support status
- **Lifecycle Support Status** is scoped to the stated **Lifecycle Data Class** and supported **Storage Targets**
- A **Deployment Surface** may contain traces of **Instance** activity without being a supported **Lifecycle Data Class**
- A **Copied Export** becomes a **Deployment Surface** after creation and is outside **Active Storage Lifecycle**
- Export actions for sensitive **Instance** data should create **Audit Log** evidence even though the exported copy is not lifecycle-controlled by the product
- Browser local storage, session storage, and cache are **Deployment Surfaces**, but the product should actively minimize deliberate browser-side storage of **Conversation Content** and other sensitive **Instance** data
- **Data Retention** is part of **Operator-Controlled Privacy**
- **Retention Execution** applies **Data Retention** rules
- **Retention Execution** may be operator-invoked before it is scheduled automatically
- A **Scheduled Retention Policy** identifies which **Lifecycle Data Classes** scheduled **Retention Execution** should include
- **Scheduled Retention Policy** should be configurable per supported **Lifecycle Data Class**
- An **Admin** may disable scheduled retention for a supported **Lifecycle Data Class** in the first version
- Disabled scheduled retention must be visible in lifecycle status and audited when changed
- New **Instances** should start with conservative scheduled retention defaults for expirable active-storage classes while governance evidence remains retained until separately configured
- **Lifecycle Readiness** requires explicit **Admin** review of current lifecycle posture even when conservative defaults are already active
- **Lifecycle Readiness** may become stale after lifecycle-relevant changes and should be restored by **Admin** review
- Stale **Lifecycle Readiness** should warn **Admins** without blocking normal **User Conversations** in the first version
- **Admin Conversations** may help repair stale **Lifecycle Readiness** while still obeying **Change Confirmation**, **Audit Log**, and **Verifiable Inference** gates
- A **Retention Scheduler** triggers scheduled **Retention Execution** automatically
- The first **Scheduled Retention Policy** support may exist before the product includes its own **Retention Scheduler**
- An externally configured **Retention Scheduler** is acceptable for the first production-ready **Active Storage Lifecycle** milestone if missing or stale scheduler execution is visible to the **Operator**
- A **Retention Scheduler Observation** can be healthy even when no data was eligible for deletion if the run created lifecycle and **Audit Log** evidence
- The first scheduled enforcement slice of **Active Storage Lifecycle** covers **Sage Session Memory**, **Uploaded Document Artifacts**, **User Memory**, and sensitive **Audit Log** detail
- The first scheduled enforcement slice of **Active Storage Lifecycle** does not schedule deletion of active **User Profiles**, current **Document Library** records, current **Retrieval Index** entries, or **Inference Verification Records**
- **Inference Verification Records** remain indefinitely retained until a separate evidence-retention policy exists
- Scheduled **Uploaded Document Artifacts** retention cleans failed, superseded, orphaned, or abandoned artifacts rather than current successful **Document Library** records
- Scheduled **Sage Session Memory** retention uses **Conversation** last activity rather than creation time when deciding staleness
- Scheduled **Audit Log** retention compacts sensitive detail while preserving lifecycle and governance evidence; it does not delete whole **Audit Log** rows in the first scheduled enforcement slice
- **Audit Log** detail compaction should be irreversible in active product storage
- The first **Audit Log** retention policy should not include an **Admin** setting to retain full sensitive audit detail indefinitely
- Full sensitive **Audit Log** detail that an **Operator** preserves outside compaction becomes a **Copied Export** or **Deployment Surface**, not active product lifecycle evidence
- **Retention Execution** reports results per **Lifecycle Data Class**
- **Retention Execution** evidence should preserve metadata-only run status, counts, per-class outcomes, retry references, and sanitized failure categories without preserving deleted content
- A **Retention Run Record** is the operational source for lifecycle status and scheduler observation, while the **Audit Log** is the tamper-evident governance trail for the same run
- Manual and machine-triggered **Retention Execution** should create the same kind of **Retention Run Record** with different actor and trigger metadata
- **Retention Run Records** should be retained indefinitely in the first version as metadata-only lifecycle evidence
- Future compaction or deletion of **Retention Run Records** should use a separate evidence-retention policy
- A **Retention Run Record** should store a self-explanatory metadata-only policy snapshot, not only a hash or reference to the current policy
- **Retention Execution** should evaluate enabled **Lifecycle Data Classes** independently and may partially succeed
- A **Retention Execution** run should fail completely only when trustworthy lifecycle evidence cannot be created or the run cannot authenticate or read policy
- Scheduled **User Memory** retention should remove stale expirable or superseded **User Memory**, not active Admin-confirmed **User Memory** merely because it is old
- Destructive **Retention Execution** requires explicit **Admin** confirmation and should make eligibility or result counts visible
- Human-triggered **Retention Execution** should require fresh preview or current eligibility counts, while machine-triggered scheduled **Retention Execution** runs from the policy snapshot and is reviewed afterward
- A dry-run or preview for broad **Retention Execution** is desired but not required for the first slice
- Operator-invoked **Retention Execution** should create an **Audit Log** event even when no data changes
- **Data Deletion** executes **Data Retention** decisions or specific deletion requests
- **Data Deletion** removes data from active product storage unless a specific **Secure Erase** guarantee is stated
- Product copy should avoid "permanent deletion" or "delete forever" unless a **Secure Erase** or backup-retention guarantee exists
- A **Content Encryption Key** protects active content storage at rest without making it end-to-end encrypted from backend workflows
- A **Content Encryption Key** belongs to the **Deployment** rather than the **Admin**
- **Artifact Encryption Posture** is a **Deployment Setting**, not an **Instance Setting**
- **Artifact Encryption Posture** should default to encrypted active storage when a **Content Encryption Key** is configured
- Plaintext uploaded artifacts are an explicit **Operator** choice reported in lifecycle status, not the default privacy posture
- Changes to **Artifact Encryption Posture** should create **Audit Log** evidence
- Changing **Artifact Encryption Posture** affects future uploaded **Documents** unless a separate migration workflow rewrites existing artifacts
- **Retrieval Content Posture** should require encrypted chunk text in active product storage
- **Retrieval Content Posture** is separate from **Artifact Encryption Posture** because derived chunk text is a distinct active content surface
- **Confidentiality Migration** is required before legacy plaintext active content storage can be reported as fully matching an encrypted posture
- **Confidentiality Migration** should report per-document results and avoid claiming **Secure Erase**
- An **Audit Log** supports **Operator-Controlled Privacy** by making important **Instance** changes visible after the fact
- **Enclave Free Prototype** integrates **Sage** directly into the product runtime
- A **Deployment** usually runs one **Instance** in the prototype
- The first productionization target is a **Single-Instance Deployment**, not Kubernetes, managed cloud hosting, multi-instance scaling, or arbitrary infrastructure
- **Deployment Readiness** is broader than **Lifecycle Readiness**; it includes external integration configuration, runtime validation, recovery posture, and reviewed lifecycle status
- **Deployment Readiness** should be visible to the **Operator** through the **Instance**, not only maintained as an internal engineering checklist
- **Deployment Settings** are the product source of truth for operator-controlled desired runtime configuration, while running services may remain stale until restart or deployment apply
- The first unified **Deployment Settings** slice covers operator-facing integration and origin settings, not low-level infrastructure wiring such as database URLs, internal service tokens, cookie names, gateway route maps, or container host/port topology
- **Deployment Readiness** is advisory in the first version except where a missing or failed prerequisite would violate a privacy-critical runtime gate such as current **Verifiable Inference**
- Stale **Lifecycle Readiness**, missing recovery drills, or unacknowledged **Deployment Surfaces** should warn **Admins** without blocking normal **User Conversations** in the first **Deployment Readiness** version
- A **Deployment Wizard** guides first-run **Deployment Readiness** review using the same underlying **Deployment Settings**, **Agent Settings**, lifecycle status, and validation APIs as the ongoing admin surfaces
- A **Deployment Wizard** must not become a parallel configuration system or hide the setting ownership split between **Deployment Settings**, **Instance Settings**, and **Agent Settings**
- The first **Deployment Wizard** slice should guide readiness review and point to existing edit surfaces before it becomes a full inline editor
- The first experience-readiness polish milestone should prioritize **Admin** confidence in initiating, configuring, verifying, and reviewing an **Instance** before broad visual polish of **User Conversations**
- The first i18n polish milestone should mean extraction, fallback correctness, interpolation safety, layout resilience, and terminology consistency before human-quality translation review across every locale
- Default language, theme, and branding should first be **Instance Settings** controlled by the **Admin**; per-user preferences are a later user preference model, not a first milestone browser-storage feature
- Diagnostic dashboards should remain available for development and verification, but they should not be the primary first impression or product path for **Admins** or **Users**
- **Deployment Automation** belongs to the **Deployment**, not to the **Admin**
- **Deployment Automation** may invoke scheduled operational workflows without representing a human **Admin** action
- A **Shared Rate Limit Store** belongs to the **Deployment**, not to the **Document Library**, **Audit Log**, or **Active Storage Lifecycle**
- **Prototype Compatibility Debt** can be removed when it preserves obsolete prototype behavior rather than an active product or migration boundary
- **Prototype Compatibility Debt** excludes **Confidentiality Migration** safeguards until legacy plaintext active content storage has been resolved
- Plaintext fallback for existing active content is a **Confidentiality Migration** concern, not **Prototype Compatibility Debt**, until the relevant storage state has been verified and migrated
- A **Deployment** includes a **Gateway**
- The **Gateway** routes requests to **Sage** or the **Enclave Control Plane**
- The **Gateway** does not own product correctness
- An **Operator** is responsible for an **Instance**
- An **Instance** has exactly one **Admin** in the current prototype
- **Instance Initiation** establishes the current prototype's **Admin**
- User onboarding is unavailable until **Instance Initiation** has happened
- **User Onboarding** may reopen for an existing **User** when the **Operator** adds required **Onboarding Questions** the user has not answered
- **User Approval** gates access after authentication and before normal user-facing product flows
- **Auto Approval** is a mode of **User Approval**
- **User Reachout** requires authentication but does not require **User Approval**
- **User Reachout** is an **Ordinary Product Flow**, not a **Conversation** or **Tool**
- A **Reachout Message** is not **Conversation Content** unless a future feature sends it to **Sage** or a **Model Provider**
- Future **Conversation Channels** may support more direct **Admin** and **User** contact paths, but the current **User Reachout** remains the email-only ordinary product flow
- The **Admin** is the authenticated control identity for the **Operator** in the current prototype
- An **Instance** has zero or more **Users**
- A **User** belongs to at most one **User Type**
- **Sage** is the **Agent Runtime** inside the **Enclave Free Prototype**
- The **Enclave Control Plane** provides operator-owned facts and actions to **Sage**
- Sage-owned public **Agent Runtime** routes should not keep duplicate Python behavior or Python tombstones as rollback paths
- Obsolete Python public **Agent Runtime** routes should be absent after the Sage hard cut rather than failing through compatibility tombstones
- Unused internal Sage-to-Python compatibility endpoints are **Prototype Compatibility Debt**
- Sage should depend only on the active private **Enclave Control Plane** contract, and obsolete internal endpoints should fail clearly rather than preserve old ownership boundaries
- **Instance Settings** belong to the **Instance**
- **Deployment Settings** belong to the **Deployment**
- **Agent Settings** belong to **Sage**
- **Agent Settings** are the source of truth for Sage's persona and conversation behavior across **Conversation Channels**
- **Conversation Channels** may shape delivery and formatting, but should not define a separate Sage identity
- The first Signal **Conversation Channel** should provide **Conversation** access to **Sage** rather than direct **Admin** to **User** messaging
- **Conversation Channels** should share the same **Conversation** and **Session Memory** model rather than creating channel-specific Sage memory
- **Conversation Channel** access should use existing **Admin** identity and **User Approval** authority rather than a separate channel-specific permission model
- **Model Provider** is an **Agent Setting**
- A **Model Provider** must satisfy the **Model Provider Requirement**
- **Tinfoil** is the current preferred **Model Provider**
- Maple-era provider labels, aliases, and UI copy are **Prototype Compatibility Debt** in the **Enclave Free Prototype**
- The **Enclave Free Prototype** should fail clearly rather than silently honoring Maple-era **Model Provider** aliases
- Upstream-native Sage code is not **Prototype Compatibility Debt** by itself, but channel-native assumptions become **Prototype Compatibility Debt** when they leak into enclave.free product behavior, docs, UI, or **Agent Settings**
- Generic deployment-facing `LLM_*` settings may remain while they describe Python-side **Deployment Settings**, diagnostics, and verification metadata
- Generic deployment-facing `LLM_*` settings should not be described as live Sage **Agent Settings** until runtime configuration is unified
- Admin-facing copy should not teach obsolete **Model Provider** labels or imply that Python deployment config live-edits Sage runtime environment
- **Encrypted Inference** protects conversation content from surrounding infrastructure
- **Verifiable Inference** lets the **Operator** verify meaningful execution claims
- An **Inference Verification Record** captures the outcome of checking a **Model Provider** against expected **Verifiable Inference** claims
- **Inference Verification Records** are historical records, with the latest record available as the current verification status
- **Deployment Automation** should create **Inference Verification Records** at startup and when provider-relevant settings change
- Startup should attempt **Verifiable Inference** checks before accepting protected model inference
- If startup verification fails, the product should enter an admin-repair mode where normal **Conversation** traffic is blocked but admin surfaces, diagnostics, and manual verification remain available
- An **Admin** may manually create an **Inference Verification Record** for troubleshooting
- Normal **Conversation** traffic should fail closed when current **Verifiable Inference** status is failed or missing
- Admin-only diagnostics may run when current **Verifiable Inference** status is failed or missing so the **Operator** can repair the **Deployment**
- Stale **Inference Verification Records** should have a grace period before normal **Conversation** traffic fails closed
- Model Provider calls that send **Conversation Content** or other user- or admin-derived product content should fail closed when current **Verifiable Inference** status is failed, missing, or stale beyond the grace period
- Verification, health checks, model listing, and non-content diagnostics may run when current **Verifiable Inference** status is failed, missing, or stale
- **Verifiable Inference** enforcement should be enabled by default for protected model inference
- Any bypass for **Verifiable Inference** enforcement should be a conspicuous development-only **Deployment Setting**, not an ordinary **Instance Setting**
- When **Verifiable Inference** enforcement is bypassed, product status and lifecycle posture should clearly report the weakened privacy posture
- A current **Inference Verification Record** is the latest successful record for the configured **Model Provider** identity, model or runtime claim set, and provider endpoint within the freshness window
- Changing provider-relevant settings should immediately make prior **Inference Verification Records** non-current for normal **Conversation** traffic
- The near-term **Inference Verification Record** freshness window should default to 24 hours
- **Sage** or its provider adapter performs **Verifiable Inference** checks because it owns model inference behavior
- The **Enclave Control Plane** stores and exposes **Inference Verification Records** as operator-visible privacy evidence
- **Inference Verification Records** are scoped to the **Deployment** but visible to the **Operator** through the **Instance**
- Each **Conversation** response should reference the current **Inference Verification Record** that allowed the model inference
- Referencing an **Inference Verification Record** from a **Conversation** response does not require per-turn provider attestation
- **Inference Verification Records** should store normalized verification fields and full provider attestation material
- Near-term **Inference Verification Records** should include provider identity, provider endpoint, model or runtime identifier, verification status, checked time, expiry time, trigger, expected claims fingerprint, actual claims fingerprint, verifier version, failure category, sanitized failure message, and full attestation material
- Full attestation material should be visible to **Admins**, while ordinary **Users** should see at most high-level verification status
- Failed **Inference Verification Records** should retain full provider attestation material when available
- Provider attestation material should be redacted only when the verifier identifies secrets or credentials in the provider response
- **Inference Verification Records** are separate from the **Audit Log**
- Verification status changes, manual verification, and blocked **Conversation** traffic due to failed, missing, or stale **Verifiable Inference** status should create concise **Audit Log** events
- The near-term verifier should use a provider-neutral verification interface with a Tinfoil implementation
- The near-term **Admin** surface for **Inference Verification Records** should live with Model Provider configuration
- The current **Inference Verification Record** view should show status, checked time, expiry time, provider claims, model or runtime claims, and manual verification controls
- Historical **Inference Verification Records** should expose full provider attestation material to **Admins**
- Normal chat surfaces should not expose detailed **Inference Verification Records** in the first version, except for a blocked-state message when **Conversation** traffic fails closed
- **Inference Verification Records** should be retained indefinitely by default as operator-visible security evidence
- **Inference Verification Records** should not share ordinary **Conversation** retention policy
- Future deletion or compaction of **Inference Verification Records** should use a separate evidence-retention policy
- Near-term lifecycle support for **Inference Verification Records** should include inventory and status before configurable retention or deletion controls
- Full provider attestation material in **Inference Verification Records** should be encrypted at rest
- Normalized **Inference Verification Record** metadata may remain queryable for status, history, lifecycle inventory, and audit correlation
- A **Trusted Execution Environment** is one mechanism for **Verifiable Inference**
- **Agent Personalization** may tailor **Agent Settings** for a **User** or **User Type**
- The **Enclave Control Plane** owns the **Document Library**
- A **Document Library** contains zero or more **Documents**
- The **Enclave Control Plane** owns document ingestion
- **Document Ingestion** starts when the backend returns a durable job identifier for an uploaded **Document**
- **Document Batch Ingestion** creates multiple independent **Document Ingestion** jobs
- **Document Batch Ingestion** may partially succeed when some selected files can become **Documents** and others cannot
- **Document Batch Ingestion** rejects later files in the same action when they resolve to an already-selected canonical document name
- **Document Replacement** preserves the Operator's intended **Document Access** for the canonical document name
- During **Document Replacement**, the existing **Document** remains current unless the replacement succeeds
- **Document Replacement** applies consistently to single-document and batch-document admin workflows
- Only current completed **Documents** are visible to **Users** for **Document Access** and **Retrieval**
- **Document Access** determines which **Documents** are available before **Retrieval** or **Required Context** is applied
- **Retrieval** is an **Agent Runtime** capability over the **Document Library**, even when the **Enclave Control Plane** executes the underlying search
- Public **Conversation** session discovery and storage belong to **Sage**, not the **Enclave Control Plane**
- In ordinary chat, selected **Documents** are **Tool** constraints for the Knowledge **Tool Set**, not hidden **Required Context**
- **Required Context** is reserved for policy-mandated context selected outside the agent's discretion
- A **User Type** has zero or more **Onboarding Questions**
- A user belongs to at most one **User Type**
- A **User Type** may become an extension point for tailored product behavior, but its core meaning is onboarding segmentation
- A **User Profile** contains answers to **Onboarding Questions**
- **Sage** may use a **User Profile** as context, but the **User Profile** is owned by the **Enclave Control Plane**
- **User Memory** is about one **User** even when it is written during another actor's **Conversation**
- **User Memory** belongs to **Sage** and must remain distinct from **User Profile**
- **User Memory** is not a user-facing product surface in the current product posture
- Admin-authored **User Memory** requires **Change Confirmation** because it changes durable state about a **User**
- **User Memory** may only be written after the subject **User** has been resolved unambiguously
- Initial **User Memory** should be limited to preferences, operational notes, context notes, and relationship notes
- **User Memory** records should keep human-readable prose with lightweight metadata rather than replacing prose with rigid profile fields
- **User Memory** should record simple source metadata
- **User Memory** source metadata should refer to the **Conversation** rather than internal agent identifiers
- Initial **User Memory** source metadata does not need exact message-level provenance
- **User Memory** changes should supersede or soft-delete prior records rather than overwriting them destructively
- **User Memory** should be deleted when its subject **User** is deleted
- **User Memory** should be stored separately from session-scoped archival memory
- User-authored **User Memory** about the current **User** may be captured ambiently when allowed
- Proposed **User Memory** writes are exposed only as an admin confirmation step in an **Admin Conversation**
- Ambient **User Memory** capture should be limited to clear, low-risk personalization facts
- Ambient **User Memory** capture should happen outside the user-facing response path
- Ambient **User Memory** capture should not block the user-facing response
- Ambient **User Memory** extraction should use the configured **Model Provider** in the first version
- Failed ambient **User Memory** capture should be logged but not surfaced in product UI in the first version
- Ambient **User Memory** extraction should run only after a simple prefilter indicates likely personalization content
- Ambient **User Memory** should be grounded in the **User's** message even when the extractor also sees Sage's response
- Ambient **User Memory** should not be created from tool results or **Retrieval** outputs in the first version
- Ambient **User Memory** capture should insert or skip duplicates rather than superseding existing records in the first version
- **User Conversations** should not support natural-language **User Memory** deletion in the first version
- Admin-authored **User Memory** writes are explicit confirmed actions, not ambient capture
- Admin-authored **User Memory** may be informed by admin-visible context when the **Admin** confirms the exact write
- **Session Memory** summaries should not duplicate **User Memory**
- **User Memory** retrieval should load a bounded set of active records for the subject **User**
- **User Memory** may use a simple importance value for bounded retrieval ordering
- Ambient **User Memory** capture should not create high-importance records
- **User Memory** writes should prevent obvious duplicate active records
- Admin-authored **User Memory** writes should create **Audit Log** entries
- Ambient **User Memory** capture should keep source metadata without creating **Audit Log** entries in the first version
- **Admins** may inspect **User Memory** for **Users** in admin-only surfaces or **Admin Conversations**
- Initial admin inspection of **User Memory** should be scoped to one **User** at a time
- **User Memory** should be included in operational backups but not ordinary **Conversation** exports in the first version
- Initial **User Memory** should be limited to low-sensitivity personalization and operational context
- Initial **User Memory** may be stored without content encryption to keep **Sage** context assembly simple
- Sensitive or critical user facts should be captured through encrypted **User Profile** fields when needed, not **User Memory**
- **Sage** should redirect sensitive or critical proposed **User Memory** into **User Profile** design instead
- Higher-sensitivity **User Memory** requires a separate encryption, retention, and access-control decision
- Initial **User Memory** should avoid tags so metadata stays minimal
- Initial **User Memory** is implicitly scoped to the current **Instance**
- **User Memory** may be loaded into both **User Conversations** and **Admin Conversations** when relevant
- **Admin Conversations** may use a **Subject User** to inspect or propose **User Memory**
- A **Subject User** is **Conversation** state, not **User Memory**
- A **Subject User** remains active until the **Admin** switches it, clears it, or starts a new **Conversation**
- A **Subject User** does not change **Document Access** in the first version
- **User Memory** for a **Subject User** may be loaded into an **Admin Conversation** when clearly labeled
- **User Profile** and **User Memory** may both inform a **Conversation** but should be labeled separately
- Ambient **User Memory** capture should be controlled by a simple **Instance Setting**
- Ambient **User Memory** should default to an expirable **User Memory Retention Class**
- Admin-authored **User Memory** should default to a durable **User Memory Retention Class**
- Superseded **User Memory** is eligible for scheduled retention after its retention window
- **Session Memory** belongs to the **Agent Runtime**
- **Session Memory Compaction** should preserve continuity for the active **Conversation** and should not be presented as **Reduced Conversation Context** unless expected context was actually omitted or materially degraded
- Ordinary **Session Memory Compaction** should render, when visible, as a quiet system notice rather than **Activity**
- **Session Memory Compaction** should preserve enough recent **Conversation Content** that ordinary multi-turn admin setup conversations do not feel reset after a short exchange
- **Session Memory Deletion** must remove the **Session Memory** associated with a **Conversation**
- **Session Memory Deletion** is logical active-storage deletion in the first version, not **Secure Erase**
- **Session Memory** is the first priority **Lifecycle Data Class** for completing **Operator-Controlled Data Lifecycle** across the **Enclave Control Plane** and **Agent Runtime** boundary
- The primary lifecycle unit for **Session Memory** is a **Conversation**
- **Data Retention** eligibility for **Conversations** should be based on last **Conversation** activity rather than creation time
- **Conversation** activity for **Data Retention** means human and Sage assistant turns, not lifecycle retries, audit writes, retention scans, or tombstone updates
- Opening or viewing a **Conversation** is not **Conversation** activity for **Data Retention**
- **Conversation UI State** belongs to the **Conversation UI Surface** and must not become the source of truth for **Session Memory** or durable **Conversation** ownership
- A **Conversation Control Snapshot** describes the visible controls that shaped a submitted turn, while current controls describe defaults for the next turn
- The first **Conversation** retention policy should be **Instance** level rather than **User Type** specific
- **Admin Conversations** and **User Conversations** should share the same **Conversation Content** and **Session Memory** retention window in the first version
- **Retention Execution** should re-check **Conversation** eligibility before deletion and skip candidates that became active
- **User** deletion may remove active **User Profile** and access state while leaving retryable **Deletion Tombstones** for incomplete **Session Memory Deletion** targets
- **Session Memory Deletion** is a coordinated workflow with explicit **Lifecycle Deletion Results**, not a distributed transaction
- **Lifecycle Deletion Results** should use **Lifecycle Error Categories** rather than raw backend error details
- Incomplete **Session Memory Deletion** should leave a retryable **Deletion Tombstone** visible to the **Operator**
- A **Deletion Tombstone** should keep lifecycle metadata and retry evidence without retaining **Conversation Content**
- **Deletion Tombstone** surfaces should not expose **Conversation Content** even when a failed target may still physically contain it
- A **Deletion Tombstone** for a deleted **User** should use a **Former Subject Reference** rather than retaining deleted **User Profile** data
- Successful **Session Memory Deletion** should leave lifecycle and audit metadata only, not **Conversation Content**
- **Deletion Tombstones** are lifecycle evidence and should remain until deletion targets complete and an evidence-retention policy allows purging them
- **Deletion Tombstones** are owned by the **Enclave Control Plane** as operator-visible lifecycle evidence
- **Deletion Tombstones** are visible to the **Admin** as the **Operator's** control identity, not to ordinary **Users** in the first version
- Deleted or tombstoned **Conversations** should disappear from ordinary **User** conversation surfaces while remaining visible in **Admin** lifecycle surfaces when evidence or retry is needed
- Tombstoned **Conversations** should be handled as retryable lifecycle records, not as active **Data Retention** candidates
- **Deletion Tombstone** retry should be manual and **Admin** invoked in the first version
- Each manual **Deletion Tombstone** retry should create a new **Audit Log** event linked to the original lifecycle workflow
- **Sage** owns the **Session Memory** deletion target and reports target results back to the **Enclave Control Plane**
- **Session Memory Deletion** should use a formal internal lifecycle contract between the **Enclave Control Plane** and **Sage**, not overload public query-session deletion semantics
- The first **Session Memory** lifecycle implementation should update security posture, session behavior, and internal contract docs alongside code
- User-initiated, **Admin**-initiated, and **Retention Execution** paths should share the same underlying **Session Memory Deletion** workflow with role-specific visibility
- **Users** should see the immediate result of their own **Session Memory Deletion** request, while retained lifecycle evidence and retryable **Deletion Tombstones** remain **Admin** visible in the first version
- User-initiated **Session Memory Deletion** should create a privacy-preserving lifecycle **Audit Log** event without **Conversation Content**
- Operator-invoked **Session Memory Deletion** should create an **Audit Log** event even when it fails or deletes nothing
- A **Conversation** may have **Session Memory**
- A **Conversation** may include **Retrieval**, **Required Context**, and **User Profile** context
- **Conversation Content** is the inference payload protected by **Encrypted Inference**
- A **Conversation Model Bench** exercises real **User Conversations** or **Admin Conversations** rather than raw **Model Provider** prompts
- **Conversation Model Bench** evidence is internal comparison material, not product **Conversation Trace** or **Audit Log** evidence
- A **Conversation Trace** may include **Tool Trace**, **Retrieval Trace**, **Reasoning Trace**, and **Reasoning Summary** details
- A **Conversation Activity Step** is a user-visible rendering unit derived from **Conversation Trace** metadata
- A **Conversation Trace** may expose raw model reasoning in both **Admin Conversations** and **User Conversations**, but it must still protect credentials, hidden system/developer instructions, internal auth headers, raw secret reveal results, infrastructure/runtime environment dumps, and other authority-bearing internals
- When the minimal blocklist catches protected content inside a **Trace Delta**, **Sage** should keep the event, replace protected content with `[redacted]`, and mark it guarded; hidden authority-bearing instructions should be redacted as a whole field
- Raw decrypted database rows should appear in **Conversation Trace** only when the row content was already intentionally returned through an authorized product view or authorized **Tool** result
- A **Reasoning Summary** is a concise explanation of how **Sage** approached a response, while a **Reasoning Trace** may include raw provider reasoning content when the **Model Provider** exposes it
- **Sage** should not fabricate a **Reasoning Trace** by asking the model to narrate hidden thoughts after the fact; when raw reasoning is unavailable, **Conversation Trace** should rely on model step, **Tool**, retry, correction, retrieval, timing, and optional **Reasoning Summary** details
- **Conversation Traces** should be persisted with the assistant turns they describe so refreshed conversations, exports, and admin troubleshooting remain coherent
- Persisted **Conversation Traces** are assistant-turn metadata, preferably stored with the assistant message record and otherwise in a sidecar record keyed to that assistant turn
- Assistant turns should have backend-generated stable message identifiers so streamed answer deltas, final responses, persisted **Conversation Traces**, exports, and deletion workflows can refer to the same turn
- **Conversation Traces** should be on by default in the transparent prototype phase
- Raw reasoning traces should persist as **Conversation Traces** with the assistant turn they describe and should be included in conversation exports by default
- **Session Memory Deletion** should delete persisted **Conversation Traces** for the associated **Conversation**
- Conversation exports should include the full persisted **Conversation Trace** by default
- **Conversation Trace** should be exposed through a structured `trace` response object on Conversation transports
- **Admin Conversations** and **User Conversations** should share the same **Conversation UI Surface** with role-specific controls
- **Activity** should be the user-facing presentation for both live **Conversation Activity Steps** and final **Conversation Trace** metadata
- **Activity** should be visible by default during the prototype phase, with a polished timeline that is verbose enough for debugging and auditability
- **Activity** should use progressive disclosure: visible rows for meaningful work, expandable details for raw or near-raw trace material, and hard protection for secrets and hidden authority-bearing instructions
- The chat UI should prefer **Conversation Streaming Transport** for **Conversation Trace** and answer updates, while preserving non-streaming fallback behavior for compatibility and resilience
- The **Conversation UI Surface** should adapt to Sage-owned **Conversation Streaming Transport** rather than redefining **Agent Runtime** behavior
- **Conversation Streaming Transport** should improve perceived latency by emitting early assistant-turn and answer-delta events even when total model generation time is unchanged
- **Sage** should emit live **Trace Deltas** from inside the **Model-Driven Tool Loop** so model steps, tool calls, tool results, retries, reasoning traces, and timing are visible as they happen
- Streaming **Conversation** transports should deliver **Trace Deltas** live, while non-streaming **Conversation** transports should return the accumulated **Conversation Trace** in the final response
- The **Conversation UI Surface** should render **Trace Deltas** as assistant-ui-style reasoning and tool-call message parts, with **Conversation Activity Steps** remaining available as summary or compatibility metadata
- During streaming turns, the **Conversation UI Surface** should render meaningful **Conversation Activity Steps** in order before the final assistant response is complete
- **Conversation Activity Steps** should remain scannable after completion rather than being packed only into a dense trace blob
- During streaming turns, **Conversation Activity Steps** must be emitted by **Sage**, and the prototype should bias toward showing enough activity to make the agent loop inspectable
- **Activity** may explain that **Sage** prepared an **Executable Change Set**, but **Change Confirmation** should remain a separate approval artifact because it authorizes state-changing action
- During streaming turns, the chat UI should create the assistant turn when the backend announces the stable assistant message identifier, append answer deltas to that turn, attach live trace status and **Trace Deltas** to that turn, and attach the final **Conversation Trace** when it arrives
- Streaming live status and Activity should use the same transparent trace posture for **Admin Conversations** and **User Conversations**
- Streamed **Conversation Trace** events must follow the same redaction rules as persisted **Conversation Traces**
- **Sage** should own **Conversation Trace** minimal blocklist protection before returning traces to clients
- The **Agent Runtime** should own **Conversation Streaming Transport** for public AI routes, while the **Enclave Control Plane** remains available through internal control-plane contracts
- **Conversation Streaming Transport** should support the same **Model-Driven Tool Loop** as non-streaming **Conversations** rather than preserving separate assistant-style and retrieval-first tool paths
- **Conversation Streaming Transport** should remain tool-aware so configuration, database, web, and knowledge-assisted **Conversations** benefit from streaming rather than falling back to delayed non-streaming turns
- **Sage** should expose enabled **Tool** contracts to the model, execute model-chosen calls, inject **Tool** results, and continue until the model can answer or produce an **Executable Change Set**
- **Sage** should not pre-classify a user turn into a scoped prompt context before the model sees available **Tools**
- The **Model-Driven Tool Loop** should stay provider-portable and should not depend on provider-native function-calling support
- Individual **Tools** and retrieval steps should emit trace material for their own work, and **Sage** should compose that material into the final **Conversation Trace** while protecting the minimal blocklist
- Ordinary **Conversation Trace** generation is conversation metadata, not **Audit Log** evidence
- The transparent prototype **Trace Visibility Posture** should not require actor-specific **Audit Log** events because it is not currently a configurable policy surface
- **Conversation Trace** blocklist handling should keep the trace event when possible, replace protected content with `[redacted]`, and mark the event guarded without failing the associated chat response
- Viewers may expand or collapse shown per-message trace details, but the prototype should avoid actor-specific trace visibility plumbing unless a later decision reintroduces it
- **Tool Trace** for `db-query` should expose authorized SQL results only when those results were intentionally returned through the database **Tool** result, while still protecting credentials and hidden authority-bearing internals
- **Admin Conversation** detailed traces may include validated read-only SQL only after sensitive literals are redacted
- `db-query` traces should not be visible in **User Conversations** because `db-query` is admin-only
- The transparent prototype posture intentionally avoids separate trace defaults for **Admin Conversations**, **User Conversations**, or **User Types**
- The default **Conversation** trace posture should expose raw reasoning and detailed tool traces for troubleshooting and auditability
- The default **User Conversation** trace posture should match the transparent prototype posture used for **Admin Conversations**
- **Activity** should be similarly transparent in **Admin Conversations** and **User Conversations** during the prototype phase
- **Sage** may invoke **Tools** during a **Conversation**
- **User Conversations** and **Admin Conversations** are both **Conversations**
- **User Conversations** and **Admin Conversations** share **Session Memory Deletion** mechanics while retaining role-specific authority and visibility
- An **Admin Conversation** may have a **Subject User**
- An **Admin Conversation** may directly perform **Enclave Control Plane** actions after **Change Confirmation**
- Every admin-conversation write that changes **Instance** or **Agent Runtime** state requires **Change Confirmation**
- **Sage** must express state-changing admin proposals as an **Executable Change Set** before the **Conversation UI Surface** can place them into **Change Confirmation**
- The **Conversation UI Surface** should treat admin apply language without a valid pending **Executable Change Set** as a **Change Set Recovery Turn**, not as a failed local apply attempt
- **Change Confirmation** should render inline with the assistant turn that produced the related **Executable Change Set**, so the explanation, **Activity**, and approval artifact remain together
- Pending **Change Confirmation** should not block ordinary follow-up turns in the **Admin Conversation**
- The **Conversation UI Surface** should allow only one actionable pending **Change Confirmation** at a time; a later pending **Executable Change Set** should make the earlier card a **Superseded Change Confirmation**
- **Change Confirmation** is the only approval artifact defined for **Conversations** in the current prototype and is scoped to **Admin Conversations**
- The **Admin Configuration Assistant** uses the **Admin Config Tool Set** so the model can call explicit configuration read **Tools** while preserving **Change Confirmation** for writes
- A **User Conversation** must not perform admin-only **Enclave Control Plane** actions
- **User Conversations** are read/assistive in the current prototype and do not have general write-capable tool authority
- **Ordinary Product Flows** may still let **Users** or **Admins** change data directly through the product outside a **Conversation**

## Example dialogue

> **Dev:** "Is this prototype separate from Enclave Free?"
> **Domain expert:** "No. The **Enclave Free Prototype** is the candidate next version of **Enclave Free**, and its defining change is that **Sage** is integrated directly as the agent runtime."
>
> **Dev:** "Does private mean the product never calls external services?"
> **Domain expert:** "No. **Operator-Controlled Privacy** means the **Operator** controls the **Instance** data boundary, configuration, document library, and approved external integrations."
>
> **Dev:** "Who decides how long uploaded documents or conversation records are kept?"
> **Domain expert:** "That is **Data Retention**. The **Operator** should control those rules for the **Instance**, even where the current prototype only implements part of the deletion path."
>
> **Dev:** "If an Operator has a 30-day retention rule, has old data been deleted automatically?"
> **Domain expert:** "Not necessarily. **Data Retention** is the rule; **Retention Execution** is the action that applies it, and it may be operator-invoked before scheduling exists."
>
> **Dev:** "If the admin marks a lifecycle class as scheduled, does the app now run cleanup by itself?"
> **Domain expert:** "No. That is a **Scheduled Retention Policy**. A **Retention Scheduler** is the separate automation that invokes scheduled **Retention Execution**."
>
> **Dev:** "If retention succeeds for uploaded artifacts but fails for Sage memory, did retention succeed?"
> **Domain expert:** "**Retention Execution** should report results per **Lifecycle Data Class**. One class can succeed while another fails or remains unsupported."
>
> **Dev:** "If Document deletion is marked complete, does that mean every backup and log trace is gone?"
> **Domain expert:** "No. A complete **Lifecycle Support Status** is scoped to the stated **Lifecycle Data Class** and supported **Storage Targets**, not every **Deployment Surface**."
>
> **Dev:** "Should uploaded Documents be encrypted to the Admin's Nostr key?"
> **Domain expert:** "No. The backend still needs to read Documents for ingestion and **Retrieval**, so active content storage should use a **Content Encryption Key** rather than the **Admin** key."
>
> **Dev:** "Can an Operator choose plaintext uploaded artifacts?"
> **Domain expert:** "Yes, but that is an explicit **Artifact Encryption Posture** choice for the **Deployment** and should be visible in lifecycle status."
>
> **Dev:** "If the Operator turns artifact encryption on, are old uploaded files automatically encrypted?"
> **Domain expert:** "No. **Artifact Encryption Posture** governs future writes unless a separate migration workflow rewrites existing artifacts, and the **Audit Log** should record the posture change."
>
> **Dev:** "If uploaded artifacts are plaintext by choice, can Retrieval chunks also be plaintext?"
> **Domain expert:** "No. **Retrieval Content Posture** is stricter: chunk text should be encrypted in active product storage and Qdrant should stay minimized."
>
> **Dev:** "If we add encryption today, can old plaintext content be marked protected?"
> **Domain expert:** "Not until **Confidentiality Migration** rewrites or verifies existing active content storage. Until then, lifecycle status should report a mixed posture."
>
> **Dev:** "Does lifecycle governance mean every trace is securely erased immediately?"
> **Domain expert:** "No. **Operator-Controlled Data Lifecycle** first means the **Operator** can see each operator-visible data class, configure or invoke supported lifecycle actions, and review truthful status for unsupported surfaces."
>
> **Dev:** "What should we make production-ready first?"
> **Domain expert:** "Start with **Active Storage Lifecycle**: make the product-owned active storage targets truthful, configurable where supported, auditable, and repairable before claiming control over deployment logs, backups, snapshots, or provider traces."
>
> **Dev:** "If I delete a User, does that delete Docker logs, gateway logs, backups, and every provider trace?"
> **Domain expert:** "No. Those are **Deployment Surfaces** unless and until the product promotes them into supported **Lifecycle Data Classes** with explicit lifecycle controls."
>
> **Dev:** "If we delete a conversation, is all Sage memory gone?"
> **Domain expert:** "For supported active **Conversation** deletion paths, yes: **Session Memory Deletion** removes the related Sage-owned **Session Memory** together with the public conversation record. Broader scheduled retention for every historical/log surface is still future work."
>
> **Dev:** "Can the operator see who changed configuration?"
> **Domain expert:** "For some configuration paths, yes. The **Audit Log** concept is broader, but current coverage is still partial."
>
> **Dev:** "Can a private instance use SMTP or Tinfoil?"
> **Domain expert:** "Yes, if those **External Integrations** are visible and configurable parts of the **Operator's** deployment choices."

> **Dev:** "Is the instance the Docker stack?"
> **Domain expert:** "No. The **Instance** is the operator-controlled product space and data boundary; the **Deployment** is the technical environment running it."

> **Dev:** "Should a cron job use the Admin's browser session to run retention?"
> **Domain expert:** "No. That would confuse a human **Admin** action with **Deployment Automation**. A deployment-owned machine actor should invoke scheduled workflows when the product supports that path."

> **Dev:** "Should the gateway decide how AI routes work?"
> **Domain expert:** "No. The **Gateway** routes requests; **Sage** and the **Enclave Control Plane** own behavior and correctness."

> **Dev:** "Is the operator the same thing as the admin key?"
> **Domain expert:** "No. The **Operator** is responsible for the **Instance**; the **Admin** is the authenticated control identity the prototype currently exposes."

> **Dev:** "Can an organization have several admins?"
> **Domain expert:** "Not in the current prototype. The first Nostr key to initiate the **Instance** becomes the single **Admin**."

> **Dev:** "Why can't users sign in before the admin?"
> **Domain expert:** "The **Instance** has not gone through **Instance Initiation** yet. The first **Admin** must authenticate before user onboarding opens."

> **Dev:** "Does onboarding only happen the first time a user signs in?"
> **Domain expert:** "Usually, but not always. **User Onboarding** can reopen when the **Operator** adds required **Onboarding Questions** that an existing **User** has not answered."

> **Dev:** "If a user has a valid magic-link session, can they chat?"
> **Domain expert:** "Only if **User Approval** allows it. Authentication proves who the user is; **User Approval** decides whether they may enter normal user-facing flows."

> **Dev:** "Does auto approval mean anyone can use the instance?"
> **Domain expert:** "No. **Auto Approval** means newly authenticated **Users** are automatically approved by the **Instance Setting** instead of waiting for manual approval."

> **Dev:** "Can a pending user contact the operator?"
> **Domain expert:** "Yes, if **User Reachout** is enabled. It is authenticated but not approval-gated, and it contacts the **Operator** outside a **Conversation**."

> **Dev:** "Is a reachout email part of Sage's conversation context?"
> **Domain expert:** "No. A **Reachout Message** is outside **Conversation Content** unless a future feature sends it to **Sage** or a **Model Provider**."

> **Dev:** "Is a tenant a User?"
> **Domain expert:** "Only if that is how the operator configures the **Instance**. In the product language, the person using Sage through the public side is a **User**."

> **Dev:** "Should Sage manage users and documents?"
> **Domain expert:** "No. **Sage** owns the **Agent Runtime** behavior; the **Enclave Control Plane** owns users, documents, instance settings, and other operator-controlled facts."

> **Dev:** "Is changing the model the same kind of configuration as changing the instance name?"
> **Domain expert:** "No. The instance name is an **Instance Setting**; model and prompt behavior are **Agent Settings**; service URLs and secrets are **Deployment Settings**."

> **Dev:** "Is Tinfoil the agent runtime?"
> **Domain expert:** "No. **Sage** is the **Agent Runtime**. Tinfoil is the current **Model Provider** used for model inference."

> **Dev:** "Why not treat every model API as equivalent?"
> **Domain expert:** "The product prefers **Tinfoil** because it supports encrypted, verifiable inference through a **Trusted Execution Environment**."

> **Dev:** "Are we locked to Tinfoil forever?"
> **Domain expert:** "No. **Tinfoil** is preferred because it currently satisfies the **Model Provider Requirement**. Another provider could replace it if it meets the same requirement."

> **Dev:** "Is a TEE the requirement?"
> **Domain expert:** "Not exactly. **Verifiable Inference** is the requirement; a **Trusted Execution Environment** is the preferred mechanism today."

> **Dev:** "Does encrypted inference just mean HTTPS?"
> **Domain expert:** "No. **Encrypted Inference** means conversation content is protected from the surrounding infrastructure while it is sent to, processed by, and returned from the **Model Provider**."

> **Dev:** "Does User Type mean a different agent?"
> **Domain expert:** "No. **User Type** is onboarding segmentation. **Agent Personalization** is the rule set that may tailor Sage behavior for that segment."

> **Dev:** "Is RAG a Python feature or a Sage feature?"
> **Domain expert:** "**Retrieval** is an **Agent Runtime** capability over the **Document Library**. The control plane can execute the search, but Sage decides how retrieved knowledge participates in the conversation."

> **Dev:** "Is an uploaded PDF the RAG database?"
> **Domain expert:** "No. The PDF is a **Document**. The operator's collection of documents is the **Document Library**. **Retrieval** selects knowledge from that library."

> **Dev:** "If an admin uploads a folder, is the folder itself a Document?"
> **Domain expert:** "No. That is **Document Batch Ingestion**: each supported file becomes its own **Document**, while the folder is only a selection convenience."

> **Dev:** "Should one unsupported file make a whole folder upload fail?"
> **Domain expert:** "No. **Document Batch Ingestion** may partially succeed: supported files begin **Document Ingestion**, while unsupported files are reported back to the Admin."

> **Dev:** "If the same folder upload contains two files with the same canonical document name, do both ingest?"
> **Domain expert:** "No. The first file is accepted and later same-action duplicates are rejected so the Admin can resolve the ambiguity."

> **Dev:** "If the admin uploads a new Policies/Handbook.md, is that a duplicate?"
> **Domain expert:** "No. It is **Document Replacement**: the new **Document** supersedes the existing Document with the same canonical document name."

> **Dev:** "Does replacing a Document depend on whether the Admin uploaded one file or a folder?"
> **Domain expert:** "No. **Document Replacement** applies consistently to single-document and batch-document admin workflows."

> **Dev:** "Does the old Handbook disappear while the replacement is processing?"
> **Domain expert:** "No. During **Document Replacement**, the existing **Document** remains current unless the replacement succeeds."

> **Dev:** "Can users select an in-progress replacement document?"
> **Domain expert:** "No. Only current completed **Documents** are visible to **Users** for **Document Access** and **Retrieval**."

> **Dev:** "Does User Type mean document permission group?"
> **Domain expert:** "No. **User Type** is onboarding segmentation. **Document Access** is the rule set that may use User Type as an input."

> **Dev:** "Can the product include document context even if Sage did not ask for it?"
> **Domain expert:** "Only when product policy requires it. Ordinary selected Documents are Knowledge **Tool** constraints, so Sage should retrieve from them through the **Model-Driven Tool Loop** rather than receiving hidden document context."

> **Dev:** "Are User Types permission roles?"
> **Domain expert:** "No. A **User Type** is how the operator segments users so different **Onboarding Questions** can be asked."

> **Dev:** "If Sage sees a user's onboarding answers, are those answers Sage memory?"
> **Domain expert:** "No. The answers are the **User Profile**. **Sage** may use that profile as context, but **Session Memory** is conversation-specific agent state."

> **Dev:** "Does deleting a query session delete Sage memory?"
> **Domain expert:** "Yes for the supported active **Conversation** deletion path. Product language should call that **Session Memory Deletion**, because deleting only a query-session record would be too narrow."

> **Dev:** "Should we call this a query session?"
> **Domain expert:** "Use **Conversation** in product language. Query session is implementation/API language for a Sage-backed conversation session."

> **Dev:** "Does encrypted inference only protect the user's latest message?"
> **Domain expert:** "No. It protects **Conversation Content**, including prompts, retrieved excerpts, required context, profile context, and tool results sent to the **Model Provider**."

> **Dev:** "Are all tool results Conversation Content?"
> **Domain expert:** "Only when they are sent to the **Model Provider** for inference. Tool data may have other security rules outside the inference payload."

> **Dev:** "Is every tool just an API endpoint?"
> **Domain expert:** "No. A **Tool** is any action or information source **Sage** can invoke during a **Conversation**. Its authority depends on the conversation type."

> **Dev:** "Can Sage apply admin configuration changes itself?"
> **Domain expert:** "Yes, and that is often ideal for admins, but Sage must ask for **Change Confirmation** before applying configuration or control-plane changes."

> **Dev:** "Which admin tool actions need confirmation?"
> **Domain expert:** "Every write that changes **Instance** or **Agent Runtime** state needs **Change Confirmation**. Reads can happen within the authority of the **Admin Conversation**."

> **Dev:** "Can Sage read uploaded Documents during an Admin Conversation when the Admin asks it to configure the Instance from those materials?"
> **Domain expert:** "Yes. Uploaded **Documents** are first-party **Instance** context. Sage may read **Document Library** and **Retrieval** context in an **Admin Conversation** to make better configuration decisions, while writes still require **Change Confirmation**."
>
> **Dev:** "Should the Admin have to manually enable config context before asking Sage to configure the Instance?"
> **Domain expert:** "No. In admin configuration contexts, the **Admin Config Tool Set** should be enabled by default. The model should call explicit configuration read **Tools** when useful, while any resulting writes still require **Change Confirmation**."
>
> **Dev:** "Should Sage ask the Admin to specify every missing preference before configuring the Instance?"
> **Domain expert:** "No. When the Admin delegates a configuration task, Sage should inspect available first-party context, choose reasonable defaults for unspecified details, state important assumptions briefly, and present any writes for **Change Confirmation**."
>
> **Dev:** "Should this stronger action bias apply to normal User Conversations too?"
> **Domain expert:** "No. The stronger action bias is for **Admin Conversations** because the Admin has operator authority. **User Conversations** should remain helpful and direct, but they should not inherit admin-style configuration or write-preparation behavior."
>
> **Dev:** "Should an Admin have to manually select uploaded Documents before asking Sage to configure the Instance from them?"
> **Domain expert:** "No. When an Admin configuration request refers to uploaded materials, instance theming, copy, or content, Sage should automatically use relevant **Retrieval** over the **Document Library** before choosing defaults or preparing changes."
>
> **Dev:** "Should Sage prepare one broad Change Confirmation for a coherent admin configuration task, or split every setting into separate confirmations?"
> **Domain expert:** "Use one reviewable **Change Confirmation** for a coherent delegated task. For example, an instance theming request may include name, tagline, colors, typography, icons, chat bubble style, and copy defaults in one changeset."
>
> **Dev:** "Should the one-action guidance prevent Sage from configuring several related settings at once?"
> **Domain expert:** "No. For ordinary step-by-step guidance, Sage should keep actions focused. For delegated **Admin Conversation** configuration tasks, Sage should group related settings into one reviewable **Change Confirmation**."
>
> **Dev:** "Should Sage receive secret Deployment Setting values by default in Admin Conversations?"
> **Domain expert:** "No. Admin configuration **Tools** may return non-secret values and secret status metadata by default, but secret values require explicit Admin sharing and should remain redacted in chat."

> **Dev:** "Can users ask Sage to change things for them?"
> **Domain expert:** "Not as a general tool authority model in the current prototype. **User Conversations** are read/assistive, except for user-owned actions handled by ordinary product flows."

> **Dev:** "Can users still update their profile?"
> **Domain expert:** "Yes. Updating a profile through the profile screen is an **Ordinary Product Flow**, not Sage using write-capable tool authority during a **User Conversation**."

> **Dev:** "Is the admin assistant a different product from user chat?"
> **Domain expert:** "No. Both are **Conversations** with **Sage**, but an **Admin Conversation** has authority to help configure or operate the **Instance**."

> **Dev:** "Can we call the deployment ready because the containers started?"
> **Domain expert:** "No. **Deployment Readiness** means the **Operator** can see that configuration, external integrations, verification, recovery posture, and lifecycle review are ready enough for real use."

## Flagged ambiguities

- "prototype" can imply a disposable demo; resolved: **Enclave Free Prototype** means the candidate next version of **Enclave Free**.
- "private" does not mean local-only or offline-only; resolved: use **Operator-Controlled Privacy** for the product principle.
- "data lifecycle governance" can imply full compliance-grade records management; resolved: **Operator-Controlled Data Lifecycle** means inventory, supported policy/action, evidence, and honest unsupported status before it means complete secure erasure across every technical surface.
- "logs" and "backups" can be mistaken for supported product records; resolved: treat them as **Deployment Surfaces** until a specific one is promoted into a **Lifecycle Data Class**.
- "retention is implemented" can confuse a configured rule with data-changing enforcement; resolved: **Data Retention** is policy and **Retention Execution** is the act of applying it.
- "scheduled retention" can confuse policy with automation; resolved: **Scheduled Retention Policy** is the configuration, while **Retention Scheduler** is the automated trigger.
- **Data Retention** is a policy concept even where implementation is incomplete; current gaps include product-owned **Retention Scheduler**, secure erase semantics, log retention, and complete historical session retention.
- **Data Deletion** is distinct from hiding or archiving data; supported Document, User, Conversation, and User Memory deletion paths now return structured lifecycle status, while remaining gaps should be treated as product work rather than glossary ambiguity.
- **Audit Log** should not be confused with debug or server logs; current audit coverage includes configuration, user governance, document governance, User Memory, and Data Deletion workflows but is not complete for every state-changing action.
- "production-ready lifecycle" can accidentally include host backups, runtime logs, snapshots, and provider traces; resolved: the first plan targets **Active Storage Lifecycle**, while those remain **Deployment Surfaces** disclosed to the **Operator**.
- "encrypted documents" can imply Admin-key or user-key encryption; resolved: backend-readable document and retrieval storage should use a **Content Encryption Key** unless a future end-to-end workflow is explicitly designed.
- External services used by a deployment should be named as **External Integrations**, not treated as hidden platform-owned dependencies.
- "instance" can mean a running server process; resolved: **Instance** means the operator-controlled product space and data boundary, while **Deployment** means the technical environment.
- "cron" or "scheduler" can be mistaken for a human admin action; resolved: scheduled machine-triggered workflows should be attributed to **Deployment Automation**.
- "gateway" can imply an API policy layer; resolved: **Gateway** is routing infrastructure and should not own product correctness.
- "operator" and "admin" are distinct: **Operator** is the responsible person or organization, while **Admin** is the authenticated control identity.
- "admin" can imply a general staff role; resolved: **Admin** is currently the single operator identity for an **Instance**.
- "registration" is too generic for first setup; resolved: use **Instance Initiation** for the first Admin authentication that claims an **Instance**.
- "signup" is too narrow for onboarding; resolved: **User Onboarding** can create a first profile and can later reopen when required questions are added.
- **User Approval** is distinct from authentication and **User Onboarding**: it gates access after sign-in.
- **User Approval** gates **Conversation** access after required **User Onboarding** is complete; pending-approval **Users** may still complete **User Type** selection and required **Onboarding Questions** before landing on the pending approval screen.
- "open signup" is too broad for approval behavior; resolved: **Auto Approval** is an **Instance Setting** that grants **User Approval** after authentication.
- **User Reachout** should not be described as a **Conversation** or **Tool**; it is an authenticated **Ordinary Product Flow** for contacting the **Operator**.
- **Reachout Message** is distinct from **Conversation Content** in the current prototype.
- "user" should not be replaced with the operator's local domain labels; resolved: **User** is the product-level term for a non-admin person using Sage inside an **Instance**.
- "agent" can imply only an LLM adapter; resolved: **Sage** is the **Agent Runtime**, including conversation behavior, session memory, prompt assembly, tool selection, and agent-facing AI configuration.
- "model backend" is too implementation-colored; resolved: use **Model Provider** for the configured service or local runtime Sage uses for inference.
- "generic LLM provider" does not capture the current provider requirement; resolved: **Tinfoil** is preferred because it supports encrypted, verifiable inference through a **Trusted Execution Environment**.
- "LLM preference" understates the security constraint; resolved: use **Model Provider Requirement** for the encrypted inference and **Verifiable Inference** requirement.
- "encrypted inference" should not be reduced to transport security; resolved: **Encrypted Inference** protects conversation content from surrounding infrastructure across the inference flow.
- "Tinfoil attestations" is implementation-specific provider language; resolved: use **Inference Verification Record** for operator-visible evidence of **Verifiable Inference**, including full provider attestation material when available.
- "Tinfoil verifier" overstates provider lock-in; resolved: use a provider-neutral verification interface with a Tinfoil implementation.
- A **Trusted Execution Environment** should not be confused with the product requirement itself; resolved: **Verifiable Inference** is the property, and a TEE is the preferred mechanism.
- "configuration" is overloaded; resolved: use **Instance Settings**, **Deployment Settings**, and **Agent Settings** for the three distinct concepts.
- "productionization" can imply support for any infrastructure; resolved: the first productionization plan targets a **Single-Instance Deployment** through the supported Compose topology.
- "deployment readiness" should not be reduced to a private engineering checklist or container health; resolved: **Deployment Readiness** is operator-visible and includes **Lifecycle Readiness** plus broader deployment configuration and recovery posture.
- **Deployment Readiness** warnings should not be confused with privacy-critical runtime gates; resolved: most readiness gaps are advisory in v1, while failed or missing **Verifiable Inference** still blocks normal **Conversations**.
- "deployment wizard" can imply a second setup system; resolved: **Deployment Wizard** is a guided first-run layer over the same admin configuration and readiness surfaces.
- "deployment config" can imply live process mutation; resolved: **Deployment Settings** express desired operator-controlled runtime configuration, and **Deployment Readiness** should report whether running services match that desired state.
- "i18n completeness" can imply finished translations in every language; resolved: the first polish milestone targets extraction and fallback correctness before human-quality translation review.
- "theme/language configurability" can mean Admin-controlled defaults or per-user preferences; resolved: first milestone treats defaults as **Instance Settings**, with per-user preferences deferred.
- "test dashboard" can blur product experience with diagnostics; resolved: diagnostic dashboards should be demoted from primary product paths.
- "user-type AI config" is implementation language; resolved: use **Agent Personalization** for operator rules that tailor Sage behavior by User or User Type.
- "RAG" is overloaded between storage, search, and answer generation; resolved: use **Document Library** for the operator-owned corpus and **Retrieval** for selecting knowledge for the agent.
- "document defaults" is implementation/UI language; resolved: use **Document Access** for operator rules that determine which **Documents** are available.
- "folder upload" can imply the folder is a knowledge source; resolved: use **Document Batch Ingestion** for the admin workflow, while each supported file remains an independent **Document**.
- "batch upload failed" can hide partial progress; resolved: **Document Batch Ingestion** reports accepted and rejected files separately.
- "duplicate document" can mean identical bytes or same operator-facing source; resolved: **Document Replacement** is based on canonical document name, not content hash.
- "forced RAG" was resolved as **Required Context** only when product policy requires context outside agent discretion; ordinary document-grounded chat should use the explicit Knowledge **Tool Set**.
- "User Type" currently appears in implementation surfaces for onboarding, document defaults, and AI config overrides; resolved: its domain meaning is onboarding segmentation, while other per-type behavior is an extension point rather than the definition.
- "custom field" is an implementation phrase; resolved: use **Onboarding Question** for the admin-defined prompt and **User Profile** for the user's structured answers.
- **User Profile** and **Session Memory** are distinct: profile information is Enclave-owned user data, while session memory is Sage-owned conversation state.
- **User Manager Dashboard** is the focused admin surface for reviewing **Users** and taking simple **User Approval** actions; schema setup for **User Types** and **Onboarding Questions** remains a separate User Settings workflow.
- "delete query session" is too narrow; resolved: use **Session Memory Deletion** for removing Sage-owned memory associated with a **Conversation**.
- "query session" is implementation/API language; resolved: use **Conversation** for the product/domain concept.
- "user message" is too narrow for privacy discussions; resolved: use **Conversation Content** for the full inference payload sent to a **Model Provider**.
- "proposal-only admin assistant" is too weak; resolved: Sage may directly apply configuration or control-plane changes during an **Admin Conversation** after **Change Confirmation**.
- "admin document access" can be mistaken for a write authority escalation; resolved: Sage may autonomously read uploaded **Documents** as first-party **Instance** context in an **Admin Conversation**, but changing **Instance Settings**, **Agent Settings**, **Deployment Settings**, or document governance still requires **Change Confirmation**.
- "config tool access" should not require the Admin to pre-debug the right context switch in admin configuration flows; resolved: the **Admin Config Tool Set** is enabled by default in admin configuration **Conversations**, and the model chooses explicit read **Tools**.
- "ask before choosing" is too timid for delegated admin configuration; resolved: Sage should choose reasonable defaults from first-party context and present writes for **Change Confirmation** rather than making the Admin supply every preference.
- "sovereign Sage" can overreach if applied globally; resolved: stronger action bias is scoped to **Admin Conversations**, not normal **User Conversations**.
- "uploaded document available" is too passive for admin configuration; resolved: when an **Admin Conversation** refers to uploaded materials, theming, copy, or content, Sage should proactively call the Knowledge **Tool Set** when it is enabled and relevant.
- "one action per response" should not force fragmented admin setup; resolved: a coherent delegated admin configuration task can be presented as one reviewable **Change Confirmation** containing multiple related writes.
- "ONE action per response" is too broad when applied to delegated admin setup; resolved: ordinary guidance should stay focused, while related admin configuration writes can be grouped into one **Change Confirmation**.
- "prose Change Confirmation" is not executable; resolved: Sage may explain proposed changes in prose, but only an **Executable Change Set** can enter **Change Confirmation**.
- "no pending changes" is a poor recovery for apply language after prose-only guidance; resolved: treat it as a **Change Set Recovery Turn** so Sage can generate the missing **Executable Change Set**.
- "compaction" is not inherently a failure; resolved: ordinary **Session Memory Compaction** should be quiet continuity machinery, while **Reduced Conversation Context** is the user-visible degradation.
- "config access" should not imply secret exposure; resolved: Admin Config **Tools** may expose non-secret configuration and secret status metadata by default, while secret values require explicit Admin sharing and stay redacted in chat.
- User-agent write authority is not defined yet; resolved for now: **User Conversations** are read/assistive and should not receive general write-capable tools.
- **Ordinary Product Flow** exists to distinguish direct product actions from Sage tool authority inside a **Conversation**.
- Future control model may introduce delegated or multiple administrators; unresolved until that design is discussed.
