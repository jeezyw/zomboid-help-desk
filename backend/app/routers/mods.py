from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config, workshop_api
from ..ini_parser import parse_ini, parse_list_field, render_list_field
from ..mod_meta import scan_workshop_mods
from ..profiles import find_ini
from .ini import apply_ini_changes

router = APIRouter()


def _current_lists() -> tuple[list[str], list[str]]:
    path = find_ini()
    settings = parse_ini(path.read_text(encoding="utf-8", errors="replace"))
    mods = parse_list_field(settings.get("Mods"))
    workshop_items = parse_list_field(settings.get("WorkshopItems"))
    return mods, workshop_items


def _aliases(m: dict) -> set[str]:
    # Mods= can reference either a mod's declared "id=" (from mod.info) or its
    # on-disk folder name - real Workshop mods aren't consistent about which, and
    # mod.info doesn't always declare an id at all (mod_id then already equals
    # folder_name via scan_workshop_mods' fallback). Match on both.
    return {m["mod_id"], m["folder_name"]}


@router.get("/api/mods")
async def mods():
    installed = scan_workshop_mods(config.WORKSHOP)
    load_order, workshop_items = _current_lists()
    enabled_set = set(load_order)

    for m in installed:
        m["enabled"] = bool(_aliases(m) & enabled_set)

    return {
        "installed": installed,
        "load_order": load_order,
        "workshop_items": workshop_items,
        "ini_path": str(find_ini()),
    }


class ModIdBody(BaseModel):
    mod_id: str


def _installed_by_alias() -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for m in scan_workshop_mods(config.WORKSHOP):
        for alias in _aliases(m):
            lookup[alias] = m
    return lookup


def enable_mod_by_id(mod_id: str) -> dict:
    """Plain function version of POST /api/mods/enable's logic, so other
    backend code (e.g. live_map.py's mod-install flow) can enable a mod
    without going through the HTTP layer - same lazy-import-from-a-router
    pattern restart_manager.py already uses for routers/players.py."""
    load_order, workshop_items = _current_lists()
    lookup = _installed_by_alias()
    match = lookup.get(mod_id)
    aliases = _aliases(match) if match else {mod_id}

    if aliases & set(load_order):
        return {"ok": True, "note": "Already enabled."}

    load_order = [*load_order, mod_id]
    workshop_id = match.get("workshop_id") if match else None
    if workshop_id and workshop_id not in workshop_items:
        workshop_items = [*workshop_items, workshop_id]

    return apply_ini_changes({
        "Mods": render_list_field(load_order),
        "WorkshopItems": render_list_field(workshop_items),
    })


@router.post("/api/mods/enable")
async def enable_mod(body: ModIdBody):
    return enable_mod_by_id(body.mod_id)


@router.post("/api/mods/disable")
async def disable_mod(body: ModIdBody):
    return _remove_mod_reference(body.mod_id)


@router.delete("/api/mods/reference/{mod_id}")
async def remove_mod_reference(mod_id: str):
    result = _remove_mod_reference(mod_id)
    return {**result, "note": "Removed from server config only. Mod files were not deleted from disk."}


def _remove_mod_reference(mod_id: str) -> dict:
    load_order, workshop_items = _current_lists()
    lookup = _installed_by_alias()
    match = lookup.get(mod_id)
    aliases = _aliases(match) if match else {mod_id}

    if not (aliases & set(load_order)):
        return {"ok": True, "note": "Was not enabled."}

    # Remove every alias that's present, not just the one string the caller sent -
    # defends against a mod ending up double-referenced (by both id and folder name).
    new_load_order = [x for x in load_order if x not in aliases]
    workshop_id = match.get("workshop_id") if match else None

    still_needed = {lookup[x]["workshop_id"] for x in new_load_order if x in lookup}
    if workshop_id and workshop_id not in still_needed and workshop_id in workshop_items:
        workshop_items = [w for w in workshop_items if w != workshop_id]

    return apply_ini_changes({
        "Mods": render_list_field(new_load_order),
        "WorkshopItems": render_list_field(workshop_items),
    })


class ReorderBody(BaseModel):
    order: list[str]


@router.post("/api/mods/reorder")
async def reorder_mods(body: ReorderBody):
    load_order, _ = _current_lists()
    if sorted(body.order) != sorted(load_order):
        raise HTTPException(400, "New order must contain exactly the currently-enabled mods (reorder only).")

    return apply_ini_changes({"Mods": render_list_field(body.order)})


def _annotate_workshop_item(item: dict, workshop_items: list[str], installed_ids: set[str]) -> dict:
    return {
        **item,
        "already_queued": item["workshop_id"] in workshop_items,
        "already_installed": item["workshop_id"] in installed_ids,
    }


@router.get("/api/mods/workshop-lookup")
async def workshop_lookup(query: str):
    """Looks up ONE Workshop item by pasted URL/id - see workshop_api.py's header
    for why this is a lookup tool, not a search engine, and why it never downloads
    anything itself."""
    try:
        workshop_id = workshop_api.extract_workshop_id(query)
        details = await workshop_api.lookup_mod(workshop_id)
    except workshop_api.WorkshopLookupError as e:
        raise HTTPException(400, str(e))

    _, workshop_items = _current_lists()
    installed_ids = {m["workshop_id"] for m in scan_workshop_mods(config.WORKSHOP)}

    details = _annotate_workshop_item(details, workshop_items, installed_ids)
    details["dependencies"] = [
        _annotate_workshop_item(d, workshop_items, installed_ids) for d in details["dependencies"]
    ]
    return details


class WorkshopQueueBody(BaseModel):
    workshop_ids: list[str]


@router.post("/api/mods/workshop-queue")
async def workshop_queue(body: WorkshopQueueBody):
    """Adds Workshop id(s) to WorkshopItems= only - does NOT touch Mods= (there's
    nothing on disk to enable yet) and does NOT download anything. The dedicated
    server's own built-in Steam downloader fetches anything listed here the next
    time it starts; after that, the newly-downloaded mod shows up in the Installed
    Mods list above like any other and can be enabled normally."""
    _, workshop_items = _current_lists()
    added = [wid for wid in body.workshop_ids if wid and wid not in workshop_items]
    if not added:
        return {"ok": True, "added": [], "note": "Already queued."}

    new_workshop_items = [*workshop_items, *added]
    result = apply_ini_changes({"WorkshopItems": render_list_field(new_workshop_items)})
    return {
        **result,
        "added": added,
        "note": "Queued. Restart the server to download - it'll then appear in "
                "Installed Mods below, ready to enable.",
    }


@router.post("/api/mods/workshop-unqueue")
async def workshop_unqueue(body: ModIdBody):
    """Cancels a pending (not-yet-downloaded) Workshop item - removes it from
    WorkshopItems= only. Refuses if it's already backing an enabled mod (that's
    what "Remove" in Installed Mods is for, which also cleans up Mods=)."""
    load_order, workshop_items = _current_lists()
    if body.mod_id not in workshop_items:
        return {"ok": True, "note": "Was not queued."}

    lookup = _installed_by_alias()
    still_needed = {lookup[x]["workshop_id"] for x in load_order if x in lookup}
    if body.mod_id in still_needed:
        raise HTTPException(400, "That Workshop item backs a currently-enabled mod - remove the mod instead.")

    new_workshop_items = [w for w in workshop_items if w != body.mod_id]
    return apply_ini_changes({"WorkshopItems": render_list_field(new_workshop_items)})
