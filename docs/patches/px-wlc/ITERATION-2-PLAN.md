# LIBERATOR visual iteration 2 — proposed, 2026-09-16

Status: approved and implemented; see [implementation and rollback record](ITERATION-2.md). Based on the customer's supplied blue landing reference and explicit request for team attribution beneath LIBERATOR with the WLC logo at the bottom.

## Intended presentation

- Retain LIBERATOR in all caps and the four-color product mark.
- Change its byline to “by Political Prisoners Support Team”, matching the supplied reference. Keep the team name in English as a brand attribution.
- Give the public entry layout a full-viewport deep blue background with subtle diagonal blue shapes. Implement the background with lightweight CSS or a decorative local SVG, not a screenshot of the interface.
- Place the product mark, byline, short cyan rule and existing instance tagline on the left. Replace the large rounded color bars with a genuine World Liberty Congress logo at the bottom of that branding area.
- Put the signup/login form in a pale, rounded card on the right. Include the magic-link helper and separated admin entry within that card. Keep labels, existing form states, and language controls.
- Use a stable blue/light-card palette for this entry composition in both system themes; keep the existing theme behavior on application pages. Scope all palette overrides to the entry layout.
- On mobile, stack a compact brand/tagline area and form. Put the WLC credit beneath the entry content, without fixed positioning, overlapping controls or a large empty hero. Allow translated copy and the longer byline to wrap naturally.
- Obtain the real WLC logo as a local SVG or transparent image before final visual approval. The current repository has only the LIBERATOR favicon; do not crop or redraw the customer screenshot as the official logo. Do not add an unexplained divider or placeholder beside the logo.

## Fix the layout scope first

Root cause: `OnboardingCard` unconditionally wraps its contents in `PxWelcome` whenever `isPxDemo` is enabled. The same card serves admin configuration, profile, approval, verification and entry pages. Its demo CSS also forces a 640px content width and removes ordinary card treatment for all those consumers.

Add an explicit presentation option to `OnboardingCard`, such as `presentation="entry"`, with the normal application card as its default. Only render `PxWelcome` and apply entry CSS when both the WLC flag and entry presentation are enabled. Do not infer this from URL substrings or hide the panel with CSS while retaining the split layout.

| Screen | Presentation |
| --- | --- |
| `/login` language selection (`UserOnboarding`) | Entry composition |
| `/auth` signup, login, error and email-sent states (`UserAuth`) | Entry composition |
| `/verify`, `/pending`, `/user-type`, `/profile` | Compact product branding and ordinary task card; no promotional panel |
| All admin setup/configuration screens, including `/admin/users` | Ordinary application layout; no promotional panel |
| Chat and other working screens | Existing compact app header |

The root URL remains its existing authentication-aware redirect. Language selection remains a separate existing step. No authentication, approval or navigation behavior change is proposed.

Restore the normal `md`/`lg`/`xl` content widths on non-entry cards; remove the inherited 640px entry restriction there. Retain appropriate compact branding without introducing a second header on screens that already have one. Verify admin configuration with the assistant panel open: removing the promotional panel should return useful space to the configuration content, not alter the assistant itself.

## Expected source changes

- `frontend/src/components/onboarding/OnboardingCard.tsx`: opt-in entry presentation; scope entry-specific structure/classes and footer placement.
- `frontend/src/pages/UserOnboarding.tsx` and `UserAuth.tsx`: explicitly select entry presentation.
- `frontend/src/branding/PxWelcome.tsx`: revised hero and separate WLC credit.
- `frontend/src/branding/PxBrand.tsx` and `pxDemo.ts`: team byline and appropriate large/compact treatments.
- `frontend/src/branding/pxDemo.css`: entry-scoped background, palette, card, responsive composition; preserve application theme tokens.
- `frontend/public/demo-branding/`: approved WLC logo, optional decorative background SVG.
- Existing patch verification fixtures and documents: route-scope checks, screenshots and rollback evidence.

## Delivery and acceptance

1. Recheck branch, deployment and upstream state before implementation; the inspected local patch is `b28eb21` on `temp/px-demo-wlc-visual-only`.
2. Commit layout-scope correction separately from the visual redesign, keeping both on the temporary patch branch.
3. Add focused regression coverage proving the entry presentation is opt-in and the demo-disabled build preserves generic behavior. Run required existing tests, localization checks and production builds.
4. Verify desktop, tablet and 320px mobile; both themes; keyboard/focus; long translations and RTL; signup/login, email-sent/error states; language selection; verification/pending/profile; admin configuration with assistant open; compact chat header.
5. Compare entry screenshots to the supplied reference. Confirm the exact team attribution, genuine WLC logo, no restored protection card, no horizontal overflow or clipped controls, and no hero on task/admin screens.
6. Record changed files, screenshots, source SHA, image identity and exact rollback commands. When implementation is authorized, build from the committed source, retain the previous frontend image, deploy only frontend, and verify publicly. Preserve backend/security fixes and stored Instance Settings.

For later configurable branding, this patch should demonstrate separately configurable entry artwork, product/team attribution, organization logo, and entry-only layout selection. Building that configuration system is outside this temporary iteration.
