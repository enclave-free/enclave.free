FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency contracts first for caching
COPY requirements.txt requirements-cpu.txt ./
COPY --chmod=755 scripts/install_dependencies.sh /usr/local/bin/install_backend_dependencies

# Install the pinned CPU stack before the general dependency graph so pip keeps
# the official PyTorch CPU wheels instead of resolving CUDA-enabled wheels.
RUN /usr/local/bin/install_backend_dependencies /app

COPY scripts/verify_cpu_runtime.py /usr/local/bin/verify_cpu_runtime.py

RUN adduser --system --group --home /home/enclave enclave \
    && mkdir -p /data /uploads /home/enclave/.cache/huggingface \
    && chown -R enclave:enclave /app /data /uploads /home/enclave

# Copy application code
COPY --chown=enclave:enclave app/ .

USER enclave

# Expose port
EXPOSE 18000

# Run the application with seed on startup
CMD ["sh", "-c", "python seed.py && uvicorn main:app --host 0.0.0.0 --port 18000 --reload"]
