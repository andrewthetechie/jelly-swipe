# Builder stage
FROM python:3.13-slim as builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies from lockfile (layer caching optimization)
RUN uv sync --frozen --no-install-project

# Copy source code
COPY . .

# Install jellyswipe package
RUN uv sync --frozen

# Final stage
FROM python:3.13-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy package data (templates/static)
COPY --from=builder /app/jellyswipe /app/jellyswipe

# Create data directory for persistent storage
RUN mkdir -p /app/data

EXPOSE 5005

CMD ["/app/.venv/bin/uvicorn", "jellyswipe:app", "--host", "0.0.0.0", "--port", "5005"]
