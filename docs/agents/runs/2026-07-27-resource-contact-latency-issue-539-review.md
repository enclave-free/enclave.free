# Review Packet

## Issue

- Issue: #539 — Prove the reported customer journeys across User Types
- Slice type: authoritative four-mapping public Conversation regression, model-backed Resource Directory replay, privacy-safe evidence, and provider-neutral final-answer Tool-intent quarantine
- Baseline: parent `ab0516b09179485f57f264d3a647e44c303454d8`; Sage `327ee9ad018c47f65124df38a16e399114fe1c93`
- Review fixed point: parent-held uncommitted harness/records plus Sage `a82ac43761475a57a45ac18f8bcb9acedaf9e7bc`
- Status: complete; final independent exact-fixed-point specification and standards reviews passed

## Authoritative mapping and boundaries

- Read-only signed GETs established four demo mappings: global/no User Type, `Family member`, `Former Political Prisoner`, and `Solidarity Networks for Political Prisoners`.
- The demo has three configured User Types. All four mappings configure default Curated Resources and Knowledge Search; web search is disabled and 16 completed documents are available/default-active.
- No user, session, feedback, prompt, document content, or mutable endpoint was accessed. Nothing on demo, staging, or production was changed.
- The isolated local fixture has no documents. Its effective-server assertion therefore proves Curated Resources only and separately records the demo-configured default Tool IDs.

## Acceptance evidence

- The evaluator has 35/35 focused tests covering real global scope/restoration, explicit Spanish execution, effective server configuration, fresh contact follow-ups, metadata-authoritative inventory semantics, conservative numeric contradiction and Spanish-negation rejection, positive controls for supported count/offset/remaining wording, lifecycle completeness, summary exit status, failure-aware evidence persistence, loopback-only targeting, evidence schema v2, failure-atomic fixture setup, and cleanup.
- Contact follow-ups for every modality require a fresh explicitly successful Curated Resources lifecycle and reject stale email, phone, URL, address, or secure-channel values.
- Inventory scoring consumes only successful, allowlisted Curated Resources metadata with exact 10/11, offset 10, remaining-count 1, and terminal 1/11 or 0/11 semantics. Boundary collisions, negation/qualification, generic “more information,” unsupported slash and `of` count pairs, spelled offsets, remaining counts, and answer-only page claims fail.
- Curated Resources Trace summaries and metadata expose returned count, total count, truncation, and next offset. A terminal continuation page says how many of the total were returned on that page and that no results remain; neither the Trace nor actual Tool result calls that page the complete set. “Complete set” is reserved for offset zero with equal returned and total counts. Distinct pagination metadata survives trace deduplication. No deterministic Tool router, answer rewriter, or completeness claim injector was introduced.
- Privacy-safe JSON excludes prompts, arguments, results, session IDs, credentials, and customer content. Fatal/partial runs carry explicit status and completed/expected case counts. An evidence-write failure recomputes the summary as failed and returns a nonzero exit status.
- Before any fixture journal or mutation is created, the evaluator rejects every API origin except `localhost`, `127.0.0.1`, and `[::1]`; there is no remote escape hatch.
- Fixture creation is journal-first, uses a deterministic valid secp256k1 key, reconciles exact issue suffixes, and cleans partial setup.

## Safety correction review

- Sage scans every provider-neutral `Tool:` / `Tool decision:` label rather than stopping after benign explanatory prose. Tests cover same-delta and split-delta benign-first attacks plus a prose-like suffix followed by an Args block.
- The classifier still requires a structural invocation, JSON/Args block, line boundary, deliberation context, or a later repeated Tool label. Ordinary explanatory prose remains allowed and streams before finish.
- Existing retry/fail-closed behavior is unchanged. A provider can still cause a safe HTTP 500 after both final candidates are rejected.
- Curly/straight apostrophes share normalized process-narration detection; same- and split-delta `I’m going to search. Tool: ...` candidates fail before exposure.

## Verification

- Evaluator: 35/35.
- Backend full suite: 424/424.
- Sage full library: 163/163; focused curly narration 2/2, Resource Tool metadata 2/2, propagation 1/1, and pagination dedupe 1/1; `cargo check`, fmt check, and diff check pass.
- Frontend full suite: 75 files / 382 tests; production build passes.
- Cleanup: zero #539 backend/Sage fixture rows and zero isolated Compose containers, network, or volumes; all evaluator artifacts report zero cleanup failures.

## Model evidence — intentionally not all green

- Full authoritative run `/tmp/issue539-authoritative-four-v2-exact-final-valid-admin.json`: 22/33 completed before a safe provider fatal. Contacts were 18/18 before the fatal; global bounded inventory and both Family inventory cases passed. A global continuation scorer-only false negative was corrected afterward.
- Targeted Former inventory `/tmp/issue539-former-inventory-targeted-final.json`: reproduced the repetitive-process-narration HTTP 500, 0/2 completed, cleanup clean.
- Targeted Solidarity all-cases `/tmp/issue539-solidarity-all-targeted-final.json`: 8/8 passed, cleanup clean.
- Current global Spanish `/tmp/issue539-global-spanish-contact-metadata-final.json`: 3/3 passed, including exact Spanish email and disabled-global control.
- Metadata inventory RED `/tmp/issue539-global-inventory-metadata-final.json`: 0/2 because trace dedupe hid the second successful page; cleanup clean. Corrected `/tmp/issue539-global-inventory-metadata-dedupe-final.json`: 2/2 passed with exact page metadata; cleanup clean.
- The packet makes no 33/33 or four-persona-green claim. Deterministic gates are green; the provider-level fail-closed result remains a residual product risk.

## First-review findings resolved

- Scan all provider-neutral labels and preserve benign streaming.
- Require exact resource sets/pages and exact total/offset semantics.
- Reject every stale contact modality and require explicit completed/succeeded Tool lifecycle.
- Make partial/fatal evidence unambiguously non-successful.
- Make fixture setup and cleanup journal-first, reconciliation-safe, and valid-key deterministic.
- Replace synthetic persona claims with the authoritative read-only demo mapping.

## Second-rereview findings resolved

- Represent the global mapping with `user_type_id=None`, mutate the global default only after journaling its exact original value, restore it exactly, and omit a fake session-default query parameter.
- Execute Spanish as an explicit replay dimension without claiming it is a live persona setting; count its stale/fresh evidence and preserve the exact reported email prompt.
- Require privacy-safe Resource Tool metadata and adversarially exact inventory wording/name semantics.
- Normalize curly apostrophes and align held process narration with syntactic Tool detection.
- Derive process exit status from the final summary's `passed`/`fatal` state.
- Preserve distinct paginated Resource Tool metadata through trace deduplication.

## Third-rereview findings resolved

- Reject numeric count, fraction, and offset claims that contradict successful Resource Tool metadata, while retaining supported terminal continuation offsets.
- Reject Spanish negated/qualified completeness such as `No son todos` and `No puedo confirmar que no haya más`.
- Scope terminal Resource Trace summaries to the returned page count and total, without an unqualified “all.”
- Reject non-loopback evaluator API bases before fixture creation or mutation.
- Recompute failed evidence status and exit nonzero when evidence persistence fails.

## Final closure-check findings resolved

- Parse and reject unsupported natural-language numeric forms: `N of N`, `next offset is N`, and `N more matching resources`; retain positive controls for authoritative forms.
- Make the actual Resource Tool result offset-aware as well as its Trace summary. A terminal continuation page now reports final-page/no-remaining semantics and cannot call its one-page subset the complete set.

## Final independent closure review

- Specification: `SPEC_STATUS: PASS` at Sage `a82ac43761475a57a45ac18f8bcb9acedaf9e7bc` and the parent-held #539 diff.
- Standards and safety: `STANDARDS_STATUS: PASS` at the same exact fixed point.
- The closure review explicitly rechecked the natural-language numeric contradiction variants, Spanish negation, actual Tool-result and Trace pagination wording, loopback-before-mutation enforcement, and failed-evidence-write exit behavior.

## Review focus verified

- Confirm later provider-neutral labels cannot hide behind already streamed benign text and no invocation bytes escape.
- Confirm inventory scoring cannot pass partial results, boundary collisions, negative/qualified completeness, generic information wording, guessed offsets, or missing metadata.
- Confirm lifecycle scoring cannot pass an attempted, failed, missing, or stale Tool call.
- Confirm setup failures cannot strand Admins, users, User Types, resources, sessions, or Sage identities.
- Confirm the evidence summary cannot represent a fatal/partial run as successful.
- Confirm evidence persistence failure cannot leave a previously successful in-memory summary or zero exit status.
- Confirm no non-loopback API base can reach fixture setup.
- Confirm local effective Tool claims remain distinct from demo-configured defaults.
- Confirm global restoration is journal-first and exact, Spanish evidence is counted, and pagination dedupe retains distinct metadata pages only.

## Residual risk

- Provider output and latency are nondeterministic. The Former inventory prompt reproducibly failed closed after unsafe repetitive process narration; this is safer than exposing it but remains a user-visible failure.
- High latency was observed alongside successful backend retrieval, so current evidence does not prove degraded clusters skip Tools.
- Provider/cluster failover and controlled degraded-condition experiments remain out of scope.
