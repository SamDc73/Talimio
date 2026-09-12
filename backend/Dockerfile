FROM ghcr.io/astral-sh/uv:python3.14-trixie

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# --no-dev matches the sync above; without it `uv run` re-syncs the dev group
# and downloads ~23MB of tooling on every cold start.
CMD ["uv", "run", "--no-dev", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--loop", "uvloop", "--http", "httptools", "--proxy-headers", "--forwarded-allow-ips", "*"]
