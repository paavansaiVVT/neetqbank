FROM python:3.12-slim
WORKDIR /app

# Install system dependencies for building C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements with verbose output to diagnose failures
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 2>&1 || \
    (echo "=== PIP INSTALL FAILED ===" && pip install --no-cache-dir -r requirements.txt --verbose && exit 1)

# Now copy the rest of the code
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
