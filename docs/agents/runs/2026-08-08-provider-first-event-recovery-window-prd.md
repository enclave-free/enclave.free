# Provider first-event recovery window

Status: Accepted for implementation

## Problem

The demo's configured model provider intermittently accepted a request but emitted no answer, reasoning event, Tool call, or other stream event before Sage's 20-second boundary. Sage retried once, but several reported Test-as-User first turns encountered the same silence twice and failed after about 40 seconds. Retrieval and Tool execution in those turns remained fast; the failure was isolated to the provider's pre-first-event phase.

## Decision

Each logical model request receives one shared budget of three identical attempts. A completely silent attempt is abandoned after 30 seconds and may consume one of the two retries. The same budget also covers the existing eligible connection, timeout, response-stream, retryable upstream, and protocol failures; failure categories do not receive separate budgets.

The request is repeated at the model-request boundary against the same configured model with the same messages, Tools, parameters, and reasoning configuration. Any provider event ends retry eligibility for that attempt. An already executed Tool batch is never replayed; later model attempts receive the same correlated Tool results already present in the request.

The 30-second boundary and three-attempt ceiling remain internal named runtime policy. They do not become an Instance Setting, Deployment Setting, Agent Setting, or Admin control.

## Acceptance criteria

1. The production first-event boundary is 30 seconds.
2. Two silent attempts followed by a successful third attempt return the third response.
3. Three eligible failures exhaust the logical request without a fourth attempt.
4. Mixed eligible failure categories share the same three-attempt ceiling.
5. The three provider requests are structurally identical.
6. A provider event prevents later model-request recovery for that attempt.
7. Tool execution occurs once when a post-Tool model request needs recovery; only the model request repeats.
8. Trace evidence identifies the step, attempt, retry reason, and terminal recovered or exhausted outcome without Conversation Content.
9. No model, reasoning, prompt, Tool-selection, routing, or provider configuration changes accompany the fix.
10. The deployed demo passes repeated fresh Admin Test-as-User first turns using the customer-reported prompt and effective User Tool configuration.

## Operational trade-off

The worst case for a logical model request becomes 90 seconds of complete provider silence before Sage returns the existing temporary-unavailability response. A cancelled silent attempt may still have incurred provider work. This deliberately spends one additional bounded attempt to improve recovery from the failure pattern observed in the demo, while keeping the retry mechanism generic and content-neutral.
