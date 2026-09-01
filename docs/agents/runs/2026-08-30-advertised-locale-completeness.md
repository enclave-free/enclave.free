# Advertised locale completeness run ledger

## Run

- Run ID: `advertised-locale-completeness-2026-08-30`
- Target repository: `enclave-free/enclave.free`
- Base branch: `staging`
- Feature branch: `feature/advertised-locale-completeness-final`
- Human owner: plebdev
- Started: 2026-08-30
- Status: platform-only multilingual-copy cleanup in progress; PR #667 remains open and unmerged

## Goal

Complete the static multilingual product copy owned by the Enclave platform so
all 31 advertised languages resolve the English catalog structure without
missing keys, placeholder drift, plural-form gaps, or unapproved raw frontend
copy.

This delivery is intentionally limited to the Enclave platform repository. The
previous Conversation Activity protocol work from issue #665 was removed at the
maintainer's direction. The Sage pin is restored to `staging`, Sage PR #54 is
not a dependency, and the localization CI job does not initialize or inspect
the Sage submodule.

## Included scope

- One typed catalog for all 31 advertised locale codes, display names, resource
  registration, onboarding choices, and Admin default-language choices.
- Direct JSON backfills for the 25 formerly incomplete locale catalogs.
- Complete key, interpolation-placeholder, and locale-required plural coverage.
- Parser-backed checks for untranslated visible JSX, translatable attributes,
  rendered variables, and registered dynamic translation-key families.
- Platform-owned static copy fixes across Admin, User, authentication,
  onboarding, Resource, loading, empty, error, and accessibility surfaces.
- Platform-owned Deployment Readiness message keys and bounded runtime values.
- Localized magic-link subjects and bodies for every advertised locale, using
  only the explicit language selected in the platform UI.
- Document `lang`/`dir` synchronization and RTL Arabic behavior.

## Explicitly excluded

- Sage source changes, Sage submodule changes, or Sage message-protocol changes.
- Conversation Activity title/status/summary localization across the Sage seam.
- Translation helpers, generators, brokers, checkpoint state, or generation
  dependencies in the shipping tree.
- Native-speaker certification; machine-assisted structural coverage still
  requires follow-up Linguistic Review for human-quality claims.
- Production deployment, release promotion, live-data changes, or merge.

## Provenance and structural evidence

- English contains 2,427 scalar leaves after removing the Sage-only Activity
  message keys.
- All 31 advertised locale resources contain every English key, preserve all
  interpolation placeholders, and include locale-required plural forms.
- Twenty-five formerly incomplete catalogs received 24,061 direct locale JSON
  entries: 24,025 shared missing leaves plus 36 locale-specific plural leaves.
- Draft translations were machine-assisted locally with `qwen3.6:35b` and
  `gemma4:26b`, then structurally validated. Native-speaker Linguistic Review
  remains an explicit nonblocking follow-up.
- The shipping tree contains no translation generator/helper, provider client,
  broker, checkpoint, or resumable generation state.
- The Deployment Readiness item/status matrix is owned by the Enclave Control
  Plane and compared exactly with the frontend translation registry.
- Magic-link locale validation accepts the same 31-code catalog and defaults to
  English when no explicit valid selection is supplied.

## Verification

- Focused localization, Chat, stream-adapter, and readiness tests: 6 files / 90
  tests passed.
- Full frontend suite after removing the Sage-only tests: 80 files / 481 tests
  passed, plus 1 file / 6 reset-script tests passed in the isolated harness.
- TypeScript, the host production frontend build, and the exact frontend-only
  Docker production build passed without a Sage checkout or build context.
- The exact Enclave Control Plane security-regression selection passed 144
  tests under Python 3.11.
- The no-Sage-dependency audit found no Sage submodule diff, Sage localization
  import, keyed Sage payload field, cross-repository localization test, or
  Sage-only locale key.
- Fresh independent Standards and Spec reviews: pending after final diff freeze.

## Visual evidence

- `docs/agents/runs/artifacts/advertised-locales/language-picker-31-locales.png`
- `docs/agents/runs/artifacts/advertised-locales/spanish-auth-desktop.png`
- `docs/agents/runs/artifacts/advertised-locales/spanish-auth-compact.png`
- `docs/agents/runs/artifacts/advertised-locales/arabic-auth-desktop.png`
- `docs/agents/runs/artifacts/advertised-locales/arabic-auth-compact.png`
- `docs/agents/runs/artifacts/advertised-locales/bengali-auth-desktop.png`
- `docs/agents/runs/artifacts/advertised-locales/bengali-auth-compact.png`
- `docs/agents/runs/artifacts/advertised-locales/finnish-auth-desktop.png`
- `docs/agents/runs/artifacts/advertised-locales/finnish-auth-compact.png`

## Delivery

- Parent PR: https://github.com/enclave-free/enclave.free/pull/667
- Further CodeRabbit attempts were explicitly waived by the maintainer; the
  final platform-only diff will use fresh independent Standards and Spec review.
- Do not merge or deploy without explicit maintainer permission.
