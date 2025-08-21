# syntax=docker/dockerfile:1.7

# Python + uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS base
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Non-root user and persistent data dir for SQLite
RUN useradd -u 10001 -m appuser && mkdir -p /data

# Copy project metadata first for caching
COPY pyproject.toml /app/
# lockfile is recommended; if missing, remove this line or add `uv lock` locally
COPY uv.lock /app/

# Install deps into project venv (.venv)
RUN uv sync --locked

# Now app code
COPY . /app/

# Make sure runtime user can read/write app (and venv) + data
RUN chown -R appuser:appuser /app /data

USER appuser

# App listens on 1991
EXPOSE 1992
ENV DATABASE_URL="sqlite:////data/elevators.db"

# Simple health endpoint check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:1991/healthz', timeout=2).status==200 else sys.exit(1)"

# Run inside the uv-managed venv; trust proxy headers
CMD ["uv", "run", "--frozen", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "1992", "--proxy-headers", "--forwarded-allow-ips", "*"]
