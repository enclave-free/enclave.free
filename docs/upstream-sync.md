# Upstream Sync

This prototype intentionally diverges from `enclave.free`, but it preserves upstream history so changes can still be pulled forward.

## Remotes

```bash
git remote -v
```

Expected:

```text
origin   https://github.com/enclave-free/enclave.free-prototype.git
upstream https://github.com/enclave-free/enclave.free.git
```

## Pull Latest Upstream

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

If the prototype-specific stack files conflict, preserve:

- `docker-compose.app.yml`
- `docker-compose.infra.yml`
- `gateway/nginx.conf`
- `runtime/sage` submodule pointer

## Update Sage Submodule

```bash
cd runtime/sage
git fetch origin
git checkout enclave-web-prototype
git pull --ff-only
cd ../..
git add runtime/sage
git commit -m "Update Sage submodule"
```

If Sage changes land on a different branch or commit, update the submodule pointer in this repo and keep the prototype docs in sync.
