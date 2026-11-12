"""FastAPI application.

    uvicorn devfest_agents.api.main:app --port 8080

The app starts and serves tools/schema even without an LLM key; chat then
answers with an SSE `error` event explaining what to add to .env.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..runtime import AgentRuntime
from ..schema_introspect import SchemaService
from ..seed import seed_tools
from ..services import Services, get_services, set_services
from . import routes_chat, routes_graph, routes_health, routes_schema, routes_tools

logger = logging.getLogger(__name__)


async def _seed_when_db_ready(services: Services) -> None:
    """Wait for Postgres (it may start after us), then seed the starter tools."""
    db = services.database()
    delay = 1.0
    while True:
        if await db.open(attempts=1, timeout=5.0):
            break
        await asyncio.sleep(delay)
        delay = min(delay * 2, 10.0)
    try:
        await seed_tools(services.repository(), services.settings.resolved_starter_tools_path)
    except Exception as exc:  # noqa: BLE001 - never take the app down for the seed
        logger.error("Seeding starter tools failed: %s", exc)


def create_app(*, services: Services | None = None, runtime: AgentRuntime | None = None,
               schema: SchemaService | None = None, connect_db: bool = True) -> FastAPI:
    services = services or get_services()
    settings = services.settings
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        set_services(services)
        background = None
        if connect_db:
            background = asyncio.create_task(_seed_when_db_ready(services))
        logger.info("Nimbus API ready (llm_key=%s, mode=%s, model=%s)",
                    "configured" if settings.llm_key_configured else "missing", settings.llm_mode,
                    settings.effective_agent_model)
        try:
            yield
        finally:
            if background is not None and not background.done():
                background.cancel()
                with contextlib.suppress(BaseException):
                    await background
            if connect_db:
                with contextlib.suppress(Exception):
                    await services.database().close()

    app = FastAPI(title="Nimbus Markets multi-agent demo", version="0.1.0", lifespan=lifespan)
    app.state.services = services
    app.state.runtime = runtime or AgentRuntime(settings=settings)
    app.state.schema = schema or SchemaService(services.database)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()) if x not in ("body",))
            errors.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
        return JSONResponse({"detail": "Invalid request: " + "; ".join(errors), "errors": errors}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(psycopg.Error)
    async def _db_error(request: Request, exc: psycopg.Error):
        logger.warning("Database error on %s: %s", request.url.path, exc)
        return JSONResponse({"detail": f"Database error: {type(exc).__name__}"}, status_code=503)

    @app.exception_handler(PoolTimeout)
    async def _pool_timeout(request: Request, exc: PoolTimeout):
        return JSONResponse({"detail": "Database unavailable (is the db container up?)"}, status_code=503)

    for module in (routes_health, routes_graph, routes_chat, routes_tools, routes_schema):
        app.include_router(module.router)

    _mount_spa(app, settings.resolved_static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path | None) -> None:
    if static_dir is None or not (static_dir / "index.html").exists():
        logger.info("No built SPA found (STATIC_DIR); serving the API only")
        return
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    index = static_dir / "index.html"
    root = static_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def _build_default_app() -> FastAPI:
    return create_app()


app = _build_default_app()
