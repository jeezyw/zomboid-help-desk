import type {
  ApplyPresetResult, AuthStatus, Backup, BaseMapStatus, BundledServerSettings, Calibration,
  CalibrationPoint, ConfigChange, LogLine, MapConfig, MapPlayersResponse, MapRenderStatus,
  MapSetupStatus, ModsResponse, PendingAction, PerksResponse, PlayersResponse, RconCommandResult,
  RconConfig, RconTestResult, RetentionPolicy, SandboxPreset, ScheduleConfig, ServerActionResult,
  ServerInfo, ServerProfile, SettingCategory, SteamStatus, TodoItem, TodosResponse, WorkshopItem,
  WorkshopQueueResult,
} from "./types";

class ApiError extends Error {}

// Registered by App.tsx once, on mount - lets any API call anywhere bounce the
// user back to the login screen the moment a session expires or is revoked
// mid-use, instead of just surfacing a confusing "Authentication required" toast
// on whatever page happened to make the call.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    if (r.status === 401 && path !== "/api/auth/login") onUnauthorized?.();
    const payload = await r.json().catch(() => ({}));
    throw new ApiError(payload.detail || `${method} ${path} failed (${r.status})`);
  }
  return r.json();
}

export { ApiError };

// --- Auth ---
export const getAuthStatus = () => request<AuthStatus>("GET", "/api/auth/status");
export const login = (username: string, password: string) =>
  request<{ ok: boolean }>("POST", "/api/auth/login", { username, password });
export const logout = () => request<{ ok: boolean }>("POST", "/api/auth/logout");

// --- Server ---
export const getServer = () => request<ServerInfo>("GET", "/api/server");
export const serverAction = (action: "start" | "stop" | "restart", warningMinutes?: number) =>
  request<ServerActionResult>(
    "POST", `/api/server/${action}`,
    warningMinutes !== undefined ? { warning_minutes: warningMinutes } : undefined
  );
export const getProfiles = () =>
  request<{ profiles: ServerProfile[]; selected: string | null }>("GET", "/api/server/profiles");
export const selectProfile = (name: string) =>
  request<{ ok: true; selected: string }>("POST", "/api/server/profiles/select", { name });
export const getRestartWarning = () => request<{ minutes: number }>("GET", "/api/server/restart-warning");
export const setRestartWarning = (minutes: number) =>
  request<{ minutes: number }>("POST", "/api/server/restart-warning", { minutes });
export const getPendingAction = () =>
  request<{ pending: PendingAction | null }>("GET", "/api/server/pending");
export const cancelPendingAction = () =>
  request<{ ok: boolean }>("POST", "/api/server/pending/cancel");

// --- Sandbox ---
type SandboxFieldsResponse = {
  path: string;
  categories: SettingCategory[];
  all_categories: { id: string; title: string }[];
};
export const getSandboxFields = () =>
  request<SandboxFieldsResponse>("GET", "/api/sandbox/fields");
export const putSandbox = (changes: Record<string, any>) =>
  request<any>("PUT", "/api/sandbox", { changes });
export const setSandboxFavorite = (key: string, favorite: boolean) =>
  request<SandboxFieldsResponse>("POST", "/api/sandbox/favorite", { key, favorite });
export const setSandboxCategory = (key: string, category: string | null) =>
  request<SandboxFieldsResponse>("POST", "/api/sandbox/category", { key, category });
export const getSandboxPresets = () =>
  request<{ presets: SandboxPreset[] }>("GET", "/api/sandbox/presets");
export const saveSandboxPreset = (name: string) =>
  request<SandboxPreset>("POST", "/api/sandbox/presets", { name });
export const applySandboxPreset = (id: number) =>
  request<ApplyPresetResult>("POST", `/api/sandbox/presets/${id}/apply`);
export const deleteSandboxPreset = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/api/sandbox/presets/${id}`);

// --- Server .ini ---
export const getIniFields = () =>
  request<{ path: string; categories: SettingCategory[] }>("GET", "/api/ini/fields");
export const putIni = (changes: Record<string, any>) =>
  request<any>("PUT", "/api/ini", { changes });

// --- Mods ---
export const getMods = () => request<ModsResponse>("GET", "/api/mods");
export const enableMod = (mod_id: string) => request<any>("POST", "/api/mods/enable", { mod_id });
export const disableMod = (mod_id: string) => request<any>("POST", "/api/mods/disable", { mod_id });
export const reorderMods = (order: string[]) => request<any>("POST", "/api/mods/reorder", { order });
export const removeModReference = (mod_id: string) =>
  request<any>("DELETE", `/api/mods/reference/${encodeURIComponent(mod_id)}`);
export const lookupWorkshopItem = (query: string) =>
  request<WorkshopItem>("GET", `/api/mods/workshop-lookup?query=${encodeURIComponent(query)}`);
export const queueWorkshopItems = (workshop_ids: string[]) =>
  request<WorkshopQueueResult>("POST", "/api/mods/workshop-queue", { workshop_ids });
export const unqueueWorkshopItem = (mod_id: string) =>
  request<any>("POST", "/api/mods/workshop-unqueue", { mod_id });

// --- Backups ---
export const getBackups = () =>
  request<{ backups: Backup[]; retention_policy: RetentionPolicy }>("GET", "/api/backups");
export const createBackup = (opts: { kind?: string; include_save?: boolean; note?: string }) =>
  request<Backup>("POST", "/api/backups", opts);
export const restoreBackup = (id: number) => request<any>("POST", `/api/backups/${id}/restore`);
export const deleteBackup = (id: number) => request<any>("DELETE", `/api/backups/${id}`);
export const setRetentionPolicy = (policy: Partial<RetentionPolicy>) =>
  request<RetentionPolicy>("PUT", "/api/backups/retention", policy);
export const getSaveDir = () =>
  request<{ path: string | null; guessed: boolean; override: string | null }>(
    "GET", "/api/backups/save-dir"
  );
export const setSaveDir = (profile: string, path: string) =>
  request<any>("POST", "/api/backups/save-dir", { profile, path });

// --- Schedule ---
export const getSchedule = () => request<ScheduleConfig>("GET", "/api/schedule");
export const setSchedule = (body: {
  mode: string; time_of_day?: string | null; interval_hours?: number | null;
}) => request<ScheduleConfig>("POST", "/api/schedule", body);

// --- Console ---
export const getLogs = (since: string | null, tail = 300) =>
  request<{ lines: LogLine[]; cursor: string | null; path: string | null; error: string | null }>(
    "GET", `/api/logs?tail=${tail}` + (since ? `&since=${encodeURIComponent(since)}` : "")
  );

// --- Players ---
export const getPlayers = () => request<PlayersResponse>("GET", "/api/players");

// --- Objectives (to-do list) ---
export const getTodos = () => request<TodosResponse>("GET", "/api/todos");
export const addTodo = (text: string, priority?: string) =>
  request<TodoItem>("POST", "/api/todos", priority ? { text, priority } : { text });
export const setTodoStatus = (id: string, status: string) =>
  request<TodoItem>("POST", `/api/todos/${id}/status`, { status });
export const setTodoPriority = (id: string, priority: string) =>
  request<TodoItem>("POST", `/api/todos/${id}/priority`, { priority });
export const setTodoBlocker = (id: string, blocker: string) =>
  request<TodoItem>("POST", `/api/todos/${id}/blocker`, { blocker });
export const reorderTodos = (order: string[]) =>
  request<{ items: TodoItem[] }>("POST", "/api/todos/reorder", { order });
export const deleteTodo = (id: string) =>
  request<{ ok: boolean }>("DELETE", `/api/todos/${id}`);

// --- Config history ---
export const getConfigHistory = () =>
  request<{ changes: ConfigChange[] }>("GET", "/api/config-history");
export const restoreConfigChange = (id: number) =>
  request<any>("POST", `/api/config-history/${id}/restore`);

// --- RCON ---
export const getRconConfig = () => request<RconConfig>("GET", "/api/rcon/config");
export const setRconHostOverride = (host: string | null) =>
  request<RconConfig>("POST", "/api/rcon/config", { host });
export const testRconConnection = () => request<RconTestResult>("POST", "/api/rcon/test");
export const kickPlayer = (username: string) =>
  request<RconCommandResult>("POST", "/api/rcon/kick", { username });
export const banPlayer = (username: string, ip: boolean, reason?: string) =>
  request<RconCommandResult>("POST", "/api/rcon/ban", { username, ip, reason: reason || null });
export const unbanPlayer = (username: string) =>
  request<RconCommandResult>("POST", "/api/rcon/unban", { username });
export const teleportPlayer = (username: string, to_username: string) =>
  request<RconCommandResult>("POST", "/api/rcon/teleport", { username, to_username });
export const setPlayerGodmode = (username: string, enabled: boolean) =>
  request<RconCommandResult>("POST", "/api/rcon/godmode", { username, enabled });
export const sendAnnouncement = (message: string) =>
  request<RconCommandResult>("POST", "/api/rcon/announce", { message });
export const sendRconCommand = (command: string) =>
  request<RconCommandResult>("POST", "/api/rcon/command", { command });
export const getPerks = () => request<PerksResponse>("GET", "/api/rcon/perks");
export const setPlayerSkill = (username: string, perk: string, level: number) =>
  request<RconCommandResult>("POST", "/api/rcon/set-skill", { username, perk, level });

// --- Live Map ---
export const getMapConfig = () => request<MapConfig>("GET", "/api/map/config");
export const getMapPlayers = () => request<MapPlayersResponse>("GET", "/api/map/players");
export const getMapSetupStatus = () => request<MapSetupStatus>("GET", "/api/map/setup-status");
export const setupLiveMap = () =>
  request<{ ok: boolean; detail?: string; mod_installed?: boolean; enabled?: boolean }>(
    "POST", "/api/map/setup"
  );

export const getCalibration = () => request<Calibration>("GET", "/api/map/calibration");
export const setCalibration = (points: CalibrationPoint[]) =>
  request<Calibration>("POST", "/api/map/calibration", { points });
export const clearCalibration = () => request<{ ok: boolean }>("DELETE", "/api/map/calibration");

// --- Steam / bundled server files ---
export const startSteamInstall = () =>
  request<{ ok: boolean; detail?: string; status: SteamStatus }>("POST", "/api/steam/install");
export const getSteamStatus = () => request<SteamStatus>("GET", "/api/steam/status");

// --- Bundled dedicated server settings ---
export const getBundledServerSettings = () =>
  request<BundledServerSettings>("GET", "/api/server/bundled-settings");
export const setBundledServerSettings = (name: string) =>
  request<BundledServerSettings>("POST", "/api/server/bundled-settings", { name });

// --- Map rendering ---
export const startMapRender = () =>
  request<{ ok: boolean; detail?: string; status: MapRenderStatus }>("POST", "/api/map/render/start");
export const getMapRenderStatus = () => request<MapRenderStatus>("GET", "/api/map/render/status");
export const cancelMapRender = () =>
  request<{ ok: boolean; detail?: string; status?: MapRenderStatus }>("POST", "/api/map/render/cancel");

export const getBaseMapStatus = () => request<BaseMapStatus>("GET", "/api/map/base/tile/status");
export const startBaseMapTile = () =>
  request<{ ok: boolean; detail?: string; status?: BaseMapStatus }>("POST", "/api/map/base/tile/start");
export const cancelBaseMapTile = () =>
  request<{ ok: boolean; detail?: string; status?: BaseMapStatus }>("POST", "/api/map/base/tile/cancel");
