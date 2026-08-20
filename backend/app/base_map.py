"""Tiles the maintainer-supplied static base map image (config.BASE_MAP_SOURCE,
a full vanilla B42 isometric render someone else already produced) into a
Leaflet-compatible {level}/{y}/{x} tile pyramid (vips's own "google" layout
axis order - see LiveMap.tsx's tile URL template), using libvips (see
Dockerfile). This
is a single flat image being sliced up, not a pzmap2dzi render - see
map_render.py for the separate in-game render pipeline, which stays available
independently of this.

Output lands under MAP_TILES_DATA/base, alongside (but separate from)
map_render.py's own output, and is served by the same always-on /map-tiles
StaticFiles mount in main.py - no new mount needed.

A pre-tiled default (SEEDED_TILES_DIR) ships baked into the image too, so a
fresh deployment gets a working Live Map immediately via seed_if_needed()
(called from main.py's startup) without needing to run this at all - request_tile()
below stays available for anyone who wants to re-tile (a different source
image, updated output, etc).

Same background-task shape as steam_files.py/map_render.py: single job at a
time, callers poll get_status().

UNVERIFIED end-to-end (flagged, not swept under the rug): `vips dzsave
--layout google` here is built from libvips' documented CLI behavior, not a
real run against the actual ~63488x32768 source image - this dev sandbox
can't run libvips at all (no working system package manager - the same
constraint that blocked steamcmd earlier), so the first real run needs to
happen in the actual Docker build/container and be checked visually. To hedge
against getting vips's own default pyramid depth slightly wrong in
_max_zoom's pre-run estimate, the real max_zoom is re-derived from whatever
level folders vips actually created once tiling finishes, rather than trusted
blindly.
"""

from __future__ import annotations

import asyncio
import math
import os
import shutil
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .db import audit

TILE_SIZE = 256
OUTPUT_DIR: Path = config.MAP_TILES / "base"

# Maintainer-supplied pre-tiled default output (the actual `vips dzsave`
# result for the shipped BASE_MAP_SOURCE image, generated once and baked into
# the image the same way BASE_MAP_SOURCE itself is - see backend/Dockerfile).
# seed_if_needed() copies this into OUTPUT_DIR on startup if nothing's tiled
# there yet, so a fresh deployment has a working Live Map immediately with no
# "Tile Base Map" click (and no libvips run) needed.
SEEDED_TILES_DIR = Path(__file__).resolve().parent / "map" / "base_tiles"

_task: asyncio.Task | None = None
_proc: asyncio.subprocess.Process | None = None
_status: dict[str, Any] = {
    "running": False,
    "last_line": None,
    "done_at": None,
    "error": None,
    "cancelled": False,
    "width": None,
    "height": None,
    "max_zoom": None,
    "tile_size": TILE_SIZE,
}


def get_status() -> dict[str, Any]:
    return {**_status, "tiles_available": tiles_available()}


def tiles_available() -> bool:
    return OUTPUT_DIR.is_dir() and any(OUTPUT_DIR.iterdir())


async def _run_capture(*args: str) -> str:
    """Isolated (like _create_subprocess below) so tests can monkeypatch this
    one function instead of needing a real libvips install."""
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode("utf-8", errors="replace")


async def _create_subprocess(*args: str) -> asyncio.subprocess.Process:
    """Isolated so tests can monkeypatch this one function with a fake process
    instead of needing a real libvips install. start_new_session so a cancel
    can signal the whole process group, same reasoning as map_render.py."""
    return await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )


async def _image_dims() -> tuple[int, int]:
    width = int((await _run_capture("vipsheader", "-f", "width", str(config.BASE_MAP_SOURCE))).strip())
    height = int((await _run_capture("vipsheader", "-f", "height", str(config.BASE_MAP_SOURCE))).strip())
    return width, height


def request_tile() -> dict[str, Any]:
    global _task

    if not config.BASE_MAP_SOURCE.is_file():
        return {
            "ok": False,
            "detail": "No base map image found in this build - place one at "
            "backend/app/map/b42_map.jpg and rebuild "
            "(docker compose build --no-cache zomboid-webui).",
        }
    if _task and not _task.done():
        return {"ok": False, "detail": "A tiling job is already running.", "status": get_status()}

    _status.update(
        running=True, last_line=None, done_at=None, error=None, cancelled=False,
        width=None, height=None, max_zoom=None,
    )
    _task = asyncio.create_task(_run())
    return {"ok": True, "status": get_status()}


def request_cancel() -> dict[str, Any]:
    if not (_task and not _task.done()):
        return {"ok": False, "detail": "No tiling job is running."}

    _status["cancelled"] = True
    pid = getattr(_proc, "pid", None)
    if pid is not None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    return {"ok": True, "status": get_status()}


async def seed_if_needed() -> None:
    """Called once at app startup (see main.py's lifespan). Never overwrites
    an operator's own tiling output - only acts when OUTPUT_DIR has nothing
    in it at all, and only if this build actually has SEEDED_TILES_DIR baked
    in (older/from-source builds without it just skip this silently)."""
    if tiles_available() or not SEEDED_TILES_DIR.is_dir():
        return
    try:
        OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copytree, SEEDED_TILES_DIR, OUTPUT_DIR, dirs_exist_ok=True)
    except OSError as e:
        _status["error"] = f"Could not seed default map tiles: {e}"
        return

    # max_zoom is derived from the tile directory itself (already copied
    # above) and is what the Leaflet viewer actually needs - deliberately
    # not gated behind the width/height lookup below, which only feeds the
    # cosmetic "last tiled WxH" status line and can fail independently
    # (e.g. vipsheader unavailable) without that mattering here.
    actual = _actual_max_zoom()
    if actual is not None:
        _status["max_zoom"] = actual

    if config.BASE_MAP_SOURCE.is_file():
        try:
            width, height = await _image_dims()
            _status["width"] = width
            _status["height"] = height
        except OSError:
            pass

    _status["done_at"] = datetime.now(timezone.utc).isoformat()
    audit("map.base_tile", "seeded_default")


def _actual_max_zoom() -> int | None:
    if not OUTPUT_DIR.is_dir():
        return None
    levels = [int(p.name) for p in OUTPUT_DIR.iterdir() if p.is_dir() and p.name.isdigit()]
    return max(levels) if levels else None


async def _run() -> None:
    global _proc
    try:
        OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)

        width, height = await _image_dims()
        _status["width"] = width
        _status["height"] = height
        # Pre-run estimate for immediate UI feedback - overwritten with the
        # real value below once vips has actually written its own levels.
        _status["max_zoom"] = math.ceil(math.log2(max(width, height) / TILE_SIZE))

        if OUTPUT_DIR.exists():
            await asyncio.to_thread(shutil.rmtree, OUTPUT_DIR)

        proc = await _create_subprocess(
            "vips", "dzsave", str(config.BASE_MAP_SOURCE), str(OUTPUT_DIR),
            "--layout", "google", "--tile-size", str(TILE_SIZE),
            "--suffix", ".jpg[Q=82]", "--overlap", "0",
        )
        _proc = proc
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if line:
                _status["last_line"] = line

        returncode = await proc.wait()
        _proc = None

        if _status["cancelled"]:
            pass
        elif returncode != 0:
            _status["error"] = f"vips dzsave exited with code {returncode}: {_status['last_line']}"
        else:
            actual = _actual_max_zoom()
            if actual is not None:
                _status["max_zoom"] = actual
            audit("map.base_tile", "completed")
    except Exception as e:
        _status["error"] = f"Tiling failed: {e}"
    finally:
        _proc = None
        _status["running"] = False
        _status["done_at"] = datetime.now(timezone.utc).isoformat()
