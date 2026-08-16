import shutil
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import ini_schema
from ..backup_service import create_backup
from ..change_tracking import record_changes
from ..db import audit
from ..ini_parser import parse_ini, parse_ini_comments, set_ini_scalars
from ..profiles import find_ini, find_profile

router = APIRouter()


class IniUpdate(BaseModel):
    changes: dict[str, Any]


@router.get("/api/ini")
async def ini():
    path = find_ini()
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(path),
        "settings": parse_ini(text),
        "raw": text,
    }


@router.get("/api/ini/fields")
async def ini_fields():
    path = find_ini()
    text = path.read_text(encoding="utf-8", errors="replace")
    settings = parse_ini(text)
    comments = parse_ini_comments(text)
    return {
        "path": str(path),
        "categories": ini_schema.build_schema(settings, comments),
    }


@router.put("/api/ini")
async def update_ini(update: IniUpdate):
    blocked = ini_schema.EXCLUDED_FROM_GENERIC & set(update.changes)
    if blocked:
        raise HTTPException(
            400,
            f"{', '.join(sorted(blocked))} must be changed via the Mod Manager, not the .ini editor.",
        )
    return apply_ini_changes(update.changes)


def apply_ini_changes(changes: dict[str, Any]) -> dict:
    profile = find_profile()
    path = find_ini()
    original = path.read_text(encoding="utf-8", errors="replace")
    current = parse_ini(original)

    record_changes("ini", profile["name"], current, changes)

    backup = path.with_name(
        path.name + f".webui-{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    )
    shutil.copy2(path, backup)

    try:
        create_backup(profile, kind="pre-change", include_save=False)
    except Exception as e:
        audit("backup.pre_change_failed", str(e))

    try:
        updated = set_ini_scalars(original, changes)
        path.write_text(updated, encoding="utf-8")
    except Exception as e:
        if backup.exists():
            shutil.copy2(backup, path)
        raise HTTPException(400, f"Could not apply .ini changes: {e}")

    audit("ini.update", str(changes))

    return {
        "ok": True,
        "backup": str(backup),
        "path": str(path),
        "restart_required": True,
    }
