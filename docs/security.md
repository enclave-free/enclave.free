# Security

This document describes Enclave's current security model and the minimum hardening steps for an internet-exposed deployment.

For a more exhaustive engineering checklist, see `docs/security-data-protection-checklist.md`.

## Security Model (Current)

- Passwordless auth:
  - Admin auth: Nostr NIP-07 signed events.
  - User auth: email magic links.
- Session handling:
  - Signed, time-limited session tokens.
  - Browser auth uses `httpOnly` cookies plus CSRF protection for unsafe requests.
  - CLI/non-browser clients can use `Authorization: Bearer <token>`.
  - See `docs/sessions.md`.
- Data protection:
  - User PII fields are encrypted at rest in SQLite once an admin has initialized the instance. Before initialization, user creation is blocked (the instance must be initialized first). The initialization step generates the encryption key.
  - Deployment config secrets are masked in reads and encrypted at rest.
  - See `docs/sqlite-encryption.md`.
- Baseline web protections:
  - Explicit CORS allowlist suitable for credentialed cookies.
  - CSRF enforcement for cookie-authenticated unsafe requests.
  - Security headers (CSP for API responses, HSTS when HTTPS is detected, X-Frame-Options, etc.).

## Production Hardening (Minimum)

### 1. Lock Down Secrets and Keys

- Set a strong, stable `SECRET_KEY` via a secret manager.
  - Rotating `SECRET_KEY` invalidates existing sessions.
- Protect admin private keys.
  - Read `docs/admin-key-recovery-runbook.md`.

### 2. Disable Dev Paths

- Ensure these are false in production:
  - `MOCK_EMAIL=false`

### 3. Enforce TLS End-to-End

- Serve the frontend and backend over HTTPS.
- Put the backend behind a reverse proxy that:
  - Terminates TLS.
  - Sets `X-Forwarded-Proto: https`.
  - Enforces HSTS (or rely on backend HSTS when HTTPS is detected).
- Configure trusted proxies if applicable (see deployment config docs).

### 4. Configure Origins for Cookie Auth

Credentialed cookies require explicit origins.

- Set `FRONTEND_URL` to your public frontend origin.
- Set `CORS_ALLOW_ORIGINS` (or `CORS_ORIGINS`) to a comma-separated list of explicit `scheme://host[:port]` origins.
- Do not use `*` — the backend silently drops it from the allowlist because credentialed cookies require explicit origins (per the Fetch spec). No error is raised; `*` entries simply have no effect.

### 5. Keep Cookies Secure

Recommended:

- `SESSION_COOKIE_SECURE=true` (or enable production mode via `ENCLAVE_ENV=production`)
- `SESSION_COOKIE_SAMESITE=lax` (or `none` only when you understand the cross-site implications)
- Set `SESSION_COOKIE_DOMAIN` only if you need cross-subdomain cookies.

### 6. Limit Network Exposure

- Ensure only necessary ports are published externally.
- Keep Qdrant and any internal services private where possible.

### 7. Review Data Flows and Retention

- Uploaded files in `uploads/` are runtime artifacts; treat them as sensitive.
- Review the Active Storage Lifecycle in Data Lifecycle Status and `docs/lifecycle-confidentiality-runbook.md`.
- Use an external Retention Scheduler for scheduled execution; the product records Retention Run Records and Retention Scheduler Observation but does not embed its own cron.
- Scheduled retention can clean stale Sage Session Memory, eligible User Memory, failed/superseded/abandoned/orphaned uploaded Document artifacts, and compactable Audit Log detail.
- The milestone does not schedule active User Profiles, current Document Library records, current Retrieval Index entries, or Inference Verification Records for deletion. Inference Verification Records remain indefinitely retained until a separate evidence-retention policy exists.
- Keep unsupported Deployment Surfaces visible in operator documentation: logs, WAL files, backups, snapshots, browser caches, copied exports, and provider traces remain outside product lifecycle control.
- Python in-memory runtime state can still exist outside the public Sage query path, such as rate-limit buckets and in-progress ingest chunks.

## Operational References

- `docs/security-data-protection-checklist.md` - status and remediation tracker.
- `docs/admin-deployment-config.md` - deployment-time security settings and validation.
- `docs/sessions.md` - cookie/bearer auth sessions and CSRF model.
