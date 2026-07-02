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

Current topology:

- Enclave Apple network: `apple-enclavefree-prototype`
- Public backend route: native host gateway on `127.0.0.1:18001`
- Core bridge: native host bridge on `127.0.0.1:18002`
- Sage bridge: native host bridge on `127.0.0.1:23000`
- Generated state: `$APPLE_SIDECAR_HOME/generated/enclavefree-prototype/`
- Host gateway state: `$APPLE_SIDECAR_HOME/run/enclavefree-prototype/`

The profile intentionally avoids repo-directory bind mounts. On this Mac,
Apple `container` can hang before process startup when this stack mounts
repo-backed directories into Linux containers. The sidecar syncs the needed
SearxNG config, uploads, generated env files, and nginx config into Apple
volumes/generated files outside this repo instead.

## Commands

```sh
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh doctor
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh prepare
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh backup
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh import-docker
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh diagnose-peers
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh up-alt
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh health
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh gateway
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh reset-network
$APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh down
```

`import-docker` reuses the app images already built by Docker Compose and loads
them into Apple `container`. Use `build` only when you specifically want to test
Apple's native image builder against the Enclave Dockerfiles.

`up-alt` is intentionally separate from cutover. It starts Apple containers on
alternate ports while the Docker Compose stack can remain available on
`18000`/`5173`.

Use `gateway` first when Apple containers are already running but the alternate
backend route needs recovery. Use `reset-network` for stale vmnet state; it
stops the Apple profile containers and recreates the Apple network while
keeping Apple volumes.

For a lighter health check that skips the live LLM route:

```sh
ENCLAVE_APPLE_SKIP_LLM_HEALTH=1 $APPLE_SIDECAR_HOME/bin/enclavefree-apple.sh health
```

## Safe Diagnostics

Use `diagnose-peers` before starting an additional Enclave Apple profile or
when validating coexistence with Firecrawl and Hermes Apple sidecars. The
diagnostic gate checks Docker Compose state, Apple image imports, alternate
port availability, live sidecar health, and shared Apple network peer
reachability. It intentionally does not start profile service containers and
does not mutate Docker Compose state.

Each run writes a report under the profile run directory, for example:

```sh
$APPLE_SIDECAR_HOME/run/enclavefree-staging-guides-apple/diagnose-peers-latest.txt
```

The report should include:

```text
service_containers_started: no
docker_compose_mutated: no
result: ok
```

For guarded profiles, `up-alt` is blocked unless the planned validation shell
sets:

```sh
export ENCLAVE_APPLE_ALLOW_UNSAFE_START=1
```

Keep `ENCLAVE_APPLE_DIAGNOSE_PROFILE_NETWORK=0` for routine diagnostics. Set it
to `1` only during a planned validation window, because probing extra Apple
networks can disturb already-running Apple sidecars on this Mac.

## Caveats

- Apple volumes are separate from Docker volumes. Use `backup` before migration
  work; restore/import remains a manual follow-up until the alternate stack is
  proven healthy.
- The local profile initializes Apple volume ownership before app startup because
  Apple named volumes do not behave exactly like Docker Compose volumes.
- The preferred current image path is `import-docker`; native Apple builds are
  available but the backend dependency layer is large.
- The nginx gateway is native on the Mac, not a published Apple container. A
  published nginx container on the custom vmnet network reproduced peer-routing
  failures in this stack.
- Firecrawl's Apple profile should join `apple-enclavefree-prototype` via
  `up-shared` when it needs to coexist with Enclave. Running Firecrawl on
  Apple's `default` network remains the known failing repro for coexistence.
- Extra Enclave Apple profiles, such as the staging-guides profile, are
  guarded by default. Prefer `diagnose-peers` for routine validation and start
  them only during an intentional validation window.
- Startup depends on Tinfoil's external verifier for
  `tinfoilsh/confidential-model-router`; verifier outages can stop sidecar
  startup without implying an Enclave source or Compose regression.
- The generated files may include local runtime routing and should not be
  checked into this repo.
- Cutover is not automated yet. The first milestone is a passing alternate stack
  on `18001` and `5174`.
