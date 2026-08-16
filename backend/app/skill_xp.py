"""Project Zomboid perk ids and level XP curves, for the Players page's "Adjust
Skills" tool (backed by RCON's addxp - see rcon_commands.cmd_addxp).

Confidence: perk ids are now HIGH confidence for every skill - all confirmed against
a real B42 SandboxVars.lua's MultiplierConfig table (which lists every real perk id,
including the Agility group and every Build 42 addition) pasted by the user
2026-08-11. That paste caught one real bug: Knapping's internal id is `FlintKnapping`,
not `Knapping` as originally guessed from Build 41 modding docs.

XP_REGULAR/XP_PASSIVE remain MEDIUM confidence - researched against B42 community
guides, not the game's own source, and not yet confirmed against a live server.
Regular-curve skills top out around level 10 needing ~9,000 XP for that last level;
passive skills (Fitness/Strength, and by extrapolation the Agility group) cost
roughly 20x more per level.

addxp ADDS xp - it can't set an absolute level directly. xp_for_level() returns the
CUMULATIVE total needed to reach a level from zero, which is what gets sent as the
add amount - a player with existing partial progress in that skill will end up
somewhat past the requested level, not exactly on it. Surfaced as a UI disclaimer,
not hidden.
"""

from __future__ import annotations

# (perk_id, display_name, curve) - curve is "regular" or "passive".
PERKS: list[tuple[str, str, str]] = [
    # --- Combat ---
    ("Axe", "Axe", "regular"),
    ("Blunt", "Blunt", "regular"),
    ("SmallBlunt", "Small Blunt", "regular"),
    ("LongBlade", "Long Blade", "regular"),
    ("SmallBlade", "Small Blade", "regular"),
    ("Spear", "Spear", "regular"),
    ("Maintenance", "Maintenance", "regular"),
    # --- Firearm ---
    ("Aiming", "Aiming", "regular"),
    ("Reloading", "Reloading", "regular"),
    # --- Crafting ---
    ("Woodwork", "Carpentry", "regular"),
    ("Cooking", "Cooking", "regular"),
    ("Farming", "Agriculture", "regular"),
    ("Doctor", "First Aid", "regular"),
    ("Electricity", "Electrical", "regular"),
    ("MetalWelding", "Welding", "regular"),
    ("Mechanics", "Mechanics", "regular"),
    ("Tailoring", "Tailoring", "regular"),
    # --- Survivalist ---
    ("Fishing", "Fishing", "regular"),
    ("Trapping", "Trapping", "regular"),
    ("PlantScavenging", "Foraging", "regular"),
    ("Fitness", "Fitness", "passive"),
    ("Strength", "Strength", "passive"),
    # --- Agility (lower confidence - see file header) ---
    ("Sprinting", "Sprinting", "passive"),
    ("Lightfoot", "Lightfooted", "passive"),
    ("Nimble", "Nimble", "passive"),
    ("Sneak", "Sneaking", "passive"),
    # --- Build 42 additions ---
    # Confirmed against a real B42 SandboxVars.lua's MultiplierConfig table (pasted
    # by the user 2026-08-11) - that table lists every real perk id, including these.
    ("FlintKnapping", "Knapping", "regular"),
    ("Masonry", "Masonry", "regular"),
    ("Pottery", "Pottery", "regular"),
    ("Blacksmith", "Blacksmithing", "regular"),
    ("Glassmaking", "Glassmaking", "regular"),
    ("Carving", "Carving", "regular"),
    ("Husbandry", "Animal Care", "regular"),
    ("Butchering", "Butchering", "regular"),
    ("Tracking", "Tracking", "regular"),
]

PERK_IDS = {p[0] for p in PERKS}

# Per-level XP deltas, index 0 = level 1.
XP_REGULAR = [75, 150, 300, 750, 1500, 3000, 4500, 6000, 7500, 9000]
XP_PASSIVE = [1500, 3000, 6000, 9000, 18000, 30000, 60000, 90000, 120000, 150000]

MAX_LEVEL = len(XP_REGULAR)


class InvalidPerkError(Exception):
    pass


class InvalidLevelError(Exception):
    pass


def xp_for_level(curve: str, level: int) -> int:
    """Cumulative XP needed to reach `level` (1-10) from zero, for the given curve."""
    if not (1 <= level <= MAX_LEVEL):
        raise InvalidLevelError(f"Level must be between 1 and {MAX_LEVEL}.")
    table = XP_PASSIVE if curve == "passive" else XP_REGULAR
    return sum(table[:level])


def perk_curve(perk_id: str) -> str:
    for pid, _label, curve in PERKS:
        if pid == perk_id:
            return curve
    raise InvalidPerkError(f"Unknown perk id: {perk_id}")
