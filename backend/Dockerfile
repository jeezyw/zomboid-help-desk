FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/index.html frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build


# The `docker` CLI, for optional in-process Docker control (see docker_control.py -
# start/stop/restart/stats for the Zomboid container). Baked in unconditionally:
# the binary is inert without /var/run/docker.sock actually being mounted, which is
# the real privilege boundary (opt-in via DOCKER_CONTROL_ENABLED, see
# docker-compose.yml) - no need for a build-arg-gated variant. Debian's apt-packaged
# docker.io turned out unreliable here (installed without error but left no working
# `docker` binary on PATH), so this pulls the CLI straight from Docker Inc.'s own
# minimal image instead - a static binary copy, no package manager involved.
FROM docker:cli AS dockercli


FROM python:3.12-slim

WORKDIR /app

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

# steamcmd, for optional bundled server hosting and map rendering (see
# steam_files.py) - only ever invoked, never runs on its own, so baking it in
# unconditionally costs nothing at rest, same reasoning as the docker CLI
# above. steamcmd's bootstrap needs 32-bit compat libs even on 64-bit hosts -
# this is the standard, widely-used installation pattern (i386 arch enabled +
# lib32gcc-s1 + Valve's own tarball), not something invented here.
#
# libvips-tools (the `vips`/`vipsheader` CLIs), for tiling the static
# maintainer-supplied base map image into a Leaflet-compatible tile
# pyramid (see base_map.py) - a huge single JPEG (tens of thousands of pixels
# per side) can't be shown in a browser directly, and vips tiles it without
# needing to decode the whole thing into memory at once, unlike a naive
# Pillow-based approach.
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates lib32gcc-s1 wget git libvips-tools \
    && mkdir -p /opt/steamcmd \
    && wget -qO- https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar -xz -C /opt/steamcmd \
    && ln -s /opt/steamcmd/steamcmd.sh /usr/local/bin/steamcmd \
    && rm -rf /var/lib/apt/lists/*

# pzmap2dzi, for optional in-process map rendering (see map_render.py) - same
# "invoked on demand, inert at rest" reasoning as steamcmd/docker above. Not
# pinned to a specific commit yet - pin this once a working combination has
# actually been verified against a real render, for reproducibility. pynput is
# excluded from its requirements: it pulls in evdev on Linux, whose C
# extension needs linux/input.h with no wheel available, and it's only used by
# pzmap2dzi's optional interactive press-a-hotkey-to-stop feature (see
# pzmap2dzi/hotkey.py) - irrelevant to a headless render with no TTY, and
# their own code already handles it missing via try/except ImportError (see
# scheduling.py) - confirmed by actually hitting and fixing this exact build
# failure earlier, not guessed preemptively.
RUN git clone https://github.com/cff29546/pzmap2dzi.git \
    && grep -v '^pynput' pzmap2dzi/requirements.txt > /tmp/pzmap2dzi-requirements.txt \
    && pip install --no-cache-dir -r /tmp/pzmap2dzi-requirements.txt

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# The ZHDPositionTracker companion mod's B42 files, baked in under a "42"
# version subfolder (NOT flattened - see live_map.py's install_mod() for why:
# every real, working mod on a real test deployment had its mod.info inside a
# per-build-version or "common" subfolder, never bare at the mod's own root -
# a bare mod.info was silently ignored by the dedicated server's mod loader,
# confirmed the hard way) so live_map.py's Settings-tab install button can
# copy it into the server's mods directory at runtime without needing
# network/git access from inside a running container. See live_map.py's
# MOD_SOURCE_DIR.
COPY mod/ZHDPositionTracker/42 ./mod/ZHDPositionTracker/42

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:APP", "--host", "0.0.0.0", "--port", "8000"]
