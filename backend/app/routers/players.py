"""Player activity: RCON-backed when configured and reachable (authoritative, live),
falling back to best-effort log-scraping (see log_patterns.py) when it isn't. The
background poll_once()/poller_loop() below are the log-scraping fallback - left
untouched by the RCON integration, since a connect-per-call RCON query is cheap
enough to run live inside GET /api/players itself rather than needing its own
background loop. Kick/ban/teleport/give-item live in routers/rcon.py and require
RCON to be configured - see rcon_config.py.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter

from .. import rcon_config
from ..console_log import find_console_log, read_since
from ..db import audit, db, get_setting, set_setting, utcnow
from ..log_patterns import match_player_event
from ..rcon_client import RconError, rcon_execute
from ..rcon_commands import cmd_players, parse_players_response

router = APIRouter()

POLL_INTERVAL_SECONDS = 25
CURSOR_KEY = "player_poller_cursor"
LAST_TICK_KEY = "player_poller_last_tick_at"


def _open_session(name: str, at: str):
    with db() as c:
        c.execute(
            "INSERT INTO player_sessions(player_name, connected_at, disconnected_at) VALUES (?,?,NULL)",
            (name, at),
        )


def _close_latest_open_session(name: str, at: str):
    with db() as c:
        row = c.execute(
            "SELECT id FROM player_sessions WHERE player_name=? AND disconnected_at IS NULL "
            "ORDER BY connected_at DESC LIMIT 1",
            (name,),
        ).fetchone()
        if row:
            c.execute("UPDATE player_sessions SET disconnected_at=? WHERE id=?", (at, row[0]))


def close_all_open_sessions(reason: str = ""):
    now = utcnow()
    with db() as c:
        c.execute(
            "UPDATE player_sessions SET disconnected_at=? WHERE disconnected_at IS NULL",
            (now,),
        )
    audit("players.sessions_closed", reason)


def get_online_count() -> int:
    with db() as c:
        row = c.execute("SELECT COUNT(*) FROM player_sessions WHERE disconnected_at IS NULL").fetchone()
        return row[0] if row else 0


async def poll_once():
    path = find_console_log()
    if not path:
        return

    cursor = get_setting(CURSOR_KEY)
    offset = int(cursor) if cursor else None

    # First-ever run: seed the cursor at the current end of file rather than
    # replaying (potentially thousands of) historical lines through the matcher.
    if offset is None:
        set_setting(CURSOR_KEY, str(path.stat().st_size))
        return

    # server-console.txt lines don't carry a reliably parseable per-line timestamp
    # (unlike the old `docker logs --timestamps` source), so connect/disconnect
    # events are stamped with wall-clock time at poll time - accurate to within one
    # poll interval, not to the exact second the event happened in-game.
    lines, new_offset = read_since(path, offset)
    now = utcnow()

    for text in lines:
        match = match_player_event(text)
        if not match:
            continue
        event, name = match
        if event == "connect":
            _close_latest_open_session(name, at=now)  # defensive: guard against a missed disconnect
            _open_session(name, at=now)
        else:
            _close_latest_open_session(name, at=now)

    set_setting(CURSOR_KEY, str(new_offset))


async def poller_loop():
    while True:
        try:
            await poll_once()
            set_setting(LAST_TICK_KEY, utcnow())
        except Exception as e:
            audit("player_poller.error", str(e))
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _duration_seconds(connected_at: str, disconnected_at: str | None) -> int:
    start = datetime.fromisoformat(connected_at)
    end = datetime.fromisoformat(disconnected_at) if disconnected_at else datetime.now(timezone.utc)
    return max(0, int((end - start).total_seconds()))


def _recent_sessions_from_db(limit: int = 50) -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT player_name, connected_at, disconnected_at FROM player_sessions "
            "WHERE disconnected_at IS NOT NULL ORDER BY disconnected_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"name": name, "connected_at": at, "disconnected_at": dat,
         "duration_seconds": _duration_seconds(at, dat)}
        for name, at, dat in rows
    ]


def _open_sessions_from_db() -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT player_name, connected_at FROM player_sessions "
            "WHERE disconnected_at IS NULL ORDER BY connected_at DESC"
        ).fetchall()
    return [
        {"name": name, "connected_at": at, "duration_seconds": _duration_seconds(at, None)}
        for name, at in rows
    ]


def _open_session_connected_at(name: str) -> str | None:
    """Best-effort cross-reference: the log-scraping poller may still be running
    independently of RCON and could already know when this player connected."""
    with db() as c:
        row = c.execute(
            "SELECT connected_at FROM player_sessions WHERE player_name=? AND disconnected_at IS NULL "
            "ORDER BY connected_at DESC LIMIT 1",
            (name,),
        ).fetchone()
    return row[0] if row else None


async def rcon_players_snapshot() -> list[str] | None:
    """None = source unavailable (not configured or the call failed for any reason);
    [] = available, nobody currently online."""
    try:
        host, port, password = rcon_config.get_rcon_target()
    except rcon_config.RconNotConfiguredError:
        return None
    try:
        raw = await rcon_execute(host, port, password, cmd_players(), connect_timeout=2.0)
    except RconError:
        return None
    return parse_players_response(raw)


@router.get("/api/players")
async def players():
    rcon_names = await rcon_players_snapshot()
    recent = _recent_sessions_from_db()

    last_tick = get_setting(LAST_TICK_KEY)
    poller_healthy = False
    if last_tick:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_tick)).total_seconds()
        poller_healthy = age < POLL_INTERVAL_SECONDS * 3

    if rcon_names is not None:
        online = []
        for name in rcon_names:
            connected_at = _open_session_connected_at(name)
            online.append({
                "name": name,
                "connected_at": connected_at,
                "duration_seconds": _duration_seconds(connected_at, None) if connected_at else 0,
            })
        return {
            "online": online,
            "recent": recent,
            "poller_healthy": poller_healthy,
            "source": "rcon",
            "disclaimer": None,
        }

    return {
        "online": _open_sessions_from_db(),
        "recent": recent,
        "poller_healthy": poller_healthy,
        "source": "log",
        "disclaimer": (
            "Player status is inferred from server console logs via best-effort "
            "pattern matching (RCON not configured or unreachable) - verify against "
            "your server's real log format."
        ),
    }
