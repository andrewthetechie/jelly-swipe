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

# Alembic reads project-root alembic.ini (see jellyswipe/migrations._alembic_config)
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/alembic /app/alembic

# Install gosu for privilege drop in entrypoint
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Create jellyswipe user/group. Default IDs are Unraid's `nobody:users`
# (PUID=99, PGID=100); the entrypoint can rewrite them at runtime.
# Note: GID 100 is already taken by the `users` group in Debian slim, so we
# let groupadd auto-assign a system GID. The entrypoint uses groupmod -o at
# runtime to set the desired PGID (allowing non-unique GIDs).
RUN groupadd --system jellyswipe \
    && useradd --system --uid 99 --gid jellyswipe \
        --no-create-home --shell /usr/sbin/nologin jellyswipe \
    && mkdir -p /app/data \
    && chown -R jellyswipe:jellyswipe /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5005/healthz', timeout=3).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 5005

CMD ["/app/.venv/bin/python", "-m", "jellyswipe.bootstrap"]
