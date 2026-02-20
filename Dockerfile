FROM node:25-bookworm AS frontend-builder

WORKDIR /app/web

RUN npm install -g pnpm@10

COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS backend-builder

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/src ./src

FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS runtime

WORKDIR /app

COPY --from=backend-builder /app /app
COPY --from=frontend-builder /app/web/dist /app/frontend_dist

ARG PLATFORM_MODE=oss

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLATFORM_MODE=${PLATFORM_MODE}

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
