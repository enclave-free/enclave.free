# Implementation analysis and prototype reference

> Name update: the current product name is **LIBERATOR**, all caps. See [the release preparation record](LIBERATOR.md) for the rename, current screenshots, and updated rollback instructions. PX references below describe the earlier version.

## Result and design choices

The patch keeps PX as the product identity. The WLC reference supplies cyan, yellow, lime, pink, deep navy, and cream. PX uses an original text-and-color-bar treatment and an original local SVG favicon; the WLC wordmark is not substituted for PX.

The welcome panel uses the existing `headerTagline` from Instance Settings. No additional mission text, signup questions, or English-only product strings were introduced. The tagline remains operator-authored text and does not automatically translate. `dir="auto"` gives the tagline appropriate direction independently of the selected interface language.

Existing IBM Plex Sans supplies the typography. Satoshi was researched but not added. This avoids adding another font download/license dependency for a temporary patch. Existing Google Fonts requests remain part of the baseline app; this patch does not add a font provider or runtime WLC asset request.

The literal WLC cyan is decorative. Interactive text uses a darker teal in light mode for contrast, and primary buttons use navy. Dark mode uses a lighter cyan with dark button text. Status colors retain the app's existing meaning, so pink decoration does not replace error styling.

## Before and after

| Before | After |
| --- | --- |
| Centered square icon badge and Instance name on entry screens | Prominent PX text with compact decorative color bars |
| One centered card for language, signup, verification and profile | Desktop introduction beside the existing form; mobile stacks the introduction above it |
| Warm neutrals with configured accent | Scoped cream/navy/teal presentation, with four WLC palette accents |
| Generic compact shared header | Compact PX identity with existing back, language, settings and theme controls |
| Heavily rounded entry card with shadow and entrance motion | Open form area, 10px primary-button/radio corners, no entry-card animation |
| Generic document title/favicon initialization | PX title and local favicon on enabled builds, including cached-settings initialization |
| Configured system/light/dark behavior | Same preference behavior, with separate checked PX light/dark palettes |
| No demo build override | Explicit default-off selector with a frontend-only Compose override |

The detailed per-file inventory is in [README](README.md). Formatting in touched components follows the repository's existing Prettier hook; there is no unrelated change to the generic `types/instance.ts` implementation.

## What worked

1. **Shared entry shell.** Styling `OnboardingCard` covered language selection, signup, email states, approval, profile, and admin entry without duplicating their control logic.
2. **Inherited token override.** The existing provider writes custom color properties directly to `html`. Defining the temporary tokens on `body` supersedes those inherited values for the rendered app, including portals mounted under body. Original settings and root properties remain intact.
3. **Display-only metadata wrapper.** Two provider imports route title/favicon application through a small patch-specific module. Cache writes and Admin configuration values remain untouched. The browser rollback check confirms that a custom purple setting survives while the visible patch is teal/navy.
4. **Build-time opt-in.** The current frontend is a compiled Vite bundle served by nginx. An explicit build argument is sufficient for one demo and adds no backend configuration API.
5. **Unmodified baseline comparison.** All five public entry assets matched the local preparation build byte for byte. This ties the patch to the live frontend much more reliably than assuming that a local branch name identifies the deployed version.
6. **Real bundles with synthetic APIs.** The browser fixture exercised the existing signup, verification, approval, and profile paths without real accounts or email. The same origin switched between enabled, disabled, and baseline bundles to test rollback with retained browser state.

## Issues found and resolved during verification

- Initial screenshot capture ran before the browser completed layout/paint after a theme or viewport change. The verification script now waits for fonts and two animation frames and disables screenshot animations. Dark-mode captures now show the actual settled dark presentation.
- The User Type page wraps the shared shell in a centered flex container. The new shell needed an explicit `width: 100%` to avoid shrinking compared with other entry pages.
- Initial synthetic endpoint/copy assumptions differed from the existing app (`/auth/magic-link`, confirmation punctuation, and generic expired-link copy). The fixture/assertions were corrected to match the application. No authentication code was changed to satisfy the fixture.
- Port 4180 on the host returned an unrelated local application despite the Docker port binding. Production HTTP verification was therefore performed inside the exact named verification container, whose HTML carried the expected PX marker and whose health check passed. That temporary container was then removed.

## Boundaries and tradeoffs

This remains source-level customization. It does not make the generic product configurable enough to recreate the result. The selector compiles the temporary identity into a build, and turning it off requires serving a different frontend build. Theme and language remain runtime preferences as before.

The compact header emphasizes PX and omits the previous tagline beside the name; the existing tagline is prominent in the welcome area. Shared palette changes also affect Admin screens. Admin workflows retain their original controls and configuration values.

The desktop decorative bars disappear below 800px to keep the form accessible without excessive scrolling. Data notices and functional form sections remain intact. No photography, additional motion library, analytics, new API request, or product dependency was introduced.

The retained baseline image procedure is documented but has not been executed on the live host. Browser session markers were preserved in local tests; that is not a claim of a live authenticated-session rollback test. Model responses, real email delivery, real Admin signing, and server authorization are outside the synthetic visual verification.

## Requirements for future customization without source edits

| Source change needed here | Future Instance Settings capability |
| --- | --- |
| PX palette and dark-mode rules | Semantic color presets with light/dark values and contrast validation |
| Separate navy button and teal link colors | Independent action, link, focus, and decorative color roles |
| Large/compact PX brand components | Brand asset or wordmark layouts with size, spacing, mobile behavior, and accessible text |
| Side-by-side welcome layout | Selectable entry-page layouts that reuse the existing auth/onboarding controls |
| Tagline promoted into hero text | Separate header tagline and welcome content slots, including localized operator content |
| Font stack and display sizing | Approved typography presets, font assets, script fallbacks, and responsive display scale |
| Header and form treatment | Surface, radius, spacing, and density controls scoped to supported components |
| Build-time identity metadata | Runtime title/favicon settings applied before first paint, with cache invalidation |
| Source branch plus image rollback | Preview, publish, version history, and restore for appearance settings |

The prototype should demonstrate these capabilities with the PX before/after screenshots as a reference. It should preserve clear ownership: Instance Settings store appearance, while a User's theme/language preference remains theirs. The temporary patch code should not become the configuration system by accident.
