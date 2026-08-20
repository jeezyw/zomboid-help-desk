import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, base_map, config, disk_usage, scheduler
from .routers import (
    auth as auth_router,
    backups, base_map as base_map_router, config_history, console, ini,
    map as map_router,
    map_render, mods, players, rcon, sandbox, schedule, server, steam, todos,
)

# Paths that stay reachable without a session even when SECURE_MODE is on - the
# frontend needs /api/auth/status to know whether to show a login screen, and
# needs /api/auth/login to actually log in, before either has a valid cookie.
_AUTH_EXEMPT_PATHS = {"/api/auth/status", "/api/auth/login"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One-shot, not a background loop like the tasks below - copies the
    # maintainer-supplied pre-tiled default map into MAP_TILES_DATA/base if
    # nothing's tiled there yet, so a fresh deployment has a working Live Map
    # immediately. Awaited directly (not backgrounded) since it's normally
    # a no-op after the first startup (tiles_available() already true).
    await base_map.seed_if_needed()

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


APP = FastAPI(title="Zomboid Help Desk", version="0.4.1", lifespan=lifespan)

for router in (server.router, sandbox.router, ini.router, mods.router,
               backups.router, schedule.router, console.router, players.router,
               config_history.router, rcon.router, todos.router, auth_router.router,
               map_router.router, map_render.router, base_map_router.router, steam.router):
    APP.include_router(router)

# Must be registered before the "/{path:path}" SPA catch-all below - Starlette
# tries routes/mounts in registration order, so a request under /map-tiles/
# would otherwise be swallowed by the catch-all and served index.html instead.
# Always mounted (not conditional on live_map.is_enabled()) and the directory
# is created up front rather than checked with is_dir(), which StaticFiles
# would otherwise error on at mount time - both because Live Map can now be
# turned on/tiles can be rendered *after* this container has already started
# (the Settings tab's one-click enable, the Live Map tab's Render Map button),
# and StaticFiles reads the filesystem per-request rather than snapshotting it
# at mount time, so files that land here later are served automatically with
# no remount needed. Serving map tile images isn't itself privileged/sensitive,
# so there's no real cost to this being unconditional.
config.MAP_TILES.mkdir(parents=True, exist_ok=True)
APP.mount("/map-tiles", StaticFiles(directory=config.MAP_TILES), name="map-tiles")


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
