"""Parser/writer for Project Zomboid's server .ini file - a flat "Key=Value" format,
much simpler than SandboxVars.lua's nested Lua tables (see routers/sandbox.py)."""

from __future__ import annotations

import re
from typing import Any

LINE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$")

# PZ's Mods=/WorkshopItems= lines are semicolon-delimited lists, e.g.
# "Mods=Munitions;OtherMod" / "WorkshopItems=2470148647;2482641150".
MOD_LIST_DELIMITER = ";"


def parse_ini_scalar(value: str) -> Any:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1]
    if v == "":
        return ""
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


def _parse_ini_full(text: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Single pass that parses settings AND captures each setting's preceding
    comment block (mirrors routers/sandbox.py's _parse_sandbox_full - real server
    .ini files document most keys with a "# description" line immediately above,
    same as SandboxVars.lua's "-- description" convention)."""
    settings: dict[str, Any] = {}
    comments: dict[str, str] = {}
    pending: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            pending = []  # blank line breaks the comment-to-setting association
            continue

        if line.startswith("#") or line.startswith(";"):
            pending.append(line.lstrip("#;").strip())
            continue

        m = LINE_RE.match(line)
        if not m:
            pending = []
            continue

        key = m.group("key")
        settings[key] = parse_ini_scalar(m.group("value"))
        if pending:
            comments[key] = "\n".join(pending)
        pending = []

    return settings, comments


def parse_ini(text: str) -> dict[str, Any]:
    settings, _ = _parse_ini_full(text)
    return settings


def parse_ini_comments(text: str) -> dict[str, str]:
    _, comments = _parse_ini_full(text)
    return comments


def _render(value: Any, quote: bool) -> str:
    if isinstance(value, bool):
        s = "true" if value else "false"
    elif value is None:
        s = ""
    else:
        s = str(value)
    return f'"{s}"' if quote and isinstance(value, str) else s


def set_ini_scalars(original: str, changes: dict[str, Any]) -> str:
    """Rewrites matching Key=Value lines in place, preserving order/comments/blanks
    (mirrors sandbox.set_flat_scalars). Unlike the SandboxVars writer, keys not found
    in the file are APPENDED rather than raising: real PZ .ini files habitually omit
    many optional keys (implicit defaults), and there's no nested-path ambiguity in
    this flat format, so append-if-missing is safe and more useful here."""
    lines = original.splitlines()
    remaining = dict(changes)
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        m = LINE_RE.match(stripped)
        if not m or m.group("key") not in remaining:
            output.append(line)
            continue

        key = m.group("key")
        value = remaining.pop(key)
        raw_value = stripped.split("=", 1)[1] if "=" in stripped else ""
        was_quoted = raw_value[:1] in ('"', "'")
        output.append(f"{key}={_render(value, quote=was_quoted)}")

    for key, value in remaining.items():
        output.append(f"{key}={_render(value, quote=False)}")

    return "\n".join(output) + ("\n" if original.endswith("\n") else "")


def parse_list_field(value: Any) -> list[str]:
    # Mods=/WorkshopItems= are semicolon-delimited lists, but parse_ini_scalar's
    # generic numeric coercion turns a single numeric-looking entry (e.g. a lone
    # Workshop id) into an int/float before this function ever sees it - stringify
    # defensively rather than assuming the caller always passes a raw str.
    text = "" if value is None else str(value)
    # Strip each entry, not just check truthiness - a manually-edited ini with
    # "Mods=TestMod; OtherMod" (space after the delimiter) would otherwise return
    # " OtherMod" verbatim, which never string-equals a real mod's id/folder name.
    return [v.strip() for v in text.split(MOD_LIST_DELIMITER) if v.strip()]


def render_list_field(items: list[str]) -> str:
    return MOD_LIST_DELIMITER.join(items)
