# Browser Storage Posture

Browser localStorage, sessionStorage, HTTP cache, and browser profile data are unsupported Deployment Surfaces. Active Storage Lifecycle does not control browser-held copies after they are written to a user or operator device.

The frontend must not deliberately persist Conversation Content, message bodies, prompts, tool output, uploaded document text, provider attestation material, or sensitive Instance data in localStorage or sessionStorage. Store only lightweight routing markers and preferences with a clear product reason.

## Allowed Browser Keys

The current allowlist lives in `frontend/src/utils/browserStoragePosture.ts`.

Keys that may remain after logout:

- `enclave-theme`: UI theme preference.
- `i18nextLng`: language preference.

Keys that are cleared by `clearLogoutBrowserStorage`:

- Admin routing markers such as the Admin public key and legacy Admin session marker.
- User routing markers such as email, display name, approval state, User Type ID, pending magic-link markers, onboarding profile cache, and legacy User session marker.

These keys are not product-owned lifecycle records. They are browser-held copies and remain Deployment Surface responsibilities until cleared by logout or browser/device policy.

## Logout Behavior

User and Admin logout paths call `clearLogoutBrowserStorage` directly or through `clearUserAuth`, `clearAllAuth`, or `clearAdminAuth`. This clears known local product markers from localStorage and sessionStorage while preserving non-sensitive preferences.

## Cache-Minimizing Responses

Sensitive Admin lifecycle status responses should include:

- `Cache-Control: no-store`
- `Pragma: no-cache`

This reduces deliberate browser and proxy caching of lifecycle posture, data-class inventory, and retention evidence. It does not claim Secure Erase for browser cache or profile data.
