"""Steam Workshop item lookups for the Mods page's "Add Mod" tool.

Uses ISteamRemoteStorage/GetPublishedFileDetails/v1 - one of the few Steam Web API
endpoints that works WITHOUT an API key for public items (confirmed common usage
pattern, no key parameter in the request below). That's why this feature is "paste
a Workshop URL/ID" rather than full-text search across the Workshop - search
(IPublishedFileService/QueryFiles) requires a key tied to a Steam account, which the
user opted to skip for v1.

This module only ever READS from Steam - it never downloads mod files itself. Adding
a mod is a two-step, two-tool process by design (see routers/mods.py): this looks up
metadata and queues the Workshop id into WorkshopItems=; Project Zomboid's own
dedicated server binary has a built-in Steam downloader that fetches anything listed
there on its next start. Keeps this app from needing steamcmd or any new privileged
volume access anywhere.
"""

from __future__ import annotations

import re

import httpx

STEAM_APPID = 108600  # Project Zomboid
API_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

_ID_RE = re.compile(r"^\d{4,}$")
_URL_ID_RE = re.compile(r"[?&]id=(\d+)")


class WorkshopLookupError(Exception):
    pass


def extract_workshop_id(query: str) -> str:
    q = query.strip()
    if _ID_RE.match(q):
        return q
    m = _URL_ID_RE.search(q)
    if m:
        return m.group(1)
    raise WorkshopLookupError(
        f'Could not find a Workshop id in "{query}" - paste either the numeric id '
        "or the full steamcommunity.com/sharedfiles/filedetails/?id=... URL."
    )


async def _fetch_details(ids: list[str]) -> dict[str, dict]:
    """Batched lookup - one HTTP call regardless of how many ids. Ids Steam
    couldn't resolve (private/deleted/wrong game) are simply absent from the
    result, not an error - the caller decides what that means."""
    if not ids:
        return {}
    data: dict[str, str] = {"itemcount": str(len(ids))}
    for i, wid in enumerate(ids):
        data[f"publishedfileids[{i}]"] = wid

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(API_URL, data=data)
        except httpx.HTTPError as e:
            raise WorkshopLookupError(f"Could not reach the Steam Workshop API: {e}")

    if r.status_code >= 400:
        raise WorkshopLookupError(f"Steam Workshop API returned HTTP {r.status_code}.")

    body = r.json().get("response", {})
    out: dict[str, dict] = {}
    for item in body.get("publishedfiledetails", []):
        if item.get("result") == 1:
            out[item["publishedfileid"]] = item
    return out


async def lookup_mod(workshop_id: str) -> dict:
    details = await _fetch_details([workshop_id])
    item = details.get(workshop_id)
    if not item:
        raise WorkshopLookupError(
            f"Workshop item {workshop_id} was not found, or is private/deleted."
        )

    if item.get("creator_app_id") != STEAM_APPID and item.get("consumer_app_id") != STEAM_APPID:
        raise WorkshopLookupError(
            f'"{item.get("title", workshop_id)}" does not look like a Project '
            f"Zomboid Workshop item."
        )

    child_ids = [c["publishedfileid"] for c in item.get("children", []) if c.get("publishedfileid")]
    child_details = await _fetch_details(child_ids) if child_ids else {}

    return {
        "workshop_id": item["publishedfileid"],
        "title": item.get("title") or f"Workshop item {workshop_id}",
        "description": (item.get("description") or "").strip(),
        "preview_url": item.get("preview_url") or None,
        "file_size": int(item.get("file_size") or 0),
        "tags": [t["tag"] for t in item.get("tags", []) if t.get("tag")],
        "dependencies": [
            {
                "workshop_id": cid,
                "title": child_details.get(cid, {}).get("title") or f"Workshop item {cid}",
            }
            for cid in child_ids
        ],
    }
