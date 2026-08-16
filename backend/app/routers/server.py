import logging
import shutil

import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config, disk_usage, docker_control, restart_manager, server_files
from ..db import audit, get_setting, set_setting, utcnow
from ..profiles import SELECTED_PROFILE_KEY

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/health")
async def health():
    return {"ok": True, "time": utcnow()}


@router.get("/api/server")
async def server():
    # Deliberately doesn't check Docker container status here - that's a separate
    # concern from these host metrics (psutil, local to this container) and isn't
    # needed for this app's purpose.
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(config.DATA) if config.DATA.exists() else None
    data_size = disk_usage.get_cached() or {}

    # Best-effort: the game server's own CPU/memory, via `docker stats` - only
    # attempted when Docker control is enabled (config.DOCKER_CONTROL_ENABLED),
    # since without the socket mounted this would just fail every single poll. A
    # failure here (docker CLI missing, container not running) must NOT break the
    # rest of this response - host metrics above are independently useful and
    # always shown regardless. cpu_percent_raw is Docker's "percent of one core"
    # figure; dividing by cpu_count normalizes it onto the same 0-100-ish scale as
    # the host cpu_percent above so the two are directly comparable at a glance.
    process = {"cpu_percent": None, "memory_bytes": None}
    if config.DOCKER_CONTROL_ENABLED:
        try:
            raw = await docker_control.stats()
            cpu_count = psutil.cpu_count() or 1
            process = {
                "cpu_percent": raw["cpu_percent_raw"] / cpu_count,
                "memory_bytes": raw["memory_bytes"],
            }
        except Exception as e:
            # Silent to the API response by design (see comment above), but logged
            # so it's actually diagnosable via `docker logs zomboid-webui` instead
            # of just silently showing no sub-line with no clue why.
            logger.warning("Could not fetch game server process stats: %s", e)

    return {
        "host": {
            "cpu_percent": psutil.cpu_percent(interval=0.05),
            "memory": {
                "used": vm.used,
                "total": vm.total,
                "percent": vm.percent,
            },
            "disk": {
                # Host filesystem stats (shutil.disk_usage reports the whole
                # filesystem a bind-mounted path resolves to, NOT that directory's
                # own size - e.g. the host's overall disk usage, not "how big is my
                # Zomboid data"). Kept for host capacity awareness.
                "used": disk.used if disk else 0,
                "total": disk.total if disk else 0,
                # Actual size of the managed directories - refreshed periodically in
                # the background (see disk_usage.py), not computed per-request.
                "zomboid_data_bytes": data_size.get("zomboid_data_bytes"),
                "workshop_bytes": data_size.get("workshop_bytes"),
                "data_size_computed_at": data_size.get("computed_at"),
            },
        },
        "process": process,
        "docker_control_enabled": config.DOCKER_CONTROL_ENABLED,
    }


class RestartWarningBody(BaseModel):
    minutes: int


# These specific routes MUST be registered before the "/api/server/{action}"
# catch-all below - Starlette matches routes in registration order, so a POST to
# e.g. "restart-warning" or "pending/cancel" would otherwise be swallowed by
# server_action("restart-warning"/"pending/cancel") and 400 as an unsupported action.
@router.get("/api/server/restart-warning")
async def get_restart_warning():
    return {"minutes": restart_manager.get_warning_minutes()}


@router.post("/api/server/restart-warning")
async def set_restart_warning(body: RestartWarningBody):
    return {"minutes": restart_manager.set_warning_minutes(body.minutes)}


@router.get("/api/server/pending")
async def get_pending_action():
    return {"pending": restart_manager.get_pending()}


@router.post("/api/server/pending/cancel")
async def cancel_pending_action():
    return {"ok": restart_manager.cancel_pending()}


class ServerActionBody(BaseModel):
    # Per-click override of the restart-warning delay for THIS action only (e.g. the
    # dropdown next to the Stop/Restart buttons) - omit to use the persisted default
    # (see restart_manager.get_warning_minutes / the Scheduled Restarts panel).
    warning_minutes: int | None = None


@router.post("/api/server/{action}")
async def server_action(action: str, body: ServerActionBody | None = None):
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(400, "Unsupported action")

    if action == "start":
        if not config.DOCKER_CONTROL_ENABLED:
            raise HTTPException(
                400,
                "Docker control is disabled. Set DOCKER_CONTROL_ENABLED=true and "
                "mount /var/run/docker.sock in docker-compose.yml to enable "
                "Start/Stop/Restart.",
            )
        # No RCON warning applies here - nothing to warn, no one is connected to a
        # stopped server. RCON also can't start a stopped process in the first
        # place: it's a TCP connection to the running game, and there's nothing to
        # connect to until the container (and the process inside it) is already up.
        result = await docker_control.start()
        audit("server.start")
        return result

    warning_minutes = body.warning_minutes if body else None
    return restart_manager.request_action(action, reason="manual", warning_minutes=warning_minutes)


@router.get("/api/server/profiles")
async def server_profiles():
    profiles = server_files.discover_profiles(config.DATA)
    selected = get_setting(SELECTED_PROFILE_KEY)
    if selected and not any(p["name"] == selected for p in profiles):
        selected = None
    return {"profiles": profiles, "selected": selected}


class ProfileSelect(BaseModel):
    name: str


@router.post("/api/server/profiles/select")
async def select_server_profile(body: ProfileSelect):
    profiles = server_files.discover_profiles(config.DATA)
    if not any(p["name"] == body.name for p in profiles):
        raise HTTPException(404, f"Profile '{body.name}' not found")
    set_setting(SELECTED_PROFILE_KEY, body.name)
    audit("server.profile.select", body.name)
    return {"ok": True, "selected": body.name}
