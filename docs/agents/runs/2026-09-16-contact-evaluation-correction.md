# Contact evaluation correction — September 16, 2026

The DeepSeek v4.1 Flash comparison exposed two evaluation conflicts. Contact prompts asked for usable real-world contacts while their source records explicitly said “do not contact.” Inventory checks rejected valid numbered ranges, abbreviated suffix lists, and terminal-page recaps even when Tool metadata showed all 11 records had been retrieved.

The contact matrix now asks for fictional directory values in English and Spanish. Source warnings remain. Exact current-pointer and required-lookup checks remain; a warning cannot turn a stale value or missing value into a contract pass. Changed and unchanged journeys receive identical prompts, without mutation hints. This is a directory-value contract, not a natural referral-quality test.

The inventory checker accepts explicit names, bounded numbered ranges, and contiguous suffix lists. It still checks unique coverage, successful Tool execution, pagination evidence, count claims, and invalid bounds. Repetition is retained as an observation: a recap cannot substitute for omitted records. This refines the specification's duplicate-name rule to distinguish repeated presentation from missing coverage.

The manifest is versioned `neutral-contact-v4`, with `inventory-coverage-v3` and hashes covering the contact prompts and source description. Old artifacts and review judgments are unchanged. Do not combine old and new fixture cohorts as if their questions were identical.

Verification:

- Before the fix, the new regression cases reproduced 18 failing subtests: ten contact prompt variants and all eight saved inventory answers.
- After the fix, all eight saved inventory answers satisfy the deterministic inventory checks. The fixture retains only synthetic answers, case IDs, and allowlisted page metadata from the September 16 run.
- Additional English/Spanish presentation variants, malformed ranges, missing names, absent Tool evidence, current-value quotations, stale quotations, and refusals are covered.
- `python -m unittest discover -s scripts/benches -p 'test_*.py'`: 103 passed.
- `python -m unittest discover -s scripts/tests -p 'test_*.py'`: 97 passed.
- `git diff --check`: passed.

A fresh isolated DeepSeek v4.1 Flash cohort subsequently ran all 169 cases using commit `aded0d46`, fixture v4 and inventory scorer v2. All requests completed, with no fallback/rate-limit events, harness failures, or fixture-deletion failures. The original artifact reports 149/169 contract passes: 80/80 openings, 24/40 changed follow-ups, 39/40 unchanged follow-ups, 5/8 inventory cases, and 1/1 disabled-tool control.

Review found three further inventory false failures: a truthful caveat about the first bounded page was treated as uncertainty about the complete set, and two terminal-page paraphrases were not recognized. New regressions reproduced those three failures. Scorer v3 corrects their interpretation while preserving checks against current uncertainty and incomplete Tool evidence. Offline replay of the unchanged raw answers gives 8/8 inventory passes and 152/169 total contract passes. This is remeasurement of the same cohort, not a new live run or semantic certification.

The remaining 17 failures comprise 15 old contact values returned without a fresh lookup and two refusals to provide secure-channel values. These are retained, not waived. The changed-source behavior is a Sage/model integration result; this run does not isolate the base model as the cause. Source warnings and opaque fixture identifiers may contribute to the two refusals, so their broader interpretation remains open.

Original raw artifact SHA-256: `57fe6a89c093808e7f7e2e20ba0237ec5a25ec9702c23a239f3b6595c1e0244e`. The operator evidence bundle contains the original artifact, the separate hashed inventory remeasurement, all failed cases, provider routing, and final deletion verification. The isolated stack/volumes and temporary credential file were removed; production returned HTTP 200 and remained on DeepSeek. Model instructions, production configuration, and earlier quote-backed safety/grounding findings are unchanged.
