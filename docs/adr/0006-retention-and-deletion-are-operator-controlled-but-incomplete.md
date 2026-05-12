# Retention And Deletion Are Operator-Controlled But Incomplete

Enclave Free treats Data Retention and Data Deletion as part of Operator-Controlled Privacy: the Operator should control how long Instance data is kept and how it is removed. The current prototype does not yet provide complete deletion coverage for every data class, including full user-data deletion, logs, uploaded document artifacts, derived document chunks, and Sage Session Memory. Until those paths are complete, product and security docs should describe retention and deletion as a direction and responsibility, not as a fully implemented guarantee.

The prototype now supports operator-invoked retention execution for stale active Conversation state and failed/superseded Document artifacts. This is still partial coverage: scheduled retention policy, secure erase semantics, and complete log/session retention remain future work.
