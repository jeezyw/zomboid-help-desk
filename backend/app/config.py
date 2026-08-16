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
