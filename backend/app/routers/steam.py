from fastapi import APIRouter

from .. import steam_files

router = APIRouter()


@router.post("/api/steam/install")
async def install():
    # {ok: False, detail, status} on an already-running job, same shape as
    # restart_manager.request_action's "already pending" rejection - not an
    # HTTP error, just a normal result the frontend already knows how to show.
    return steam_files.request_install()


@router.get("/api/steam/status")
async def status():
    return steam_files.get_status()
