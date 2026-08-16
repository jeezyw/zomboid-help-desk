import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import sandbox_presets, sandbox_schema
from ..backup_service import create_backup
from ..change_tracking import record_changes
from ..db import audit
from ..profiles import find_profile, find_sandbox

router = APIRouter()


def parse_lua_scalar(value: str) -> Any:
    value = value.strip().rstrip(",")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() == "nil":
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def _parse_sandbox_full(text: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Single pass that parses settings AND captures each setting's preceding
    comment block (real SandboxVars.lua files document nearly every field with a
    "-- description" / "-- N = Label" comment immediately above it - a much better
    source of truth than a hand-written guess, and one that scales to every field
    in the file instead of just the ones curated in sandbox_schema.KNOWN_FIELDS)."""
    result: dict[str, Any] = {}
    comments: dict[str, str] = {}
    stack: list[str] = []
    pending: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            pending = []  # blank line breaks the comment-to-setting association
            continue

        if line.startswith("--"):
            pending.append(line.lstrip("-").strip())
            continue

        # Supports common:
        # ZombieLore = {
        #   PopulationMultiplier = 1.0,
        # }
        m = re.match(r"^([A-Za-z_][\w]*)\s*=\s*\{", line)
        if m:
            # The whole file is wrapped in a top-level "SandboxVars = { ... }"
            # table; treat it as transparent so keys inside it aren't prefixed
            # with "SandboxVars." (which would never match KNOWN_FIELDS).
            if not (not stack and m.group(1) == "SandboxVars"):
                stack.append(m.group(1))
            pending = []
            continue

        if line.startswith("}") or line.startswith("},"):
            if stack:
                stack.pop()
            pending = []
            continue

        m = re.match(r"^([A-Za-z_][\w]*)\s*=\s*(.+?)(?:,)?$", line)
        if not m:
            pending = []
            continue

        key, raw_value = m.groups()
        full_key = ".".join(stack + [key])
        result[full_key] = parse_lua_scalar(raw_value)
        if pending:
            comments[full_key] = "\n".join(pending)
        pending = []

    return result, comments


def parse_sandbox(text: str) -> dict[str, Any]:
    settings, _ = _parse_sandbox_full(text)
    return settings


def parse_sandbox_comments(text: str) -> dict[str, str]:
    _, comments = _parse_sandbox_full(text)
    return comments


def set_flat_scalars(original: str, changes: dict[str, Any]) -> str:
    lines = original.splitlines()
    stack: list[str] = []
    remaining = dict(changes)
    output: list[str] = []

    for line in lines:
        stripped = line.strip()

        open_m = re.match(r"^([A-Za-z_][\w]*)\s*=\s*\{", stripped)
        if open_m:
            # Mirror parse_sandbox: the outer "SandboxVars" wrapper is transparent.
            if not (not stack and open_m.group(1) == "SandboxVars"):
                stack.append(open_m.group(1))
            output.append(line)
            continue

        if stripped.startswith("}") or stripped.startswith("},"):
            if stack:
                stack.pop()
            output.append(line)
            continue

        m = re.match(r"^(\s*)([A-Za-z_][\w]*)(\s*=\s*)(.+?)(,\s*)?$", line)
        if not m:
            output.append(line)
            continue

        indent, key, eq, old, comma = m.groups()
        path = ".".join(stack + [key])

        if path not in remaining:
            output.append(line)
            continue

        value = remaining.pop(path)

        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = "nil"
        elif isinstance(value, str):
            rendered = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        else:
            rendered = str(value)

        output.append(f"{indent}{key}{eq}{rendered}{comma or ''}")

    if remaining:
        raise ValueError(
            "Settings not found in existing SandboxVars.lua: "
            + ", ".join(remaining)
        )

    return "\n".join(output) + ("\n" if original.endswith("\n") else "")


class SandboxUpdate(BaseModel):
    changes: dict[str, Any]


@router.get("/api/sandbox")
async def sandbox():
    path = find_sandbox()
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(path),
        "settings": parse_sandbox(text),
        "raw": text,
    }


def _current_fields_payload() -> dict:
    path = find_sandbox()
    text = path.read_text(encoding="utf-8", errors="replace")
    settings, comments = _parse_sandbox_full(text)
    return {
        "path": str(path),
        "categories": sandbox_schema.build_schema(settings, comments),
        # The full static category list (unlike "categories" above, not filtered to
        # only ones with fields right now) - so the Sort Mode picker can always
        # target every real category, even one that's currently empty.
        "all_categories": [{"id": c["id"], "title": c["title"]} for c in sandbox_schema.CATEGORIES],
    }


@router.get("/api/sandbox/fields")
async def sandbox_fields():
    return _current_fields_payload()


class FavoriteBody(BaseModel):
    key: str
    favorite: bool


@router.post("/api/sandbox/favorite")
async def set_favorite(body: FavoriteBody):
    sandbox_schema.set_favorite(body.key, body.favorite)
    return _current_fields_payload()


class CategoryBody(BaseModel):
    key: str
    category: str | None = None


@router.post("/api/sandbox/category")
async def set_category(body: CategoryBody):
    valid_ids = {c["id"] for c in sandbox_schema.CATEGORIES}
    if body.category is not None and body.category not in valid_ids:
        raise HTTPException(400, f"'{body.category}' is not a valid category.")
    sandbox_schema.set_category_override(body.key, body.category)
    return _current_fields_payload()


@router.put("/api/sandbox")
async def update_sandbox(update: SandboxUpdate):
    return apply_sandbox_changes(update.changes)


@router.get("/api/sandbox/presets")
async def list_sandbox_presets():
    return {"presets": sandbox_presets.list_presets()}


class SavePresetBody(BaseModel):
    name: str


@router.post("/api/sandbox/presets")
async def save_sandbox_preset(body: SavePresetBody):
    profile = find_profile()
    settings = parse_sandbox(find_sandbox().read_text(encoding="utf-8", errors="replace"))
    try:
        preset = sandbox_presets.save_preset(body.name, profile["name"], settings)
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit("sandbox.preset_saved", f"{preset['name']} ({preset['field_count']} fields)")
    return preset


@router.delete("/api/sandbox/presets/{preset_id}")
async def delete_sandbox_preset(preset_id: int):
    if not sandbox_presets.delete_preset(preset_id):
        raise HTTPException(404, "Preset not found.")
    return {"ok": True}


@router.post("/api/sandbox/presets/{preset_id}/apply")
async def apply_sandbox_preset(preset_id: int):
    preset = sandbox_presets.get_preset(preset_id)
    if not preset:
        raise HTTPException(404, "Preset not found.")

    # Presets can be saved from - and later applied to - different profiles, or
    # applied after the file itself changed shape (a mod added/removed since the
    # preset was saved), so a saved key may no longer exist in the CURRENT file.
    # Apply whatever still matches rather than failing the whole preset over a
    # handful of stale keys - set_flat_scalars (used by apply_sandbox_changes)
    # raises if asked to write a key it can't find, so those must be filtered out
    # up front, not just left for it to reject.
    current = parse_sandbox(find_sandbox().read_text(encoding="utf-8", errors="replace"))
    applicable = {k: v for k, v in preset["settings"].items() if k in current}
    skipped = [k for k in preset["settings"] if k not in current]

    if not applicable:
        raise HTTPException(400, "None of this preset's settings exist in the current SandboxVars.lua.")

    result = apply_sandbox_changes(applicable)
    audit("sandbox.preset_applied", f"{preset['name']} ({len(applicable)} fields, {len(skipped)} skipped)")
    return {**result, "applied_count": len(applicable), "skipped": skipped}


def apply_sandbox_changes(changes: dict[str, Any]) -> dict:
    profile = find_profile()
    path = Path(profile["sandbox_vars"])
    original = path.read_text(encoding="utf-8", errors="replace")
    current = parse_sandbox(original)

    record_changes("sandbox", profile["name"], current, changes)

    backup = path.with_name(
        path.name + f".webui-{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    )
    shutil.copy2(path, backup)

    try:
        create_backup(profile, kind="pre-change", include_save=False)
    except Exception as e:
        audit("backup.pre_change_failed", str(e))

    try:
        updated = set_flat_scalars(original, changes)
        path.write_text(updated, encoding="utf-8")
    except Exception as e:
        if backup.exists():
            shutil.copy2(backup, path)
        raise HTTPException(400, f"Could not apply SandboxVars changes: {e}")

    audit("sandbox.update", str(changes))

    return {
        "ok": True,
        "backup": str(backup),
        "path": str(path),
        "restart_required": True,
    }
