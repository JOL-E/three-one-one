# syntax=docker/dockerfile:1
# One image for every installation (DECISIONS #12). From the repo root:
#   docker build -t three-one-one .

# 1. The React app. Built on the build machine's own platform: the result is the
#    same static files for every platform, so this stage never runs emulated.
FROM --platform=$BUILDPLATFORM node:26-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# uv, only to install the Python packages; it doesn't end up in the image.
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

# 2. The server: Python, the packages, the code, the built app.
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/venv \
    PATH=/app/venv/bin:$PATH \
    DATA_DIR=/data

# Runs as an ordinary user. uid 1000 is the first user on most Linux hosts, so
# files in a mounted data folder belong to them.
RUN useradd --uid 1000 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data && chown app:app /data

WORKDIR /app/backend
# The packages first, the code after: a code change reuses the package layer.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY backend/ ./
COPY --from=frontend /src/frontend/dist /app/frontend/dist
# Gathers /static/ (login page, admin) with hashed names and gzipped copies, and
# gzips the built app the same way. The settings need some values to load; these
# are placeholders for this step only.
RUN SECRET_KEY=build-only BASE_URL=http://build.invalid DATA_DIR=/tmp/build \
    python manage.py collectstatic --noinput --verbosity 0 \
    && python -m whitenoise.compress --quiet /app/frontend/dist \
    && rm -rf /tmp/build

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)"]
CMD ["./docker-entrypoint.sh"]
