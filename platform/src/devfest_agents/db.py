"""Two async connection pools.

* ``app``   (DATABASE_URL)        read/write on the ``tools`` schema, read on finance/trading
                                   (schema browser, tool registry, run log).
* ``agent`` (AGENT_DATABASE_URL)  the SELECT-only ``agent_ro`` role used to run tool SQL.

Postgres may come up after the app (compose, `make dev`), so opening retries with
backoff. Pools are opened lazily too, so `adk web` (which never runs the FastAPI
lifespan) gets working tools on the first question.
"""

from __future__ import annotations

import asyncio
import logging
import time

from psycopg_pool import AsyncConnectionPool

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


def _redact(url: str) -> str:
    """postgresql://user:secret@host/db -> postgresql://user:***@host/db"""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


class Database:
    def __init__(self, app_url: str, agent_url: str, *, max_size: int = 8):
        self.app_url = app_url
        self.agent_url = agent_url
        self.app_pool = AsyncConnectionPool(
            app_url, open=False, min_size=1, max_size=max_size, kwargs={"autocommit": True}, name="app"
        )
        self.agent_pool = AsyncConnectionPool(
            agent_url, open=False, min_size=1, max_size=max_size, kwargs={"autocommit": True}, name="agent"
        )
        self._opened = False
        self._lock = asyncio.Lock()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "Database":
        settings = settings or get_settings()
        return cls(settings.database_url, settings.agent_database_url)

    async def open(self, *, attempts: int = 1, first_delay: float = 1.0, max_delay: float = 8.0,
                   timeout: float = 5.0) -> bool:
        """Open both pools. Returns True when connections were established.

        On failure the pools stay open and psycopg_pool keeps reconnecting in the
        background, so a DB that starts late is picked up without a restart.
        """
        async with self._lock:
            if not self._opened:
                await self.app_pool.open(wait=False)
                await self.agent_pool.open(wait=False)
                self._opened = True
        delay = first_delay
        for attempt in range(1, attempts + 1):
            try:
                await self.app_pool.wait(timeout=timeout)
                await self.agent_pool.wait(timeout=timeout)
                logger.info("Database connected (%s)", _redact(self.app_url))
                return True
            except Exception as exc:  # noqa: BLE001 - PoolTimeout or connection errors
                if attempt == attempts:
                    logger.warning("Database not reachable after %d attempt(s): %s", attempts, type(exc).__name__)
                    return False
                logger.info("Waiting for database (attempt %d/%d)...", attempt, attempts)
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
        return False

    async def ensure_open(self) -> None:
        if not self._opened:
            await self.open(attempts=1, timeout=3.0)

    async def close(self) -> None:
        if self._opened:
            await self.app_pool.close()
            await self.agent_pool.close()
            self._opened = False

    async def ping(self) -> bool:
        try:
            await self.ensure_open()
            async with self.app_pool.connection(timeout=2.0) as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False


_database: Database | None = None
_database_loop: asyncio.AbstractEventLoop | None = None


def get_database() -> Database:
    """Process-wide Database bound to the running event loop."""
    global _database, _database_loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _database is None or (loop is not None and _database_loop is not None and loop is not _database_loop):
        _database = Database.from_settings()
        _database_loop = loop
    elif _database_loop is None:
        _database_loop = loop
    return _database


def set_database(db: Database | None) -> None:
    global _database, _database_loop
    _database = db
    try:
        _database_loop = asyncio.get_running_loop() if db is not None else None
    except RuntimeError:
        _database_loop = None


def monotonic_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
