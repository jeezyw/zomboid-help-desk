export type FieldOption = { value: number; label: string };

// Shared shape for both the SandboxVars.lua editor and the .ini editor - the backend
// schemas (sandbox_schema.py / ini_schema.py) both build this same structure.
export type SettingField = {
  key: string;
  label: string;
  description: string;
  type: "select" | "toggle" | "slider" | "number" | "text";
  options: FieldOption[] | null;
  min: number | null;
  max: number | null;
  step: number | null;
  value: any;
  known: boolean;
  sensitive: boolean;
  category: string;
  // Only present in the Sandbox schema (sandbox_schema.py) - the .ini editor
  // doesn't have Priority Vars/category reassignment, so these are absent there.
  favorite?: boolean;
  category_overridden?: boolean;
};
export type SettingCategory = { id: string; title: string; fields: SettingField[] };

export type SandboxPreset = {
  id: number;
  name: string;
  created_at: string;
  profile: string;
  field_count: number;
};
export type ApplyPresetResult = {
  ok: boolean;
  restart_required: boolean;
  applied_count: number;
  skipped: string[];
};

export type ServerProfile = {
  name: string;
  directory: string;
  sandbox_vars: string;
  ini: string | null;
  spawnpoints: string | null;
  spawnregions: string | null;
};

export type ServerInfo = {
  host: {
    cpu_percent: number;
    memory: { used: number; total: number; percent: number };
    disk: {
      used: number;
      total: number;
      zomboid_data_bytes: number | null;
      workshop_bytes: number | null;
      data_size_computed_at: string | null;
    };
  };
  // Best-effort - null when Docker control is disabled/unreachable (never an
  // error state on its own, the host metrics above still work independently).
  process: {
    cpu_percent: number | null;
    memory_bytes: number | null;
  };
  docker_control_enabled: boolean;
};

export type ModEntry = {
  mod_id: string;
  folder_name: string;
  workshop_id: string;
  name: string;
  description: string;
  path: string;
  enabled: boolean;
};
export type ModsResponse = {
  installed: ModEntry[];
  load_order: string[];
  workshop_items: string[];
  ini_path: string;
};

export type WorkshopDependency = {
  workshop_id: string;
  title: string;
  already_queued: boolean;
  already_installed: boolean;
};
export type WorkshopItem = {
  workshop_id: string;
  title: string;
  description: string;
  preview_url: string | null;
  file_size: number;
  tags: string[];
  dependencies: WorkshopDependency[];
  already_queued: boolean;
  already_installed: boolean;
};
export type WorkshopQueueResult = { ok: boolean; added: string[]; note: string };

export type Backup = {
  id: number;
  profile: string;
  created_at: string;
  kind: "manual" | "scheduled" | "pre-change" | "pre-restore-safety";
  size_bytes: number;
  path: string;
  includes_save_data: boolean;
  save_dir_path: string | null;
  note: string;
};
export type RetentionPolicy = {
  hourly: number;
  daily: number;
  weekly: number;
  monthly: number;
  always_keep_manual: boolean;
};

export type ScheduleMode = "off" | "daily_at" | "interval_hours" | "when_empty";
export type ScheduleConfig = {
  mode: ScheduleMode;
  time_of_day: string | null;
  interval_hours: number | null;
  last_run_at: string | null;
  updated_at: string;
  next_run_at: string | null;
  current_player_count: number;
};

export type LogCategory = "INFO" | "WARN" | "ERROR" | "PLAYER" | "MOD" | "SYSTEM";
export type LogLine = { ts: string; text: string; category: LogCategory };

export type PlayerSession = {
  name: string;
  connected_at: string | null;
  disconnected_at?: string;
  duration_seconds: number;
};
export type PlayersResponse = {
  online: PlayerSession[];
  recent: PlayerSession[];
  poller_healthy: boolean;
  source: "rcon" | "log";
  disclaimer: string | null;
};

export type RconConfig = {
  host: string;
  port: number | null;
  password_set: boolean;
  source: "ini" | "not configured";
};
export type RconTestResult = {
  ok: boolean;
  stage: "config" | "dns" | "connect" | "auth" | "command" | null;
  detail: string;
};
export type RconCommandResult = { ok: boolean; response: string };

export type Perk = { id: string; label: string; curve: "regular" | "passive" };
export type PerksResponse = { perks: Perk[]; max_level: number };

export type PendingAction = {
  action: "stop" | "restart";
  reason: string;
  fires_at: string;
  warning_minutes: number;
};
export type ServerActionResult = {
  ok: boolean;
  // Only present for stop/restart (which go through restart_manager) - start
  // returns the plain docker_control result instead, with no "pending" field.
  pending?: PendingAction;
  detail?: string;
};

export type ConfigChange = {
  id: number;
  changed_at: string;
  source: "sandbox" | "ini";
  profile: string;
  key: string;
  old_value: any;
  new_value: any;
};

export type TodoStatus = { id: string; title: string };
export type TodoPriority = { id: string; title: string };
export type TodoItem = {
  id: string;
  text: string;
  status: string;
  priority: string;
  blocker: string;
  created_at: string;
  updated_at: string;
};
export type TodosResponse = { items: TodoItem[]; statuses: TodoStatus[]; priorities: TodoPriority[] };

export type AuthStatus = { secure_mode: boolean; authenticated: boolean };

export type Page =
  | "Dashboard" | "Sandbox" | "Server" | "Mods" | "Backups" | "Console" | "Players"
  | "RCON Tools" | "To-Do";
