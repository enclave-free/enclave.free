# Implement the bounded provider first-event recovery window

Parent spec: #607

## Outcome

Sage gives each logical model request a 30-second pre-first-event boundary and at most three identical attempts, while preserving the existing model-driven Tool loop and never replaying executed Tools.

## Work

- Refactor the same-model recovery path to use one shared three-attempt ceiling.
- Change the production pre-first-event boundary from 20 to 30 seconds.
- Keep retry eligibility generic and content-neutral across the existing eligible failure categories.
- Preserve request identity, provider-event cutoffs, Tool-result reuse, and privacy-safe trace evidence.
- Update current architecture, Tool contract, and domain documentation.

## Acceptance

- Two silent attempts can recover on the third identical request.
- Three eligible failures exhaust without a fourth request, including mixed categories.
- Any provider event prevents recovery for that attempt.
- Post-Tool recovery does not replay Tool execution.
- Targeted and full Sage checks pass.
- Parent integration checks pass with the updated Sage pin.
- Demo verification repeats the customer-reported Admin Test-as-User first turn in fresh sessions.

## Non-goals

No model, prompt, reasoning, routing, Tool-selection, provider, failover, or configuration-surface changes.

