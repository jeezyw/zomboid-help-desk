"""Actual on-disk size of the managed data directories (Zomboid config/saves,
Workshop mods) - NOT the same thing as shutil.disk_usage(), which reports stats for
the whole FILESYSTEM a path lives on. A bind-mounted host directory's filesystem is
typically the host's real disk (or a much larger shared volume), so disk_usage() on
it reports the host's overall used/total space, not "how big is this directory tree"
- wildly misleading as a "how much space is my Zomboid data using" metric.

Computing a real directory size means walking every file, which can be slow for a
large save + many installed mods. That's run in a background thread on a timer
(not inline per-request) and cached, so GET /api/server stays fast and never blocks
the event loop on a multi-second directory walk.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from . import config
from .db import audit, get_setting, set_setting, utcnow

REFRESH_INTERVAL_SECONDS = 300  # directory walks are too slow to redo every dashboard poll
CACHE_KEY = "data_disk_usage_cache"


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue  # gone/permission-denied mid-walk - skip rather than fail the whole scan
    return total


def _compute() -> dict:
    return {
        "zomboid_data_bytes": _dir_size_bytes(config.DATA),
        "workshop_bytes": _dir_size_bytes(config.WORKSHOP),
        "computed_at": utcnow(),
    }


async def refresh_once():
    result = await asyncio.to_thread(_compute)
    set_setting(CACHE_KEY, json.dumps(result))


async def refresh_loop():
    while True:
        try:
            await refresh_once()
        except Exception as e:
            audit("disk_usage.refresh_error", str(e))
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


def get_cached() -> dict | None:
    raw = get_setting(CACHE_KEY)
    return json.loads(raw) if raw else None
