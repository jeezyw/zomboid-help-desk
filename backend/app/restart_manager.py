"""Owns the configurable stop/restart warning delay and the single in-process
"pending action" that warns via RCON, waits, then performs the real Docker action -
as a background asyncio.Task so callers (the manual HTTP endpoint, the scheduler
tick) never block for the delay.

Only one pending action at a time. request_action() is deliberately NOT async - it
just spawns the background task and returns immediately, so both an `await`ing HTTP
handler and a plain synchronous call from scheduler.py's tick work the same way.

Lazy-imports docker_control/rcon_client/players inside the task body (not at
module level) to avoid a circular import with routers/server.py and scheduler.py,
which both import this module.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from . import config
from .db import audit, get_setting, set_setting

WARNING_MINUTES_KEY = "restart_warning_minutes"
DEFAULT_WARNING_MINUTES = 5

_pending_task: asyncio.Task | None = None
_pending_info: dict[str, Any] | None = None


def get_warning_minutes() -> int:
    raw = get_setting(WARNING_MINUTES_KEY)
    return int(raw) if raw is not None else DEFAULT_WARNING_MINUTES


def set_warning_minutes(minutes: int) -> int:
    minutes = max(0, int(minutes))
    set_setting(WARNING_MINUTES_KEY, str(minutes))
    return minutes


def get_pending() -> dict[str, Any] | None:
    if _pending_task is None or _pending_task.done():
        return None
    return _pending_info


def cancel_pending() -> bool:
    global _pending_task
    if _pending_task and not _pending_task.done():
        _pending_task.cancel()
        audit("server.pending_action_cancelled", str(_pending_info))
        return True
    return False


async def _send_warning(message: str) -> None:
    from . import rcon_config
    from .rcon_client import RconError, rcon_execute
    from .rcon_commands import cmd_servermsg

    try:
        host, port, password = rcon_config.get_rcon_target()
    except rcon_config.RconNotConfiguredError:
        return
    try:
        await rcon_execute(host, port, password, cmd_servermsg(message))
    except RconError as e:
        audit("rcon.warning_failed", str(e))


async def _do_docker_action(action: str) -> dict:
    from . import docker_control
    from .routers.players import close_all_open_sessions

    result = await getattr(docker_control, action)()
    audit(f"server.{action}", "via restart_manager")
    close_all_open_sessions(reason=f"server_{action}")
    return result


def request_action(action: str, reason: str, warning_minutes: int | None = None) -> dict:
    """warning_minutes overrides the persisted default for this ONE action (e.g. a
    per-click delay picked in the UI right when Stop/Restart is clicked) - it does
    NOT change the persisted setting used for scheduled restarts or future clicks.
    Omit it (as scheduler.py's tick does) to use the persisted default as before."""
    global _pending_task, _pending_info

    if action not in ("stop", "restart"):
        raise ValueError(f"Unsupported action for request_action: {action}")

    if not config.DOCKER_CONTROL_ENABLED:
        return {
            "ok": False,
            "detail": "Docker control is disabled. Set DOCKER_CONTROL_ENABLED=true "
            "and mount /var/run/docker.sock in docker-compose.yml to enable "
            "Start/Stop/Restart.",
        }

    if _pending_task and not _pending_task.done():
        return {"ok": False, "detail": "An action is already pending.", "pending": _pending_info}

    minutes = max(0, int(warning_minutes)) if warning_minutes is not None else get_warning_minutes()
    fires_at = datetime.now().astimezone() + timedelta(minutes=minutes)
    _pending_info = {
        "action": action, "reason": reason,
        "fires_at": fires_at.isoformat(), "warning_minutes": minutes,
    }

    verb = "restarting" if action == "restart" else "stopping"

    async def _run():
        global _pending_task, _pending_info
        try:
            if minutes > 0:
                msg = f"Server {verb} in {minutes} minute{'s' if minutes != 1 else ''}"
                await _send_warning(f"{msg}: {reason}" if reason else msg)
                await asyncio.sleep(minutes * 60)
                await _send_warning(f"Server {verb} now")
            else:
                msg = f"Server {verb} now"
                await _send_warning(f"{msg}: {reason}" if reason else msg)
            await _do_docker_action(action)
        finally:
            _pending_task = None
            _pending_info = None

    _pending_task = asyncio.create_task(_run())
    return {"ok": True, "pending": _pending_info}
