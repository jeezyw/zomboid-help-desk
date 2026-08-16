"""Scheduled Restarts: a single-row schedule config, evaluated once a minute by a
background asyncio task (see main.py's lifespan). Restarts go through
restart_manager, which sends an RCON warning (if configured) some number of minutes
before actually restarting - see restart_manager.py.

time_of_day is interpreted in the container's LOCAL time (datetime.now(), not UTC) to
match an admin's intuitive "restart at 4am" - set TZ in docker-compose.yml so this is
predictable rather than silently defaulting to UTC.

The due-check for daily_at/interval_hours fires restart_manager.request_action()
*warning_minutes early* so the RCON warning has time to play out and the actual
restart still lands on the configured time/interval, not warning_minutes after it.
when_empty is reactive (there's no way to know in advance when the server will go
empty), so for that mode the actual restart unavoidably lands warning_minutes after
the empty+cooldown condition is first observed, not before.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from . import restart_manager
from .db import audit, db, utcnow

TICK_SECONDS = 60
DEFAULT_WHEN_EMPTY_COOLDOWN_HOURS = 6


def _row_to_dict(row) -> dict:
    return {
        "mode": row[1], "time_of_day": row[2], "interval_hours": row[3],
        "last_run_at": row[4], "updated_at": row[5],
    }


def get_schedule() -> dict:
    with db() as c:
        row = c.execute("SELECT * FROM scheduled_restarts WHERE id=1").fetchone()
    if not row:
        return {"mode": "off", "time_of_day": None, "interval_hours": None,
                "last_run_at": None, "updated_at": utcnow()}
    return _row_to_dict(row)


def set_schedule(mode: str, time_of_day: str | None, interval_hours: float | None) -> dict:
    with db() as c:
        c.execute(
            "INSERT INTO scheduled_restarts(id, mode, time_of_day, interval_hours, last_run_at, updated_at) "
            "VALUES (1,?,?,?,NULL,?) "
            "ON CONFLICT(id) DO UPDATE SET mode=excluded.mode, time_of_day=excluded.time_of_day, "
            "interval_hours=excluded.interval_hours, last_run_at=NULL, updated_at=excluded.updated_at",
            (mode, time_of_day, interval_hours, utcnow()),
        )
    audit("schedule.update", f"mode={mode}")
    return get_schedule()


def _set_last_run(at: datetime):
    with db() as c:
        c.execute("UPDATE scheduled_restarts SET last_run_at=? WHERE id=1", (at.isoformat(),))


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def compute_next_run(schedule: dict, now: datetime) -> str | None:
    mode = schedule["mode"]
    if mode == "off" or mode == "when_empty":
        return None  # when_empty is conditional, not a fixed timestamp

    if mode == "daily_at" and schedule["time_of_day"]:
        hh, mm = map(int, schedule["time_of_day"].split(":"))
        candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.isoformat()

    if mode == "interval_hours" and schedule["interval_hours"]:
        base = _parse(schedule["last_run_at"]) if schedule["last_run_at"] else _parse(schedule["updated_at"])
        return (base + timedelta(hours=schedule["interval_hours"])).isoformat()

    return None


async def _tick(get_online_count):
    schedule = get_schedule()
    mode = schedule["mode"]
    if mode == "off":
        return

    now = datetime.now().astimezone()
    warning_minutes = restart_manager.get_warning_minutes()
    due = False

    if mode == "daily_at" and schedule["time_of_day"]:
        hh, mm = map(int, schedule["time_of_day"].split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        warn_at = target - timedelta(minutes=warning_minutes)
        already_ran_today = (
            schedule["last_run_at"] is not None
            and _parse(schedule["last_run_at"]).astimezone().date() == now.date()
        )
        due = now.hour == warn_at.hour and now.minute == warn_at.minute and not already_ran_today

    elif mode == "interval_hours" and schedule["interval_hours"]:
        base = _parse(schedule["last_run_at"]) if schedule["last_run_at"] else _parse(schedule["updated_at"])
        due = now - base.astimezone() >= timedelta(hours=schedule["interval_hours"]) - timedelta(minutes=warning_minutes)

    elif mode == "when_empty":
        cooldown_hours = schedule["interval_hours"] or DEFAULT_WHEN_EMPTY_COOLDOWN_HOURS
        base = _parse(schedule["last_run_at"]) if schedule["last_run_at"] else _parse(schedule["updated_at"])
        cooldown_ok = now - base.astimezone() >= timedelta(hours=cooldown_hours)
        due = cooldown_ok and get_online_count() == 0

    if due:
        # Sync call: request_action() only spawns the background warn-then-restart
        # task and returns immediately. last_run_at is set right away (not after the
        # delayed restart actually completes) so the next several ticks during the
        # warning window don't re-trigger - request_action()'s own single-pending
        # guard is a second layer of the same protection.
        restart_manager.request_action("restart", reason=f"scheduled:{mode}")
        _set_last_run(now)


async def restart_loop():
    # Imported lazily: routers/players.py depends on earlier-initialized state,
    # avoid a module-load-order cycle with main.py.
    from .routers.players import get_online_count

    while True:
        try:
            await _tick(get_online_count)
        except Exception as e:
            audit("scheduler.error", str(e))
        await asyncio.sleep(TICK_SECONDS)
