# Benchmark modernization evidence

Raw captures are immutable. Partial `*-review.json` files contain only supported negative judgments; omitted entries remain unreviewed, and the full planned denominator is retained. `*-measurements.json` files are derived summaries that can be regenerated with the review CLI. These are synthetic conversations, not advice or expert certification.

- [Historical consent evidence](historical-consent-evidence.json) and [partial review](historical-consent-review.json): retained private-memory documentation regression. The original legacy capture did not establish complete session/cleanup provenance.
- [Fresh consent evidence](fresh-consent-evidence.json) and [partial review](fresh-consent-review.json): 10-turn engineering cohort; observer-record workaround remains blocked.
- [Initial balanced run](balanced-conversations-initial.json): 75/76 completed. Predates the explicit semantic fixture fingerprint; final paired comparison rules withhold its timing comparison.
- [Initial natural corpus](natural-corpus-initial.json) and [partial review](natural-corpus-initial-review.json): 25/25 completed, but missing authoritative source manifest prevents general grounding certification.
- [Contact setup failure](modern-contact-full-setup-failure.json): preserved zero-request harness attempt.
- [First full contact run](modern-contact-full-first-attempt.json): all 169 requests, with cleanup rate-limit failures.
- [Contact scorer replay](modern-contact-full-pointer-remeasured.json): source and scorer byte hashes bind the replay; original summary and cleanup failures remain available. The replay corrects Markdown URL and approved Spanish address-alias false negatives.
- [CodeRabbit review](coderabbit-review.json): six local review issues; dispositions are recorded in the run ledger.

- [Final balanced capture](balanced-conversations-final.json) and [classification replay](balanced-conversations-final-remeasured.json): 76/76 completed; synthetic-referral delivery is an observation requiring review.
- [Final natural corpus](natural-corpus-final.json): 25/25 completed with exact source manifest and successful owned cleanup. The [partial review](natural-corpus-final-review.json) and [measurements](natural-corpus-final-measurements.json) retain two consent-workaround failures.

The formatter explicitly excludes this directory so byte-based replay provenance remains stable. See the [run ledger](../../2026-09-10-benchmark-modernization.md) for commands, test results, and final cohort interpretation.

- [Final contact matrix](contact-final.json) and [observed source provenance](contact-final-provenance.json): 139/169 deterministic passes, 169 completed requests, no harness or cleanup failures. Changed-contact follow-ups passed 12/40.
