# Zomboid Help Desk

A self-hosted admin web UI for a Project Zomboid dedicated server:
settings, mod management, player map, backups, scheduled restarts, RCON 
player tools, aconsole viewer, and more - all in one Docker container.

Current build: 0.4.1

## Prerequisites

- Docker + the Docker Compose plugin
- Either an existing, already-running Project Zomboid dedicated server you can
  point this at, **or** let this app install and host one itself (`SERVER_MODE:
  bundled` - see Bundled Server Hosting below)

## Architecture Note

A single container:

Docker-based Start/Stop/Restart and live game-process CPU/RAM stats are
**optional** (`DOCKER_CONTROL_ENABLED` in `docker-compose.yml`, off by default) -
they work by shelling out to the `docker` CLI against `/var/run/docker.sock`, 
which is bind-mounted into the container. Set`DOCKER_CONTROL_ENABLED` 
to `"false"` and comment out the `docker.sock` mount fora fully unprivileged 
container. Everything else (settings editors, mods,backups, RCON admin tools, 
console tailing) works with zero Docker privilege seither way. Console, config, 
save data are read straight off the bind-mounted `ZOMBOID_DATA`/`WORKSHOP_DATA` 
directories.

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
  LIVE_MAP_ENABLED: "false"        # "true" to enable the Live Map tab, (see below)
  MAP_TILES_DATA: /data/map-tiles
  GAME_FILES_DATA: /data/game-files  # steamcmd install dir - bundled hosting and/or map rendering
  SERVER_MODE: external            # "bundled" to host the server yourself (see below)
volumes:
  - /path/to/your/zomboid/data:/data/zomboid       # your Zomboid data dir
  - /path/to/your/zomboid/workshop:/data/workshop  # your Workshop mods dir
  - ./webui-data:/app/data
  # - /var/run/docker.sock:/var/run/docker.sock    # uncomment with DOCKER_CONTROL_ENABLED
  # - /path/to/your/rendered/map/tiles:/data/map-tiles  # uncomment with LIVE_MAP_ENABLED
  # - /path/to/your/game-files:/data/game-files     # uncomment for SERVER_MODE=bundled
ports:
  - "8080:8000"                    # change the left side for a different host port
```
## Secure Mode

Before exposing the WebUI outside your LAN, put it behind HTTPS (e.g. a reverse proxy)
and turn on secure mode (`SECURE_MODE=true` + `WEBUI_USERNAME`/`WEBUI_PASSWORD` - see
Configuration below). This just makes the user login before they can access the WebUI.

If `SECURE_MODE` is `"true"`, `WEBUI_PASSWORD` must be set to something non-empty
or the container refuses to start.

## WebUI's Data

The WebUI's SQLite databaselives at `./webui-data/webui.db`. 
It's a plain file you can just copy it or make backups from the 
Backups page. Stored under `./webui-data/backups/`. 

The To-Do page is deliberately kept OUT of that database in its own plain file that lives at 
`./webui-data/todos.json`. Use it for whatever. I keep game-related objectives in there for
our little group of players and all of us can read it and add objectives.

## Live Map

Optional, off by default. Shows a top-down map of your world plus a live
player-position list. Two things need to be set up first - both from inside
the app, not `docker-compose.yml`:

1. **Player positions**: **Settings tab → "Install Mod & Enable Live Map"**.
   One click installs the ZHDPositionTracker companion mod onto your server
   (at `WORKSHOP_DATA/mods/ZHDPositionTracker/42/`. It then writes a
   small JSON file with everyone's position every few seconds - the webui
   reads and plots it.

   **Client-side note**: each connecting player needs their own local copy of
   the mod to satisfy the server/client check - it has no client Lua at all,
   so this is purely a formality. Settings tab → "Download Mod (for Players)"
   gives you a zip already rooted at `ZHDPositionTracker/` - send it to
   players and have them extract it directly into their own `Zomboid/mods/`
   folder.
   
2. **Map tiles**: two independent options, both from the Live Map/Settings
   tabs, either or both can be used:
   
   **Base Map (Vanilla, Isometric)**: works out of the box.
   
   **Map Calibration**: Do not use this yet unless you can upload a new map file with
   which to calibrate to. The file used exceeds git's file size limit, if you want it
   message me and I'll send you a google drive link.
     
## Bundled Server Hosting

Optional (`SERVER_MODE: bundled`). Lets this app install and run its own PZ
dedicated server rather than managing an external server, which is still the
default (`SERVER_MODE: external`). The server runs as a **subprocess of this
same container** - no separate container, no Docker socket, no
`DOCKER_CONTROL_ENABLED` needed for this mode at all. Tradeoff: restarting/
updating the webui container also stops the game server.

1. Set `SERVER_MODE: bundled` in `docker-compose.yml` and uncomment the
   `game-files` volume line and pick a volume location. Rebuild the container.
2. From the Server tab's "Dedicated Server" panel: set a server name, then
   Install/Update Server Files (steamcmd).
3. Use the existing Start button to launch it for the first time - the server
   generates its own config on first boot, which then shows up under Server
   Files exactly like an externally-run server's would.

## Feedback

This is an early build being shared for testing - if something breaks or behaves
oddly, lemme know what happened and what you were doing when it broke and I will 
take a look when I can. If you can send the output of
```bash
docker compose logs zomboid-webui
```
