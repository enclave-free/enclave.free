# Default GLM Reasoning Effort to None

Status: Accepted.

The Enclave Free deployment will send an explicit `reasoning_effort` on every
native Conversation model request. `TINFOIL_REASONING_EFFORT` is the single
deployment setting and defaults to `none` for the authoritative `glm-5-2`
model. Sage validates the provider-supported values at startup and exposes the
effective non-secret value through its runtime configuration fingerprint.

This is a deployment-level model choice, not Agent orchestration. Sage will not
select reasoning effort from prompt keywords, Persona, enabled Tools, or the
current Tool-loop step. There is no User or Admin UI control and no automatic
escalation to a higher level. Operators may explicitly choose another supported
provider value for a controlled evaluation or a future deployment decision.

## Evidence

The previous deployment omitted the field, causing GLM 5.2 to use the
provider's maximum-reasoning default. The complete four-Persona customer replay
at that default produced a 92.9-second median total turn, two 180-second active
request failures, and a 958-word median response. Retrieval and Curated Resource
execution remained sub-second and therefore did not explain the dominant delay.

A matched live demo evaluation then compared `none` and `high` across two
repetitions of four representative scenarios: a no-Tool control, Knowledge
Search, Curated Resources, and a combined Knowledge/Curated turn. All sixteen
turns selected the expected Tools and produced comparably grounded answers.
Across the eight turns per setting, `none` reduced mean first-visible-answer
time from 9.9 seconds to 5.1 seconds and mean completion time from 47.7 seconds
to 40.0 seconds. Its maximum completion was 112.7 seconds versus 130.6 seconds
at `high`.

Two additional known-risk scenarios tested the judgment that could plausibly
benefit from more reasoning. At `none`, Sage clearly rejected covertly recording
a torture survivor against his stated wishes and returned only Nicaragua-relevant
vetted referrals. The pair completed in 47.1 seconds. At `high`, the answers
reached the same conclusions but took 113.4 seconds. No measured safety,
grounding, Tool-selection, or country-relevance improvement justified that cost.

These samples are bounded release evidence rather than a universal model claim.
They establish the best current platform default and leave future changes to the
same explicit, scenario-based evaluation process.

## Consequences

- The platform no longer silently inherits a provider reasoning default that
  can change or impose unmeasured latency.
- GLM 5.2 remains responsible for Tool selection and final answers; Sage does
  not add compensating routing, answer rewriting, or hidden escalation logic.
- The focused benchmark includes tight-consent and Nicaragua-referral cases in
  addition to ordinary, Retrieval, Curated Resource, and combined Tool turns.
- Higher reasoning levels remain available as an operator-controlled experiment,
  but changing the production default requires paired latency and inspected
  answer-quality evidence.
