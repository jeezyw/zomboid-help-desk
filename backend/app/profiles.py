from pathlib import Path

from fastapi import HTTPException

from . import config, server_files
from .db import get_setting, set_setting

SELECTED_PROFILE_KEY = "selected_server_profile"


def find_profile() -> dict:
    profiles = server_files.discover_profiles(config.DATA)
    if not profiles:
        raise HTTPException(
            404,
            f"No Project Zomboid server config files were detected under {config.DATA}. "
            "Point HOST_ZOMBOID_DATA at the directory containing your "
            "<servername>_SandboxVars.lua file (usually .../Zomboid/Server/).",
        )

    selected_name = get_setting(SELECTED_PROFILE_KEY)
    if selected_name:
        match = next((p for p in profiles if p["name"] == selected_name), None)
        if match:
            return match
        # Previously selected profile's files are gone (renamed/moved) - fall through
        # to auto-resolution below instead of getting permanently stuck.

    if len(profiles) == 1:
        set_setting(SELECTED_PROFILE_KEY, profiles[0]["name"])
        return profiles[0]

    names = ", ".join(p["name"] for p in profiles)
    raise HTTPException(
        409,
        f"Multiple server profiles detected ({names}). Choose one in Server Files.",
    )


def find_sandbox() -> Path:
    return Path(find_profile()["sandbox_vars"])


def find_ini() -> Path:
    profile = find_profile()
    if not profile.get("ini"):
        raise HTTPException(
            404,
            f"No .ini file was found alongside {profile['sandbox_vars']}.",
        )
    return Path(profile["ini"])
