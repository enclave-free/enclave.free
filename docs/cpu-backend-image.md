# CPU-Only Core Backend Image

The supported core backend image targets CPU Single-Instance Deployments. Its
Torch and torchvision wheels are pinned in `backend/requirements-cpu.txt` and
come from PyTorch's official CPU wheel index. `backend/requirements.txt` keeps
the application's pinned Torch capability so the general dependency install
accepts the preinstalled CPU wheel instead of replacing it.

Build and verify the artifact natively with Apple Containers:

```bash
container build --tag enclavefree-core-backend:cpu backend
scripts/verify_cpu_backend_image.sh enclavefree-core-backend:cpu
```

The verifier executes inside the built image. It fails unless Torch 2.8.0 and
torchvision 0.23.0 are installed, Torch reports no CUDA runtime or availability,
no CUDA/NVIDIA runtime distributions are present, and torchvision,
sentence-transformers, transformers, Docling, and the backend application all
import successfully.

Docker-based CI or deployment hosts can run the same artifact check explicitly:

```bash
CONTAINER_RUNTIME=docker scripts/verify_cpu_backend_image.sh enclavefree-core-backend:cpu
```

Record like-for-like Apple image sizes with `container image list --format json`
and compare the `variants[].size` values. The implementation run compared the
prior Apple image `apple/enclavefree-core-backend:dev`
(`e84b6c0f5a70b564b388c851b4bf1b933bbf658a0b80295016c7ed868078dac0`,
3,300,590,209 bytes) with `enclavefree-core-backend:cpu`
(`a59fd5f8bebddbe86cf998a685f75451de7049c99fe41b7d67a9783435de123f`,
526,230,016 bytes), an 84.1% reduction using the same Apple Containers field.
The separately observed 9.4 GB v0.4.0 release image is useful deployment context,
not the denominator for that percentage. The verifier intentionally has no
permanent byte threshold because harmless base-image and dependency-layer changes
can change the exact size.
