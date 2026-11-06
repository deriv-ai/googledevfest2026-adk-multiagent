"""RSS feed definitions, fetching and parsing for the news MCP server.

Only free, key-less RSS endpoints are used (Google News RSS topic searches).
Everything fails soft: a network or parse error yields an empty list and a
note, never an exception that would break an MCP tool call.
"""

from __future__ import annotations

import html
import logging
import re
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx

log = logging.getLogger("news_mcp.feeds")

GOOGLE_NEWS_SEARCH = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
USER_AGENT = "nimbus-news-mcp/1.0 (+DevFest ADK demo; RSS reader)"
HTTP_TIMEOUT = httpx.Timeout(8.0, connect=4.0)

# topic -> Google News search query. Kept to broad, public market themes that
# match the demo's (synthetic) instrument universe. Google News needs quotes
# around multi-word terms combined with OR, otherwise it returns nothing.
TOPIC_QUERIES: dict[str, str] = {
    "markets": "\"stock market\" OR \"global markets\" when:2d",
    "crypto": "bitcoin OR ethereum OR crypto market when:2d",
    "forex": "forex OR currencies OR \"US dollar\" when:2d",
    "commodities": "gold OR crude oil OR commodities when:2d",
    "economy": "\"central bank\" OR inflation OR \"interest rates\" when:2d",
}
TOPICS = tuple(TOPIC_QUERIES)


def topic_url(topic: str) -> str:
    return GOOGLE_NEWS_SEARCH.format(q=quote_plus(TOPIC_QUERIES[topic]))


def search_url(query: str) -> str:
    return GOOGLE_NEWS_SEARCH.format(q=quote_plus(query))


@dataclass
class FeedState:
    topic: str
    url: str
    items: list[dict[str, Any]] = field(default_factory=list)
    last_polled: float | None = None
    last_error: str | None = None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(value: str | None, limit: int = 400) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    if not value:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", value))
    text = _WS_RE.sub(" ", text).strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def _published_iso(entry: Any) -> str:
    raw = entry.get("published") or entry.get("updated") or ""
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError):
        return raw


def _published_ts(item: dict[str, Any]) -> float:
    try:
        from datetime import datetime

        return datetime.fromisoformat(item["published"]).timestamp()
    except (KeyError, ValueError, TypeError):
        return 0.0


def parse_feed(content: bytes, default_source: str = "") -> list[dict[str, Any]]:
    """Parse RSS/Atom bytes into the contract's item shape."""
    parsed = feedparser.parse(content)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        title = clean_text(entry.get("title"), 300)
        source = ""
        src = entry.get("source")
        if isinstance(src, dict):
            source = src.get("title", "") or ""
        # Google News titles look like "Headline - Publisher": split the publisher off.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].rstrip()
        summary = clean_text(entry.get("summary"), 400)
        if summary.startswith(title):  # Google News repeats the headline as summary
            summary = summary[len(title):].strip(" -–\xa0")
        if summary == source:  # ... followed only by the publisher name
            summary = ""
        items.append({
            "title": title,
            "link": entry.get("link", ""),
            "source": source or default_source,
            "published": _published_iso(entry),
            "summary": summary,
        })
    items.sort(key=_published_ts, reverse=True)
    return items


async def fetch_feed(client: httpx.AsyncClient, url: str, default_source: str = "Google News") -> list[dict[str, Any]]:
    """GET + parse one feed. Raises httpx errors to the caller (which fails soft)."""
    resp = await client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    resp.raise_for_status()
    return parse_feed(resp.content, default_source)


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT)


def now() -> float:
    return time.time()
