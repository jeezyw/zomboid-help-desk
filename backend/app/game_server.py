"""Runs the PZ dedicated server as a subprocess of THIS container
(SERVER_MODE=bundled) - start()/stop()/restart()/stats(), parallel to
docker_control.py but for a child process instead of a sibling container. No
Docker access needed for any of this - that's the whole point of bundled mode.

Single-worker constraint (already relied on elsewhere in this app, e.g.
restart_manager.py's pending-action state): the module-level `_process` handle
only makes sense with exactly one uvicorn worker.

If this container itself restarts, the subprocess dies with it (it's a child
process) - an explicitly accepted tradeoff of running the game server this way
rather than as a separate container, not a bug to work around.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import psutil
from fastapi import HTTPException

from . import config
from .db import get_setting, set_setting

SERVER_NAME_KEY = "bundled_server_name"
DEFAULT_SERVER_NAME = "servertest"

_process: subprocess.Popen | None = None


def get_server_name() -> str:
    return get_setting(SERVER_NAME_KEY) or DEFAULT_SERVER_NAME


def set_server_name(name: str) -> str:
    name = name.strip() or DEFAULT_SERVER_NAME
    set_setting(SERVER_NAME_KEY, name)
    return name


def is_running() -> bool:
    return _process is not None and _process.poll() is None


def _start_sync() -> dict[str, Any]:
    global _process
    if is_running():
        raise HTTPException(400, "The bundled server is already running.")

    start_script = config.GAME_FILES / "start-server.sh"
    if not start_script.is_file():
        raise HTTPException(
            400,
            "PZ dedicated server files not found under GAME_FILES_DATA - install "
            "them first from the Server tab's dedicated server panel.",
        )

    # UNVERIFIED against a real install (same honesty standard as this project's
    # other best-effort integrations, e.g. rcon_commands.py's confidence-level
    # header): -cachedir is assumed to redirect PZ's user-data directory
    # (normally ~/Zomboid) to ZOMBOID_DATA, and -servername picks the named
    # profile. Confirm against a live server if the process exits immediately
    # or writes config somewhere unexpected.
    _process = subprocess.Popen(
        [str(start_script), "-cachedir", str(config.DATA), "-servername", get_server_name()],
        cwd=str(config.GAME_FILES),
    )
    return {"ok": True, "action": "start"}


async def start() -> dict[str, Any]:
    return await asyncio.to_thread(_start_sync)


async def stop() -> dict[str, Any]:
    global _process
    if not is_running():
        raise HTTPException(400, "The bundled server isn't running.")

    # Prefer a clean in-game shutdown via RCON `quit` (same command the World
    # Tools panel already sends manually) - falls straight through to a hard
    # stop below if RCON isn't configured/reachable, rather than blocking on it.
    # The long graceful-wait below only makes sense if `quit` actually got sent -
    # if RCON itself failed, there's nothing that's going to make the process
    # exit on its own, so skip straight to terminate() instead of blocking for
    # up to 30s waiting on a shutdown that was never actually requested.
    quit_sent = False
    try:
        from . import rcon_config
        from .rcon_client import rcon_execute

        host, port, password = rcon_config.get_rcon_target()
        await rcon_execute(host, port, password, "quit")
        quit_sent = True
    except Exception:
        pass

    proc = _process

    def _wait(timeout: float) -> None:
        proc.wait(timeout=timeout)

    try:
        await asyncio.to_thread(_wait, 30 if quit_sent else 2)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            await asyncio.to_thread(_wait, 10)
        except subprocess.TimeoutExpired:
            proc.kill()
            await asyncio.to_thread(_wait, 10)

    _process = None
    return {"ok": True, "action": "stop"}


async def restart() -> dict[str, Any]:
    await stop()
    return await start()


def _stats_sync() -> dict[str, Any]:
    if not is_running():
        return {"cpu_percent_raw": 0.0, "memory_bytes": 0}
    try:
        p = psutil.Process(_process.pid)
        # A short blocking interval gives a real reading (a bare, interval-less
        # call just returns 0.0 on first use) - same tradeoff docker_control's
        # `docker stats --no-stream` already makes, just done locally with psutil
        # instead of shelling out.
        cpu = p.cpu_percent(interval=0.5)
        mem = p.memory_info().rss
        return {"cpu_percent_raw": cpu, "memory_bytes": mem}
    except psutil.NoSuchProcess:
        return {"cpu_percent_raw": 0.0, "memory_bytes": 0}


async def stats() -> dict[str, Any]:
    return await asyncio.to_thread(_stats_sync)
