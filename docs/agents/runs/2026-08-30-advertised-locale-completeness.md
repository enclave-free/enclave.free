# Advertised locale completeness run ledger

## Run

- Run ID: `advertised-locale-completeness-2026-08-30`
- Loop: Feature Dev
- Target repo: `enclave-free/enclave.free`
- Base branch: `staging`
- Feature branch: `feature/advertised-locale-completeness-final` (clean-history shipping branch)
- Human owner: plebdev
- Started: 2026-08-30
- Current status: #660–#666 complete and verified; non-draft staging PR #667 open, PR review in progress
- Skill setup status: complete; issue tracker, triage labels, and multi-context domain docs are configured

## Goal

Systematically finish Jim's localization work end to end so every language the product advertises is connected to all static user-facing copy, the contract is enforced in CI, server-authored display copy does not silently leak English, and the result is delivered as a reviewed non-draft PR into `staging`.

## Durable artifacts

- CONTEXT updates: defined Advertised Locale, Locale Structural Completeness, and Linguistic Review
- ADRs: none warranted yet
- Prototype source branch, if any: none planned
- Spec issue: #659
- Tickets: #660, #661, #662, #663, #664, #665, #666
- Ticket sessions: #660–#665 complete; #666 integration evidence and PR preparation in progress
- Agent briefs: pending
- Review packets: pending
- Local CodeRabbit report: `docs/agents/runs/2026-08-31-advertised-locale-completeness-coderabbit-local.md` (service unavailable after three authenticated attempts; independent Standards + Spec fallback passed)
- PR URL: https://github.com/enclave-free/enclave.free/pull/667; Sage dependency PR: https://github.com/enclave-free/sage/pull/54
- Existing source work: PR #658, issues #495 and #647

## Commands

- Install: `cd frontend && npm ci`
- Typecheck: `cd frontend && npx tsc --noEmit`
- Test: `cd frontend && npm test -- --run`
- Build: `cd frontend && npm run build`; production contract via `scripts/test_frontend_runtime.sh`
- Visual verification: local production frontend plus scripted browser checks and screenshots for Spanish, Arabic, and representative additional locales

## Ticket ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #660 | AFK | complete | Standards + Spec passed | Locale catalog and contract foundation | yes |
| #661 | AFK | complete and integrated | final Standards + Spec pass | Static frontend, keyed readiness descriptors and values, accessibility, and rendered error-state closeout | yes |
| #662 | AFK | complete and integrated | final Standards + Spec pass | High-need locale catalogs | yes |
| #663 | AFK | complete and integrated | final Standards + Spec pass | Remaining locale catalogs | yes |
| #664 | AFK | complete and integrated | backend + frontend Standards and Spec reviews passed | Localized magic-link email | yes |
| #665 | AFK | complete and integrated; Sage PR remains open | parent + Sage Standards and Spec passed; final CodeRabbit finding fixed and independently re-reviewed | Sage Activity message contract | yes |
| #666 | AFK | complete | final Standards + Spec pass | Integration and release evidence | yes |

## Parked HITL slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| Translation quality review | Native-speaker review is not available for every advertised locale | Does not block structural completeness or automated verification | Optional post-PR linguistic review | Record provenance and residual linguistic risk |

## Issue session ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #660 | `c76b02a` | `/root/ticket_660` | `1111324`, `043fa3e`, `82886c9` | Standards pass; Spec pass | 457 tests, typecheck, build, 5/5 runtime checks |
| #661 | `34d8ba0` | `/root/ticket_661` | source `689c0e6`, `5ffab9a`, `1d1a630`; integrated `4a2fd02`, `f6c6b02`, `77801fd` | Standards pass; Spec pass | 477 tests, typecheck, build, parser asset exclusion; reviewer focused suites passed |
| #662/#663 | `a637c3d` | local direct catalog edit | `38f8857` | parent final review pending | 31 locales have zero missing English keys, zero required plural forms, and placeholder parity; 25,261 direct locale leaves added; no translation-helper source ships |
| #664 | backend `64195eb`; frontend `77801fd` | `/root/ticket_664`, `/root/ticket_664_frontend` | backend `4ca58b4`, `3edf00a`, `f818dc3`, `4af368a`; frontend integrated `855d180`, `7f8ad82`, `c733473`, `0dbd693` | Backend pass; frontend Standards pass; frontend Spec pass | 143 backend security regression tests; 24 affected frontend tests, 28 localization-contract tests, typecheck, build |
| #665 (Sage) | `f41321e` | `/root/ticket_665`, `/root/fix_665_coderabbit` | `bbbc43f`, `b86d4dc`, `69f0c43`, `2f8db4b`, `77a385f`, `0391240`, `5e1ef84`, `bc00da6` | Standards pass; Spec pass; CodeRabbit three-round loop complete; final finding fixed and re-reviewed | 195 sage-core + 67 binary tests, focused serialization/activity tests, check, workspace strict clippy, fmt |
| #665 (parent frontend) | `77801fd` | `/root/ticket_665` | source `e6ae176`, `ea525ae`, `61c302d`; integrated `1d05c12`, `8433c2a`, `1d8c763` | Standards pass; Spec pass | 83 files / 486 tests, 67 focused tests, pinned Sage focused tests, typecheck, build, parser asset exclusion |
| #666 | `1d8c763` | `/root` | `672eee7`, `38f8857`, `2bdf9c6`, `def891b` | Standards pass; Spec pass | frontend 83 files / 490 tests; Enclave Control Plane 432 tests; security regression 143 tests; typecheck; build; 5 runtime + 3 Compose tests; Sage fmt, strict clippy, 195 library + 67 binary tests, and executable check |

## Evidence captured

- PR #658 head: `c76b02a1829155666f7412f73fb43e0061b9951b`
- English locale: 2,475 scalar leaves.
- All 31 advertised locales have English-key parity and every locale-required plural form.
- Twenty-five formerly incomplete locale catalogs gained 25,225 shared English-key translations plus 36 locale-specific plural leaves across Czech, Hebrew, Italian, Polish, Portuguese, Romanian, and Ukrainian: 25,261 direct locale entries total.
- Deployment Readiness now carries stable label, summary, and next-action keys alongside compatibility English text; runtime acknowledgement counts and changed setting names remain interpolation values instead of disappearing when localized copy resolves.
- Parser-backed static-copy enforcement covers visible JSX and translatable attributes, and every Admin default-language choice derives from the same 31-locale catalog as onboarding and i18next.
- Catalog changes are direct locale JSON edits. Draft translations were machine-assisted locally with `qwen3.6:35b` and `gemma4:26b`, then structurally validated and reviewed for untranslated English labels. The deliverable contains no translation generator, broker, checkpoint state, or generation-only dependency. Native-speaker Linguistic Review remains an explicit nonblocking follow-up rather than being implied by structural completeness.
- The binding-aware AST contract recognizes actual translation bindings, rejects indirect dynamic keys, requires zero missing locale keys and zero missing locale-specific plural forms, and stays out of production assets.
- Focused readiness/localization verification passed 3 files / 50 tests; the complete frontend suite passed 83 files / 490 tests; TypeScript, production build, parser asset exclusion, the 5-test production container/runtime contract, and the 3-test Compose contract passed.
- The complete Enclave Control Plane suite passed 432 tests, and the exact security-regression workflow selection passed 143 tests.
- The pinned Sage commit passed formatting, workspace strict clippy, 195 library tests, 67 binary tests, doc tests, and the `enclave_web` executable check.
- Browser evidence confirms the 31-locale picker plus Spanish, Arabic, Bengali, and Finnish authentication at 1280×900 and 390×844. The document `lang`/`dir` values were `es/ltr`, `ar/rtl`, `bn/ltr`, and `fi/ltr`; every compact capture had `scrollWidth === clientWidth`, and no Vite error overlay appeared. Screenshots: `docs/agents/runs/artifacts/advertised-locales/language-picker-31-locales.png`, `spanish-auth-desktop.png`, `spanish-auth-compact.png`, `arabic-auth-desktop.png`, `arabic-auth-compact.png`, `bengali-auth-desktop.png`, `bengali-auth-compact.png`, `finnish-auth-desktop.png`, and `finnish-auth-compact.png`.
- The magic-link renderer supports all 31 advertised locale codes, uses exact placeholder validation, separates plain RFC subjects from escaped HTML, and isolates RTL URL/identity fragments. Frontend locale propagation remains intentionally sequenced after #661.
- Sage PR #54 adds keyed Activity descriptors while preserving English compatibility fields and stable safe machine identifiers; provider-controlled unsafe display data and trace IDs are redacted before stream, snapshot, persistence, and export boundaries.
- Final Sage review additionally gates timing title keys on canonical fallback equality, so custom compatibility titles remain visible and unkeyed instead of being replaced by localized static copy.

## Open questions

- None. The user's full-control instruction is taken as approval of the recommended structural-completeness definition and machine-assisted translation provenance.

## Escalations

- The wire-compatible readiness response still exposes parallel fallback/key/value fields. Rendering is centralized in one helper; replacing the compatibility wire shape with a nested descriptor is deliberately deferred as unrelated API cleanup rather than expanding this static-copy completion PR.
