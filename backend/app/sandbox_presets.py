"""Saved Sandbox presets - named snapshots of the full current SandboxVars.lua
settings, so an admin can save a known-good configuration and reapply it later
(including onto a different server profile) without re-entering every value by
hand. Stored in webui.db like the rest of this app's own state (audit log,
backups, config history, etc.) - unlike the Objectives to-do list, there was no
request to keep this out of sqlite, so it follows the app's normal pattern.
"""

from __future__ import annotations

import json
from typing import Any

from .db import db, utcnow


def list_presets() -> list[dict[str, Any]]:
    with db() as c:
        rows = c.execute(
            "SELECT id, name, created_at, profile, settings FROM sandbox_presets ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": r[0], "name": r[1], "created_at": r[2], "profile": r[3],
            "field_count": len(json.loads(r[4])),
        }
        for r in rows
    ]


def get_preset(preset_id: int) -> dict[str, Any] | None:
    with db() as c:
        row = c.execute(
            "SELECT id, name, created_at, profile, settings FROM sandbox_presets WHERE id=?",
            (preset_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "name": row[1], "created_at": row[2], "profile": row[3],
        "settings": json.loads(row[4]),
    }


def save_preset(name: str, profile: str, settings: dict[str, Any]) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise ValueError("Preset name cannot be empty.")
    if not settings:
        raise ValueError("No settings to save - is SandboxVars.lua empty?")

    created_at = utcnow()
    with db() as c:
        cur = c.execute(
            "INSERT INTO sandbox_presets(name, created_at, profile, settings) VALUES (?,?,?,?)",
            (name, created_at, profile, json.dumps(settings)),
        )
        preset_id = cur.lastrowid
    return {
        "id": preset_id, "name": name, "created_at": created_at, "profile": profile,
        "field_count": len(settings),
    }


def delete_preset(preset_id: int) -> bool:
    with db() as c:
        cur = c.execute("DELETE FROM sandbox_presets WHERE id=?", (preset_id,))
        return cur.rowcount > 0
