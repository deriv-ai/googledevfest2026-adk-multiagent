# App image: FastAPI + ADK agents + the built React SPA.
# Also used by the adk-web service (`adk web` dev UI on :8000).
# Build context is the repo root. /app mirrors the repo: platform/src, my_agent, evals.

# ---- 1. build the SPA --------------------------------------------------------
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY platform/web/package.json platform/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY platform/web/ ./
RUN npm run build

# ---- 2. python runtime -------------------------------------------------------
FROM python:3.13-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

# OpenSSL probes the CPU at startup. Some Linux VMs on Apple Silicon (seen on an M4 with
# Podman) report SVE but trap SVE instructions, so that probe kills Python with
# "Illegal instruction" (exit 132) as soon as anything loads OpenSSL (cryptography, psycopg,
# aiohttp). A fixed capability mask skips the probe. 0x1 = NEON only, which every 64-bit ARM
# CPU has; x86 builds ignore this variable.
ENV PYTHONDONTWRITEBYTECODE=1 \
    OPENSSL_armcap=0x1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app

WORKDIR /app/platform

# Dependencies first (cached layer), then the project itself.
COPY platform/pyproject.toml platform/uv.lock platform/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY platform/src ./src
RUN uv sync --frozen --no-dev \
    && rm -rf /root/.cache

COPY platform/seed /app/seed
COPY my_agent /app/my_agent
COPY --from=web /web/dist /app/static

# The base image's pip is never used (uv installs everything) and carries its own
# vendored copies of urllib3/msgpack that trivy flags; drop it from the runtime image.
RUN /usr/local/bin/python3 -m pip uninstall -y --root-user-action=ignore pip \
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin nimbus \
    && chown -R nimbus /app/platform/src /app/my_agent
USER nimbus

ENV STATIC_DIR=/app/static \
    STARTER_TOOLS_PATH=/app/seed/starter_tools.yaml \
    HOME=/tmp
EXPOSE 8080 8000

CMD ["uvicorn", "devfest_agents.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
