from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import scheduler
from .players import get_online_count

router = APIRouter()


def _response() -> dict:
    schedule = scheduler.get_schedule()
    now = datetime.now().astimezone()
    return {
        **schedule,
        "next_run_at": scheduler.compute_next_run(schedule, now),
        "current_player_count": get_online_count(),
    }


@router.get("/api/schedule")
async def get_schedule():
    return _response()


class ScheduleBody(BaseModel):
    mode: str
    time_of_day: str | None = None
    interval_hours: float | None = None


@router.post("/api/schedule")
async def set_schedule(body: ScheduleBody):
    if body.mode not in {"off", "daily_at", "interval_hours", "when_empty"}:
        raise HTTPException(400, "Invalid mode")
    if body.mode == "daily_at":
        if not body.time_of_day or not _valid_time(body.time_of_day):
            raise HTTPException(400, "time_of_day (HH:MM) is required for daily_at")
    if body.mode in ("interval_hours", "when_empty") and body.mode == "interval_hours":
        if not body.interval_hours or body.interval_hours <= 0:
            raise HTTPException(400, "interval_hours must be > 0")

    scheduler.set_schedule(body.mode, body.time_of_day, body.interval_hours)
    return _response()


def _valid_time(value: str) -> bool:
    try:
        hh, mm = value.split(":")
        return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
    except ValueError:
        return False
