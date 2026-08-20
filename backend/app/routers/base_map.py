from fastapi import APIRouter

from .. import base_map

router = APIRouter()


@router.post("/api/map/base/tile/start")
async def start():
    return base_map.request_tile()


@router.get("/api/map/base/tile/status")
async def status():
    return base_map.get_status()


@router.post("/api/map/base/tile/cancel")
async def cancel():
    return base_map.request_cancel()
