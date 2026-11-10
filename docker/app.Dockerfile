# App image: FastAPI + ADK agents + the built React SPA.
# Also used by the adk-web service (`adk web` dev UI on :8000).

# ---- 1. build the SPA --------------------------------------------------------
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 2. python runtime -------------------------------------------------------
FROM python:3.13-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev \
    && rm -rf /root/.cache

COPY seed ./seed
COPY --from=web /web/dist ./static

# The base image's pip is never used (uv installs everything) and carries its own
# vendored copies of urllib3/msgpack that trivy flags; drop it from the runtime image.
RUN /usr/local/bin/python3 -m pip uninstall -y --root-user-action=ignore pip \
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin nimbus \
    && chown -R nimbus /app/src
USER nimbus

ENV STATIC_DIR=/app/static \
    STARTER_TOOLS_PATH=/app/seed/starter_tools.yaml \
    HOME=/tmp
EXPOSE 8080 8000

CMD ["uvicorn", "devfest_agents.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
