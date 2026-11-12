"""News MCP server for the Nimbus Markets demo.

A small MCP server (mcp>=2: ``MCPServer``, the successor of ``FastMCP``) served
over streamable HTTP at ``http://0.0.0.0:8001/mcp``. A background "news
listener" polls free Google News RSS topic searches every NEWS_POLL_SECONDS
into an in-memory rolling buffer; tools read from that buffer (and
``search_news`` also queries Google News RSS live).

Tools (names/signatures are part of docs/CONTRACT.md):
  latest_headlines(topic="markets", limit=10)
  search_news(query, limit=10)
  list_feeds()

Fail soft: when the internet is unreachable the tools return a single
``{"note": "..."}`` element instead of raising, so the agent can tell the user
that live news is unavailable.

Run locally:  python -m news_mcp.server     (or python news_mcp/server.py)
Health check: GET /healthz
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time
from typing import Any

import uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # pragma: no cover - mcp 1.x fallback
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]

if __package__ in (None, ""):  # allow `python news_mcp/server.py`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from news_mcp import feeds  # type: ignore[no-redef]
else:
    from . import feeds

log = logging.getLogger("news_mcp")

HOST = os.environ.get("NEWS_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("NEWS_MCP_PORT", "8001"))
POLL_SECONDS = max(30, int(os.environ.get("NEWS_POLL_SECONDS", "300")))
BUFFER_SIZE = int(os.environ.get("NEWS_BUFFER_SIZE", "100"))
SEARCH_CACHE_SECONDS = 300
MAX_LIMIT = 30

STATE: dict[str, feeds.FeedState] = {
    t: feeds.FeedState(topic=t, url=feeds.topic_url(t)) for t in feeds.TOPICS
}
_search_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

OFFLINE_NOTE = (
    "Live news is unavailable right now (the news server could not reach its RSS feeds - "
    "the machine may be offline). Answer without news, and say so."
)

mcp = _Server(
    name="nimbus-news",
    instructions=(
        "Live market news from free public RSS feeds (Google News). Use latest_headlines for a topic "
        "overview, search_news for a specific instrument/event (e.g. 'Bitcoin', 'gold price', 'US dollar'), "
        "and list_feeds to see what is cached. Headlines are real-world news; Nimbus Markets' own numbers "
        "are synthetic and come from the finance/trading agents."
    ),
)


def _clamp(limit: int) -> int:
    try:
        return max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        return 10


def _merge(state: feeds.FeedState, fresh: list[dict[str, Any]]) -> None:
    """Merge newest items into the rolling buffer, de-duplicated by link/title."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in fresh + state.items:
        key = item.get("link") or item.get("title", "")
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=feeds._published_ts, reverse=True)
    state.items = merged[:BUFFER_SIZE]


async def poll_topic(client, state: feeds.FeedState) -> None:
    try:
        items = await feeds.fetch_feed(client, state.url)
        _merge(state, items)
        state.last_error = None
        log.info("polled %s: %d items (%d cached)", state.topic, len(items), len(state.items))
    except Exception as exc:  # noqa: BLE001 - fail soft on anything network/parse related
        state.last_error = f"{type(exc).__name__}: {exc}"[:200]
        log.warning("poll %s failed: %s", state.topic, state.last_error)
    finally:
        state.last_polled = time.time()


async def poll_all() -> None:
    async with feeds.make_client() as client:
        await asyncio.gather(*(poll_topic(client, s) for s in STATE.values()))


async def news_listener() -> None:
    """Background task: poll every topic feed every POLL_SECONDS forever."""
    log.info("news listener started: %d feeds every %ss", len(STATE), POLL_SECONDS)
    while True:
        await poll_all()
        await asyncio.sleep(POLL_SECONDS)


# --------------------------------------------------------------------------- #
# MCP tools
# --------------------------------------------------------------------------- #
@mcp.tool()
async def latest_headlines(topic: str = "markets", limit: int = 10) -> list[dict[str, Any]]:
    """Latest real-world news headlines for a market topic, newest first.

    topic: one of markets, crypto, forex, commodities, economy (default markets).
    limit: number of headlines, 1-30 (default 10).
    Returns a list of {title, link, source, published (ISO 8601), summary}.
    If live news is unavailable, returns a single {"note": ...} item instead.
    """
    topic = (topic or "markets").strip().lower()
    if topic not in STATE:
        return [{"note": f"Unknown topic '{topic}'. Use one of: {', '.join(feeds.TOPICS)}."}]
    state = STATE[topic]
    if not state.items:  # nothing cached yet (startup or offline): try once now
        async with feeds.make_client() as client:
            await poll_topic(client, state)
    if not state.items:
        return [{"note": OFFLINE_NOTE, "error": state.last_error}]
    return state.items[: _clamp(limit)]


@mcp.tool()
async def search_news(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search real-world news for a keyword or phrase (Google News RSS), newest first.

    query: e.g. "Bitcoin", "gold price", "US Tech 100", "ECB interest rates".
    limit: number of results, 1-30 (default 10).
    Returns a list of {title, link, source, published (ISO 8601), summary}.
    Falls back to the cached topic headlines when the live search fails; if nothing
    is available returns a single {"note": ...} item.
    """
    query = (query or "").strip()
    if not query:
        return [{"note": "Empty query. Pass a keyword such as 'Bitcoin' or 'oil price'."}]
    limit = _clamp(limit)
    key = query.lower()
    cached = _search_cache.get(key)
    if cached and time.time() - cached[0] < SEARCH_CACHE_SECONDS:
        return cached[1][:limit]
    try:
        async with feeds.make_client() as client:
            items = await feeds.fetch_feed(client, feeds.search_url(query))
        _search_cache[key] = (time.time(), items)
        if len(_search_cache) > 200:
            oldest = min(_search_cache, key=lambda k: _search_cache[k][0])
            _search_cache.pop(oldest, None)
        if items:
            return items[:limit]
    except Exception as exc:  # noqa: BLE001
        log.warning("search %r failed: %s", query, exc)
    # fallback: keyword match over the rolling buffer
    words = [w for w in key.split() if len(w) > 2] or [key]
    hits = [
        item for s in STATE.values() for item in s.items
        if any(w in (item["title"] + " " + item["summary"]).lower() for w in words)
    ]
    if hits:
        return hits[:limit]
    return [{"note": OFFLINE_NOTE if not any(s.items for s in STATE.values())
             else f"No recent news found for '{query}'."}]


@mcp.tool()
async def list_feeds() -> list[dict[str, Any]]:
    """List the RSS feeds the background news listener polls.

    Returns a list of {topic, url, items_cached, last_polled (ISO 8601 or null), last_error}.
    """
    out = []
    for s in STATE.values():
        out.append({
            "topic": s.topic,
            "url": s.url,
            "items_cached": len(s.items),
            "last_polled": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s.last_polled))
                            if s.last_polled else None),
            "last_error": s.last_error,
        })
    return out


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request: Request) -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "feeds": len(STATE),
        "items_cached": sum(len(s.items) for s in STATE.values()),
        "poll_seconds": POLL_SECONDS,
    })


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
def build_app():
    """Starlette app: MCP at /mcp + /healthz, with the news listener in its lifespan."""
    app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, host=HOST)
    inner_lifespan = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(a):
        task = asyncio.create_task(news_listener(), name="news-listener")
        try:
            async with inner_lifespan(a):
                yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app.router.lifespan_context = lifespan
    return _NoGetStream(app)


class _NoGetStream:
    """ASGI wrapper: answer a bare GET /mcp with 405 instead of an endless SSE stream.

    The server is stateless, so there is no standalone server->client stream to offer
    (MCP clients only open it when they hold a session id). Returning 405 is what the
    spec prescribes and makes simple "is it up?" probes (GET /mcp) return instantly.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "GET" and scope["path"].rstrip("/") == "/mcp":
            await JSONResponse({"detail": "Use POST (MCP streamable HTTP, stateless). Health: GET /healthz"},
                               status_code=405, headers={"Allow": "POST"})(scope, receive, send)
            return
        await self.app(scope, receive, send)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(build_app(), host=HOST, port=PORT, log_level="info", proxy_headers=True)


if __name__ == "__main__":
    main()
