"""Live Map data: player positions written by the ZHDPositionTracker companion
mod (see mod/ZHDPositionTracker/), and presence of a rendered map tile set.

UNVERIFIED assumption (same honesty standard as console_log.py's "UNVERIFIED
assumption" for server-console.txt, and rcon_commands.py's confidence-level
header): PZ's getFileWriter is understood to write into "<Zomboid root>/Lua/",
and config.DATA already maps to that same Zomboid root (confirmed by
console_log.py finding "server-console.txt" and a "Logs/" dir directly under
it). CANDIDATE_PATHS below reflects that best guess plus a couple of fallback
guesses for getFileWriter's mod-namespacing behavior, which varies across PZ
versions - not confirmed against a live server. If the Live Map tab shows no
players despite the mod being installed and enabled, this is the first thing
to check: find where ZHDPositions.json actually landed and add it here.
"""

from __future__ import annotations

import io
import json
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .db import get_setting, set_setting

FILE_NAME = "ZHDPositions.json"
STALE_AFTER_SECONDS = 30

# Baked into the image at this path by backend/Dockerfile (COPY
# mod/ZHDPositionTracker/42 ...ZHDPositionTracker/42) - preserves the "42"
# per-build-version subfolder rather than flattening it away. CONFIRMED
# necessary against a real deployment: every real, working mod found there
# had its mod.info inside a per-build-version (e.g. "42", "42.13") or
# "common" subfolder, never bare at the mod's own root - a bare mod.info at
# the top level was silently ignored by the dedicated server's mod loader
# ("required mod ... not found", despite the file genuinely being present,
# correctly permissioned, and correctly referenced in Mods=). An earlier
# version of this app flattened that subfolder away specifically to match
# this app's own simplified mod_meta.py scanner - convenient for us, but
# wrong for the real game engine.
MOD_ID = "ZHDPositionTracker"
MOD_VERSION_SUBFOLDER = "42"
MOD_SOURCE_DIR = Path("/app/mod") / MOD_ID

# Was used as a synthetic Steam Workshop id in an earlier (wrong, actively
# dangerous - see git history) attempt at this. No longer used for anything;
# kept only so install_mod() can find and remove that old stray copy.
_OLD_FAKE_WORKSHOP_ID = "1000000001"

# Earlier guesses at where this mod needed to live, tried and disproven
# against a real deployment before landing on the layout below - install_mod()
# removes any stray copy left at any of these from a prior run of this app,
# so a fixed version doesn't leave dead, confusing duplicates behind.
_STALE_DEST_CANDIDATES = [
    config.WORKSHOP / "content" / "108600" / _OLD_FAKE_WORKSHOP_ID / "mods" / MOD_ID,
    config.DATA / "mods" / MOD_ID,
]

LIVE_MAP_ENABLED_KEY = "live_map_enabled_override"

CANDIDATE_PATHS = [
    config.DATA / "Lua" / FILE_NAME,
    config.DATA / "Lua" / "ZHDPositionTracker" / FILE_NAME,
    config.DATA / FILE_NAME,
]


def find_position_file() -> Path | None:
    for p in CANDIDATE_PATHS:
        if p.is_file():
            return p
    return None


def read_positions() -> dict[str, Any]:
    """Never raises - a missing/malformed file (mod not installed yet, wrong
    guessed path, server never started, momentary partial write) just means no
    players show on the map, not a broken API response."""
    path = find_position_file()
    if path is None:
        return {"players": [], "updated_at": None, "stale": True}

    try:
        mtime = path.stat().st_mtime
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        players = data.get("players", [])
        if not isinstance(players, list):
            players = []
    except (OSError, json.JSONDecodeError):
        return {"players": [], "updated_at": None, "stale": True}

    updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    stale = (time.time() - mtime) > STALE_AFTER_SECONDS
    # A stale snapshot can't be trusted to reflect who's actually still
    # connected - don't report anyone as "present" (map markers or the
    # player list) from data this old. The mod itself only ever writes
    # currently-online players each cycle, so freshness is the only thing
    # that can go wrong here.
    return {"players": [] if stale else players, "updated_at": updated_at, "stale": stale}


def tiles_available() -> bool:
    return config.MAP_TILES.is_dir() and any(config.MAP_TILES.iterdir())


def is_enabled() -> bool:
    """LIVE_MAP_ENABLED is an env var (a deploy-time default), but the whole
    point of the Settings tab's one-click setup is turning this on from the
    running app without an env var edit + restart - so the real source of
    truth is this kv-stored override once one has been set, falling back to
    the env var only for a container that's never had the button clicked."""
    override = get_setting(LIVE_MAP_ENABLED_KEY)
    if override is not None:
        return override == "1"
    return config.LIVE_MAP_ENABLED


def set_enabled(value: bool) -> bool:
    set_setting(LIVE_MAP_ENABLED_KEY, "1" if value else "0")
    return value


def _dest_dir() -> Path:
    return config.WORKSHOP / "mods" / MOD_ID


def mod_installed() -> bool:
    return (_dest_dir() / MOD_VERSION_SUBFOLDER / "mod.info").is_file()


def build_mod_zip() -> bytes:
    """Zips the bundled ZHDPositionTracker mod for distribution to players.
    Since this isn't a real Steam Workshop item, each connecting player's own
    client needs a local copy to pass PZ's mod compatibility check (it's a
    formality only - see README's Live Map section, the mod has no client-side
    Lua at all). Archive paths are rooted at MOD_ID/, matching MOD_SOURCE_DIR's
    own folder name, so extracting the zip directly into a player's local
    Zomboid/mods/ directory reproduces the same
    <mods_root>/ZHDPositionTracker/42/... layout the server itself uses -
    same MOD_VERSION_SUBFOLDER nesting requirement as install_mod() below."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(MOD_SOURCE_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(Path(MOD_ID) / path.relative_to(MOD_SOURCE_DIR)))
    return buf.getvalue()


def _enable_mods_entry_only() -> dict:
    """Adds MOD_ID to Mods= and ONLY Mods= - never touches WorkshopItems=.
    Kept as a dedicated function (rather than routers/mods.py's generic
    enable_mod_by_id()) as defense-in-depth: WorkshopItems= doesn't just mark
    an id for local discovery, it tells the dedicated server to
    validate/download that item from Steam, and PZ's own error handling for a
    failed Workshop download has a null-pointer bug
    (GameServerWorkshopItems.Install) that crashes the whole server in a
    restart loop - confirmed the hard way against a live deployment, when an
    earlier (wrong) version of this function placed this mod's files under a
    synthetic Workshop-content-style id and let the generic enable path
    auto-add it to WorkshopItems=. This also proactively strips that old
    synthetic id back out of WorkshopItems= if it's still there from before,
    so re-running setup is itself a safety net.
    """
    from .ini_parser import parse_ini, parse_list_field, render_list_field
    from .profiles import find_ini
    from .routers.ini import apply_ini_changes

    path = find_ini()
    settings = parse_ini(path.read_text(encoding="utf-8", errors="replace"))
    load_order = parse_list_field(settings.get("Mods"))
    workshop_items = parse_list_field(settings.get("WorkshopItems"))

    changes: dict[str, Any] = {}
    if _OLD_FAKE_WORKSHOP_ID in workshop_items:
        changes["WorkshopItems"] = render_list_field(
            [w for w in workshop_items if w != _OLD_FAKE_WORKSHOP_ID]
        )

    if MOD_ID in load_order:
        if not changes:
            return {"ok": True, "note": "Already enabled."}
        return apply_ini_changes(changes)

    changes["Mods"] = render_list_field([*load_order, MOD_ID])
    return apply_ini_changes(changes)


def install_mod() -> dict[str, Any]:
    """Copies the bundled ZHDPositionTracker mod into WORKSHOP_DATA/mods/ and
    enables it via the .ini (Mods= only) - same two steps
    mod/ZHDPositionTracker/README.md's manual instructions describe, just
    done for the user instead of by hand.

    Destination layout - CONFIRMED against a real deployment (not a docs
    guess), arrived at the hard way after several wrong guesses along the way:
    a flat WORKSHOP_DATA/mods/ layout, a flat <ZOMBOID_DATA>/mods/ layout
    (the generic-docs convention, which also matched a real server mount but
    still wasn't it), and mimicking the Steam Workshop content tree under a
    synthetic id (which additionally turned out actively dangerous - see
    _enable_mods_entry_only()'s docstring). `docker top`/`docker inspect` on
    the real PZ server container showed its launch flags
    (`-modfolders workshop,steam,mods`) and confirmed mount paths, which
    narrowed things down but still didn't nail the exact right folder among
    the three named scan roots - what finally confirmed it was manually
    placing the mod under WORKSHOP_DATA/mods/ on a real deployment and
    watching it actually load.

    Separately, and just as necessary: the mod.info has to sit inside a
    MOD_VERSION_SUBFOLDER ("42") subdirectory, not bare at the mod's own
    root - confirmed by checking every real, currently-loading mod's actual
    file layout on that deployment: 100% of them had mod.info inside a
    per-build-version or "common" subfolder, none had ONLY a bare top-level
    mod.info. See MOD_VERSION_SUBFOLDER's definition above for the fuller
    story.
    """
    if not MOD_SOURCE_DIR.is_dir():
        return {
            "ok": False,
            "detail": "Mod files not found in this image - rebuild zomboid-webui "
            "(docker compose build --no-cache zomboid-webui).",
        }

    for stale in _STALE_DEST_CANDIDATES:
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)

    dest = _dest_dir()
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(MOD_SOURCE_DIR, dest, dirs_exist_ok=True)
    except OSError as e:
        return {"ok": False, "detail": f"Could not copy mod files: {e}"}

    return {"ok": True, "enable_result": _enable_mods_entry_only()}


def setup() -> dict[str, Any]:
    """The Settings tab's single button: install the mod (if not already) and
    turn Live Map on. Doesn't touch MAP_TILES_DATA/tiles - that's still a
    separate step (Live Map tab's Map Rendering panel) since it's a genuinely
    heavy job that shouldn't be bundled into a single "quick setup" click."""
    result = install_mod()
    if not result["ok"]:
        return result
    set_enabled(True)
    return {"ok": True, "mod_installed": True, "enabled": True}
