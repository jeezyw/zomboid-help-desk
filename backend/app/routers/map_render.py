from fastapi import APIRouter

from .. import map_render

router = APIRouter()


@router.post("/api/map/render/start")
async def start():
    return map_render.request_render()


@router.get("/api/map/render/status")
async def status():
    return map_render.get_status()


@router.post("/api/map/render/cancel")
async def cancel():
    return map_render.request_cancel()
