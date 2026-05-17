# Production Configuration Guardrails

Set `ENCLAVE_ENV=production` for internet-exposed or production-like deployments. Production mode makes validation fail hard for development shortcuts and weak secret posture while still reporting Deployment-dependent checks as actionable warnings.

## Required Production Posture

- `SECRET_KEY` must be strong, stable, and supplied by a deployment secret manager.
- `MOCK_EMAIL=false`; configure real SMTP for magic links.
- `SIMULATE_USER_AUTH=false`.
- `SIMULATE_ADMIN_AUTH=false`.
- `PROTECTED_INFERENCE_DEVELOPMENT_BYPASS=false`.
- `SESSION_COOKIE_SECURE` must not be explicitly disabled.
- `BACKEND_RELOAD=false`; do not use development reload loops in production.
- `RATE_LIMIT_BACKEND=valkey` and `RATE_LIMIT_VALKEY_URL` configured.
- Public `INSTANCE_URL`, `FRONTEND_URL`, `API_BASE_URL`, and `ADMIN_BASE_URL` should use HTTPS.
- External Model Provider and embedding endpoints should use HTTPS, except internal Compose service-network endpoints.

## Network Exposure

Compose defaults bind the public gateway and frontend to `127.0.0.1`; internal services use Docker `expose` rather than broad host port publishing. If a deployment changes this, record the exposure review and put public entrypoints behind TLS, firewalling, and a reverse proxy.

`POST /admin/deployment/config/validate` reports a warning when the deployment advertises a broad published host such as `0.0.0.0`, because the application cannot prove the firewall, proxy, or cloud edge policy from inside the container.

