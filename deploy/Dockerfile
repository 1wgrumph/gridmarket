# syntax=docker/dockerfile:1
# Build context is the repository root: docker build -f deploy/Dockerfile .

FROM node:22-slim AS dashboard
WORKDIR /src/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
# Empty hides every God's Eye link and the embedded live grid.
ARG VITE_GODSEYE_URL=
ENV VITE_GODSEYE_URL=$VITE_GODSEYE_URL
RUN npm run build

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/backend \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRIDMARKET_DB=/data/gridmarket.db
WORKDIR /app
# Runtime dependencies only: no dev group, no ml or quant extra.
COPY backend/pyproject.toml backend/uv.lock backend/
RUN uv sync --project backend --frozen --no-dev --no-install-project
# main.py resolves docs/ and dashboard/dist relative to /app (parents[2] of the package).
COPY backend/gridmarket_server backend/gridmarket_server
# The bots loop imports the SDK; PYTHONPATH=/app/backend makes it `import gridmarket`.
COPY sdk/python/gridmarket backend/gridmarket
COPY docs/ docs/
COPY --from=dashboard /src/dashboard/dist dashboard/dist
RUN groupadd --gid 10001 gridmarket \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin gridmarket \
    && mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/market/status', timeout=2); import gridmarket_server.health as h; assert h.db_writable(), 'database is not writable'"]
CMD ["uvicorn", "gridmarket_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
