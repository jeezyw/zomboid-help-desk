"""Discovers installed Workshop mods and reads their mod.info metadata.

Searches for "mods/" directories at ANY depth under the workshop root (matches the
original /api/mods' "**/mods/*" glob) since real steamcmd/Workshop layouts commonly
nest several levels deep, e.g. "<WORKSHOP>/steamapps/workshop/content/108600/
<workshop_id>/mods/<mod_folder>/". The workshop id is taken from the directory
immediately containing "mods/", which holds regardless of how deep that prefix is.
"""

from __future__ import annotations

from pathlib import Path

from .ini_parser import parse_ini


def read_mod_info(mod_dir: Path) -> dict:
    """mod.info uses the same flat "Key=Value" grammar as the server .ini."""
    p = mod_dir / "mod.info"
    if not p.exists():
        return {}
    return parse_ini(p.read_text(encoding="utf-8", errors="replace"))


def scan_workshop_mods(workshop_dir: Path) -> list[dict]:
    out: list[dict] = []
    if not workshop_dir.exists():
        return out

    for mods_root in sorted(workshop_dir.glob("**/mods")):
        if not mods_root.is_dir():
            continue
        workshop_id = mods_root.parent.name
        for mod_dir in sorted(mods_root.glob("*")):
            if not mod_dir.is_dir():
                continue
            info = read_mod_info(mod_dir)
            out.append({
                "mod_id": info.get("id") or mod_dir.name,
                "folder_name": mod_dir.name,
                "workshop_id": workshop_id,
                "name": info.get("name") or mod_dir.name,
                "description": info.get("description", ""),
                "path": str(mod_dir),
            })
    return out
