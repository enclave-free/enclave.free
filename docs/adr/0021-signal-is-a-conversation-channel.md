# Signal Is A Conversation Channel

The Enclave Free Prototype treats enclave.free as the durable home where Sage lives: the Instance owns the Agent Settings, Conversation authority, Session Memory, and first-party context that shape Sage behavior. Signal should be added, if and when it is added, as a Conversation Channel into that same Sage rather than as a separate native Sage runtime with its own identity, memory, or permission model. This preserves the product boundary that Sage is the Agent Runtime inside enclave.free while still leaving room for Signal-specific delivery and formatting constraints.

## Considered Options

- Keep upstream Signal-native Sage as the conceptual parent and adapt enclave.free around it. Rejected because it would make Instance-owned Agent Settings and product authority secondary to a channel-specific persona.
- Treat Signal as a separate agent with separate memory. Rejected because Users and Admins should experience the same Sage inside the same Instance across channels.
- Delay all Signal intent until implementation. Rejected because the existing upstream code already contains Signal-native assumptions that future work could accidentally preserve as product direction.

## Consequences

The first Signal integration should provide Conversation access to Sage, not direct Admin-to-User messaging. Direct contact paths may be considered later, but current User Reachout remains the email-only ordinary product flow until a separate decision changes it. Signal access should use existing Admin identity and User Approval authority, with channel linking or verification treated as delivery setup rather than a new permission system.
