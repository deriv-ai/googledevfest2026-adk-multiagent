# Build context is the repo root.
# News MCP server: FastMCP-style streamable HTTP server on :8001 (/mcp, /healthz).
# Installs only the "news" dependency group from uv.lock (mcp, feedparser, httpx).
FROM python:3.13-slim

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
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY platform/pyproject.toml platform/uv.lock ./
RUN uv sync --frozen --only-group news --no-install-project \
    && rm -rf /root/.cache

COPY platform/news_mcp ./news_mcp

# The base image's pip is never used (uv installs everything) and carries its own
# vendored copies of urllib3/msgpack that trivy flags; drop it from the runtime image.
RUN /usr/local/bin/python3 -m pip uninstall -y --root-user-action=ignore pip \
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin newsmcp
USER newsmcp

ENV NEWS_MCP_HOST=0.0.0.0 \
    NEWS_MCP_PORT=8001 \
    NEWS_POLL_SECONDS=300
EXPOSE 8001

CMD ["python", "-m", "news_mcp.server"]
