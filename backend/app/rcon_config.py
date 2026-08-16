"""Resolves where/how to reach RCON. Port and password live in the server .ini (the
same file the ini editor already reads/writes) and are read live on every call rather
than cached, so they can never drift from the file that's the actual source of truth.
Host is a WebUI-owned setting (kv table) since it's not a PZ server concept - it
defaults to the game container's name (best-effort Docker DNS), which only resolves
if the WebUI ends up sharing a Docker network with it; otherwise an explicit
host/IP override is required. See routers/rcon.py's /api/rcon/test for diagnosing
which of these is the case.
"""

from __future__ import annotations

from . import config
from .db import get_setting, set_setting
from .ini_parser import parse_ini
from .profiles import find_ini

RCON_HOST_OVERRIDE_KEY = "rcon_host_override"


class RconNotConfiguredError(Exception):
    """RCONPassword is blank or absent in the server .ini."""


def get_rcon_host() -> str:
    override = get_setting(RCON_HOST_OVERRIDE_KEY)
    return override if override else config.ZOMBOID_CONTAINER


def set_rcon_host_override(host: str | None):
    set_setting(RCON_HOST_OVERRIDE_KEY, host or "")


def get_rcon_port_password() -> tuple[int | None, str | None]:
    path = find_ini()
    settings = parse_ini(path.read_text(encoding="utf-8", errors="replace"))
    port = settings.get("RCONPort")
    password = settings.get("RCONPassword")
    if not password:
        return None, None
    return (int(port) if port else None), str(password)


def get_rcon_target() -> tuple[str, int, str]:
    port, password = get_rcon_port_password()
    if not password:
        raise RconNotConfiguredError("RCONPassword is not set in the server .ini.")
    return get_rcon_host(), port or 27015, password
