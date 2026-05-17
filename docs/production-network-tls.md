# Production Network and TLS Guidance

Internet-exposed deployments should terminate TLS before requests reach Enclave and should preserve enough proxy metadata for the application to apply security headers correctly.

## Recommended Posture

- Serve public frontend and backend origins over HTTPS.
- Set `INSTANCE_URL`, `FRONTEND_URL`, `API_BASE_URL`, and `ADMIN_BASE_URL` to their public `https://` origins.
- Enable `FORCE_HTTPS=true` after TLS is working.
- Keep `HSTS_MAX_AGE` at `31536000` or higher for production domains.
- Set `TRUSTED_PROXIES` to describe the TLS-terminating reverse proxy or edge provider.
- Keep `CORS_ORIGINS` explicit. Do not use `*` with credentialed auth.

## Reverse Proxy Boundary

Enclave can validate visible configuration and apply HSTS when requests arrive as HTTPS or when the reverse proxy forwards `X-Forwarded-Proto: https`. It cannot prove every Deployment's edge routing, certificate renewal, or proxy header policy from inside the container. Operators remain responsible for the reverse proxy, DNS, certificates, load balancer, and firewall rules.

## External Provider Endpoints

External Model Provider and embedding endpoints should use HTTPS in production. Internal Compose endpoints such as `http://tinfoil-proxy:8089/v1`, `http://searxng:8080`, and `http://qdrant:6333` are local service-network exceptions and should not be exposed publicly.

## Validation Evidence

`POST /admin/deployment/config/validate` reports production errors for visible public HTTP origins, missing HTTPS enforcement, weak HSTS, and external provider endpoints configured with plain HTTP. It reports a warning when `TRUSTED_PROXIES` is empty in production because the exact proxy chain is a Deployment responsibility.

