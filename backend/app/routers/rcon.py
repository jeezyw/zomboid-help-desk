from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import rcon_config, skill_xp
from ..db import audit
from ..rcon_client import (
    RconAuthError,
    RconConnectError,
    RconDnsError,
    RconError,
    RconTimeoutError,
    rcon_execute,
)
from ..rcon_commands import (
    cmd_addxp,
    cmd_ban,
    cmd_godmode_player,
    cmd_help,
    cmd_kick,
    cmd_servermsg,
    cmd_teleport,
    cmd_unban,
)

router = APIRouter()


@router.get("/api/rcon/config")
async def get_rcon_config():
    port, password = rcon_config.get_rcon_port_password()
    return {
        "host": rcon_config.get_rcon_host(),
        "port": port,
        "password_set": bool(password),
        "source": "ini" if password else "not configured",
    }


class RconHostBody(BaseModel):
    host: str | None = None


@router.post("/api/rcon/config")
async def set_rcon_config(body: RconHostBody):
    rcon_config.set_rcon_host_override(body.host)
    return await get_rcon_config()


@router.post("/api/rcon/test")
async def test_rcon():
    try:
        host, port, password = rcon_config.get_rcon_target()
    except rcon_config.RconNotConfiguredError:
        return {
            "ok": False, "stage": "config",
            "detail": "RCONPassword is empty in the server .ini - set RCONPort/RCONPassword "
                       "in Server Settings first, then restart the server.",
        }

    try:
        raw = await rcon_execute(host, port, password, cmd_help())
    except RconDnsError as e:
        return {
            "ok": False, "stage": "dns",
            "detail": f"Could not resolve host '{host}': {e}. If the game server isn't on "
                       "the same Docker network as the WebUI, set an explicit host/IP override.",
        }
    except (RconConnectError, RconTimeoutError) as e:
        return {"ok": False, "stage": "connect", "detail": f"Could not reach {host}:{port}: {e}"}
    except RconAuthError:
        return {
            "ok": False, "stage": "auth",
            "detail": "Connected, but authentication was rejected - check RCONPassword.",
        }
    except RconError as e:
        return {"ok": False, "stage": "command", "detail": f"Connected and authenticated, but the test command failed: {e}"}

    return {"ok": True, "stage": None, "detail": raw}


async def _run_admin_command(command: str, action: str, detail: str) -> dict:
    try:
        host, port, password = rcon_config.get_rcon_target()
    except rcon_config.RconNotConfiguredError:
        raise HTTPException(400, "RCON is not configured - set RCONPort/RCONPassword in Server Settings first.")

    try:
        raw = await rcon_execute(host, port, password, command)
    except RconError as e:
        raise HTTPException(502, f"RCON command failed: {e}")

    audit(action, detail)
    return {"ok": True, "response": raw}


class UsernameBody(BaseModel):
    username: str


@router.post("/api/rcon/kick")
async def kick_player(body: UsernameBody):
    return await _run_admin_command(cmd_kick(body.username), "rcon.kick", body.username)


class BanBody(BaseModel):
    username: str
    ip: bool = False
    reason: str | None = None


@router.post("/api/rcon/ban")
async def ban_player(body: BanBody):
    detail = f"{body.username}" + (f" (ip) reason={body.reason}" if body.ip or body.reason else "")
    return await _run_admin_command(cmd_ban(body.username, body.ip, body.reason), "rcon.ban", detail)


@router.post("/api/rcon/unban")
async def unban_player(body: UsernameBody):
    return await _run_admin_command(cmd_unban(body.username), "rcon.unban", body.username)


class TeleportBody(BaseModel):
    username: str
    to_username: str


@router.post("/api/rcon/teleport")
async def teleport_player(body: TeleportBody):
    detail = f"{body.username} -> {body.to_username}"
    return await _run_admin_command(cmd_teleport(body.username, body.to_username), "rcon.teleport", detail)


class GodmodeBody(BaseModel):
    username: str
    enabled: bool


@router.post("/api/rcon/godmode")
async def godmode_player(body: GodmodeBody):
    detail = f"{body.username}: {'enabled' if body.enabled else 'disabled'}"
    return await _run_admin_command(cmd_godmode_player(body.username, body.enabled), "rcon.godmode", detail)


@router.get("/api/rcon/perks")
async def list_perks():
    return {
        "perks": [{"id": pid, "label": label, "curve": curve} for pid, label, curve in skill_xp.PERKS],
        "max_level": skill_xp.MAX_LEVEL,
    }


class SetSkillBody(BaseModel):
    username: str
    perk: str
    level: int


@router.post("/api/rcon/set-skill")
async def set_skill(body: SetSkillBody):
    """Grants a skill enough XP to reach `level` from zero via addxp (see
    skill_xp.py's header) - addxp ADDS xp, it can't set an absolute level, so a
    player with existing progress in this skill will end up somewhat past the
    requested level rather than exactly on it. That caveat is surfaced in the
    frontend, not hidden here."""
    try:
        curve = skill_xp.perk_curve(body.perk)
        xp = skill_xp.xp_for_level(curve, body.level)
    except (skill_xp.InvalidPerkError, skill_xp.InvalidLevelError) as e:
        raise HTTPException(400, str(e))
    detail = f"{body.username}: {body.perk} -> level {body.level} (+{xp} xp)"
    return await _run_admin_command(cmd_addxp(body.username, body.perk, xp), "rcon.set_skill", detail)


class AnnounceBody(BaseModel):
    message: str


@router.post("/api/rcon/announce")
async def announce(body: AnnounceBody):
    return await _run_admin_command(cmd_servermsg(body.message), "rcon.announce", body.message)


class RawCommandBody(BaseModel):
    command: str


@router.post("/api/rcon/command")
async def send_raw_command(body: RawCommandBody):
    """Generic RCON pass-through for the Send Command panel (Server page).
    Deliberately unrestricted - any command string, including destructive ones like
    `quit` - matching this app's existing single-admin/LAN-trusted posture (same as
    the free-text .ini/Sandbox editors). Dangerous-command confirmation lives in the
    frontend (a confirm dialog on the Quit button), not as a backend restriction."""
    return await _run_admin_command(body.command, "rcon.raw_command", body.command)
