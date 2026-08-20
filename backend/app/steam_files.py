"""Fetches/updates PZ dedicated server files via steamcmd (anonymous login, no
Steam account needed - app id 380870 is the public PZ dedicated server depot).

Shared foundation for two optional features: bundled server hosting (needs the
actual server binaries) and map rendering (needs texture packs) - both just
call install() and poll get_status(), neither cares which triggered it.

Runs as a single in-process background asyncio.Task, same shape as
restart_manager.py's pending-action pattern: only one install at a time,
request_install() returns immediately, callers poll get_status(). Progress
parsing is best-effort - steamcmd prints lines like
"Update state (0x61) downloading, progress: 45.23 (1234567 / 2730000)" to
stdout; the exact format has been stable across steamcmd versions historically
but isn't contractual, so a line that doesn't match the expected pattern just
means progress_pct stays at its last known value rather than erroring.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from . import config
from .db import audit

APP_ID = "380870"  # Project Zomboid Dedicated Server

_task: asyncio.Task | None = None
_status: dict[str, Any] = {
    "running": False,
    "progress_pct": None,
    "last_line": None,
    "done_at": None,
    "error": None,
}

_PROGRESS_RE = re.compile(r"progress:\s*([\d.]+)")


async def _create_subprocess(*args: str) -> asyncio.subprocess.Process:
    """Isolated so tests can monkeypatch this one function with a fake process
    instead of needing a real steamcmd binary."""
    return await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )


def get_status() -> dict[str, Any]:
    return dict(_status)


def request_install() -> dict[str, Any]:
    global _task
    if _task and not _task.done():
        return {"ok": False, "detail": "An install/update is already running.", "status": get_status()}

    _status.update(running=True, progress_pct=None, last_line=None, done_at=None, error=None)
    _task = asyncio.create_task(_run())
    return {"ok": True, "status": get_status()}


async def _run() -> None:
    config.GAME_FILES.mkdir(parents=True, exist_ok=True)
    try:
        proc = await _create_subprocess(
            "steamcmd",
            "+force_install_dir", str(config.GAME_FILES),
            "+login", "anonymous",
            "+app_update", APP_ID, "validate",
            "+quit",
        )
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            _status["last_line"] = line
            m = _PROGRESS_RE.search(line)
            if m:
                try:
                    _status["progress_pct"] = float(m.group(1))
                except ValueError:
                    pass

        returncode = await proc.wait()
        if returncode != 0:
            _status["error"] = f"steamcmd exited with code {returncode}"
        else:
            _status["progress_pct"] = 100.0
        audit("steam.install", f"app {APP_ID}, exit code {returncode}")
    except FileNotFoundError:
        _status["error"] = (
            "The 'steamcmd' command was not found in this container. Rebuild "
            "with 'docker compose build --no-cache zomboid-webui'."
        )
    except Exception as e:
        _status["error"] = f"steamcmd failed: {e}"
    finally:
        _status["running"] = False
        _status["done_at"] = datetime.now(timezone.utc).isoformat()
