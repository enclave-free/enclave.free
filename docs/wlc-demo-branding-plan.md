# World Liberty Congress demo branding: research and proposed plan

Research date: 2026-09-08. Status: branch prepared for implementation; no application or deployment changes.

## Temporary branch and removal contract

- Branch: `temp/px-demo-wlc-visual-only`.
- Preparation base: `063e132ce0b77a238cd8bccdd4f36cfd38369eae` (release 0.4.20). Verify the actual deployed base before implementation; do not include an unrelated upgrade in the demo patch.
- Purpose: a temporary visual-only customization of the PX demo Instance, using WLC as the visual reference. PX remains the name.
- This branch intentionally contains organization-specific presentation code. Keep it isolated from generic Enclave releases. Do not merge it into `main` or `staging` as a general product feature.
- Allowed changes: frontend presentation, local visual assets, the minimum build wiring needed to enable the patch, focused verification, and patch documentation.
- Excluded changes: backend behavior, authentication, User Approval, Conversations logic, database schema/data, saved Instance Settings, and email identity.
- Keep implementation commits limited to this patch. Record their hashes and changed files here when implementation is complete, together with the deployed image, retained rollback image, and tested activation/removal commands.
- Removal is part of completion: verify the original frontend can be restored without restoring data or clearing a User's session. Later remove the temporary source changes and build override from the demo's running version.

## Reference for the frontend prototype

The finished patch will be a concrete visual reference for the improved frontend prototype. The future goal is to achieve this degree of customization through Instance Settings without changing source code.

During implementation, record which changes required source edits: palette, typography, logo treatment, welcome-page layout, supporting copy, form surfaces, and shared header treatment. Capture before/after desktop and mobile screenshots and note the settings that would be needed to reproduce the result. Store those findings with this document so they remain useful after the patch is removed.

This work demonstrates the desired result; it does not build the future customization system. Transfer the visual findings and requirements into that prototype deliberately, rather than making its design depend on this temporary implementation.

## Recommendation

Confirmed user requirement: keep **PX** as the Instance name and primary product identity throughout the temporary patch. Use WLC as the visual reference, not as a replacement name. Keep PX in page headings, the shared header, browser title, and email identity.

Build one small, opt-in WLC presentation overlay for the existing demo. Reuse the current authentication and onboarding components, with a more editorial welcome layout, properly sized WLC artwork, and coordinated typography and colors across the user journey. Keep the original appearance as the default. Avoid creating a separate signup implementation or a general white-label system for this temporary need.

Use a dedicated branch/worktree based on the demo's confirmed deployed commit when implementation begins. This research worktree is based on current remote main `063e132` (release 0.4.20), verified against GitHub with `git ls-remote`; its tree matches `origin/release/0.4.20`. The deployed commit has not been verified through host access.

## WLC identity research and visual direction

The reference is the official [World Liberty Congress website](https://worldlibertycongress.org/). Its content emphasizes a global pro-democracy movement, member programs, practical support, and advocacy. Its membership application is a different activity from creating an Enclave demo account; do not copy that application's extra questions into the demo signup.

The official [color logo PNG](https://worldlibertycongress.org/wp-content/uploads/2023/07/WLC_LOGO-2023_COLOR.png) is 1695 × 612 with transparency. Visual inspection confirms a bold stacked black wordmark beside a mark with black horizontal bars and four colored vertical bars. Preserve that asset's proportions and provide enough width; do not squeeze the wordmark into the existing square badge. An official [favicon asset](https://worldlibertycongress.org/wp-content/uploads/2023/08/FAVICON_2023-300x300.jpg) is also available.

| Role | Observed color | Proposed use |
| --- | --- | --- |
| Cyan | `#00B2CB` | Main brand accent, selected states, restrained highlights |
| Yellow | `#F8DD04` | Small decorative accent |
| Lime | `#9BC335` | Small decorative accent |
| Pink | `#E30E58` | Small decorative accent |
| Near-black | `#191919` | Wordmark and strong text |
| Deep navy | `#0A2533` | Primary action background and strong contrast |
| Cream / pale lavender | `#FAF2E5` / `#F5F7FF` | Optional quiet background surfaces |

The four bright colors and near-black were measured from the official logo and corroborated by the site's [Elementor global CSS](https://worldlibertycongress.org/wp-content/uploads/elementor/css/post-14.css). That stylesheet also declares Satoshi, Passion One, and fallback families. Use Satoshi for the proposed main typography if its distribution terms can be satisfied, with a local font asset and script fallbacks; otherwise begin with the existing humanist preset. Passion One is an optional display treatment, not a recommended body font. These are observations from deployed assets, not a formal brand manual.

The [homepage CSS](https://worldlibertycongress.org/wp-content/uploads/elementor/css/post-8743.css) and [theme CSS](https://worldlibertycongress.org/wp-content/uploads/blocksy/css/global.css) indicate wide editorial sections, photographic program tiles with dark overlays, modest 10px card corners, generous spacing, and light/deep-navy action treatments. The site contains multiple theme generations, so a live visual comparison should settle exact spacing during implementation.

Recommended composition: prominent PX branding, a generous light background, a bold short welcome statement, and a clean form panel. WLC supplies the palette, typography, and layout reference. Any WLC logo treatment is secondary to PX and should be settled in visual review. On desktop, place the introduction beside the language/auth panel; on mobile, stack them. Use the four logo colors sparingly and navy for readable primary buttons. Keep photography optional for this first patch; the logo, typography, palette, and composition provide a strong identity without introducing a large image or carousel. Carry the same restrained treatment into chat rather than repeating a large welcome hero there.

## Current demo and relevant source

The deployment handoff identifies [demo.enclave.free](https://demo.enclave.free) as the demo. Read-only HTTP inspection returned 200 from Caddy/nginx. Its [public settings](https://demo.enclave.free/api/settings/public) currently report:

| Setting | Observed value |
| --- | --- |
| Instance name | PX |
| Header tagline | Empowering Families of Political Prisoners |
| Logo / favicon URL | Empty |
| Primary color | blue |
| Typography | humanist |
| Surface style | gradient |
| Default theme | system |

These observations identify the current baseline; the task should not overwrite its operational configuration. No authenticated session, user records, or private configuration was accessed. The live app was checked via HTTP and public settings; a rendered live-browser visual audit remains part of implementation preparation.

- [`HomeRedirect.tsx`](../frontend/src/pages/HomeRedirect.tsx) sends unauthenticated visitors into `/login`, with separate initialized/admin/authenticated behavior. There is no standalone marketing landing page.
- [`UserOnboarding.tsx`](../frontend/src/pages/UserOnboarding.tsx) implements language selection at `/login`; a saved explicit language choice skips to `/auth`. Make this initial screen the branded welcome/entry experience without adding a new required step.
- [`UserAuth.tsx`](../frontend/src/pages/UserAuth.tsx) owns signup/login tabs, name/email fields, submission, success/error states, and data notices. Reuse its behavior and fields.
- [`OnboardingCard.tsx`](../frontend/src/components/onboarding/OnboardingCard.tsx) is the shared visual shell. It is the main place for the optional WLC entry layout; audit its admin consumers before changing its defaults.
- [`InstanceLogo.tsx`](../frontend/src/components/shared/InstanceLogo.tsx) places artwork in a 40px image inside a 64px badge; [`AppHeader.tsx`](../frontend/src/components/shared/AppHeader.tsx) uses a 20px image inside a 32px badge. A full WLC wordmark needs an aspect-ratio-preserving variant rather than these icon slots.
- [`InstanceConfigContext.tsx`](../frontend/src/context/InstanceConfigContext.tsx) already resolves instance name, logo, favicon, custom primary color, header layout/tagline, surface style, and typography from public settings, then saves config to localStorage. It also applies colors inline, which can override stylesheet rules.
- [`instance.ts`](../frontend/src/types/instance.ts) contains existing accent helpers, including readable accent text selection. [`index.css`](../frontend/src/index.css) holds shared semantic tokens. [`ThemeProvider.tsx`](../frontend/src/theme/ThemeProvider.tsx) handles stored/system/server default themes.
- [`index.html`](../frontend/index.html) restores cached branding before React starts. The overlay must handle first paint as well as later context updates.
- [`frontend/Dockerfile`](../frontend/Dockerfile) compiles a Vite production bundle and serves it with nginx. [`docker-compose.app.yml`](../docker-compose.app.yml) builds that production target. A build-time brand option must be passed into the build explicitly; setting a variable only on a running nginx container will not change compiled assets.
- [`auth.py`](../backend/app/auth.py) chooses magic-link email identity from `public_email_display_name`, then `instance_name`, then Enclave. A browser-only overlay will not change those emails.

## Implementation design

1. **Capture the baseline.** Verify the demo host's deployed commit and frontend image, save the current image under an explicit rollback tag, record active Compose overrides and public branding values, and capture desktop/mobile screenshots. Build from that deployed base unless an upgrade is separately intended.
2. **Add a single brand selector.** Proposed build option: `VITE_DEMO_BRAND=wlc`, absent by default, wired through a demo-specific Compose build override and Docker build argument. This is a proposed option, not an existing setting. Keep the WLC assets, copy, and tokens together under a small `frontend/src/branding/` module and local asset directory.
3. **Keep the overlay ephemeral.** Resolve displayed branding from the underlying instance config plus the selected demo overlay. Keep the overlay out of `saveInstanceConfig`, localStorage, backend settings, and admin form values. Apply brand styling after the existing config effects through one explicit integration point; do not fight inline colors with scattered `!important` rules. Handle title/favicon/first-paint initialization through the same selected profile.
4. **Style the entry journey.** Add a WLC variant to the shared entry shell: roomy brand/mission area and focused language or auth panel on desktop; stacked layout on mobile. Retain language choice, signup/login tabs, form validation, magic-link submission, data notices, and all existing redirects. Keep the wordmark legible on small screens.
5. **Carry the identity through.** Apply restrained shared colors, typography, wordmark, favicon, button/focus styles, and surfaces to verification, user-type/profile onboarding, pending approval, chat, and settings. Preserve established information hierarchy in chat. Admin navigation and form behavior stay intact; any inherited shared styling must remain usable and admin settings must show actual persisted values.
6. **Make theme and language behavior explicit.** Prefer a WLC light presentation for first-time visitors, without persisting a new preference; preserve explicit user theme choice and provide a checked dark adaptation. Avoid English-only replacement of existing translated controls. New short branded copy needs the app's localization/fallback conventions and RTL checks.
7. **Review and deploy only after implementation review.** Provide before/after desktop/mobile captures and the exact frontend image/activation and rollback commands for the confirmed host. Current scope is preparation for implementation; deployment has not been requested.

Confirmed copy direction: PX as the primary identity; a short demo descriptor and an invitation to access resources/support. A demo account must not read as an application for formal WLC membership. The current PX purpose can inform a supporting line, but confirm its desired prominence during visual review.

## Rollback

Primary operational rollback: select the retained pre-patch frontend image and recreate only the frontend service using the host's verified deployment invocation. Do not depend on rebuilding an old commit during an urgent rollback. Pin the WLC image too, so a later rebuild cannot silently change what is running.

Secondary rollback: unset the demo build selector, rebuild, and redeploy the frontend. Source cleanup: revert the contained patch commit(s). A branch by itself is not an operational rollback strategy.

Because the overlay never overwrites stored branding, database settings, users, conversations, or theme preferences, rollback should restore the original presentation without data restoration. Verify this with a returning browser, not only an incognito session. Ensure WLC title/favicon/inline tokens are removed when disabled. A browser already holding the old JavaScript needs a reload to receive either deployment.

Keep the existing PX magic-link email identity. No email display-name, Instance name, or SMTP sender/domain change is needed for this visual patch.

## Validation and completion criteria

- Build and typecheck with WLC both enabled and disabled; run relevant existing frontend tests for auth, header/config, routing, and localization. Add focused checks for the non-persistent overlay and default-off behavior where needed.
- Confirm a fresh visitor sees the WLC welcome/language screen; returning visitors with a saved language go directly to the branded auth page; signed-in users retain normal routing.
- Check signup/login, submitted and failed/expired magic-link states, onboarding, pending approval, chat, and admin access. During development, use local/mocked auth; sending a real test email is a separate explicit action.
- Check mobile and desktop, keyboard/focus, contrast, reduced motion, theme toggle, long translated strings, and RTL. Scope WLC font overrides so unsupported scripts retain appropriate fallbacks.
- Serve WLC assets locally; avoid runtime hotlinks to the source website. Verify missing artwork fails gracefully.
- Exercise rollback in the same browser with its cache and existing session. Original PX branding should reappear with user data, auth state, language, and prior theme choice intact.

## Scope and effort

This should be a small frontend patch centered on one brand profile, one entry-shell variant, and the two shared logo/header components, with limited initialization/build wiring. Existing settings alone provide a quick approximation, but cannot supply the desired welcome composition, exact typography, and correctly sized wordmark. A separate WLC app or broad branding settings feature would exceed the temporary demo need.

Planning estimate: one focused implementation day plus visual review and deployment/rollback verification, assuming readily usable official assets and no unrelated deployed-version differences. This is an estimate, not a measured delivery commitment.
