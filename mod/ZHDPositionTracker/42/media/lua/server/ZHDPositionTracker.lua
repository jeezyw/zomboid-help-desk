--[[
ZHD Position Tracker - server-side only.

Periodically writes every online player's username/x/y/z to a small JSON file,
which Zomboid Help Desk's backend (see backend/app/live_map.py) reads to plot
players on the Live Map tab. Runs on the dedicated server process only (this
file lives under media/lua/server/, never loaded by clients) since only the
server has authoritative positions for every connected player - a client only
ever knows its own.

UNVERIFIED - flagging this honestly rather than pretending otherwise, per this
project's existing confidence-level convention (see rcon_commands.py's header):

  1. getFileWriter's exact landing path relative to the server's Zomboid data
     root has NOT been confirmed against a live B42 server. This has only been
     written against PZ modding documentation, not tested. If
     backend/app/live_map.py's find_position_file() doesn't find this file,
     the first thing to check is where getFileWriter(FILE_NAME, true, false)
     actually lands, and update OUTPUT_PATH_HINT / find_position_file()'s
     search candidates to match.
  2. There's no guaranteed global JSON encoder in the PZ Lua sandbox across
     versions, so this hand-rolls a minimal one below rather than depend on
     one that might not exist - only handles the flat structure this script
     itself produces, not general-purpose.
  3. WRITE_INTERVAL_SECONDS below is a starting guess, not a tuned value -
     adjust for your player count/server load.
]]

local FILE_NAME = "ZHDPositions.json"
-- Best-effort note for whoever verifies this live: getFileWriter's mod-relative
-- write path convention has varied across PZ versions - this may land under
-- something like Zomboid/Lua/<FILE_NAME> rather than directly in the server's
-- data root. Confirm the real path, then check backend/app/live_map.py's
-- find_position_file() looks in the right place.
local OUTPUT_PATH_HINT = "Zomboid/Lua/" .. FILE_NAME

local WRITE_INTERVAL_SECONDS = 8
local lastWriteTime = 0

local function encodeJSON(players)
    local parts = {}
    for i = 1, #players do
        local p = players[i]
        parts[i] = string.format(
            '{"username":"%s","x":%.2f,"y":%.2f,"z":%.2f}',
            tostring(p.username):gsub('"', '\\"'), p.x, p.y, p.z
        )
    end
    return '{"players":[' .. table.concat(parts, ",") .. "]}"
end

local function writePositions()
    local online = getOnlinePlayers()
    if not online then return end

    local players = {}
    for i = 0, online:size() - 1 do
        local player = online:get(i)
        if player then
            players[#players + 1] = {
                username = player:getUsername(),
                x = player:getX(),
                y = player:getY(),
                z = player:getZ(),
            }
        end
    end

    local writer = getFileWriter(FILE_NAME, true, false)
    if writer then
        writer:write(encodeJSON(players))
        writer:close()
    end
end

local function onTick()
    local now = os.time()
    if now - lastWriteTime >= WRITE_INTERVAL_SECONDS then
        lastWriteTime = now
        writePositions()
    end
end

Events.OnTick.Add(onTick)
