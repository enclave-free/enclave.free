# Remove the unused Accelerate checkpoint loader

Issue: [#670](https://github.com/enclave-free/enclave.free/issues/670).

## Finding and application boundary

CVE-2026-69112 reports path traversal and a special-file denial of service in Accelerate's sharded-checkpoint loader. A model-controlled `weight_map` can name a relative escape, an absolute path, or a FIFO. The report applies to the installed `accelerate 1.14.0`; there was no newer published release at investigation on 2026-09-08.

A disposable copy of the old backend reproduced both relative and absolute out-of-directory shard loads; an ordinary local checkpoint also loaded successfully. No production data or runtime container was used for that probe.

Enclave does not call either affected loader directly. Uploaded documents enter PDF/text extraction under generated upload paths, not model checkpoint selection. `store.get_embedding_model` uses the operator-selected `EMBEDDING_MODEL` only for local embeddings; default Tinfoil embeddings are remote. `ingest.extract_pdf_text` defaults to PyMuPDF; quality mode constructs Docling's PDF converter with OCR and table structure disabled. The demo was confirmed to use Tinfoil and the default fast PDF mode.

Upstream treats deliberately selected model artifacts as trusted input and declined a proposed fix. That does not make the installed loader's behavior disappear. Removing the unused dependency is preferable to adding an audit exception or maintaining a custom fork.

Primary references:

- [Upstream issue and reproduction](https://github.com/huggingface/accelerate/issues/4067)
- [Maintainer response on proposed fix](https://github.com/huggingface/accelerate/pull/4214)
- [Upstream artifact trust policy](https://github.com/huggingface/accelerate/blob/main/SECURITY.md)
- [Docling slim packaging](https://github.com/docling-project/docling/blob/main/docling/.agents/skills/docling/references/slim-packaging.md)

## Change

`docling` is a meta-package for `docling-slim[standard]`. Its broad local-model extra pulls in Accelerate. Enclave now requests `docling-slim[format-pdf]` and `docling-ibm-models` directly, preserving the existing PDF converter and layout model along with the existing Torch/Transformers/Sentence Transformers stack. Enclave does not expose Docling's CLI, training, OCR, VLM, or general format-conversion features.

The CI model dependency contract rejects an installed Accelerate module and exercises real local SentenceTransformer encoding and PDF converter construction. The CPU artifact verifier also rejects Accelerate. No advisory suppression was added and no authentication, configuration, ingest fallback, or UI behavior was changed.

## Validation commands

```bash
python -m unittest backend.tests.test_model_dependency_contract
ENCLAVE_VERIFY_QUALITY_PDF=1 python -m unittest backend.tests.test_model_dependency_contract
CONTAINER_RUNTIME=docker scripts/verify_cpu_backend_image.sh IMAGE
```

The second command downloads Docling's normal layout weights and verifies actual PDF conversion directly, without allowing Enclave's PyMuPDF fallback to hide a failure. The local embedding test generates a tiny model and tokenizer locally, so it requires no external model service. The dependency-absence check also runs in the regular backend security CI suite. Fresh image and release results are recorded after verification.

## Compatibility and rollback

The app's supported fast PDF, quality PDF and local/remote embedding paths must remain usable. Deliberately installing the removed `docling` standard extra would reintroduce the excluded dependency; rerun the artifact check after any dependency change. Existing environments must rebuild from the revised requirements, rather than only installing over the old environment and leaving orphaned packages behind.

For deployment, preserve the current backend image and SQLite backup, replace only the backend service, and verify health plus document/model checks. Keep the existing LIBERATOR frontend image and Compose overrides. Image rollback restores the prior backend without changing frontend branding or database contents; it also restores the old vulnerable dependency and is only a recovery measure.
