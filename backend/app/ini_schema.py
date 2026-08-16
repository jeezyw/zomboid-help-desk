"""B42 server .ini schema - mirrors sandbox_schema.py's approach: a curated set of
KNOWN_FIELDS with real labels/descriptions/types, plus a generic type-inferred
fallback for anything present in the real file that isn't mapped here. Nothing is
ever hidden. Mods=/WorkshopItems= are deliberately excluded - the Mod Manager
(routers/mods.py) owns those via dedicated structured read/write, not free-text edits.
"""

from __future__ import annotations

import re
from typing import Any

KNOWN_FIELDS: dict[str, dict[str, Any]] = {
    # --- General ---
    "PublicName": {
        "category": "general", "label": "Public Name",
        "description": "The name shown in the public server browser.",
        "type": "text",
    },
    "PublicDescription": {
        "category": "general", "label": "Description",
        "description": "Shown alongside the server name in the browser.",
        "type": "text",
    },
    "Public": {
        "category": "general", "label": "List Publicly",
        "description": "Whether the server appears in the public server browser.",
        "type": "toggle",
    },
    "Password": {
        "category": "general", "label": "Server Password",
        "description": "Leave blank for no password.",
        "type": "text", "sensitive": True,
    },
    "MaxPlayers": {
        "category": "general", "label": "Max Players",
        "description": "Maximum number of connected players.",
        "type": "number", "min": 1, "max": 100, "step": 1,
    },
    "Map": {
        "category": "general", "label": "Map",
        "description": "Starting map (e.g. \"Muldraugh, KY\").",
        "type": "text",
    },

    # --- Network ---
    "Open": {
        "category": "network", "label": "Open to LAN",
        "description": "Allow LAN connections without a Steam relay.",
        "type": "toggle",
    },
    "DefaultPort": {
        "category": "network", "label": "Game Port",
        "description": "The primary game server port.",
        "type": "number", "min": 1, "max": 65535, "step": 1,
    },
    "UDPPort": {
        "category": "network", "label": "UDP Port",
        "description": "UDP port used for the Steam networking layer.",
        "type": "number", "min": 1, "max": 65535, "step": 1,
    },
    "SteamVAC": {
        "category": "network", "label": "Steam VAC",
        "description": "Enable Valve Anti-Cheat.",
        "type": "toggle",
    },
    "PingLimit": {
        "category": "network", "label": "Ping Limit",
        "description": "Players over this ping (ms) are disconnected. 0 disables the limit.",
        "type": "number", "min": 0, "max": 5000, "step": 10,
    },
    "RCONPort": {
        "category": "network", "label": "RCON Port",
        "description": "TCP port for the remote console used by the WebUI's admin tools.",
        "type": "number", "min": 1, "max": 65535, "step": 1,
    },
    "RCONPassword": {
        "category": "network", "label": "RCON Password",
        "description": "Password required to authenticate via RCON. Leave blank to disable RCON.",
        "type": "text", "sensitive": True,
    },

    # --- Gameplay ---
    "PVP": {
        "category": "gameplay", "label": "PVP",
        "description": "Allow player-versus-player combat.",
        "type": "toggle",
    },
    "PauseEmpty": {
        "category": "gameplay", "label": "Pause When Empty",
        "description": "Pause the in-game clock while no players are connected.",
        "type": "toggle",
    },
    "GlobalChat": {
        "category": "gameplay", "label": "Global Chat",
        "description": "Enable the server-wide chat channel.",
        "type": "toggle",
    },
    "FastForwardMultiplier": {
        "category": "gameplay", "label": "Fast Forward Multiplier",
        "description": "Speed multiplier applied while sleeping/fast-forwarding.",
        "type": "number", "min": 1, "max": 100, "step": 1,
    },
    "SaveWorldEveryMinutes": {
        "category": "gameplay", "label": "Autosave Interval (minutes)",
        "description": "How often the world is saved. 0 disables periodic autosave.",
        "type": "number", "min": 0, "max": 1440, "step": 1,
    },
    "DisplayUserName": {
        "category": "gameplay", "label": "Display Usernames",
        "description": "Show player usernames above their characters.",
        "type": "toggle",
    },

    # --- Safehouses ---
    "PlayerSafehouse": {
        "category": "safehouse", "label": "Player Safehouses",
        "description": "Allow players to claim safehouses.",
        "type": "toggle",
    },
    "AdminSafehouse": {
        "category": "safehouse", "label": "Admin-Only Safehouses",
        "description": "Restrict safehouse claiming to admins.",
        "type": "toggle",
    },
    "SafehouseAllowTrepass": {
        "category": "safehouse", "label": "Allow Trespass",
        "description": "Allow non-members to enter a claimed safehouse.",
        "type": "toggle",
    },
    "SafehouseAllowFire": {
        "category": "safehouse", "label": "Allow Fire",
        "description": "Allow fire to spread inside safehouses.",
        "type": "toggle",
    },
    "SafehouseAllowLoot": {
        "category": "safehouse", "label": "Allow Loot",
        "description": "Allow non-members to loot containers inside a safehouse.",
        "type": "toggle",
    },
    "SafehouseAllowRespawn": {
        "category": "safehouse", "label": "Allow Respawn",
        "description": "Allow players to respawn inside their safehouse.",
        "type": "toggle",
    },
    "SafeHouseRemovalTime": {
        "category": "safehouse", "label": "Removal Time (hours)",
        "description": "Hours of owner inactivity before a safehouse claim is released.",
        "type": "number", "min": 0, "max": 8760, "step": 1,
    },

    # --- Built-in backups (PZ's own server-side backup system, separate from the
    # WebUI's Backup Manager - both are useful, this just exposes the server's own) ---
    "BackupsCount": {
        "category": "backups", "label": "Backup Count",
        "description": "Number of the server's own rotating save backups to keep.",
        "type": "number", "min": 0, "max": 100, "step": 1,
    },
    "BackupsOnStart": {
        "category": "backups", "label": "Backup On Start",
        "description": "Take a backup every time the server starts.",
        "type": "toggle",
    },
    "BackupsPeriod": {
        "category": "backups", "label": "Backup Period (minutes)",
        "description": "How often the server takes its own backup. 0 disables periodic backup.",
        "type": "number", "min": 0, "max": 1440, "step": 1,
    },
}

# Mods/WorkshopItems are intentionally excluded from the generic schema; the Mod
# Manager (routers/mods.py) owns them via dedicated structured endpoints.
EXCLUDED_FROM_GENERIC = {"Mods", "WorkshopItems"}

CATEGORIES = [
    {"id": "general", "title": "General"},
    {"id": "network", "title": "Network"},
    {"id": "gameplay", "title": "Gameplay"},
    {"id": "safehouse", "title": "Safehouses"},
    {"id": "backups", "title": "Built-in Backups"},
    {"id": "other", "title": "Other Detected Settings"},
]


def _humanize(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", key).strip()


def build_fields(settings: dict[str, Any], comments: dict[str, str] | None = None) -> list[dict[str, Any]]:
    comments = comments or {}
    fields: list[dict[str, Any]] = []
    consumed: set[str] = set(EXCLUDED_FROM_GENERIC)

    for key, meta in KNOWN_FIELDS.items():
        fields.append({
            "key": key,
            "label": meta["label"],
            "description": meta.get("description", ""),
            "type": meta["type"],
            "options": meta.get("options"),
            "min": meta.get("min"),
            "max": meta.get("max"),
            "step": meta.get("step"),
            "value": settings.get(key),
            "category": meta["category"],
            "known": True,
            "sensitive": meta.get("sensitive", False),
        })
        consumed.add(key)

    for key, value in settings.items():
        if key in consumed:
            continue
        if isinstance(value, bool):
            ftype = "toggle"
        elif isinstance(value, (int, float)):
            ftype = "number"
        else:
            ftype = "text"
        description = comments.get(key) or f"Raw key: {key}"
        fields.append({
            "key": key,
            "label": _humanize(key),
            "description": description,
            "type": ftype,
            "options": None,
            "min": None, "max": None, "step": None,
            "value": value,
            "category": "other",
            "known": False,
            "sensitive": any(w in key.lower() for w in ("password", "secret", "token")),
        })

    return fields


def build_schema(settings: dict[str, Any], comments: dict[str, str] | None = None) -> list[dict[str, Any]]:
    fields = build_fields(settings, comments)
    by_category: dict[str, list[dict[str, Any]]] = {c["id"]: [] for c in CATEGORIES}
    for f in fields:
        by_category.setdefault(f["category"], []).append(f)

    result = []
    for cat in CATEGORIES:
        cat_fields = by_category.get(cat["id"], [])
        if not cat_fields:
            continue
        cat_fields.sort(key=lambda f: f["label"])
        result.append({"id": cat["id"], "title": cat["title"], "fields": cat_fields})
    return result
