from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from .. import live_map, map_calibration

router = APIRouter()


class CalibrationPoint(BaseModel):
    world_x: float
    world_y: float
    pixel_x: float
    pixel_y: float


class SetCalibration(BaseModel):
    points: list[CalibrationPoint]


@router.get("/api/map/config")
async def map_config():
    # Always returns 200, even when the feature is off - the frontend polls
    # this first to decide whether to show the Live Map tab's real content or
    # an explanatory empty state, same pattern as /api/server's
    # docker_control_enabled flag.
    enabled = live_map.is_enabled()
    return {
        "enabled": enabled,
        "tiles_available": live_map.tiles_available() if enabled else False,
    }


@router.get("/api/map/players")
async def map_players():
    if not live_map.is_enabled():
        return {"players": [], "updated_at": None, "stale": True}
    return live_map.read_positions()


@router.get("/api/map/setup-status")
async def map_setup_status():
    return {
        "mod_installed": live_map.mod_installed(),
        "enabled": live_map.is_enabled(),
        "tiles_available": live_map.tiles_available(),
    }


@router.post("/api/map/setup")
async def map_setup():
    return live_map.setup()


@router.get("/api/map/mod-download")
async def download_mod():
    if not live_map.MOD_SOURCE_DIR.is_dir():
        raise HTTPException(404, "Mod files not found in this image.")
    return Response(
        content=live_map.build_mod_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="ZHDPositionTracker.zip"'},
    )


@router.get("/api/map/calibration")
async def get_calibration():
    return map_calibration.get_calibration()


@router.post("/api/map/calibration")
async def set_calibration(body: SetCalibration):
    if len(body.points) != 3:
        raise HTTPException(400, "Calibration needs exactly 3 points.")
    try:
        return map_calibration.set_calibration([p.model_dump() for p in body.points])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/api/map/calibration")
async def delete_calibration():
    map_calibration.clear_calibration()
    return {"ok": True}
