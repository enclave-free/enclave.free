# Release Process

This repo starts semantic versioning at `0.1.0`.

The release process is intentionally small:

1. Make sure `main` is clean and up to date.
2. Update `VERSION`, `frontend/package.json`, and `frontend/package-lock.json`.
3. Update `CHANGELOG.md`.
4. Commit the release checkpoint.
5. Tag the commit with `vX.Y.Z`.
6. Push `main` and the tag.

Example:

```bash
git checkout main
git pull --ff-only origin main

# edit VERSION, frontend/package.json, frontend/package-lock.json, CHANGELOG.md
git add VERSION frontend/package.json frontend/package-lock.json CHANGELOG.md
git commit -m "Release 0.1.0"

git tag -a v0.1.0 -m "Enclave Free 0.1.0"
git push origin main
git push origin v0.1.0
```

Pushing a `vX.Y.Z` tag runs `.github/workflows/release.yml`.

The release workflow:

- checks that the tag matches `VERSION`
- checks that the frontend package version matches the tag
- builds simple release notes from recent commits
- creates a GitHub Release

For short-lived demo infrastructure changes, keep runtime-only notes outside the
repo or in deployment handoff docs. Do not commit secrets, API keys, private
Nostr keys, or one-off Droplet `.env` files.
