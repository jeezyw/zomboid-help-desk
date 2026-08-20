import os
from pathlib import Path

DATA = Path(os.getenv("ZOMBOID_DATA", "/data/zomboid"))
WORKSHOP = Path(os.getenv("WORKSHOP_DATA", "/data/workshop"))
DB = Path(os.getenv("DB_PATH", "/app/data/webui.db"))
FRONTEND = Path("/app/frontend/dist")
BACKUP_ROOT = Path(os.getenv("BACKUP_ROOT", "/app/data/backups"))

# Off by default - a fresh deployment is fully unprivileged. Flipping this on (and
# uncommenting the docker.sock mount in docker-compose.yml) grants this container
# host-root-equivalent access, in exchange for Start/Stop/Restart and process
# CPU/RAM stats. See docker_control.py.
DOCKER_CONTROL_ENABLED = os.getenv("DOCKER_CONTROL_ENABLED", "false").strip().lower() in (
    "1", "true", "yes",
)

# Used as the default RCON host guess - see rcon_config.py.
ZOMBOID_CONTAINER = os.getenv("ZOMBOID_CONTAINER", "zomboid-b42")

SECURE_MODE = os.getenv("SECURE_MODE", "false").strip().lower() in ("1", "true", "yes")
AUTH_USERNAME = os.getenv("WEBUI_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("WEBUI_PASSWORD", "")

if SECURE_MODE and not AUTH_PASSWORD:
    raise RuntimeError(
        "SECURE_MODE is enabled but WEBUI_PASSWORD is not set - refusing to start "
        "with an empty password. Set WEBUI_PASSWORD in docker-compose.yml."
    )

# Off by default - requires both the ZHDPositionTracker companion mod (see
# mod/ZHDPositionTracker/) installed on the game server for live player
# positions, and MAP_TILES_DATA pointed at a rendered tile set for the map
# background. See live_map.py.
LIVE_MAP_ENABLED = os.getenv("LIVE_MAP_ENABLED", "false").strip().lower() in (
    "1", "true", "yes",
)
MAP_TILES = Path(os.getenv("MAP_TILES_DATA", "/data/map-tiles"))

# Where steamcmd installs PZ dedicated server files (binaries/game assets/
# texture packs) - distinct from ZOMBOID_DATA, which is just the Server/ config
# + saves directory. Shared by optional bundled server hosting and the map
# renderer's texture-pack needs. See steam_files.py.
GAME_FILES = Path(os.getenv("GAME_FILES_DATA", "/data/game-files"))

# A maintainer-supplied static vanilla B42 map image (full isometric render,
# not user-rendered) - baked into the image at build time via the normal
# `COPY backend/app ./app` step (it just lives inside the Python package
# tree). Tiled at runtime into MAP_TILES_DATA/base by base_map.py, so users
# get a working live map without needing steamcmd/pzmap2dzi/a multi-hour
# render themselves. Optional - if this file isn't present (e.g. a from-source
# build without it), base_map.py's tile button fails cleanly.
BASE_MAP_SOURCE = Path(__file__).resolve().parent / "map" / "b42_map.jpg"

# "external" (default) - this app manages a PZ server that runs in its own
# separate Docker container, named by ZOMBOID_CONTAINER, via docker_control.py
# (requires DOCKER_CONTROL_ENABLED).
# "bundled" - this app installs (via steamcmd) and runs its own PZ server as a
# subprocess of THIS container instead - see game_server.py. No Docker access
# needed for this mode at all; ZOMBOID_CONTAINER/DOCKER_CONTROL_ENABLED are
# irrelevant to it.
SERVER_MODE = os.getenv("SERVER_MODE", "external").strip().lower()
if SERVER_MODE not in ("external", "bundled"):
    raise RuntimeError(f"Invalid SERVER_MODE: {SERVER_MODE!r} - must be 'external' or 'bundled'.")
