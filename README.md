# Zomboid Help Desk

A self-hosted admin web UI for a Project Zomboid dedicated server: sandbox/.ini
editors, mod management, backups, scheduled restarts, RCON player tools, a
console viewer, and more - all in one Docker container.

Current build: 0.3.1

## Prerequisites

- Docker + the Docker Compose plugin (`docker compose`, not the old standalone
  `docker-compose`).
- An existing, already-running Project Zomboid dedicated server you can point
  this at - this app does not stand one up for you. It reads/writes that
  server's config, save, and (optionally) console files, and can optionally
  control its container via Docker.

## Architecture

A single container:

Browser -> WebUI/API -> Zomboid data (bind mounts) / RCON / Docker

Docker-based Start/Stop/Restart and live game-process CPU/RAM stats are
**optional** (`DOCKER_CONTROL_ENABLED` in `docker-compose.yml`, off by default) -
they work by shelling out to the `docker` CLI against
`/var/run/docker.sock`, which is bind-mounted into the container. That grants the
WebUI container host-root-equivalent access to the Docker daemon. Set
`DOCKER_CONTROL_ENABLED` to `"false"` and comment out the `docker.sock` mount for
a fully unprivileged container - everything else (settings editors, mods,
backups, RCON admin tools, console tailing) works with zero Docker privileges
either way. RCON is a plain TCP connection to the game process, and
console/config/save data are read straight off the bind-mounted
`ZOMBOID_DATA`/`WORKSHOP_DATA` directories.

## Important

Before exposing the WebUI outside your LAN, put it behind HTTPS (e.g. a reverse proxy)
and turn on secure mode (`SECURE_MODE=true` + `WEBUI_USERNAME`/`WEBUI_PASSWORD` - see
Configuration below). Secure mode is off by default, matching the rest of this app's
LAN-trusted-by-default posture.

## Deploy

Everything is configured directly in `docker-compose.yml` - there's no separate
`.env` file to keep in sync with it. Open it, edit the values under `environment:`
and `volumes:` for your setup (see Configuration below), then from the extracted
directory:

```bash
docker compose up -d --build
```

Then open:

```text
http://SERVER_IP:8080
```

## Check services

```bash
docker compose ps
docker compose logs -f zomboid-webui
```

## Existing Zomboid server

The WebUI does not replace your existing Zomboid service. `ZOMBOID_CONTAINER` names
it - used as the RCON host guess always, and (if `DOCKER_CONTROL_ENABLED=true`) as
the target of Docker start/stop/restart/stats too.

If the existing server is managed by another Compose project, that is okay: Docker
can still control the named container.

## Configuration

Everything lives in `docker-compose.yml` - there is no `.env` file. Edit the
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

## WebUI's own data

The WebUI's SQLite database (audit log, config-change history, backup metadata,
RCON host override, restart schedule, sandbox sorting/favorites, etc.) lives at
`./webui-data/webui.db`, directly in this project directory via a host bind mount
(not a named Docker volume) - so it's a plain file you can back up, inspect, or
copy without going through `docker cp`/`docker volume inspect`. Manual backups you
create from the Backups page also land under `./webui-data/backups/`. The
Objectives (to-do list) page is deliberately kept OUT of that database - it's its
own plain file at `./webui-data/todos.json`.

## Current features

- Dashboard (server status, CPU/RAM/disk, online players, health checks)
- Optional Docker control (`DOCKER_CONTROL_ENABLED`, off by default): start/stop/
  restart plus live game-process CPU/RAM stats
- Optional secure mode (`SECURE_MODE`, off by default): a single shared admin
  login gating the whole app, session cookie persisted in the SQLite db so a
  container restart doesn't force every browser tab to re-login
- Live, filtered console (INFO/WARN/ERROR/PLAYER/MOD/SYSTEM), incremental polling
- SandboxVars.lua discovery, accurate schema, and editor
- Sandbox Presets: save the current full set of sandbox settings under a name,
  list/apply/delete them later (applying skips any saved key that no longer exists
  in the current file rather than failing outright) - applying offers an immediate
  restart at a delay of your choosing
- Server .ini discovery, schema, and editor
- Mod Manager (enable/disable/reorder/remove-reference, driven by the .ini's
  `Mods=`/`WorkshopItems=`) plus an Add Mod tool: paste a Steam Workshop URL/id to
  look it up and queue it - the dedicated server downloads queued items itself on
  its next start
- Backup Manager: manual backups (config + optional save data), retention policy,
  restore (with an automatic safety snapshot first), download, delete
- Automatic pre-change backups and `.bak` sidecar copies before every settings write
- Configuration History: every sandbox/.ini change is recorded with old/new values
  and can be reverted from the Backups page
- Scheduled Restarts: off / daily-at / every-N-hours / restart-when-empty
- Player Activity: RCON-backed (accurate, live) when `RCONPort`/`RCONPassword` are set
  in the .ini and reachable; falls back to best-effort log-scraping otherwise (see
  disclaimer on the Players page, gone once RCON is connected)
- RCON Admin Tools (Players page): kick / ban (+IP, reason) / unban / teleport /
  give-item / server-wide announcements, plus a brief in-game warning sent
  automatically before manual or scheduled restarts
- Workshop directory discovery
- Objectives: a free-text game to-do list with a status per item (Planned/In
  Progress/Blocked/Complete, each with its own border treatment - dim glow/green
  pulse/caution-tape - plus a Blocker note field while Blocked), a priority (Urgent/
  Moderate/Low tint the row red/orange/yellow, Wish dims the text instead), with the
  active list auto-sorted top to bottom by priority and manual drag-free reordering
  available within a priority tier (arrows disabled across tier boundaries) - stored
  as its own plain file, not the SQLite db, see above. Completed objectives move to
  a separate Completed panel, deletable from there
- Audit log foundation, SQLite persistence
- Responsive admin UI

## Known limitations / next targets

- **Secure mode is off by default.** See the warning above - turn on `SECURE_MODE`
  + put this behind HTTPS before exposing it beyond your LAN. It's a single shared
  login (no per-user accounts), which matches the rest of this app's single-admin
  model.
- **RCON reachability isn't guaranteed out of the box.** The WebUI defaults to
  reaching RCON via the game container's name (works only if it ends up sharing a
  Docker network with the WebUI) - set an explicit host/IP override on the Players
  page and use "Test Connection" to diagnose. `backend/app/rcon_commands.py`'s
  command syntax (particularly `banuser`'s flags and `additem`'s argument form) is
  transcribed from documentation, not yet verified against a live server - `Test
  Connection` returns the real `help` output so it can be checked. The
  connect/disconnect log patterns in `backend/app/log_patterns.py` (the fallback path
  when RCON isn't configured) are similarly best-effort.
- **No invisible/coordinate-teleport.** Only kick/ban/unban/teleport (user-to-user)/
  give-item/announce/godmode/adjust-skills are implemented.
- **No Steam Workshop search or install.** The Mod Manager only manages mods already
  present under the workshop mount and already referenced in the .ini.
- **No WebSockets.** The console and player feed use incremental polling; a live push
  layer is the natural next upgrade.
- Not yet built: Discord integration, a full Lua-error/mod-attribution log analyzer,
  historical metrics graphs, map/player-position tracking, mod conflict/dependency
  detection, a server version update manager, multi-server support.

## Feedback

This is an early build being shared for testing - if something breaks or behaves
oddly, please open an issue on this repo with what you were doing, what you
expected, and (if relevant) the output of `docker compose logs zomboid-webui`.
