# Contact evaluation correction — September 16, 2026

The DeepSeek v4.1 Flash comparison exposed two evaluation conflicts. Contact prompts asked for usable real-world contacts while their source records explicitly said “do not contact.” Inventory checks rejected valid numbered ranges, abbreviated suffix lists, and terminal-page recaps even when Tool metadata showed all 11 records had been retrieved.

The contact matrix now asks for fictional directory values in English and Spanish. Source warnings remain. Exact current-pointer and required-lookup checks remain; a warning cannot turn a stale value or missing value into a contract pass. Changed and unchanged journeys receive identical prompts, without mutation hints. This is a directory-value contract, not a natural referral-quality test.

The inventory checker accepts explicit names, bounded numbered ranges, and contiguous suffix lists. It still checks unique coverage, successful Tool execution, pagination evidence, count claims, and invalid bounds. Repetition is retained as an observation: a recap cannot substitute for omitted records. This refines the specification's duplicate-name rule to distinguish repeated presentation from missing coverage.

The manifest is versioned `neutral-contact-v4`, with `inventory-coverage-v2` and hashes covering the contact prompts and source description. Old artifacts and review judgments are unchanged. Do not combine old and new fixture cohorts as if their questions were identical.

Verification:

- Before the fix, the new regression cases reproduced 18 failing subtests: ten contact prompt variants and all eight saved inventory answers.
- After the fix, all eight saved inventory answers satisfy the deterministic inventory checks. The fixture retains only synthetic answers, case IDs, and allowlisted page metadata from the September 16 run.
- Additional English/Spanish presentation variants, malformed ranges, missing names, absent Tool evidence, current-value quotations, stale quotations, and refusals are covered.
- `python -m unittest discover -s scripts/benches -p 'test_*.py'`: 103 passed.
- `python -m unittest discover -s scripts/tests -p 'test_*.py'`: 94 passed.
- `git diff --check`: passed.

No live model calls were made for this correction. The saved-answer replay tests scorer behavior; it is not a new model-quality score or semantic certification. A new isolated live cohort is needed to measure answers to the corrected contact prompts. Model instructions, production configuration, and the earlier quote-backed safety/grounding findings are unchanged.
