"""PZ dedicated-server RCON command strings.

Isolated in one small file for the same reason log_patterns.py isolates its regexes:
these are transcribed from documented Project Zomboid console commands and have NOT
been verified against a live server. Confidence levels:

  HIGH   - players, kickuser, unbanuser, teleport, servermsg (confirmed against a
           live server 2026-08-10). additem was also confirmed then - item id must
           be unquoted, e.g. `additem "user" Base.308Bullets 2`, NOT
           `additem "user" "Base.308Bullets" 2` - but there's no cmd_additem here
           anymore: additem is built client-side in serverCommands.ts's Command
           Builder (RCON Tools tab) via the generic /api/rcon/command pass-through,
           not its own backend endpoint, since give-item as a dedicated feature was
           removed as redundant with the Command Builder.
  MEDIUM - banuser's flag syntax (-ip, -r "reason") - verify against real `help`
           output before relying on ban. addxp's syntax (`addxp "user" Perk=amount`,
           perk unquoted, mirroring additem's unquoted-argument convention) - NOT yet
           confirmed against a live server, verify before relying on it. skill_xp.py
           carries the same confidence caveat for the perk id list and XP curve.
           godmodeplayer's syntax (`godmodeplayer "user" -true`/`-false`) is
           transcribed directly from a real server's `help` output (2026-08-11) but
           not yet live-tested. Note RCON has no query command for a player's
           CURRENT godmode state - the frontend toggle reflects what this app last
           told the server, not verified live truth (see Players.tsx).

POST /api/rcon/test runs cmd_help() on a successful auth specifically so the real
`help` output can be diffed against what's assumed here.
"""

from __future__ import annotations


def cmd_players() -> str:
    return "players"


def cmd_kick(username: str) -> str:
    return f'kickuser "{username}"'


def cmd_ban(username: str, ip: bool = False, reason: str | None = None) -> str:
    parts = [f'banuser "{username}"']
    if ip:
        parts.append("-ip")
    if reason:
        parts.append(f'-r "{reason}"')
    return " ".join(parts)


def cmd_unban(username: str) -> str:
    return f'unbanuser "{username}"'


def cmd_teleport(username: str, to_username: str) -> str:
    return f'teleport "{username}" "{to_username}"'


def cmd_addxp(username: str, perk: str, amount: int) -> str:
    # Unverified against a live server - see this file's header. Perk name unquoted,
    # matching additem's confirmed unquoted-item-id convention.
    return f'addxp "{username}" {perk}={amount}'


def cmd_godmode_player(username: str, enabled: bool) -> str:
    return f'godmodeplayer "{username}" -{"true" if enabled else "false"}'


def cmd_servermsg(message: str) -> str:
    return f'servermsg "{message}"'


def cmd_help() -> str:
    return "help"


def parse_players_response(text: str) -> list[str]:
    """Expected shape (best-effort, unverified): a header line followed by one
    "-name" line per connected player, e.g. "Players connected (2):\\n-Jeezy\\n-Bob"."""
    names = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("-"):
            names.append(line[1:].strip())
    return names
