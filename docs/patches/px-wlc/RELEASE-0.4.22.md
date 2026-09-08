# Backend dependency fix after the LIBERATOR rollout

Released and deployed on 2026-09-08: [v0.4.22](https://github.com/enclave-free/enclave.free/releases/tag/v0.4.22), main `8b783c8`, reviewed source `c91b9a7`. Resolves [#670](https://github.com/enclave-free/enclave.free/issues/670), the dependency scan failure recorded during the 0.4.21 visual rollout.

The generic backend now selects Docling’s PDF parser, layout model and spatial index directly. The unused Accelerate checkpoint loader is absent from both the fresh image and live runtime. No new audit exception was added. See [the security investigation](../../security/accelerate-removal.md).

## Verified results

- Old disposable backend reproduced relative and absolute out-of-directory shard loads; the new dependency absence test failed on that image as expected.
- Exact release image: all four model checks pass, including actual Docling quality PDF conversion without fallback and real local SentenceTransformer encoding.
- CPU artifact verification passes, including `ingest` and `main` imports; `pip check` reports no broken requirements; 28 nearby ingestion/store/workflow tests pass.
- Generic frontend suite: 488 tests pass. Both PR CI runs pass all jobs, including dependency and SAST scans. Independent security review has no remaining findings after the spatial-index correction.
- Live backend is healthy and `accelerate` cannot be found by Python. Public health succeeds and the provider smoke test returns `success: true`, model `glm-5-2`, response `hello`.
- All public Instance Settings match their pre-deployment values. LIBERATOR’s HTML is byte-identical to the earlier deployment. Every non-core-backend container retains its original ID and image.

Backend image: `sha256:99855d295dc42a48c5f6ee46e577400931dfa4af0818442200f4c4455a7b59b3` (`enclave-backend:0.4.22-c91b9a7`).

Frontend image remains `sha256:c81c520d9ff3fb6ee49121d81b903cacca6fc4fab4c5a73c58766bb069e60a67`, built from temporary visual source `2c54a68`. This branch includes the generic 0.4.22 fix for future builds; the live frontend did not require a rebuild.

## Rollback

The old backend image and a consistent SQLite snapshot were retained on the server before replacement. The snapshot passed SQLite `quick_check`. Exact commands and private operational paths are in the local 0.4.22 operator record outside Git.

Backend rollback recreates only `core-backend` using the retained image. It needs no database restore because this change has no schema or data migration. It also restores the removed dependency, so it is a recovery measure. The original visual-only rollback procedures remain available and do not undo this backend fix.
