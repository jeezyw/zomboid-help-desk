/** Structured definitions for every Project Zomboid server console command, for the
 * Server page's Send Command builder. Transcribed directly from the user's own
 * server's `help` output (pasted 2026-08-11), not guessed - this is the actual command
 * list and "Use:" syntax the live server reports. A handful of entries have a real
 * command keyword that differs from the list's bullet label (the game's own data,
 * not a transcription error here) - `command` below is always the real keyword taken
 * from the "Use: /xxx" text, e.g. `kick`'s bullet maps to the real keyword `kickuser`,
 * `godmod`'s maps to `godmode`, `addsteamid`/`removesteamid` map to the camelCased
 * `addSteamID`/`removeSteamID`.
 *
 * A few commands' in-game descriptions are themselves untranslated placeholder
 * strings (`UI_ServerOptionDesc_...`) with no real syntax documented - createhorde2,
 * list, log, remove, removezombies, stats. reloadalllua's description is a verbatim
 * copy of reloadlua's, so its "no arguments, reloads everything" shape here is an
 * inference from the name, not documented. All of these are marked
 * `confidence: "low"` and should be tested carefully before relying on them.
 *
 * Quoting conventions mostly follow each command's own "Use:" text, EXCEPT additem/
 * removeitem's item id and banid/banip/unbanid/unbanip's id, which are sent unquoted -
 * additem was confirmed live (see rcon_commands.py) to fail silently if the item id
 * is quoted, and banid/banip/unbanid/unbanip's own "Use:" lines never show quotes
 * around their argument (unlike every "username" argument elsewhere, which does).
 */

export type CmdFieldType =
  | "player" | "player-optional" | "text" | "text-optional" | "number"
  | "number-optional" | "select" | "bool-flag" | "item";

export type CmdField = {
  key: string;
  label: string;
  type: CmdFieldType;
  options?: string[];
  placeholder?: string;
};

export type ServerCommandDef = {
  id: string;
  command: string;
  label: string;
  description: string;
  group: string;
  fields: CmdField[];
  danger?: boolean;
  confidence?: "low";
  build: (v: Record<string, string>) => string;
};

const boolSuffix = (v: string) => (v ? ` -${v}` : "");
const q = (s: string) => `"${s}"`;

export const SERVER_COMMANDS: ServerCommandDef[] = [
  // --- Items ---
  {
    id: "additem", command: "additem", label: "Give Item", group: "Items",
    description: 'Give an item to a player. Use: /additem "username" module.item count',
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "item", label: "Item", type: "item" },
      { key: "count", label: "Count", type: "number-optional", placeholder: "1" },
    ],
    build: (v) => `additem ${q(v.username)} ${v.item} ${v.count || 1}`,
  },
  {
    id: "removeitem", command: "removeitem", label: "Remove Item (from self)", group: "Items",
    description: "Removes items from the admin's own inventory (the RCON connection, not a chosen player). 0 removes all of that type.",
    fields: [
      { key: "item", label: "Item", type: "item" },
      { key: "count", label: "Count (0 = all)", type: "number-optional", placeholder: "1" },
    ],
    build: (v) => `removeitem ${v.item} ${v.count || 1}`,
  },
  {
    id: "addkey", command: "addkey", label: "Give Key", group: "Items",
    description: 'Give a key to a player. Use: /addkey "username" "keyId" "name"',
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "keyId", label: "Key ID", type: "text" },
      { key: "name", label: "Name (optional)", type: "text-optional" },
    ],
    build: (v) => `addkey ${q(v.username)} ${q(v.keyId)}${v.name ? ` ${q(v.name)}` : ""}`,
  },
  {
    id: "addvehicle", command: "addvehicle", label: "Spawn Vehicle", group: "Items",
    description: 'Spawn a vehicle. Use: /addvehicle "script" "user or x,y,z"',
    fields: [
      { key: "script", label: "Vehicle Script (e.g. Base.VanAmbulance)", type: "text" },
      { key: "target", label: "Target (username or x,y,z)", type: "text" },
    ],
    build: (v) => `addvehicle ${q(v.script)} ${q(v.target)}`,
  },

  // --- Player Actions ---
  {
    id: "teleport", command: "teleport", label: "Teleport to Player", group: "Player Actions",
    description: 'Teleport a player to another (or bring one player to a target). Use: /teleport "player1" "player2"',
    fields: [
      { key: "player1", label: "Player", type: "player" },
      { key: "player2", label: "Teleport To (optional)", type: "player-optional" },
    ],
    build: (v) => `teleport ${q(v.player1)}${v.player2 ? ` ${q(v.player2)}` : ""}`,
  },
  {
    id: "teleportplayer", command: "teleportplayer", label: "Teleport Player to Player", group: "Player Actions",
    description: 'Teleport one player to another. Use: /teleportplayer "player1" "player2"',
    fields: [
      { key: "player1", label: "Player", type: "player" },
      { key: "player2", label: "Teleport To", type: "player" },
    ],
    build: (v) => `teleportplayer ${q(v.player1)} ${q(v.player2)}`,
  },
  {
    id: "teleportto", command: "teleportto", label: "Teleport to Coordinates", group: "Player Actions",
    description: "Teleport the admin connection to world coordinates.",
    fields: [
      { key: "x", label: "X", type: "number" },
      { key: "y", label: "Y", type: "number" },
      { key: "z", label: "Z", type: "number-optional", placeholder: "0" },
    ],
    build: (v) => `teleportto ${v.x},${v.y},${v.z || 0}`,
  },
  {
    id: "addxp", command: "addxp", label: "Give Skill XP", group: "Player Actions",
    description: 'Give XP to a player. Use: /addxp "playername" perkname=xp -true (also on RCON Tools as "Adjust Skills")',
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "perk", label: "Perk (internal id, e.g. Woodwork)", type: "text" },
      { key: "xp", label: "XP Amount", type: "number" },
      { key: "multiplier", label: "Apply XP Multiplier", type: "bool-flag" },
    ],
    build: (v) => `addxp ${q(v.username)} ${v.perk}=${v.xp}${boolSuffix(v.multiplier)}`,
  },
  {
    id: "setaccesslevel", command: "setaccesslevel", label: "Set Access Level", group: "Player Actions",
    description: 'Set a player\'s admin access level. Use: /setaccesslevel "username" "accesslevel"',
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "level", label: "Access Level", type: "select", options: ["Admin", "Moderator", "Overseer", "GM", "Observer"] },
    ],
    build: (v) => `setaccesslevel ${q(v.username)} ${q(v.level)}`,
  },
  {
    id: "setpassword", command: "setpassword", label: "Set Password", group: "Player Actions",
    description: 'Change a user\'s password. Use: /setpassword "username" "newpassword"',
    fields: [
      { key: "username", label: "Username", type: "text" },
      { key: "password", label: "New Password", type: "text" },
    ],
    build: (v) => `setpassword ${q(v.username)} ${q(v.password)}`,
  },
  {
    id: "removemapsymbolsforuser", command: "removemapsymbolsforuser", label: "Clear Map Symbols", group: "Player Actions",
    description: "Removes all shared in-game map symbols placed by a user.",
    fields: [{ key: "username", label: "Player", type: "player" }],
    build: (v) => `removemapsymbolsforuser ${q(v.username)}`,
  },

  // --- Player State (toggles) ---
  {
    id: "godmodeplayer", command: "godmodeplayer", label: "Godmode (Player)", group: "Player State",
    description: "Make a player invincible.",
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "value", label: "Enable", type: "bool-flag" },
    ],
    build: (v) => `godmodeplayer ${q(v.username)}${boolSuffix(v.value)}`,
  },
  {
    id: "invisibleplayer", command: "invisibleplayer", label: "Invisible to Zombies (Player)", group: "Player State",
    description: "Make a player invisible to zombies.",
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "value", label: "Enable", type: "bool-flag" },
    ],
    build: (v) => `invisibleplayer ${q(v.username)}${boolSuffix(v.value)}`,
  },
  {
    id: "noclip", command: "noclip", label: "No-clip (Player)", group: "Player State",
    description: "Makes a player pass through walls and structures. Toggles if no value is given.",
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "value", label: "Enable", type: "bool-flag" },
    ],
    build: (v) => `noclip ${q(v.username)}${boolSuffix(v.value)}`,
  },
  {
    id: "voiceban", command: "voiceban", label: "Voice Ban", group: "Player State",
    description: 'Block voice chat from a user. Use: /voiceban "username" -value',
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "value", label: "Enable", type: "bool-flag" },
    ],
    build: (v) => `voiceban ${q(v.username)}${boolSuffix(v.value)}`,
  },
  {
    id: "godmode", command: "godmode", label: "Godmode (Self/Console)", group: "Player State",
    description: "Make the admin connection invincible. Toggles if no value is given.",
    fields: [{ key: "value", label: "Enable", type: "bool-flag" }],
    build: (v) => `godmode${boolSuffix(v.value)}`,
  },
  {
    id: "invisible", command: "invisible", label: "Invisible to Zombies (Self/Console)", group: "Player State",
    description: "Make the admin connection invisible to zombies. Toggles if no value is given.",
    fields: [{ key: "value", label: "Enable", type: "bool-flag" }],
    build: (v) => `invisible${boolSuffix(v.value)}`,
  },

  // --- Moderation ---
  {
    id: "kick", command: "kickuser", label: "Kick Player", group: "Moderation",
    description: 'Kick a user. Use: /kickuser "username" -r "reason" (also on Players page)',
    fields: [
      { key: "username", label: "Player", type: "player" },
      { key: "reason", label: "Reason (optional)", type: "text-optional" },
    ],
    build: (v) => `kickuser ${q(v.username)}${v.reason ? ` -r ${q(v.reason)}` : ""}`,
  },
  {
    id: "banuser", command: "banuser", label: "Ban Player", group: "Moderation",
    description: 'Ban a user. Use: /banuser "username" -ip -r "reason" (also on Players page)',
    danger: true,
    fields: [
      { key: "username", label: "Player", type: "text" },
      { key: "ip", label: "Also Ban IP", type: "bool-flag" },
      { key: "reason", label: "Reason (optional)", type: "text-optional" },
    ],
    build: (v) => `banuser ${q(v.username)}${v.ip === "true" ? " -ip" : ""}${v.reason ? ` -r ${q(v.reason)}` : ""}`,
  },
  {
    id: "unbanuser", command: "unbanuser", label: "Unban Player", group: "Moderation",
    description: 'Unban a player. Use: /unbanuser "username" (also on Players page)',
    fields: [{ key: "username", label: "Username", type: "text" }],
    build: (v) => `unbanuser ${q(v.username)}`,
  },
  {
    id: "banid", command: "banid", label: "Ban SteamID", group: "Moderation",
    description: "Ban a SteamID.", danger: true,
    fields: [{ key: "steamid", label: "SteamID", type: "text" }],
    build: (v) => `banid ${v.steamid}`,
  },
  {
    id: "unbanid", command: "unbanid", label: "Unban SteamID", group: "Moderation",
    description: "Unban a SteamID.",
    fields: [{ key: "steamid", label: "SteamID", type: "text" }],
    build: (v) => `unbanid ${v.steamid}`,
  },
  {
    id: "banip", command: "banip", label: "Ban IP", group: "Moderation",
    description: "Ban an IP address.", danger: true,
    fields: [{ key: "ip", label: "IP Address", type: "text" }],
    build: (v) => `banip ${v.ip}`,
  },
  {
    id: "unbanip", command: "unbanip", label: "Unban IP", group: "Moderation",
    description: "Unban an IP address.",
    fields: [{ key: "ip", label: "IP Address", type: "text" }],
    build: (v) => `unbanip ${v.ip}`,
  },
  {
    id: "addsteamid", command: "addSteamID", label: "Allow SteamID", group: "Moderation",
    description: "Add a SteamID to the server's allowed list.",
    fields: [{ key: "steamid", label: "SteamID", type: "text" }],
    build: (v) => `addSteamID ${q(v.steamid)}`,
  },
  {
    id: "removesteamid", command: "removeSteamID", label: "Disallow SteamID", group: "Moderation",
    description: "Remove a SteamID from the server's allowed list.",
    fields: [{ key: "steamid", label: "SteamID", type: "text" }],
    build: (v) => `removeSteamID ${q(v.steamid)}`,
  },
  {
    id: "adduser", command: "adduser", label: "Add Whitelisted User", group: "Moderation",
    description: 'Add a new user to a whitelisted server. Use: /adduser "username" "password"',
    fields: [
      { key: "username", label: "Username", type: "text" },
      { key: "password", label: "Password (optional)", type: "text-optional" },
    ],
    build: (v) => `adduser ${q(v.username)}${v.password ? ` ${q(v.password)}` : ""}`,
  },
  {
    id: "removeuserfromwhitelist", command: "removeuserfromwhitelist", label: "Remove Whitelisted User", group: "Moderation",
    description: "Remove a user from the whitelist.", danger: true,
    fields: [{ key: "username", label: "Username", type: "text" }],
    build: (v) => `removeuserfromwhitelist ${q(v.username)}`,
  },

  // --- Safehouses ---
  {
    id: "addtosafehouse", command: "addtosafehouse", label: "Add Player to Safehouse", group: "Safehouses",
    description: 'Use: /addtosafehouse "title" "username"',
    fields: [
      { key: "title", label: "Safehouse Title", type: "text" },
      { key: "username", label: "Player", type: "player" },
    ],
    build: (v) => `addtosafehouse ${q(v.title)} ${q(v.username)}`,
  },
  {
    id: "kickfromsafehouse", command: "kickfromsafehouse", label: "Remove Player from Safehouse", group: "Safehouses",
    description: 'Use: /kickfromsafehouse "title" "username"',
    fields: [
      { key: "title", label: "Safehouse Title", type: "text" },
      { key: "username", label: "Player", type: "player" },
    ],
    build: (v) => `kickfromsafehouse ${q(v.title)} ${q(v.username)}`,
  },
  {
    id: "releasesafehouse", command: "releasesafehouse", label: "Release Safehouse", group: "Safehouses",
    description: 'Use: /releasesafehouse "title"', danger: true,
    fields: [{ key: "title", label: "Safehouse Title", type: "text" }],
    build: (v) => `releasesafehouse ${q(v.title)}`,
  },

  // --- World Events / Weather ---
  {
    id: "createhorde", command: "createhorde", label: "Spawn Horde Near Player", group: "World Events",
    description: 'Use: /createhorde count "username"',
    fields: [
      { key: "count", label: "Count", type: "number", placeholder: "150" },
      { key: "username", label: "Near Player (optional)", type: "player-optional" },
    ],
    build: (v) => `createhorde ${v.count}${v.username ? ` ${q(v.username)}` : ""}`,
  },
  {
    id: "createhorde2", command: "createhorde2", label: "Spawn Horde (variant 2)", group: "World Events",
    description: "Undocumented in the server's own help output - assumed to share createhorde's arguments.",
    confidence: "low",
    fields: [
      { key: "count", label: "Count", type: "number", placeholder: "150" },
      { key: "username", label: "Near Player (optional)", type: "player-optional" },
    ],
    build: (v) => `createhorde2 ${v.count}${v.username ? ` ${q(v.username)}` : ""}`,
  },
  {
    id: "removezombies", command: "removezombies", label: "Remove Zombies", group: "World Events",
    description: "Undocumented in the server's own help output.",
    confidence: "low", fields: [],
    build: () => "removezombies",
  },
  {
    id: "chopper", command: "chopper", label: "Helicopter Event", group: "World Events",
    description: "Place a helicopter event on a random player.",
    fields: [], build: () => "chopper",
  },
  {
    id: "gunshot", command: "gunshot", label: "Gunshot Sound", group: "World Events",
    description: "Place a gunshot sound on a random player.",
    fields: [], build: () => "gunshot",
  },
  {
    id: "alarm", command: "alarm", label: "Building Alarm", group: "World Events",
    description: "Sound a building alarm at the admin's position (must be in a room).",
    fields: [], build: () => "alarm",
  },
  {
    id: "lightning", command: "lightning", label: "Lightning", group: "World Events",
    description: 'Use: /lightning "username" (optional)',
    fields: [{ key: "username", label: "Near Player (optional)", type: "player-optional" }],
    build: (v) => `lightning${v.username ? ` ${q(v.username)}` : ""}`,
  },
  {
    id: "thunder", command: "thunder", label: "Thunder", group: "World Events",
    description: 'Use: /thunder "username" (optional)',
    fields: [{ key: "username", label: "Near Player (optional)", type: "player-optional" }],
    build: (v) => `thunder${v.username ? ` ${q(v.username)}` : ""}`,
  },
  {
    id: "startrain", command: "startrain", label: "Start Rain", group: "World Events",
    description: "Optional intensity 1-100.",
    fields: [{ key: "intensity", label: "Intensity 1-100 (optional)", type: "number-optional" }],
    build: (v) => `startrain${v.intensity ? ` ${q(v.intensity)}` : ""}`,
  },
  {
    id: "stoprain", command: "stoprain", label: "Stop Rain", group: "World Events",
    description: "Stop raining on the server.", fields: [], build: () => "stoprain",
  },
  {
    id: "startstorm", command: "startstorm", label: "Start Storm", group: "World Events",
    description: "Optional duration in game hours.",
    fields: [{ key: "duration", label: "Duration (hours, optional)", type: "number-optional" }],
    build: (v) => `startstorm${v.duration ? ` ${q(v.duration)}` : ""}`,
  },
  {
    id: "stopweather", command: "stopweather", label: "Stop Weather", group: "World Events",
    description: "Stop weather on the server.", fields: [], build: () => "stopweather",
  },
  {
    id: "setTimeSpeed", command: "setTimeSpeed", label: "Set Time Speed", group: "World Events",
    description: "Set the time multiplier on the server.",
    fields: [{ key: "period", label: "Multiplier", type: "number", placeholder: "10" }],
    build: (v) => `setTimeSpeed ${v.period}`,
  },
  {
    id: "worldgen", command: "worldgen", label: "World Generator Control", group: "World Events",
    description: "Control the full world generator.",
    fields: [{ key: "sub", label: "Action", type: "select", options: ["start", "recheck", "stop", "status"] }],
    build: (v) => `worldgen ${v.sub}`,
  },

  // --- Server / Lua ---
  {
    id: "changeoption", command: "changeoption", label: "Change Server Option", group: "Server / System",
    description: 'Use: /changeoption optionName "newValue" (also on Server page .ini editor)',
    fields: [
      { key: "option", label: "Option Name", type: "text" },
      { key: "value", label: "New Value", type: "text" },
    ],
    build: (v) => `changeoption ${v.option} ${q(v.value)}`,
  },
  {
    id: "reloadoptions", command: "reloadoptions", label: "Reload Server Options", group: "Server / System",
    description: "Reload server options (ServerOptions.ini) and send to clients.",
    fields: [], build: () => "reloadoptions",
  },
  {
    id: "reloadlua", command: "reloadlua", label: "Reload Lua Script", group: "Server / System",
    description: 'Use: /reloadlua "filename"',
    fields: [{ key: "filename", label: "Filename", type: "text" }],
    build: (v) => `reloadlua ${q(v.filename)}`,
  },
  {
    id: "reloadalllua", command: "reloadalllua", label: "Reload All Lua Scripts", group: "Server / System",
    description: "Its in-game description is a verbatim copy of reloadlua's, with no filename argument shown - assumed to reload everything with no arguments.",
    confidence: "low", fields: [], build: () => "reloadalllua",
  },
  {
    id: "checkModsNeedUpdate", command: "checkModsNeedUpdate", label: "Check Mods Need Update", group: "Server / System",
    description: "Indicates whether a mod has been updated. Writes the answer to the server log file.",
    fields: [], build: () => "checkModsNeedUpdate",
  },
  {
    id: "showoptions", command: "showoptions", label: "Show Options", group: "Server / System",
    description: "Show the list of current server options and values.",
    fields: [], build: () => "showoptions",
  },
  {
    id: "stats", command: "stats", label: "Server Stats", group: "Server / System",
    description: "Get server statistics. Undocumented sub-arguments - try \"help\" as the argument.",
    confidence: "low",
    fields: [{ key: "args", label: "Arguments (optional)", type: "text-optional", placeholder: "help" }],
    build: (v) => `stats${v.args ? ` ${v.args}` : ""}`,
  },
  {
    id: "log", command: "log", label: "Set Log Level", group: "Server / System",
    description: "Undocumented in the server's own help output (\"Use /log %1$s %2$s\" - literal placeholder text).",
    confidence: "low",
    fields: [
      { key: "a", label: "Argument 1", type: "text" },
      { key: "b", label: "Argument 2", type: "text-optional" },
    ],
    build: (v) => `log ${v.a}${v.b ? ` ${v.b}` : ""}`,
  },
  {
    id: "list", command: "list", label: "List (undocumented)", group: "Server / System",
    description: "Undocumented in the server's own help output.",
    confidence: "low", fields: [], build: () => "list",
  },
  {
    id: "remove", command: "remove", label: "Remove (undocumented)", group: "Server / System",
    description: "Undocumented in the server's own help output.",
    confidence: "low",
    fields: [{ key: "args", label: "Arguments", type: "text-optional" }],
    build: (v) => `remove${v.args ? ` ${v.args}` : ""}`,
  },
];

export const COMMAND_GROUPS = Array.from(new Set(SERVER_COMMANDS.map((c) => c.group)));
