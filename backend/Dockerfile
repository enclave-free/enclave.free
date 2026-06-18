FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

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
