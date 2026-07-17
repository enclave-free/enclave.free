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

Record the image size from the runtime's image inspection output when preparing
a release. Compare it with the 9.4 GB v0.4.0 backend image baseline; the release
evidence should show a material reduction, but the verifier intentionally has no
permanent byte threshold because harmless base-image and dependency layer changes
can change the exact size.
