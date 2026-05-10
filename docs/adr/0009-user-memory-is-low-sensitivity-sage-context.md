# User Memory Is Low-Sensitivity Sage Context

The Enclave Free Prototype will treat User Memory as Sage-owned, low-sensitivity personalization and operational context about a specific User, separate from User Profile and Session Memory. Initial User Memory may be stored without content encryption so Sage can load it directly during Conversation context assembly; sensitive, critical, or operator-defined facts should instead be captured through User Profile fields, where the existing admin-defined onboarding and selective encryption model already applies.

## Considered Options

- Reuse encrypted User Profile fields for all remembered facts. Rejected because User Memory is ambient personalization, while User Profile is structured operator-defined data.
- Encrypt User Memory with the existing admin-private-key/NIP-04 pattern. Rejected because Sage cannot decrypt those records during normal User Conversations without introducing a larger key-management change.
- Add a new Sage runtime encryption scheme for User Memory. Deferred because it would complicate the first version, while the intended User Memory scope is deliberately low sensitivity.

## Consequences

User Memory must not become a place for legal status, medical facts, risk assessments, credibility judgments, secrets, or other high-stakes case facts. If an admin asks Sage to remember that kind of information, Sage should redirect the request toward creating or updating an encrypted User Profile field instead.
