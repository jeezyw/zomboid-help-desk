"""
Discovers Project Zomboid dedicated server config files under the mounted data
directory, and groups them by server-name prefix into "profiles".

PZ dedicated servers name their config files after the server's name, e.g. for a
server named "servertest":

    servertest_SandboxVars.lua
    servertest.ini
    servertest_spawnpoints.lua
    servertest_spawnregions.lua

all living in the same directory (usually .../Zomboid/Server/). We anchor
discovery on *_SandboxVars.lua (every dedicated server has exactly one), derive
the server-name prefix from it, then look for the sibling files by name.

If a bare "SandboxVars.lua" exists with no prefix (unusual, but seen on some
setups), it's treated as an "(unnamed)" profile and we fall back to grabbing the
first .ini found alongside it, since we can't derive its name to look for
"<prefix>.ini".
"""

from __future__ import annotations

import re
from pathlib import Path

SANDBOX_RE = re.compile(r"^(?P<prefix>.*)_SandboxVars\.lua$")


def _sibling(directory: Path, filename: str) -> str | None:
    candidate = directory / filename
    return str(candidate) if candidate.exists() else None


def _first_ini(directory: Path) -> str | None:
    inis = sorted(directory.glob("*.ini"))
    return str(inis[0]) if inis else None


def discover_profiles(data_dir: Path) -> list[dict]:
    if not data_dir.exists():
        return []

    profiles: dict[tuple[str, str], dict] = {}

    for f in data_dir.glob("**/*SandboxVars.lua"):
        if not f.is_file():
            continue

        m = SANDBOX_RE.match(f.name)
        prefix = m.group("prefix") if m else ""
        directory = f.parent

        key = (str(directory), prefix)
        if key in profiles:
            continue

        profiles[key] = {
            "name": prefix or "(unnamed)",
            "directory": str(directory),
            "sandbox_vars": str(f),
            "ini": (
                _sibling(directory, f"{prefix}.ini") if prefix else _first_ini(directory)
            ),
            "spawnpoints": _sibling(directory, f"{prefix}_spawnpoints.lua") if prefix else None,
            "spawnregions": _sibling(directory, f"{prefix}_spawnregions.lua") if prefix else None,
        }

    return sorted(profiles.values(), key=lambda p: (p["directory"], p["name"]))
