# Apple Container Sidecar Profile

Status: experimental local migration path.

This repo still treats Docker Compose as the canonical local runtime. The Apple
`container` profile is a side-by-side adapter for migration testing only; it does
not change application source, Dockerfiles, or the Compose files.

## Constraint

The Enclave Free Compose stack relies on Docker's service-name DNS. App and
gateway config refer to names such as `postgres`, `qdrant`, `searxng`,
`valkey`, `tinfoil-proxy`, `core-backend`, and `sage`. Apple `container` does
not provide Compose-compatible service-name DNS, so the local Apple profile
generates env files and an nginx config with inspected Apple container IPs and a
small gateway bridge for the backend-to-Sage edge.

## Local Profile

The local operator script lives outside this repo under `$APPLE_SIDECAR_HOME`:

```sh
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh
```

Generated files live outside this repo:

```sh
$APPLE_SIDECAR_HOME/generated/enclavefree-prototype/
```

Set the local sidecar home before running commands:

```sh
export APPLE_SIDECAR_HOME=/path/to/apple-container-migration
export ENCLAVE_APPLE_MIGRATION_DIR="$APPLE_SIDECAR_HOME"
export ENCLAVE_FREE_REPO="$(pwd)"
```

Alternate local ports:

- Backend gateway: `http://127.0.0.1:18001`
- Frontend: `http://127.0.0.1:5174`

## Commands

```sh
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh doctor
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh prepare
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh backup
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh import-docker
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh up-alt
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh health
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh down
```

`import-docker` reuses the app images already built by Docker Compose and loads
them into Apple `container`. Use `build` only when you specifically want to test
Apple's native image builder against the Enclave Dockerfiles.

`up-alt` is intentionally separate from cutover. It starts Apple containers on
alternate ports while the Docker Compose stack can remain available on
`18000`/`5173`.

## Caveats

- Apple volumes are separate from Docker volumes. Use `backup` before migration
  work; restore/import remains a manual follow-up until the alternate stack is
  proven healthy.
- The local profile initializes Apple volume ownership before app startup because
  Apple named volumes do not behave exactly like Docker Compose volumes.
- The preferred current image path is `import-docker`; native Apple builds are
  available but the backend dependency layer is large.
- The generated files may include local runtime routing and should not be
  checked into this repo.
- Cutover is not automated yet. The first milestone is a passing alternate stack
  on `18001` and `5174`.
