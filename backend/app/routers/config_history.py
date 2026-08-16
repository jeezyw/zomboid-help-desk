import json

from fastapi import APIRouter, HTTPException

from .. import ini_schema
from ..db import db

router = APIRouter()


def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "changed_at": row[1], "source": row[2], "profile": row[3],
        "key": row[4],
        "old_value": json.loads(row[5]) if row[5] is not None else None,
        "new_value": json.loads(row[6]) if row[6] is not None else None,
    }


@router.get("/api/config-history")
async def config_history(source: str | None = None, profile: str | None = None, limit: int = 100):
    limit = max(1, min(limit, 1000))
    query = "SELECT * FROM config_changes WHERE 1=1"
    params: list = []
    if source:
        query += " AND source=?"
        params.append(source)
    if profile:
        query += " AND profile=?"
        params.append(profile)
    query += " ORDER BY changed_at DESC LIMIT ?"
    params.append(limit)

    with db() as c:
        rows = c.execute(query, params).fetchall()
    return {"changes": [_row_to_dict(r) for r in rows]}


@router.post("/api/config-history/{change_id}/restore")
async def restore_change(change_id: int):
    with db() as c:
        row = c.execute("SELECT * FROM config_changes WHERE id=?", (change_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"Change {change_id} not found")

    change = _row_to_dict(row)
    if change["source"] == "ini" and change["key"] in ini_schema.EXCLUDED_FROM_GENERIC:
        raise HTTPException(
            400,
            f"Restore {change['key']} via the Mod Manager, not generic config history.",
        )

    # Imported lazily to avoid a routers/sandbox <-> routers/ini <-> routers/config_history cycle.
    if change["source"] == "sandbox":
        from .sandbox import apply_sandbox_changes
        result = apply_sandbox_changes({change["key"]: change["old_value"]})
    else:
        from .ini import apply_ini_changes
        result = apply_ini_changes({change["key"]: change["old_value"]})

    return {"ok": True, "restored_key": change["key"], **result}
