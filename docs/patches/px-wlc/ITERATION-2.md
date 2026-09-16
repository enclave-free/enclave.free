# LIBERATOR entry layout, iteration 2

Implemented 2026-09-16 on `temp/px-demo-wlc-visual-only`, retaining generic release 0.4.25. The original customer reference and accepted scope are summarized in [the plan](ITERATION-2-PLAN.md).

## Changes

| Before | After |
| --- | --- |
| Every `OnboardingCard` received the promotional side panel and a 640px content limit. | Only language selection and signup/login opt into `presentation="entry"`. Admin, profile, approval and verification pages use normal card widths and compact branding. |
| Cream/navy split background and decorative rounded bars. | Entry-only deep blue background with lightweight diagonal SVG artwork, white product branding, cyan rule, and a pale rounded form card. |
| “by World Liberty Congress” beneath LIBERATOR. | “by Political Prisoners Support Team”, with WLC separately credited by an official white vector logo below the branding. |
| Admin sign-in footer outside the form card. | On entry screens it sits inside the card beneath a divider. Standard card footer placement is unchanged. |
| Entry colors follow system theme. | Entry composition retains its blue/pale palette in both themes; application theme tokens still follow user preferences. |
| Large promotional panel consumes task-screen space. | Desktop admin configuration can use its declared `xl` width alongside the existing assistant. Mobile entry stacks the compact introduction, form and WLC credit. |

The source changes are confined to temporary branding files, `OnboardingCard`, and the two entry-page callers. No authentication, approval, backend, database or saved Instance Settings changes are included. The earlier sign-in protection-card removal is retained.

Screenshots: [desktop entry](screenshots/iteration-2/entry-1178.png), [320px entry](screenshots/iteration-2/entry-320.png), [admin configuration with assistant](screenshots/iteration-2/admin-config-with-assistant.png).

## Official logo provenance

Source: [World Liberty Congress, Pathway to Freedom handbook](https://worldlibertycongress.org/wp-content/uploads/2023/12/231121_WLC_Political-Prisoners_EN_A5_RZ_web.pdf), cover page. The white logo's existing vector paths were extracted with Poppler `pdftocairo -f 1 -l 1 -svg`; only the logo paths are retained with a tight SVG viewBox. No font substitution, redraw, external resources, scripts or customer-screenshot crop. This is WLC's published monochrome logo; its geometry and white fill are preserved. The four-color LIBERATOR product mark remains.

`entry-background.svg` is decorative original vector artwork built for this patch, with no image-generation or external network dependency. Both assets are served locally.

## Verification

`OnboardingCard.test.tsx` covers standard/default scope, explicit entry scope and disabled-demo behavior. `verify-browser-v2.mjs` runs against the isolated fixture (never deploy it): entry widths 320–1440px, light/dark, Arabic RTL, language persistence, email failure/retry/success, verification, pending approval, profile completion, chat controls, admin configuration with its assistant, and same-browser disabled-brand rollback. Required full frontend tests and both enabled/disabled production builds run before deployment.

Local results: all 493 tests across 83 files pass; both enabled/disabled production builds pass; all 14 browser flow checks pass, including admin configuration with its assistant. The pre-iteration merged frontend matches the deployed 0.4.25 source byte for byte.

Live verification is read-only: landing, signup/login, visible credit and locally served logo, mobile/theme layout and public admin entry. Authenticated admin layout is verified with fixture data without modifying live accounts.

## Rollback

The scope correction and visual redesign are separate commits. Revert the visual redesign to restore the previous entry appearance while retaining the fix that removes the panel from task pages. Revert the scope commit as well only if deliberately restoring the old panel behavior. For removing all temporary branding, reverse these follow-ups before the original patch commits described in README.

Before deployment, retain the currently running frontend image and save its image ID, container inventory and a Compose rollback override. Recreate only `frontend` with the saved override to restore the previous live screen. No database restore is needed. Preserve the current generic 0.4.25 backend/Sage release overrides. Exact deployment/rollback commands and screenshots live in the workspace operator record `docs/releases/wlc-iteration-2/` outside the repository.

Future customization should separate entry artwork, product/team attribution, organization credit and layout selection. This patch demonstrates those boundaries; it does not introduce a configuration system.
