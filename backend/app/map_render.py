"""Renders a PZ map tile set in-process, using pzmap2dzi (vendored via `git
clone` in backend/Dockerfile - see that file for what's confirmed vs. still
unverified about that dependency stack). Runs entirely within this container -
GAME_FILES_DATA/ZOMBOID_DATA/WORKSHOP_DATA/MAP_TILES_DATA are all already
mounted here, no Docker access needed for any of this.

Same background-task shape as steam_files.py: single job at a time, progress
tracked via the subprocess's stdout, callers poll get_status().
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from . import config
from .db import audit

PZMAP2DZI_DIR = Path("/app/pzmap2dzi")
CONF_PATH = PZMAP2DZI_DIR / "conf" / "conf.yaml"

# Confirmed verbatim from pzmap2dzi's own run_top_view_only.bat - the
# top-view-only layer set (its cheaper mode, over the isometric layer set
# used previously), matching what was explicitly asked for.
RENDER_STEPS: tuple[tuple[str, ...], ...] = (
    ("python3", "main.py", "deploy"),
    ("python3", "main.py", "unpack"),
    ("python3", "main.py", "render", "base_top", "zombie_top", "foraging_top", "rooms", "objects", "streets"),
)

# The render step reports progress as "job: <done>/<total> worker: ..."
# (pzmap2dzi/scheduling.py's update_status) - confirmed against the real
# source, not guessed.
_JOB_PROGRESS_RE = re.compile(r"job:\s*(\d+)\s*/\s*(\d+)")

_task: asyncio.Task | None = None
_proc: asyncio.subprocess.Process | None = None
_status: dict[str, Any] = {
    "running": False,
    "step": None,
    "progress_pct": None,
    "last_line": None,
    "done_at": None,
    "error": None,
    "cancelled": False,
}


def get_status() -> dict[str, Any]:
    return dict(_status)


def _configure() -> None:
    """Patches conf.yaml's folder paths - real field names (pz_root, output_root,
    mod_root, save_game_root, save_games) fetched verbatim from pzmap2dzi's own
    conf.yaml during development, not guessed.

    UNVERIFIED (flagged same as elsewhere in this project): pz_root's expected
    contents. pzmap2dzi's own example default points at a full PZ game client
    install; GAME_FILES_DATA here is populated by steam_files.py via the free
    anonymous *dedicated server* depot (app id 380870) - whether that has the
    same media/texturepacks/media/maps layout pzmap2dzi expects from a full
    client install is not confirmed. If rendering fails looking for missing
    textures/maps, this is the first thing to check.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    with CONF_PATH.open() as f:
        conf = yaml.load(f)

    conf["pz_root"] = str(config.GAME_FILES)
    conf["output_root"] = str(config.MAP_TILES)
    conf["mod_root"] = str(config.WORKSHOP)
    conf["save_game_root"] = str(config.DATA / "Saves")
    conf["save_games"] = "all"

    with CONF_PATH.open("w") as f:
        yaml.dump(conf, f)


async def _create_subprocess(*args: str) -> asyncio.subprocess.Process:
    """Isolated so tests can monkeypatch this one function with a fake process
    instead of needing a real pzmap2dzi checkout + game/map data.

    PYTHONUNBUFFERED so progress lines (printed with end='\\r', no trailing
    newline) actually reach us as they're written instead of sitting in a
    block-buffered pipe. start_new_session so a cancel can signal the whole
    process group - the render step spawns its own worker subprocesses
    (pzmap2dzi/mptask.py), which a plain SIGTERM to just the main process
    wouldn't reach.
    """
    return await asyncio.create_subprocess_exec(
        *args, cwd=str(PZMAP2DZI_DIR),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        start_new_session=True,
    )


def request_render() -> dict[str, Any]:
    global _task

    if not (config.GAME_FILES / "media").is_dir():
        return {
            "ok": False,
            "detail": "No game files found under GAME_FILES_DATA - install server "
            "files first from the Server tab's dedicated server panel.",
        }
    if _task and not _task.done():
        return {"ok": False, "detail": "A render is already running.", "status": get_status()}

    _status.update(
        running=True, step=None, progress_pct=0, last_line=None,
        done_at=None, error=None, cancelled=False,
    )
    _task = asyncio.create_task(_run())
    return {"ok": True, "status": get_status()}


def request_cancel() -> dict[str, Any]:
    """Kills the render's whole process group. pzmap2dzi tracks per-tile/source
    change signatures on disk, so a killed render should pick back up close to
    where it left off next time rather than starting over - not exhaustively
    verified against a real multi-hour run, though."""
    if not (_task and not _task.done()):
        return {"ok": False, "detail": "No render is running."}

    _status["cancelled"] = True
    pid = getattr(_proc, "pid", None)
    if pid is not None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    return {"ok": True, "status": get_status()}


def _next_chunk(buf: bytes) -> tuple[bytes, bytes] | None:
    """Splits buf on the first \\r or \\n (pzmap2dzi's progress lines end in
    \\r, not \\n, so a plain readline()-based split would never see them)."""
    positions = [i for i in (buf.find(b"\n"), buf.find(b"\r")) if i != -1]
    if not positions:
        return None
    idx = min(positions)
    return buf[:idx], buf[idx + 1:]


def _progress_fraction(line: str) -> float:
    match = _JOB_PROGRESS_RE.search(line)
    if not match:
        return 0.0
    done, total = int(match.group(1)), int(match.group(2))
    return min(done / total, 1.0) if total else 0.0


async def _run_step(step_index: int, *args: str) -> bool:
    """Runs one pzmap2dzi step, streaming its output into _status['last_line']
    (and, for the render step, _status['progress_pct'] via its "job: N/M"
    status line). Returns False (recording the error, unless cancelled) on a
    non-zero exit, so the pipeline stops rather than pressing on with e.g.
    `render` after `deploy` failed."""
    global _proc

    step_name = args[2] if len(args) > 2 else args[-1]
    _status["step"] = step_name

    proc = await _create_subprocess(*args)
    _proc = proc
    assert proc.stdout is not None

    buf = b""
    while True:
        chunk = await proc.stdout.read(4096)
        if not chunk:
            break
        buf += chunk
        while True:
            split = _next_chunk(buf)
            if split is None:
                break
            raw, buf = split
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                _status["last_line"] = line
                fraction = _progress_fraction(line)
                _status["progress_pct"] = round(((step_index + fraction) / len(RENDER_STEPS)) * 100, 1)
    tail = buf.decode("utf-8", errors="replace").strip()
    if tail:
        _status["last_line"] = tail

    returncode = await proc.wait()
    _proc = None

    if _status["cancelled"]:
        return False
    if returncode != 0:
        _status["error"] = f"{' '.join(args)} exited with code {returncode}: {_status['last_line']}"
        return False
    return True


async def _run() -> None:
    global _proc
    try:
        config.MAP_TILES.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(_configure)

        for step_index, args in enumerate(RENDER_STEPS):
            if not await _run_step(step_index, *args):
                break
        else:
            _status["progress_pct"] = 100
            audit("map.render", "completed")
    except Exception as e:
        _status["error"] = f"Render failed: {e}"
    finally:
        _proc = None
        _status["running"] = False
        _status["done_at"] = datetime.now(timezone.utc).isoformat()
