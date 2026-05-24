# Signal Conversation Channel Spike

Status: design spike, ready to break into AFK implementation issues

## Goal

Define the smallest end-to-end Signal Conversation Channel slice that proves Conversation access to Sage without creating a separate Signal-native agent, memory store, or permission model.

## First Slice

The first implementation slice should accept an inbound Signal message from a linked participant, map it to the existing Admin identity and User Approval authority, deliver it to the same Conversation and Session Memory model used by enclave.free web chat, and return Sage's response through Signal with channel-specific delivery and formatting constraints.

The slice should preserve Agent Settings as the source of truth for Sage identity. Signal may shape delivery details such as message length, attachments, latency expectations, and supported formatting, but it must not define Sage's persona or grant new product authority.

## Out Of Scope

- Out of scope: direct Admin-to-User messaging.
- Out of scope: replacing email-only User Reachout.
- Out of scope: Signal-only Session Memory.
- Out of scope: a separate channel-specific permission model.

## Open Implementation Questions

- How should Signal account linking prove control of a phone number without creating a new approval path?
- Where should channel delivery metadata live so it can audit routing without forking Conversation Content?
- Which Signal formatting limits should be represented in the Sage runtime profile before the first AFK build slice?
