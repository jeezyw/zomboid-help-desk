"""Game objectives / to-do list for the Objectives page.

Deliberately a flat JSON file at <webui-data>/todos.json, NOT a table in webui.db
like everything else in this app - the user specifically wants this as its own
plain, human-readable/editable file living alongside webui.db, not buried in
sqlite. Written atomically (write to a temp file, then rename over the real one)
so a crash or container restart mid-write can't leave a half-written, corrupt file.

No categories - just free-text objectives with a status and a priority, ordered by
importance. List POSITION in the JSON array IS the importance ranking (index 0 =
most important) - there's no separate order field to keep in sync with it. Priority
is a separate, purely visual signal (row tint in the frontend) - it doesn't affect
ordering at all, only status/position do.
"""

from __future__ import annotations

import uuid
import json
from typing import Any

from . import config
from .db import utcnow

TODOS_PATH = config.DB.parent / "todos.json"

STATUSES: list[dict[str, str]] = [
    {"id": "planned", "title": "Planned"},
    {"id": "in_progress", "title": "In Progress"},
    {"id": "blocked", "title": "Blocked"},
    {"id": "complete", "title": "Complete"},
]
VALID_STATUS_IDS = {s["id"] for s in STATUSES}
DEFAULT_STATUS = "planned"

PRIORITIES: list[dict[str, str]] = [
    {"id": "urgent", "title": "Urgent"},
    {"id": "moderate", "title": "Moderate"},
    {"id": "low", "title": "Low"},
    {"id": "wish", "title": "Wish"},
]
VALID_PRIORITY_IDS = {p["id"] for p in PRIORITIES}
DEFAULT_PRIORITY = "moderate"


def _read() -> list[dict[str, Any]]:
    if not TODOS_PATH.exists():
        return []
    try:
        data = json.loads(TODOS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    # Backfill for objectives saved before priority/blocker existed - self-heals on
    # read, persisted back to disk next time anything writes.
    for item in data:
        item.setdefault("priority", DEFAULT_PRIORITY)
        item.setdefault("blocker", "")
    return data


def _write(items: list[dict[str, Any]]) -> None:
    TODOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TODOS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
    tmp.replace(TODOS_PATH)


def list_todos() -> list[dict[str, Any]]:
    return _read()


def add_todo(text: str, priority: str = DEFAULT_PRIORITY) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Objective text cannot be empty.")
    if priority not in VALID_PRIORITY_IDS:
        raise ValueError(f"Unknown priority: {priority}")

    item = {
        "id": uuid.uuid4().hex,
        "text": text,
        "status": DEFAULT_STATUS,
        "priority": priority,
        "blocker": "",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    items = _read()
    items.append(item)  # new objectives start at the bottom of the priority order
    _write(items)
    return item


def set_status(item_id: str, status: str) -> dict[str, Any]:
    if status not in VALID_STATUS_IDS:
        raise ValueError(f"Unknown status: {status}")
    items = _read()
    for item in items:
        if item["id"] == item_id:
            item["status"] = status
            item["updated_at"] = utcnow()
            _write(items)
            return item
    raise KeyError(item_id)


def set_priority(item_id: str, priority: str) -> dict[str, Any]:
    if priority not in VALID_PRIORITY_IDS:
        raise ValueError(f"Unknown priority: {priority}")
    items = _read()
    for item in items:
        if item["id"] == item_id:
            item["priority"] = priority
            item["updated_at"] = utcnow()
            _write(items)
            return item
    raise KeyError(item_id)


def set_blocker(item_id: str, blocker: str) -> dict[str, Any]:
    """Free-text note on what's blocking an objective - independent of status, so
    it survives being toggled off Blocked and back without re-typing (the frontend
    only shows/edits this field while status is "blocked", but nothing here forces
    that - an empty string just clears it)."""
    items = _read()
    for item in items:
        if item["id"] == item_id:
            item["blocker"] = blocker.strip()
            item["updated_at"] = utcnow()
            _write(items)
            return item
    raise KeyError(item_id)


def reorder_todos(order: list[str]) -> list[dict[str, Any]]:
    items = _read()
    by_id = {i["id"]: i for i in items}
    if sorted(order) != sorted(by_id):
        raise ValueError("New order must contain exactly the current objectives.")
    reordered = [by_id[i] for i in order]
    _write(reordered)
    return reordered


def delete_todo(item_id: str) -> bool:
    items = _read()
    remaining = [i for i in items if i["id"] != item_id]
    if len(remaining) == len(items):
        return False
    _write(remaining)
    return True
