# Zomboid Help Desk

A self-hosted admin web UI for a Project Zomboid dedicated server: sandbox/.ini
editors, mod management, backups, scheduled restarts, RCON player tools, a
console viewer, and more - all in one Docker container.

Current build: 0.3.1

## Prerequisites

- Docker + the Docker Compose plugin
- An existing, already-running Project Zomboid dedicated server you can point
  this at

## Architecture Note

A single container:

Docker-based Start/Stop/Restart and live game-process CPU/RAM stats are
**optional** (`DOCKER_CONTROL_ENABLED` in `docker-compose.yml`, off by default) -
they work by shelling out to the `docker` CLI against `/var/run/docker.sock`, 
which is bind-mounted into the container. That grants the WebUI container 
host-root-equivalent access to the Docker daemon. Set`DOCKER_CONTROL_ENABLED` 
to `"false"` and comment out the `docker.sock` mount fora fully unprivileged 
container. Everything else (settings editors, mods,backups, RCON admin tools, 
console tailing) works with zero Docker privilege seither way. Console, config, 
save data are read straight off the bind-mounted `ZOMBOID_DATA`/`WORKSHOP_DATA` 
directories.

## Secure Mode

Before exposing the WebUI outside your LAN, put it behind HTTPS (e.g. a reverse proxy)
and turn on secure mode (`SECURE_MODE=true` + `WEBUI_USERNAME`/`WEBUI_PASSWORD` - see
Configuration below). This just makes the user login before they can access the WebUI.

## Deploying the Container

Everything is configured directly in `docker-compose.yml`. Open it, edit the values
under `environment:` and `volumes:` for your setup.
```bash
docker compose up -d --build
```
If that doesn't build correctly, just run
```bash
sh ./builder.sh
```
This will build with a clean cache. First it will
build the docker control agent then the webui.

To use the webui open:
```text
http://SERVER_IP:8080
```

## Configuration

Everything lives in `docker-compose.yml`
`zomboid-webui` service directly:

```yaml
environment:
  ZOMBOID_CONTAINER: zomboid-b42   # name of your existing Zomboid container
  TZ: UTC
  DOCKER_CONTROL_ENABLED: "false"  # "true" to enable Start/Stop/Restart + stats
  SECURE_MODE: "false"             # "true" to require a login (see below)
  WEBUI_USERNAME: admin
  WEBUI_PASSWORD: ""
volumes:
  - /path/to/your/zomboid/data:/data/zomboid       # your Zomboid data dir
  - /path/to/your/zomboid/workshop:/data/workshop  # your Workshop mods dir
  - ./webui-data:/app/data
  # - /var/run/docker.sock:/var/run/docker.sock    # uncomment with DOCKER_CONTROL_ENABLED
ports:
  - "8080:8000"                    # change the left side for a different host port
```

If `SECURE_MODE` is `"true"`, `WEBUI_PASSWORD` must be set to something non-empty
or the container refuses to start (fails fast rather than running "secure" with
an empty password).

## WebUI's Data

The WebUI's SQLite databaselives at `./webui-data/webui.db`. 
It's a plain file you can just copy it or make backups from the 
Backups page. Stored under `./webui-data/backups/`. The To-Do page is 
deliberately kept OUT of that database in its own plain file that lives at 
`./webui-data/todos.json`.

## Feedback

This is an early build being shared for testing - if something breaks or behaves
oddly, lemme know what happened and what you were doing when it broke and I will 
take a look when I can. If you can send the output of
```bash
docker compose logs zomboid-webui
```
