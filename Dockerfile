# ==============================================================================
# SATYAHD ZERO-TRUST POLICY ENFORCEMENT MIDDLEMAN - DOCKERFILE
# ==============================================================================
FROM python:3.12-slim

# Prevent Python from writing bytecode and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0

WORKDIR /app

# Install minimal OS dependencies for cryptography and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data and anchors directories exist
RUN mkdir -p data anchors

# Expose standard port
EXPOSE 8000

# Container health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default execution: Run FastAPI HTTP Server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
