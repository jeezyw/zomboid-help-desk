"""
B42 SandboxVars.lua schema.

This is deliberately a hybrid, not a claim of 100% fidelity to every internal Lua key:

- KNOWN_FIELDS covers settings we're confident about (exact key path, real dropdown
  labels, real min/max) sourced from PZwiki's Custom Sandbox reference plus stable,
  long-standing SandboxVars conventions (ZombieLore.*, ZombieConfig.*).
- LOOT_SUFFIX handles the "*Loot" rarity category generically, since the exact set of
  loot categories has changed between builds (B42 added Canned Food, Insanely Rare,
  etc.) but the naming pattern and 7-point rarity scale are stable.
- Anything present in the user's actual file that isn't matched by either of the above
  still shows up, grouped by its top-level Lua table, with a type inferred from the
  parsed Python value (bool -> toggle, number -> number field, else -> text). Nothing
  is ever hidden.

A field that doesn't match the user's real file simply won't show a current value;
it will never be invented or written unless the user explicitly sets it.
"""

from __future__ import annotations

import re
from typing import Any

from .db import db


def scale(*labels: str) -> list[dict[str, Any]]:
    return [{"value": i + 1, "label": label} for i, label in enumerate(labels)]


RARITY_SCALE = scale(
    "None (not recommended)", "Insanely rare", "Extremely rare",
    "Rare", "Normal", "Common", "Abundant",
)

FREQUENCY_6 = scale("Never", "Extremely Rare", "Rare", "Sometimes", "Often", "Very Often")
FREQUENCY_4 = scale("Never", "Once", "Sometimes", "Often")
LEVEL_5 = scale("Very Low", "Low", "Normal", "High", "Very High")
LEVEL_3 = scale("Low", "Normal", "High")

KNOWN_FIELDS: dict[str, dict[str, Any]] = {
    # --- Zombies: population ---
    "Zombies": {
        "category": "zombies", "label": "Zombie Count",
        "description": "Overall zombie population level.",
        "type": "select",
        "options": scale("Insane", "Very High", "High", "Normal", "Low", "None"),
    },
    "Distribution": {
        "category": "zombies", "label": "Zombie Distribution",
        "description": "Whether zombies are spread evenly or concentrated in urban areas.",
        "type": "select", "options": scale("Urban Focused", "Uniform"),
    },

    # --- Zombies: lore (behavior) ---
    "ZombieLore.Speed": {
        "category": "zombies", "label": "Speed",
        "description": "How fast zombies move when giving chase.",
        "type": "select", "options": scale("Sprinters", "Fast Shamblers", "Shamblers", "Random"),
    },
    "ZombieLore.Strength": {
        "category": "zombies", "label": "Strength",
        "description": "How hard zombies hit and how likely they are to break skin.",
        "type": "select", "options": scale("Superhuman", "Normal", "Weak", "Random"),
    },
    "ZombieLore.Toughness": {
        "category": "zombies", "label": "Toughness",
        "description": "Zombie hitpoints and how easily they're knocked down.",
        "type": "select", "options": scale("Tough", "Normal", "Fragile", "Random"),
    },
    "ZombieLore.Transmission": {
        "category": "zombies", "label": "Transmission",
        "description": "How the infection spreads.",
        "type": "select",
        "options": scale("Blood + Saliva", "Saliva Only", "Everyone's Infected", "None"),
    },
    "ZombieLore.Cognition": {
        "category": "zombies", "label": "Cognition",
        "description": "How well zombies navigate, open doors, or break through obstacles.",
        "type": "select", "options": scale("Navigate + Use Doors", "Navigate", "Basic Navigation", "Random"),
    },
    "ZombieLore.Memory": {
        "category": "zombies", "label": "Memory",
        "description": "How long a zombie will give chase before giving up.",
        "type": "select", "options": scale("Long", "Normal", "Short", "None", "Random"),
    },
    "ZombieLore.Sight": {
        "category": "zombies", "label": "Sight",
        "description": "How far and wide zombies can spot a player.",
        "type": "select", "options": scale("Eagle", "Normal", "Poor", "Random"),
    },
    "ZombieLore.Hearing": {
        "category": "zombies", "label": "Hearing",
        "description": "How far zombies react to noise.",
        "type": "select", "options": scale("Pinpoint", "Normal", "Poor", "Random"),
    },

    # --- Zombies: config (advanced / numeric) ---
    "ZombieConfig.PopulationMultiplier": {
        "category": "zombies", "label": "Population Multiplier",
        "description": "Overall population scale. 4.0 = Insane, 1.0 = Normal, 0.0 = None.",
        "type": "slider", "min": 0, "max": 4, "step": 0.05,
    },
    "ZombieConfig.PopulationStartMultiplier": {
        "category": "zombies", "label": "Population Start Multiplier",
        "description": "Desired population at the start of the game.",
        "type": "slider", "min": 0, "max": 4, "step": 0.05,
    },
    "ZombieConfig.PopulationPeakMultiplier": {
        "category": "zombies", "label": "Population Peak Multiplier",
        "description": "Desired population on the peak day.",
        "type": "slider", "min": 0, "max": 4, "step": 0.05,
    },
    "ZombieConfig.PopulationPeakDay": {
        "category": "zombies", "label": "Population Peak Day",
        "description": "The in-game day population reaches its peak.",
        "type": "slider", "min": 1, "max": 365, "step": 1,
    },
    "ZombieConfig.RespawnHours": {
        "category": "zombies", "label": "Respawn Hours",
        "description": "Hours before zombies may respawn in a cell. 0 disables respawn entirely.",
        "type": "slider", "min": 0, "max": 8760, "step": 1,
    },
    "ZombieConfig.RespawnUnseenHours": {
        "category": "zombies", "label": "Respawn Unseen Hours",
        "description": "Hours a chunk must go unseen before zombies may respawn in it.",
        "type": "slider", "min": 0, "max": 8760, "step": 1,
    },
    "ZombieConfig.RespawnMultiplier": {
        "category": "zombies", "label": "Respawn Multiplier",
        "description": "Fraction of a cell's desired population that may respawn every Respawn Hours.",
        "type": "slider", "min": 0, "max": 1, "step": 0.01,
    },
    "ZombieConfig.RedistributeHours": {
        "category": "zombies", "label": "Redistribute Hours",
        "description": "Hours before zombies migrate to empty parts of the same cell. 0 disables migration.",
        "type": "slider", "min": 0, "max": 8760, "step": 1,
    },
    "ZombieConfig.FollowSoundDistance": {
        "category": "zombies", "label": "Follow Sound Distance",
        "description": "Distance a virtual zombie will walk towards the last sound it heard.",
        "type": "slider", "min": 0, "max": 1000, "step": 10,
    },
    "ZombieConfig.RallyGroupSize": {
        "category": "zombies", "label": "Rally Group Size",
        "description": "Size of idle zombie groups. 0 disables grouping.",
        "type": "slider", "min": 0, "max": 1000, "step": 1,
    },
    "ZombieConfig.RallyTravelDistance": {
        "category": "zombies", "label": "Rally Travel Distance",
        "description": "Distance zombies travel to form groups when idle.",
        "type": "slider", "min": 5, "max": 50, "step": 1,
    },
    "ZombieConfig.RallyGroupSeparation": {
        "category": "zombies", "label": "Rally Group Separation",
        "description": "Distance maintained between zombie groups.",
        "type": "slider", "min": 5, "max": 25, "step": 1,
    },
    "ZombieConfig.RallyGroupRadius": {
        "category": "zombies", "label": "Rally Group Radius",
        "description": "How close group members stay to their group's leader.",
        "type": "slider", "min": 1, "max": 10, "step": 1,
    },

    # --- Character ---
    # B42 moved this from a flat "XpMultiplier" key (B41) into the nested
    # MultiplierConfig table - the old flat key doesn't exist in a real B42
    # SandboxVars.lua at all, so editing it here silently did nothing (confirmed
    # against a live server's MultiplierConfig table, pasted by the user 2026-08-11).
    "MultiplierConfig.Global": {
        "category": "character", "label": "XP Multiplier (Global)",
        "description": "Rate at which all skills level up, when \"Use Global XP Multiplier\" "
                        "below is enabled - per-skill multipliers in the same file are ignored "
                        "while it's on.",
        "type": "number", "min": 0, "max": 1000, "step": 0.1,
    },
    "MultiplierConfig.GlobalToggle": {
        "category": "character", "label": "Use Global XP Multiplier",
        "description": "When enabled, all skills use the Global XP Multiplier above instead of "
                        "their individual multipliers.",
        "type": "toggle",
    },
    "Nutrition": {
        "category": "character", "label": "Nutrition",
        "description": "Whether the nutritional value of food affects player condition.",
        "type": "toggle",
    },
    "StarterKit": {
        "category": "character", "label": "Starter Kit",
        "description": "Start with a school bag, baseball bat, hammer, and water bottle.",
        "type": "toggle",
    },

    # --- World / time ---
    "StartMonth": {
        "category": "world", "label": "Start Month",
        "description": "The month the game begins in. Affects weather and foraging.",
        "type": "select",
        "options": scale("January", "February", "March", "April", "May", "June",
                          "July", "August", "September", "October", "November", "December"),
    },
    "StartDay": {
        "category": "world", "label": "Start Day",
        "description": "Day of the month the game begins on.",
        "type": "slider", "min": 1, "max": 28, "step": 1,
    },
}

# Loot rarity: any top-level key ending in "Loot" gets the 7-point rarity scale,
# regardless of exactly which categories this build ships (B42 has added new ones).
LOOT_KEY = re.compile(r"^([A-Za-z]+)Loot$")

CATEGORIES = [
    {"id": "zombies", "title": "Zombies"},
    {"id": "loot", "title": "Loot & Items"},
    {"id": "weapons", "title": "Weapons & Combat"},
    {"id": "vehicles", "title": "Vehicles"},
    {"id": "farming", "title": "Farming & Foraging"},
    {"id": "skills", "title": "Skills & XP"},
    {"id": "character", "title": "Character"},
    {"id": "world", "title": "World & Time"},
    {"id": "mods", "title": "Mod Settings"},
    {"id": "other", "title": "Other Detected Settings"},
]

# Structural routing: SandboxVars.lua nests some vanilla setting groups under their
# own top-level Lua table, and (this is the useful part) so do mods that add their
# own sandbox options - e.g. a "CommonSense" or "ImmersiveSuicide" mod installed
# writes settings under "CommonSense.*"/"ImmersiveSuicide.*". Any dotted-prefix table
# NOT in this known-vanilla list is therefore very likely mod-injected, which is a
# far more reliable signal than guessing at keywords - route those to "mods" instead
# of scattering them across topical categories where they don't actually belong.
KNOWN_VANILLA_TABLE_CATEGORIES: dict[str, str] = {
    "ZombieLore": "zombies",
    "ZombieConfig": "zombies",
    "ZCollision": "zombies",
    "MultiplierConfig": "skills",
    "Map": "world",
}

# Best-effort keyword categorization for settings NOT in KNOWN_FIELDS or routed above
# - sorts them into the right tab instead of dumping everything into "Other Detected
# Settings". This is a heuristic over the key name (case-insensitive substring
# match), not a claim that every match is semantically correct - same spirit as
# log_patterns.py's best-effort regexes. Checked in this order (first match wins),
# most specific/unambiguous categories first so a broad keyword elsewhere doesn't
# steal a field that's actually a better fit for an earlier category.
CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("zombies", (
        "zombie", "infect", "shambl", "sprinter", "rally", "respawn", "population",
        "distribution", "migration", "reanimate", "corpse", "alarm", "gunshot",
        "helicopter", "chopper", "metaevent", "metaknowledge",
    )),
    ("weapons", (
        "weapon", "firearm", "gun", "ammo", "ranged", "melee", "recoil", "aiming",
        "reload", "sight", "silencer", "suppressor", "attackblock", "vulnerab",
    )),
    ("vehicles", (
        "vehicle", "car", "engine", "fuel", "traffic", "carjack", "siren", "gas",
    )),
    ("farming", (
        "farm", "crop", "forag", "fish", "trap", "compost", "plant", "seed",
        "nutrition", "hunger", "thirst", "animal", "clay", "food", "fridge", "dirt",
    )),
    ("loot", (
        "loot", "container", "clothing",
    )),
    ("world", (
        "weather", "season", "erosion", "nature", "map", "temperature", "rain",
        "storm", "wind", "fog", "snow", "elec", "water", "generator", "time",
        "day", "night", "climate", "fire", "removal", "lightbulb", "lockedhouse",
        "survivorhouse", "startyear", "zonestory", "rat", "maggot", "basement",
    )),
    ("character", (
        "xp", "skill", "health", "injury", "wound", "endurance", "fitness",
        "strength", "trait", "occupation", "clothes", "player", "character",
        "moodle", "sleep", "boredom", "unhapp", "stress", "panic", "fracture",
        "construction", "discomfort", "climb", "poison", "regen", "literature",
        "recipe", "stats", "page",
    )),
]


def _guess_category(key: str) -> str:
    if "." in key:
        prefix = key.split(".")[0]
        if prefix in KNOWN_VANILLA_TABLE_CATEGORIES:
            return KNOWN_VANILLA_TABLE_CATEGORIES[prefix]
        return "mods"  # unrecognized table prefix - very likely mod-injected, see comment above

    lower = key.lower()
    for category_id, keywords in CATEGORY_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return category_id
    return "other"


# --- Per-admin overrides: Priority Vars (favorites) + manual category reassignment.
# Global, not per-server-profile - same scoping as e.g. the RCON host override and
# backup retention policy, which are also admin UI preferences rather than
# server-specific data.

def get_field_overrides() -> dict[str, dict[str, Any]]:
    with db() as c:
        rows = c.execute("SELECT key, favorite, category_override FROM sandbox_field_overrides").fetchall()
    return {
        key: {"favorite": bool(favorite), "category_override": category_override}
        for key, favorite, category_override in rows
    }


def set_favorite(key: str, favorite: bool) -> None:
    with db() as c:
        c.execute(
            "INSERT INTO sandbox_field_overrides(key, favorite, category_override) VALUES (?,?,NULL) "
            "ON CONFLICT(key) DO UPDATE SET favorite=excluded.favorite",
            (key, int(favorite)),
        )


def set_category_override(key: str, category: str | None) -> None:
    with db() as c:
        c.execute(
            "INSERT INTO sandbox_field_overrides(key, favorite, category_override) VALUES (?,0,?) "
            "ON CONFLICT(key) DO UPDATE SET category_override=excluded.category_override",
            (key, category),
        )


def _humanize(key: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", key.split(".")[-1])
    return words.strip()


# Matches a comment line documenting one option of a numbered scale, e.g. the "1 =
# Insane" in a block like "-- Default = Normal\n-- 1 = Insane\n-- 2 = Very High...".
OPTION_LINE_RE = re.compile(r"^(\d+)\s*=\s*(.+)$")

# Matches the "Min: 0.00 Max: 1000.00" that real SandboxVars.lua comments document
# for most numeric settings (see MultiplierConfig's comments for a real example) -
# same convention the server .ini's own comments use.
LIMITS_RE = re.compile(r"Min:\s*(-?[\d.]+)\s*Max:\s*(-?[\d.]+)", re.IGNORECASE)


def _parse_comment_block(comment: str) -> tuple[str, list[dict[str, Any]] | None, float | None, float | None]:
    """Splits a setting's preceding "-- ..." comment block (see
    routers/sandbox.py's parse_sandbox_comments) into a prose description, and:
    - if the block documents a numbered scale, a matching list of select options -
      real labels straight from the file's own documentation rather than a guess.
    - if the block documents "Min: X Max: Y", those bounds (for the generic-fallback
      slider in build_fields below) - also straight from the file, not guessed."""
    prose: list[str] = []
    options: list[dict[str, Any]] = []
    for line in comment.split("\n"):
        m = OPTION_LINE_RE.match(line.strip())
        if m:
            options.append({"value": int(m.group(1)), "label": m.group(2).strip()})
        elif line.strip():
            prose.append(line.strip())
    description = " ".join(prose)

    limits = LIMITS_RE.search(description)
    min_val = float(limits.group(1)) if limits else None
    max_val = float(limits.group(2)) if limits else None

    return description, (options if len(options) >= 2 else None), min_val, max_val


def build_fields(settings: dict[str, Any], comments: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Merge KNOWN_FIELDS + loot pattern + generic fallback against real parsed settings."""
    comments = comments or {}
    fields: list[dict[str, Any]] = []
    consumed: set[str] = set()

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
            "sensitive": False,
        })
        consumed.add(key)

    for key, value in settings.items():
        if key in consumed:
            continue
        top_key = key.split(".")[-1]
        m = LOOT_KEY.match(top_key)
        if m:
            fields.append({
                "key": key,
                "label": _humanize(m.group(1)) + " Loot",
                "description": "Loot rarity for this item category.",
                "type": "select",
                "options": RARITY_SCALE,
                "min": None, "max": None, "step": None,
                "value": value,
                "category": "loot",
                "known": True,
                "sensitive": False,
            })
            consumed.add(key)

    for key, value in settings.items():
        if key in consumed:
            continue

        description = ""
        options = None
        min_val = max_val = None
        comment = comments.get(key)
        if comment:
            description, options, min_val, max_val = _parse_comment_block(comment)
        if not description:
            # No comment (or an empty/unparseable one) - show the raw Lua key path
            # instead of leaving this blank. Also the only way to see which table a
            # nested key lives under, since the label above only shows the last path
            # segment (e.g. "ZombieConfig.AlarmDecay" -> "Alarm Decay").
            description = f"Raw key: {key}"

        is_numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        step = None
        if options:
            ftype = "select"
        elif isinstance(value, bool):
            ftype = "toggle"
        elif is_numeric and min_val is not None and max_val is not None:
            # The file documented real bounds for this one - render it as a slider
            # like a curated KNOWN_FIELDS entry instead of a bare number box.
            ftype = "slider"
            step = 1 if isinstance(value, int) else 0.1
        elif is_numeric:
            ftype = "number"
        else:
            ftype = "text"

        fields.append({
            "key": key,
            "label": _humanize(key),
            "description": description,
            "type": ftype,
            "options": options,
            "min": min_val, "max": max_val, "step": step,
            "value": value,
            "category": _guess_category(key),
            "known": False,
            "sensitive": any(w in key.lower() for w in ("password", "secret", "token")),
        })

    # Apply per-admin overrides uniformly, regardless of which loop above produced
    # the field - a curated, loot-pattern, or generic-fallback field can all be
    # favorited or manually reassigned the same way.
    valid_category_ids = {c["id"] for c in CATEGORIES}
    overrides = get_field_overrides()
    for f in fields:
        override = overrides.get(f["key"])
        f["favorite"] = bool(override and override["favorite"])
        f["category_overridden"] = bool(override and override["category_override"] in valid_category_ids)
        if f["category_overridden"]:
            f["category"] = override["category_override"]

    return fields


def build_schema(settings: dict[str, Any], comments: dict[str, str] | None = None) -> list[dict[str, Any]]:
    fields = build_fields(settings, comments)
    by_category: dict[str, list[dict[str, Any]]] = {c["id"]: [] for c in CATEGORIES}
    for f in fields:
        by_category.setdefault(f["category"], []).append(f)

    result = []

    # Priority Vars is a pinned shortcut view, not a real category a field "lives
    # in" - favorited fields appear here AND in their normal category tab below.
    favorites = sorted((f for f in fields if f["favorite"]), key=lambda f: f["label"])
    if favorites:
        result.append({"id": "favorites", "title": "Priority Vars", "fields": favorites})

    for cat in CATEGORIES:
        cat_fields = by_category.get(cat["id"], [])
        if not cat_fields:
            continue
        cat_fields.sort(key=lambda f: f["label"])
        result.append({"id": cat["id"], "title": cat["title"], "fields": cat_fields})
    return result
