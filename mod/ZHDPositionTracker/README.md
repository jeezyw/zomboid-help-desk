# ZHD Position Tracker

Server-side-only companion mod for Zomboid Help Desk's Live Map tab
(`LIVE_MAP_ENABLED`). Writes online players' positions to a JSON file every
few seconds - see `42/media/lua/server/ZHDPositionTracker.lua` for the full
"what's verified vs. not" notes.

## Install

1. Copy this `ZHDPositionTracker/` folder into your Zomboid server's mods
   directory (wherever your other local/Workshop mods live).
2. In Zomboid Help Desk's Mods page, enable "ZHD Position Tracker" like any
   other mod (adds it to `Mods=` in the server .ini).
3. Restart the server.
4. See the main project README's Live Map section for the remaining setup
   (map tiles, `LIVE_MAP_ENABLED`).

This mod does nothing visible in-game - it only writes a small data file for
the webui to read.
