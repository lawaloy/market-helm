FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/app/.local/bin:${PATH}"

WORKDIR /app

# Psycopg's default Python implementation loads libpq at runtime.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip tooling
RUN python -m pip install --upgrade pip setuptools wheel

# Install runtime dependencies first to leverage layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . /app

# Install the package
RUN pip install --no-cache-dir .

# Create a non-root user and fix permissions
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app

USER app

# Optional: simple health check (fails fast if entrypoint missing)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD market-helm --help >/dev/null 2>&1 || exit 1

ENTRYPOINT ["market-helm"]
