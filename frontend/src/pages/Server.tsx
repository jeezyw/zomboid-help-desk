import { useEffect, useState } from "react";
import {
  AlertTriangle, Clock, ExternalLink, Info, Play, Power, RotateCw, Shield, Square, Terminal, XCircle,
} from "lucide-react";
import {
  cancelPendingAction, getIniFields, getPendingAction, getPlayers, getProfiles, getRconConfig,
  getRestartWarning, getSchedule, getServer, putIni, selectProfile, sendRconCommand, serverAction,
  setRconHostOverride, setRestartWarning, setSchedule, testRconConnection,
} from "../api";
import { usePolling } from "../hooks/usePolling";
import { SettingsEditor } from "../components/SettingsEditor";
import { FileCheck } from "../components/FileCheck";
import { ItemPicker } from "../components/ItemPicker";
import { COMMAND_GROUPS, SERVER_COMMANDS } from "../serverCommands";
import type {
  PendingAction, RconConfig, RconTestResult, ScheduleConfig, ScheduleMode, ServerProfile,
  SettingCategory,
} from "../types";

export function Server({ setToast }: { setToast: (msg: string) => void }) {
  const [profiles, setProfiles] = useState<ServerProfile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [rcon, setRcon] = useState<RconConfig | null>(null);
  // A deploy-time setting (DOCKER_CONTROL_ENABLED), not something that changes at
  // runtime - one fetch on mount is enough, no need to poll it.
  const [dockerControlEnabled, setDockerControlEnabled] = useState(false);

  async function loadProfiles() {
    try {
      const data = await getProfiles();
      setProfiles(data.profiles);
      setSelected(data.selected);
    } catch {
      // ServerFilesPanel shows its own empty state
    }
  }

  useEffect(() => {
    loadProfiles();
    getRconConfig().then(setRcon).catch(() => {});
    getServer().then((s) => setDockerControlEnabled(s.docker_control_enabled)).catch(() => {});
  }, []);

  async function onSelect(name: string) {
    try {
      await selectProfile(name);
      setToast(`Using server profile "${name}".`);
      await loadProfiles();
    } catch (e: any) {
      setToast(e.message || "Could not select that profile.");
    }
  }

  return (
    <>
      <ServerControlPanel setToast={setToast} dockerControlEnabled={dockerControlEnabled} />
      <ServerFilesPanel profiles={profiles} selected={selected} onSelect={onSelect} />
      <RconSetupPanel rcon={rcon} onChange={setRcon} setToast={setToast} />
      <SendCommandPanel setToast={setToast} />
      <SchedulePanel setToast={setToast} rconConfigured={rcon?.password_set ?? false} />
      <IniEditor setToast={setToast} />
      <AboutPanel />
    </>
  );
}

function fmtCountdown(firesAt: string): string {
  const seconds = Math.max(0, Math.round((new Date(firesAt).getTime() - Date.now()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.ceil(seconds / 60)}m`;
}

const RESTART_DELAY_OPTIONS = Array.from({ length: 31 }, (_, i) => i); // 0-30 minutes

function ServerControlPanel({
  setToast, dockerControlEnabled,
}: {
  setToast: (msg: string) => void;
  dockerControlEnabled: boolean;
}) {
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [picking, setPicking] = useState<"stop" | "restart" | null>(null);
  const [delay, setDelay] = useState(1);
  const [busy, setBusy] = useState(false);

  usePolling(async () => {
    if (!dockerControlEnabled) return;
    try {
      setPending((await getPendingAction()).pending);
    } catch {
      // non-critical
    }
  }, 5000);

  async function start() {
    setBusy(true);
    setToast("Starting server...");
    try {
      await serverAction("start");
      setToast("Server start request complete.");
    } catch (e: any) {
      setToast(e.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  function begin(action: "stop" | "restart") {
    setDelay(1);
    setPicking(action);
  }

  async function confirmAction() {
    if (!picking) return;
    const verb = picking === "restart" ? "Restart" : "Stop";
    const when = delay === 0 ? "immediately" : `in ${delay} minute${delay !== 1 ? "s" : ""}`;
    if (!window.confirm(`${verb} the server ${when}?`)) return;

    setBusy(true);
    try {
      const result = await serverAction(picking, delay);
      if (result.pending) {
        setPending(result.pending);
        const mins = result.pending.warning_minutes;
        setToast(
          mins > 0
            ? `${verb} warning sent - ${picking === "restart" ? "restarting" : "stopping"} in ${mins} minute${mins !== 1 ? "s" : ""}.`
            : `Server ${picking} request complete.`
        );
      } else {
        setToast(result.detail || `Could not ${picking} the server.`);
      }
    } catch (e: any) {
      setToast(e.message || "Action failed.");
    } finally {
      setBusy(false);
      setPicking(null);
    }
  }

  async function cancelPending() {
    try {
      await cancelPendingAction();
      setPending(null);
      setToast("Pending action cancelled.");
    } catch (e: any) {
      setToast(e.message || "Could not cancel.");
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Server Control</span><Power size={16} /></div>

      {!dockerControlEnabled && (
        <div className="notice notice-warning">
          <AlertTriangle size={14} />
          Docker control is disabled - set <code>DOCKER_CONTROL_ENABLED=true</code> and
          uncomment the docker.sock mount in docker-compose.yml to Start/Stop/Restart the
          server from here.
        </div>
      )}

      {dockerControlEnabled && pending && (
        <div className="pending-bar" style={{ marginBottom: 14, position: "static" }}>
          <div className="pending-info">
            <AlertTriangle size={16} />
            Server {pending.action === "restart" ? "restarting" : "stopping"} in {fmtCountdown(pending.fires_at)}
            {pending.reason && pending.reason !== "manual" ? ` (${pending.reason})` : ""}
          </div>
          <div className="pending-actions">
            <button onClick={cancelPending}><XCircle size={14} /> Cancel</button>
          </div>
        </div>
      )}

      {dockerControlEnabled && (
        <div className="hero-buttons">
          <button className="primary" onClick={start} disabled={busy || picking !== null}><Play size={16} /> Start</button>
          <button onClick={() => begin("stop")} disabled={busy || picking !== null}><Square size={16} /> Stop</button>
          <button onClick={() => begin("restart")} disabled={busy || picking !== null}><RotateCw size={16} /> Restart</button>
        </div>
      )}

      {dockerControlEnabled && picking && (
        <div className="mod-row" style={{ marginTop: 14 }}>
          <div className="mod-row-info">
            <label style={{ display: "block", marginBottom: 6 }}>
              Delay before {picking === "restart" ? "restarting" : "stopping"}
            </label>
            <select value={delay} onChange={(e) => setDelay(Number(e.target.value))} style={{ width: 140 }} disabled={busy}>
              {RESTART_DELAY_OPTIONS.map((m) => (
                <option key={m} value={m}>{m === 0 ? "Instant" : `${m} min${m !== 1 ? "s" : ""}`}</option>
              ))}
            </select>
          </div>
          <div className="mod-row-actions">
            <button onClick={() => setPicking(null)} disabled={busy}>Cancel</button>
            <button className={picking === "restart" ? "primary" : "danger"} onClick={confirmAction} disabled={busy}>
              Confirm {picking === "restart" ? "Restart" : "Stop"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

const BUILD_VERSION = "0.3.1";

function AboutPanel() {
  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>About</span><Info size={16} /></div>
      <div className="muted">Zomboid Help Desk &middot; Build {BUILD_VERSION}</div>
    </section>
  );
}

function ServerFilesPanel({
  profiles, selected, onSelect,
}: {
  profiles: ServerProfile[];
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  if (!profiles.length) {
    return (
      <section className="panel files-panel">
        <div className="panel-title"><span>Server Files</span></div>
        <div className="empty">
          No server config files detected. Point HOST_ZOMBOID_DATA at the directory
          containing your &lt;servername&gt;_SandboxVars.lua file (usually .../Zomboid/Server/).
        </div>
      </section>
    );
  }

  const shown = profiles.filter((p) => !selected || p.name === selected);

  return (
    <section className="panel files-panel">
      <div className="panel-title">
        <span>Server Files</span>
        {profiles.length > 1 && <span className="muted">{profiles.length} profiles detected</span>}
      </div>

      {profiles.length > 1 && (
        <select className="profile-picker" value={selected ?? ""} onChange={(e) => onSelect(e.target.value)}>
          <option value="" disabled>Choose a server profile…</option>
          {profiles.map((p) => (
            <option key={p.name} value={p.name}>{p.name} — {p.directory}</option>
          ))}
        </select>
      )}

      {shown.map((p) => (
        <div className="profile-card" key={p.name}>
          <div className="profile-name">{p.name}<span className="muted"> · {p.directory}</span></div>
          <div className="file-checklist">
            <FileCheck label="SandboxVars.lua" found path={p.sandbox_vars} />
            <FileCheck label="Server .ini" found={!!p.ini} path={p.ini} />
            <FileCheck label="Spawnpoints" found={!!p.spawnpoints} path={p.spawnpoints} />
            <FileCheck label="Spawnregions" found={!!p.spawnregions} path={p.spawnregions} />
          </div>
        </div>
      ))}
    </section>
  );
}

function RconSetupPanel({
  rcon, onChange, setToast,
}: {
  rcon: RconConfig | null;
  onChange: (c: RconConfig) => void;
  setToast: (msg: string) => void;
}) {
  const [hostInput, setHostInput] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<RconTestResult | null>(null);

  useEffect(() => {
    if (rcon) setHostInput(rcon.host);
  }, [rcon?.host]);

  async function saveHost() {
    try {
      onChange(await setRconHostOverride(hostInput || null));
      setToast("RCON host saved.");
    } catch (e: any) {
      setToast(e.message || "Could not save RCON host.");
    }
  }

  async function test() {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await testRconConnection());
    } catch (e: any) {
      setTestResult({ ok: false, stage: null, detail: e.message || "Test failed." });
    } finally {
      setTesting(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>RCON Setup</span><Shield size={16} /></div>

      {!rcon?.password_set && (
        <div className="notice notice-warning">
          <AlertTriangle size={14} />
          RCON isn't configured. Set RCONPort and RCONPassword in the .ini editor
          below, restart the server, then test the connection here.
        </div>
      )}

      <div className="settings-grid">
        <div className="setting">
          <label>RCON Host</label>
          <input
            type="text" value={hostInput} placeholder="container name or IP"
            onChange={(e) => setHostInput(e.target.value)}
            onBlur={saveHost}
          />
        </div>
        <div className="setting">
          <label>RCON Port</label>
          <input type="text" value={rcon?.port ?? "not set"} disabled />
        </div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", marginTop: 14, gap: 8 }}>
        <small className="muted">
          {testResult ? (testResult.ok ? "Connected." : `Failed at "${testResult.stage}": ${testResult.detail}`) : "Not tested yet."}
        </small>
        <button onClick={test} disabled={testing}>{testing ? "Testing…" : "Test Connection"}</button>
      </div>
    </section>
  );
}

const COMMON_COMMANDS: { label: string; command: string; danger?: boolean; confirm?: string }[] = [
  { label: "Save World", command: "save" },
  { label: "List Players", command: "players" },
  { label: "Show Options", command: "showoptions" },
  { label: "Help", command: "help" },
  { label: "Trigger Gunshot", command: "gunshot" },
];

function SendCommandPanel({ setToast }: { setToast: (msg: string) => void }) {
  const [customCommand, setCustomCommand] = useState("");
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState<string | null>(null);

  async function send(command: string, confirmMessage?: string) {
    if (!command.trim()) return;
    if (confirmMessage && !window.confirm(confirmMessage)) return;
    setSending(true);
    try {
      const r = await sendRconCommand(command);
      setResponse(r.response);
      setToast(`Sent: ${command}`);
    } catch (e: any) {
      setToast(e.message || "Command failed.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Send Command</span><Terminal size={16} /></div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        {COMMON_COMMANDS.map((c) => (
          <button
            key={c.command}
            className={c.danger ? "danger" : undefined}
            disabled={sending}
            onClick={() => send(c.command, c.confirm)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <CommandBuilder onSend={send} sending={sending} />

      <div className="panel-title" style={{ marginTop: 20 }}><span>Custom Command</span></div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          type="text" placeholder="Custom RCON command…" value={customCommand}
          onChange={(e) => setCustomCommand(e.target.value)}
          style={{ flex: 1 }}
          onKeyDown={(e) => { if (e.key === "Enter") send(customCommand); }}
        />
        <button onClick={() => send(customCommand)} disabled={sending || !customCommand.trim()}>Send</button>
      </div>

      {response !== null && (
        <pre
          style={{
            marginTop: 14, background: "#080b0d", border: "1px solid #20272c", borderRadius: 9,
            padding: 12, maxHeight: 200, overflow: "auto", color: "#b8c2c9", fontSize: 12,
            whiteSpace: "pre-wrap", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          }}
        >
          {response}
        </pre>
      )}
    </section>
  );
}

function CommandBuilder({
  onSend, sending,
}: {
  onSend: (command: string, confirmMessage?: string) => Promise<void>;
  sending: boolean;
}) {
  const [group, setGroup] = useState(COMMAND_GROUPS[0]);
  const [commandId, setCommandId] = useState(SERVER_COMMANDS.find((c) => c.group === COMMAND_GROUPS[0])!.id);
  const [values, setValues] = useState<Record<string, string>>({});
  const [online, setOnline] = useState<string[]>([]);

  useEffect(() => {
    getPlayers().then((r) => setOnline(r.online.map((p) => p.name))).catch(() => {});
  }, []);

  const inGroup = SERVER_COMMANDS.filter((c) => c.group === group);
  const def = SERVER_COMMANDS.find((c) => c.id === commandId) ?? inGroup[0];

  function pickGroup(g: string) {
    setGroup(g);
    const first = SERVER_COMMANDS.find((c) => c.group === g);
    if (first) { setCommandId(first.id); setValues({}); }
  }

  function pickCommand(id: string) {
    setCommandId(id);
    setValues({});
  }

  function setField(key: string, val: string) {
    setValues((prev) => ({ ...prev, [key]: val }));
  }

  const missingRequired = def.fields.some((f) => {
    const optional = f.type.endsWith("-optional") || f.type === "bool-flag";
    return !optional && !values[f.key]?.trim();
  });

  async function run() {
    if (missingRequired) return;
    const built = def.build(values);
    const confirmMessage = def.danger
      ? `Send "${built}"? This is a destructive/moderation command - double check the target before confirming.`
      : undefined;
    await onSend(built, confirmMessage);
  }

  return (
    <div style={{ marginBottom: 14 }}>
      <div className="panel-title" style={{ marginTop: 6 }}><span>Command Builder</span></div>

      <div className="settings-grid">
        <div className="setting">
          <label>Category</label>
          <select value={group} onChange={(e) => pickGroup(e.target.value)}>
            {COMMAND_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div className="setting">
          <label>Command</label>
          <select value={def.id} onChange={(e) => pickCommand(e.target.value)}>
            {inGroup.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>
      </div>

      <small className="muted" style={{ display: "block", marginTop: 8 }}>{def.description}</small>
      {def.confidence === "low" && (
        <div className="notice notice-warning" style={{ marginTop: 8 }}>
          <AlertTriangle size={14} />
          Undocumented/low-confidence command - the server's own help output doesn't
          describe its real arguments. Test carefully.
        </div>
      )}

      {def.fields.length > 0 && (
        <div className="settings-grid" style={{ marginTop: 10 }}>
          {def.fields.map((f) => (
            <div className="setting" key={f.key}>
              <label>{f.label}</label>
              {f.type === "player" || f.type === "player-optional" ? (
                <select value={values[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)}>
                  <option value="">{f.type === "player-optional" ? "(none)" : "Choose a player…"}</option>
                  {online.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
              ) : f.type === "bool-flag" ? (
                <select value={values[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)}>
                  <option value="">(default)</option>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : f.type === "select" ? (
                <select value={values[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)}>
                  <option value="" disabled>Choose…</option>
                  {(f.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : f.type === "item" ? (
                <>
                  <ItemPicker value={values[f.key] ?? ""} onChange={(v) => setField(f.key, v)} />
                  <a
                    href="https://pzwiki.net/wiki/PZwiki:Item_list"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="muted"
                    style={{ display: "inline-flex", alignItems: "center", gap: 5, marginTop: 6, fontSize: 12 }}
                  >
                    <ExternalLink size={12} /> Full item list (PZwiki)
                  </a>
                </>
              ) : (
                <input
                  type={f.type.startsWith("number") ? "number" : "text"}
                  value={values[f.key] ?? ""}
                  placeholder={f.placeholder}
                  onChange={(e) => setField(f.key, e.target.value)}
                />
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <button className={def.danger ? "danger" : "primary"} onClick={run} disabled={sending || missingRequired}>
          Build &amp; Send
        </button>
      </div>
    </div>
  );
}

function IniEditor({ setToast }: { setToast: (msg: string) => void }) {
  const [categories, setCategories] = useState<SettingCategory[]>([]);
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await getIniFields();
      setCategories(data.categories);
      setPath(data.path);
      setError("");
    } catch (e: any) {
      setCategories([]);
      setError(e.message || "Server .ini was not found.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function apply(changes: Record<string, any>) {
    try {
      const data = await putIni(changes);
      setToast("Saved. Backup created. Restart the server for changes to take effect.");
      await load();
      return data;
    } catch (e: any) {
      setToast(e.message || "Could not save changes.");
      throw e;
    }
  }

  return (
    <SettingsEditor
      categories={categories}
      path={path}
      loading={loading}
      error={error}
      emptyTitle="No server .ini found"
      emptyBody="This profile has no sibling .ini file yet."
      onApply={apply}
    />
  );
}

function SchedulePanel({
  setToast, rconConfigured,
}: {
  setToast: (msg: string) => void;
  rconConfigured: boolean;
}) {
  const [schedule, setScheduleState] = useState<ScheduleConfig | null>(null);
  const [mode, setMode] = useState<ScheduleMode>("off");
  const [timeOfDay, setTimeOfDay] = useState("04:00");
  const [intervalHours, setIntervalHours] = useState(6);
  const [saving, setSaving] = useState(false);
  const [warningMinutes, setWarningMinutesState] = useState(5);

  useEffect(() => {
    getRestartWarning().then((r) => setWarningMinutesState(r.minutes)).catch(() => {});
  }, []);

  async function saveWarningMinutes(minutes: number) {
    try {
      const r = await setRestartWarning(minutes);
      setWarningMinutesState(r.minutes);
      setToast("Restart warning saved.");
    } catch (e: any) {
      setToast(e.message || "Could not save restart warning.");
    }
  }

  async function load() {
    try {
      const data = await getSchedule();
      setScheduleState(data);
      setMode(data.mode);
      if (data.time_of_day) setTimeOfDay(data.time_of_day);
      if (data.interval_hours) setIntervalHours(data.interval_hours);
    } catch {
      // schedule panel just stays blank
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  async function save() {
    setSaving(true);
    try {
      const body: any = { mode };
      if (mode === "daily_at") body.time_of_day = timeOfDay;
      if (mode === "interval_hours" || mode === "when_empty") body.interval_hours = intervalHours;
      const data = await setSchedule(body);
      setScheduleState(data);
      setToast("Restart schedule saved.");
    } catch (e: any) {
      setToast(e.message || "Could not save schedule.");
    } finally {
      setSaving(false);
    }
  }

  const nextRun = schedule?.next_run_at ? new Date(schedule.next_run_at) : null;

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Scheduled Restarts</span><Clock size={16} /></div>

      <div className="notice notice-warning">
        <AlertTriangle size={14} />
        {rconConfigured
          ? `A warning is sent via RCON ${warningMinutes} minute${warningMinutes !== 1 ? "s" : ""} before a stop or restart`
            + (warningMinutes === 0 ? " (immediately, no delay)." : " - both manual and scheduled.")
          : "No in-game stop/restart warning is sent (RCON isn't configured) - players will be disconnected without notice. Set it up in the RCON Setup panel above."}
      </div>

      <div className="settings-grid">
        <div className="setting">
          <label>Mode</label>
          <select value={mode} onChange={(e) => setMode(e.target.value as ScheduleMode)}>
            <option value="off">Off</option>
            <option value="daily_at">Daily at a fixed time</option>
            <option value="interval_hours">Every N hours</option>
            <option value="when_empty">When empty (with cooldown)</option>
          </select>
        </div>

        <div className="setting">
          <label>Restart/Stop Warning (minutes)</label>
          <input
            type="number" min={0} max={60} value={warningMinutes}
            onChange={(e) => setWarningMinutesState(Number(e.target.value))}
            onBlur={(e) => saveWarningMinutes(Number(e.target.value))}
          />
        </div>

        {mode === "daily_at" && (
          <div className="setting">
            <label>Time of day (server local time)</label>
            <input type="time" value={timeOfDay} onChange={(e) => setTimeOfDay(e.target.value)} />
          </div>
        )}

        {(mode === "interval_hours" || mode === "when_empty") && (
          <div className="setting">
            <label>{mode === "interval_hours" ? "Interval (hours)" : "Minimum cooldown (hours)"}</label>
            <input
              type="number" min={1} max={168} value={intervalHours}
              onChange={(e) => setIntervalHours(Number(e.target.value))}
            />
          </div>
        )}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", marginTop: 14, gap: 8 }}>
        <small className="muted">
          {schedule?.mode === "off" && "No restart is scheduled."}
          {schedule?.mode === "daily_at" && nextRun && `Next restart: ${nextRun.toLocaleString()}`}
          {schedule?.mode === "interval_hours" && nextRun && `Next restart: ${nextRun.toLocaleString()}`}
          {schedule?.mode === "when_empty" && `Restarts once empty for the cooldown period. Players online: ${schedule.current_player_count}`}
        </small>
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save Schedule"}
        </button>
      </div>
    </section>
  );
}
