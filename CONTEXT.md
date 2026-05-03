# Enclave Free Prototype

The Enclave Free prototype is the candidate next version of Enclave Free, distinguished from the original product by integrating Sage directly as the agent runtime.

## Language

**Enclave Free**:
The product for private, operator-controlled AI assistance over curated organizational knowledge.
_Avoid_: original app, legacy app

**Operator-Controlled Privacy**:
The product principle that an **Operator** controls the **Instance** data boundary, configuration, document library, and approved external integrations.
_Avoid_: local-only, offline-only

**Data Retention**:
The **Operator** controlled rules for how long **Instance** data is kept before deletion or review.
_Avoid_: cleanup, storage duration

**Data Deletion**:
The **Operator** controlled action or workflow that removes **Instance** data from active storage according to **Data Retention** rules or a specific deletion request.
_Avoid_: cleanup, hide, archive

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
Technical environment settings for the **Deployment**.
_Avoid_: instance settings

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

**Document Access**:
Operator rules that determine which **Documents** are available to a **User** or **User Type**.
_Avoid_: permissions, RAG defaults

**Retrieval**:
The act of selecting relevant knowledge from the **Document Library** for use in an agent conversation.
_Avoid_: RAG

**Required Context**:
Operator- or route-mandated knowledge from the **Document Library** that must be included in an agent conversation.
_Avoid_: forced RAG

**User Type**:
An operator-defined user segment that determines which onboarding questions are asked of a user.
_Avoid_: role, permission group, audience segment

**Onboarding Question**:
An operator-defined question used to collect structured information from a user during onboarding.
_Avoid_: custom field

**User Profile**:
The structured information a **User** provides in response to **Onboarding Questions**.
_Avoid_: user fields, profile fields

**Session Memory**:
The conversation-specific information **Sage** retains to support an ongoing agent interaction.
_Avoid_: user profile, chat history

**Session Memory Deletion**:
**Data Deletion** for **Sage** owned **Session Memory** associated with a **Conversation**.
_Avoid_: delete query session

**Conversation**:
An ongoing interaction between a **User** or **Admin** and **Sage**.
_Avoid_: query session, chat session

**Conversation Content**:
The messages, prompts, retrieved document excerpts, required context, user profile context, tool results, and other content sent to a **Model Provider** for inference.
_Avoid_: user message, prompt text

**Tool**:
An action or information source that **Sage** can invoke during a **Conversation**.
_Avoid_: endpoint, function call

**Ordinary Product Flow**:
A non-agent UI or API path where a **User** or **Admin** performs an action directly through the product.
_Avoid_: tool, conversation action

**Change Confirmation**:
The explicit **Admin** approval Sage must receive before applying state-changing actions during an **Admin Conversation**.
_Avoid_: review-only workflow

**User Conversation**:
A **Conversation** between a **User** and **Sage** for assistance inside an **Instance**.
_Avoid_: user query

**Admin Conversation**:
A **Conversation** between the **Admin** and **Sage** for configuring or operating an **Instance**.
_Avoid_: admin query

## Relationships

- **Enclave Free Prototype** succeeds the first version of **Enclave Free** if the prototype direction is validated
- **Enclave Free** is guided by **Operator-Controlled Privacy**
- **Operator-Controlled Privacy** allows **External Integrations** when they are visible and configurable by the **Operator**
- **Data Retention** is part of **Operator-Controlled Privacy**
- **Data Deletion** executes **Data Retention** decisions or specific deletion requests
- An **Audit Log** supports **Operator-Controlled Privacy** by making important **Instance** changes visible after the fact
- **Enclave Free Prototype** integrates **Sage** directly into the product runtime
- A **Deployment** usually runs one **Instance** in the prototype
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
- The **Admin** is the authenticated control identity for the **Operator** in the current prototype
- An **Instance** has zero or more **Users**
- A **User** belongs to at most one **User Type**
- **Sage** is the **Agent Runtime** inside the **Enclave Free Prototype**
- The **Enclave Control Plane** provides operator-owned facts and actions to **Sage**
- **Instance Settings** belong to the **Instance**
- **Deployment Settings** belong to the **Deployment**
- **Agent Settings** belong to **Sage**
- **Model Provider** is an **Agent Setting**
- A **Model Provider** must satisfy the **Model Provider Requirement**
- **Tinfoil** is the current preferred **Model Provider**
- **Encrypted Inference** protects conversation content from surrounding infrastructure
- **Verifiable Inference** lets the **Operator** verify meaningful execution claims
- A **Trusted Execution Environment** is one mechanism for **Verifiable Inference**
- **Agent Personalization** may tailor **Agent Settings** for a **User** or **User Type**
- The **Enclave Control Plane** owns the **Document Library**
- A **Document Library** contains zero or more **Documents**
- The **Enclave Control Plane** owns document ingestion
- **Document Access** determines which **Documents** are available before **Retrieval** or **Required Context** is applied
- **Retrieval** is an **Agent Runtime** capability over the **Document Library**, even when the current implementation asks the **Enclave Control Plane** to execute the search
- **Required Context** is selected outside the agent's discretion and passed to **Sage** for use in the conversation
- A **User Type** has zero or more **Onboarding Questions**
- A user belongs to at most one **User Type**
- A **User Type** may become an extension point for tailored product behavior, but its core meaning is onboarding segmentation
- A **User Profile** contains answers to **Onboarding Questions**
- **Sage** may use a **User Profile** as context, but the **User Profile** is owned by the **Enclave Control Plane**
- **Session Memory** belongs to the **Agent Runtime**
- **Session Memory Deletion** must remove the **Session Memory** associated with a **Conversation**
- A **Conversation** may have **Session Memory**
- A **Conversation** may include **Retrieval**, **Required Context**, and **User Profile** context
- **Conversation Content** is the inference payload protected by **Encrypted Inference**
- **Sage** may invoke **Tools** during a **Conversation**
- **User Conversations** and **Admin Conversations** are both **Conversations**
- An **Admin Conversation** may directly perform **Enclave Control Plane** actions after **Change Confirmation**
- Every admin-conversation write that changes **Instance** or **Agent Runtime** state requires **Change Confirmation**
- A **User Conversation** must not perform admin-only **Enclave Control Plane** actions
- **User Conversations** are read/assistive in the current prototype and do not have general write-capable tool authority
- **Ordinary Product Flows** may still let **Users** or **Admins** change data directly through the product outside a **Conversation**

## Example dialogue

> **Dev:** "Is this prototype separate from Enclave Free?"
> **Domain expert:** "No. The **Enclave Free Prototype** is the candidate next version of **Enclave Free**, and its defining change is that **Sage** is integrated directly as the agent runtime."

> **Dev:** "Does private mean the product never calls external services?"
> **Domain expert:** "No. **Operator-Controlled Privacy** means the **Operator** controls the **Instance** data boundary, configuration, document library, and approved external integrations."

> **Dev:** "Who decides how long uploaded documents or conversation records are kept?"
> **Domain expert:** "That is **Data Retention**. The **Operator** should control those rules for the **Instance**, even where the current prototype only implements part of the deletion path."

> **Dev:** "If we delete a conversation, is all Sage memory gone?"
> **Domain expert:** "Not yet. **Data Deletion** for a **Conversation** must eventually include the related **Session Memory**, but the current prototype does not guarantee full Sage memory purge."

> **Dev:** "Can the operator see who changed configuration?"
> **Domain expert:** "For some configuration paths, yes. The **Audit Log** concept is broader, but current coverage is still partial."

> **Dev:** "Can a private instance use SMTP or Tinfoil?"
> **Domain expert:** "Yes, if those **External Integrations** are visible and configurable parts of the **Operator's** deployment choices."

> **Dev:** "Is the instance the Docker stack?"
> **Domain expert:** "No. The **Instance** is the operator-controlled product space and data boundary; the **Deployment** is the technical environment running it."

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

> **Dev:** "Does User Type mean document permission group?"
> **Domain expert:** "No. **User Type** is onboarding segmentation. **Document Access** is the rule set that may use User Type as an input."

> **Dev:** "Can the product include document context even if Sage did not ask for it?"
> **Domain expert:** "Yes. That is **Required Context**: knowledge the product must pass into the conversation because policy or route behavior requires it."

> **Dev:** "Are User Types permission roles?"
> **Domain expert:** "No. A **User Type** is how the operator segments users so different **Onboarding Questions** can be asked."

> **Dev:** "If Sage sees a user's onboarding answers, are those answers Sage memory?"
> **Domain expert:** "No. The answers are the **User Profile**. **Sage** may use that profile as context, but **Session Memory** is conversation-specific agent state."

> **Dev:** "Does deleting a query session delete Sage memory?"
> **Domain expert:** "Not necessarily in the current prototype. That requires **Session Memory Deletion**, which is the deletion path for Sage-owned memory associated with a **Conversation**."

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

> **Dev:** "Can users ask Sage to change things for them?"
> **Domain expert:** "Not as a general tool authority model in the current prototype. **User Conversations** are read/assistive, except for user-owned actions handled by ordinary product flows."

> **Dev:** "Can users still update their profile?"
> **Domain expert:** "Yes. Updating a profile through the profile screen is an **Ordinary Product Flow**, not Sage using write-capable tool authority during a **User Conversation**."

> **Dev:** "Is the admin assistant a different product from user chat?"
> **Domain expert:** "No. Both are **Conversations** with **Sage**, but an **Admin Conversation** has authority to help configure or operate the **Instance**."

## Flagged ambiguities

- "prototype" can imply a disposable demo; resolved: **Enclave Free Prototype** means the candidate next version of **Enclave Free**.
- "private" does not mean local-only or offline-only; resolved: use **Operator-Controlled Privacy** for the product principle.
- **Data Retention** is a policy concept even where implementation is incomplete; current gaps include full user-data deletion and full Sage Session Memory purge.
- **Data Deletion** is distinct from hiding or archiving data; current deletion gaps should be treated as product work, not glossary ambiguity.
- **Audit Log** should not be confused with debug or server logs; current audit coverage is strongest for configuration changes and is not complete for every state-changing action.
- External services used by a deployment should be named as **External Integrations**, not treated as hidden platform-owned dependencies.
- "instance" can mean a running server process; resolved: **Instance** means the operator-controlled product space and data boundary, while **Deployment** means the technical environment.
- "gateway" can imply an API policy layer; resolved: **Gateway** is routing infrastructure and should not own product correctness.
- "operator" and "admin" are distinct: **Operator** is the responsible person or organization, while **Admin** is the authenticated control identity.
- "admin" can imply a general staff role; resolved: **Admin** is currently the single operator identity for an **Instance**.
- "registration" is too generic for first setup; resolved: use **Instance Initiation** for the first Admin authentication that claims an **Instance**.
- "signup" is too narrow for onboarding; resolved: **User Onboarding** can create a first profile and can later reopen when required questions are added.
- **User Approval** is distinct from authentication and **User Onboarding**: it gates access after sign-in.
- "open signup" is too broad for approval behavior; resolved: **Auto Approval** is an **Instance Setting** that grants **User Approval** after authentication.
- **User Reachout** should not be described as a **Conversation** or **Tool**; it is an authenticated **Ordinary Product Flow** for contacting the **Operator**.
- **Reachout Message** is distinct from **Conversation Content** in the current prototype.
- "user" should not be replaced with the operator's local domain labels; resolved: **User** is the product-level term for a non-admin person using Sage inside an **Instance**.
- "agent" can imply only an LLM adapter; resolved: **Sage** is the **Agent Runtime**, including conversation behavior, session memory, prompt assembly, tool selection, and agent-facing AI configuration.
- "model backend" is too implementation-colored; resolved: use **Model Provider** for the configured service or local runtime Sage uses for inference.
- "generic LLM provider" does not capture the current provider requirement; resolved: **Tinfoil** is preferred because it supports encrypted, verifiable inference through a **Trusted Execution Environment**.
- "LLM preference" understates the security constraint; resolved: use **Model Provider Requirement** for the encrypted inference and **Verifiable Inference** requirement.
- "encrypted inference" should not be reduced to transport security; resolved: **Encrypted Inference** protects conversation content from surrounding infrastructure across the inference flow.
- A **Trusted Execution Environment** should not be confused with the product requirement itself; resolved: **Verifiable Inference** is the property, and a TEE is the preferred mechanism.
- "configuration" is overloaded; resolved: use **Instance Settings**, **Deployment Settings**, and **Agent Settings** for the three distinct concepts.
- "user-type AI config" is implementation language; resolved: use **Agent Personalization** for operator rules that tailor Sage behavior by User or User Type.
- "RAG" is overloaded between storage, search, and answer generation; resolved: use **Document Library** for the operator-owned corpus and **Retrieval** for selecting knowledge for the agent.
- "document defaults" is implementation/UI language; resolved: use **Document Access** for operator rules that determine which **Documents** are available.
- "forced RAG" was resolved as **Required Context** because the requirement comes from product policy or route behavior, not from the agent's tool choice.
- "User Type" currently appears in implementation surfaces for onboarding, document defaults, and AI config overrides; resolved: its domain meaning is onboarding segmentation, while other per-type behavior is an extension point rather than the definition.
- "custom field" is an implementation phrase; resolved: use **Onboarding Question** for the admin-defined prompt and **User Profile** for the user's structured answers.
- **User Profile** and **Session Memory** are distinct: profile information is Enclave-owned user data, while session memory is Sage-owned conversation state.
- "delete query session" is too narrow; resolved: use **Session Memory Deletion** for removing Sage-owned memory associated with a **Conversation**.
- "query session" is implementation/API language; resolved: use **Conversation** for the product/domain concept.
- "user message" is too narrow for privacy discussions; resolved: use **Conversation Content** for the full inference payload sent to a **Model Provider**.
- "proposal-only admin assistant" is too weak; resolved: Sage may directly apply configuration or control-plane changes during an **Admin Conversation** after **Change Confirmation**.
- User-agent write authority is not defined yet; resolved for now: **User Conversations** are read/assistive and should not receive general write-capable tools.
- **Ordinary Product Flow** exists to distinguish direct product actions from Sage tool authority inside a **Conversation**.
- Future control model may introduce delegated or multiple administrators; unresolved until that design is discussed.
