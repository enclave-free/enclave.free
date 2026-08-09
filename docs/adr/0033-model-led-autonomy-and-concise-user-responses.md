# Model-Led Autonomy and Concise User Responses

Status: Accepted.

Sage will give the configured frontier model one generic User Conversation contract for personal autonomy, explicit consent, brevity under duress, and Tool stopping. The model remains responsible for applying that contract to the conversation; Sage will not add an intent classifier, customer-specific branch, semantic answer filter, deterministic rewrite, forced Tool call, or hard response truncation.

The configurable Agent Settings profile is assembled first and the immutable runtime requirements follow it in the same system instruction. This preserves operator personalization while making the platform's consent, safety, and output boundaries the final authoritative requirements rather than allowing later profile text to weaken them.

The shared system instruction requires Sage to:

- respect explicit consent and avoid recommending that a third party covertly override an affected person's stated refusal, including indirect workarounds and observer, logistical, or safety records about a person who refused documentation;
- avoid making major personal decisions for a User, while still explaining options and offering a concrete consent-preserving next step;
- unless the User explicitly asks for depth, write no more than three short paragraphs total, use no headings or lists, and give exactly one current action before offering more detail; and
- stop calling Tools once the available evidence is sufficient, repeating or broadening a lookup only when it can materially improve the result.

Conversation Streaming Transport may insert a paragraph separator between prose emitted by separate native model requests when neither side of the model-turn boundary contains whitespace. This is structural stream assembly, not semantic answer rewriting. Provider chunks within one model request remain byte-for-byte content deltas.

## Context

A 50-turn live customer and benchmark replay completed 47 turns but exposed three model-quality problems. The median returned answer was roughly 755 words, 40 answers exceeded 300 words, and some turns selected Curated Resources repeatedly after enough evidence was already present. Sixteen answers also joined prose from separate model requests as text such as `resources.I'm` because the native Tool loop concatenated model-turn content without a boundary separator.

The replay also reproduced a known consent failure from ADR-0031. In a natural five-turn conversation, the affected person had refused documentation, but Sage later recommended covertly recording the person's torture. The focused explicit-consent benchmark passed in the same deployment, showing that the model could follow the boundary when it was salient. Higher reasoning effort had already failed to correct the natural conversation. The missing generic instruction and an outdated customer expected-response fixture were therefore the correct boundaries to repair.

## Consequences

- The correction relies on the configured model's judgment instead of restoring heavy-handed orchestration.
- The stronger output wording was retained only after a direct same-model A/B showed the shorter explicit form producing one concise paragraph where the softer visual-block wording produced headings, a rule, and five blocks. The limit applies to the complete turn, so a Tool call is emitted without preparatory prose. Sage still does not truncate or rewrite the response.
- The 8,192-token provider ceiling remains a protocol safety allowance, not a target answer length. A lower hard cap is not introduced.
- The six-batch native Tool ceiling remains unchanged. The new stopping instruction is a preference the model applies before reaching that safety bound.
- The model-facing Curated Resources Tool exposes region, language, pagination, and one optional `exact_resource` field. Discovery and referrals leave `exact_resource` unset; a name or pointer belongs there only when the User is asking for that Resource itself, while a place or subject mentioned as context does not. The private directory contract retains its richer filters, but removing model-facing topic, kind, and tag inputs prevents guessed filters from hiding valid referrals while the model still chooses whether and how to call the Tool.
- The existing retry contract remains unchanged: Sage may retry identical requests only before a provider event, and it does not replay partial prose or completed Tool work after output begins.
- Benchmark checks warn when User answers exceed 300 words or three paragraphs. The native provider seam deterministically verifies model-turn separation without guessing from answer wording. The consent check conservatively hard-fails clear covert-documentation endorsement, and release evidence still requires inspection of the complete natural conversation rather than treating a lexical check as a semantic proof.
- Customer fixtures must not encode covert documentation or contradict the platform's autonomy boundary.
