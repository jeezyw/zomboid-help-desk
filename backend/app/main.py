import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from . import auth, config, disk_usage, scheduler
from .routers import (
    auth as auth_router,
    backups, config_history, console, ini, mods, players, rcon, sandbox, schedule, server, todos,
)

# Paths that stay reachable without a session even when SECURE_MODE is on - the
# frontend needs /api/auth/status to know whether to show a login screen, and
# needs /api/auth/login to actually log in, before either has a valid cookie.
_AUTH_EXEMPT_PATHS = {"/api/auth/status", "/api/auth/login"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Single-worker constraint: these run as in-process asyncio background tasks, so
    # uvicorn must run a single worker (no --workers flag) or they'd double-fire.
    restart_task = asyncio.create_task(scheduler.restart_loop())
    player_poll_task = asyncio.create_task(players.poller_loop())
    disk_usage_task = asyncio.create_task(disk_usage.refresh_loop())
    try:
        yield
    finally:
        restart_task.cancel()
        player_poll_task.cancel()
        disk_usage_task.cancel()


APP = FastAPI(title="Zomboid Help Desk", version="0.3.1", lifespan=lifespan)

for router in (server.router, sandbox.router, ini.router, mods.router,
               backups.router, schedule.router, console.router, players.router,
               config_history.router, rcon.router, todos.router, auth_router.router):
    APP.include_router(router)


@APP.middleware("http")
async def require_auth(request: Request, call_next):
    # Off entirely unless SECURE_MODE is on (config.py already fails fast at
    # startup if it's on with no password set). Only /api/* is gated - the SPA's
    # static assets (below) hold no secrets, and the SPA itself is what renders
    # the login screen, so it has to be reachable before a session exists.
    if (
        config.SECURE_MODE
        and request.url.path.startswith("/api/")
        and request.url.path not in _AUTH_EXEMPT_PATHS
    ):
        token = request.cookies.get(auth.COOKIE_NAME)
        if not auth.validate_session(token):
            return JSONResponse({"detail": "Authentication required."}, status_code=401)
    return await call_next(request)


@APP.get("/")
async def index():
    path = config.FRONTEND / "index.html"
    if not path.exists():
        return {"message": "Zomboid WebUI API is running", "docs": "/docs"}
    return FileResponse(path)


@APP.get("/{path:path}")
async def frontend(path: str):
    requested = config.FRONTEND / path
    if requested.exists() and requested.is_file():
        return FileResponse(requested)

    index = config.FRONTEND / "index.html"
    if index.exists():
        return FileResponse(index)

    raise HTTPException(404)
