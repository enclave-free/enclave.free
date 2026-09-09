# World Liberty Congress attribution

Requested 2026-09-09: add the exact line “by World Liberty Congress” beneath LIBERATOR. The shared temporary `PxBrand` component displays this attribution on onboarding, signup/login, and application headers. LIBERATOR remains the product name and browser title.

Only the temporary branding files `frontend/src/branding/PxBrand.tsx`, `pxDemo.ts` and `pxDemo.css` change. The fixed attribution lives alongside the product name in the branding constants. The attribution uses normal letter spacing, secondary text color with existing light/dark tokens, and smaller type (14px large brand, 12px compact header). It is accessible text within the existing home link. It does not alter saved settings or generic branding; the component is used only when the WLC build flag is enabled.

## Verification and rollback

Run the existing frontend pre-commit suite and production build. Check attribution visibility on landing and signup/login, light/dark themes and 320px mobile, including the compact application header. Keep the previous card removal intact.

Revert the commit introducing this document to remove only the attribution. For live rollback, retain the prior frontend image and recreate only `frontend` using its saved Compose override. No backend or data changes are involved. This follow-up is part of the temporary branding patch and should be removed with that patch.
