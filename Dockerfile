# syntax=docker/dockerfile:1
# VidHarbor (影坞) — multi-stage image: Vue frontend build + FastAPI/uvicorn runtime.
# Multi-arch: all base images publish linux/amd64 and linux/arm64.

# ---------- Stage 1: build the frontend ----------
FROM node:22-alpine AS frontend-build
WORKDIR /build
# Deps first so source edits don't bust the npm layer
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: backend runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# ffmpeg = probe/transcode/remux; tzdata = TZ / scheduler display; ca-certificates = https
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

# Python deps from the lockfile (cached until pyproject/uv.lock change)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# App code + built frontend.
# PROJECT_ROOT inside the container is /app, so the app finds:
#   /app/backend/app, /app/frontend/dist, /app/data, /app/library, /app/config.toml (optional)
COPY backend/app ./app
COPY --from=frontend-build /build/dist /app/frontend/dist

# Default mount points for data/ and library/ (compose bind-mounts these)
RUN mkdir -p /app/data /app/library

EXPOSE 8666

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8666/api/health', timeout=3)" || exit 1

# [server] host/port from config.toml are bypassed on purpose: containers must bind 0.0.0.0.
# Open SSE streams never end on their own: without a graceful-shutdown cap uvicorn waits for
# them forever and `docker stop` ends in SIGKILL before the app's shutdown cleanup runs.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8666 --timeout-graceful-shutdown 5"]
