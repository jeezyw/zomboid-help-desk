from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import backup_service
from ..profiles import find_profile

router = APIRouter()


@router.get("/api/backups")
async def list_backups(profile: str | None = None):
    name = profile or find_profile()["name"]
    return {
        "backups": backup_service.list_backups(name),
        "retention_policy": backup_service.get_retention_policy(),
    }


class CreateBackupBody(BaseModel):
    kind: str = "manual"
    include_save: bool = False
    note: str = ""


@router.post("/api/backups")
async def create_backup(body: CreateBackupBody):
    profile = find_profile()
    return backup_service.create_backup(profile, kind=body.kind, include_save=body.include_save, note=body.note)


@router.get("/api/backups/{backup_id}/download")
async def download_backup(backup_id: int):
    row = backup_service.get_backup(backup_id)
    if not row:
        raise HTTPException(404, f"Backup {backup_id} not found")
    return FileResponse(row["path"], filename=f"{row['profile']}-{row['created_at']}.tar.gz")


@router.post("/api/backups/{backup_id}/restore")
async def restore_backup(backup_id: int):
    profile = find_profile()
    try:
        return backup_service.restore_backup(profile, backup_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/api/backups/{backup_id}")
async def delete_backup(backup_id: int):
    row = backup_service.get_backup(backup_id)
    if not row:
        raise HTTPException(404, f"Backup {backup_id} not found")
    backup_service.delete_backup(backup_id)
    return {"ok": True}


@router.get("/api/backups/retention")
async def get_retention():
    return backup_service.get_retention_policy()


@router.put("/api/backups/retention")
async def set_retention(policy: dict):
    backup_service.set_retention_policy(policy)
    return backup_service.get_retention_policy()


@router.post("/api/backups/sweep")
async def sweep(profile: str | None = None):
    name = profile or find_profile()["name"]
    return backup_service.sweep_retention(name)


@router.get("/api/backups/save-dir")
async def get_save_dir():
    profile = find_profile()
    override = backup_service.get_save_dir_override(profile["name"])
    resolved = backup_service.discover_save_dir(profile)
    return {
        "path": str(resolved) if resolved else None,
        "guessed": resolved is not None and not override,
        "override": override,
    }


class SaveDirBody(BaseModel):
    profile: str
    path: str


@router.post("/api/backups/save-dir")
async def set_save_dir(body: SaveDirBody):
    backup_service.set_save_dir_override(body.profile, body.path)
    return {"ok": True}
