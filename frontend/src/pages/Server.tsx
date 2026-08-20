import { useEffect, useState } from "react";
import {
  AlertTriangle, Clock, Download, Info, Play, Power, RotateCw, Square, XCircle,
} from "lucide-react";
import {
  cancelPendingAction, getBundledServerSettings, getIniFields, getPendingAction, getProfiles,
  getRconConfig, getRestartWarning, getSchedule, getServer, putIni, selectProfile,
  serverAction, setBundledServerSettings, setRconHostOverride, setRestartWarning, setSchedule,
  testRconConnection,
} from "../api";
import { usePolling } from "../hooks/usePolling";
import { SettingsEditor } from "../components/SettingsEditor";
import { FileCheck } from "../components/FileCheck";
import type {
  PendingAction, RconConfig, RconTestResult, ScheduleConfig, ScheduleMode, ServerProfile,
  SettingCategory,
} from "../types";

export function Server({ setToast }: { setToast: (msg: string) => void }) {
  const [profiles, setProfiles] = useState<ServerProfile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [rcon, setRcon] = useState<RconConfig | null>(null);
  // Deploy-time settings (DOCKER_CONTROL_ENABLED/SERVER_MODE), not something
  // that changes at runtime - one fetch on mount is enough, no need to poll it.
  const [dockerControlEnabled, setDockerControlEnabled] = useState(false);
  const [serverMode, setServerMode] = useState<"external" | "bundled">("external");

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
    getServer().then((s) => {
      setDockerControlEnabled(s.docker_control_enabled);
      setServerMode(s.server_mode);
    }).catch(() => {});
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
      {serverMode === "bundled" && <BundledServerPanel setToast={setToast} />}
      <ServerFilesPanel profiles={profiles} selected={selected} onSelect={onSelect} />
      <SchedulePanel setToast={setToast} rconConfigured={rcon?.password_set ?? false} />
      <IniEditor setToast={setToast} rcon={rcon} onRconChange={setRcon} />
      <AboutPanel />
    </>
  );
}

function BundledServerPanel({ setToast }: { setToast: (msg: string) => void }) {
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);

  useEffect(() => {
    getBundledServerSettings().then((s) => setName(s.name)).catch(() => {});
  }, []);

  async function saveName() {
    if (!name.trim()) return;
    setSavingName(true);
    try {
      const s = await setBundledServerSettings(name.trim());
      setName(s.name);
      setToast("Server name saved.");
    } catch (e: any) {
      setToast(e.message || "Could not save the server name.");
    } finally {
      setSavingName(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Dedicated Server</span><Download size={16} /></div>

      <p className="muted" style={{ marginTop: 0 }}>
        Bundled server mode - this app installs and runs the Project Zomboid dedicated
        server itself, as a subprocess of this container (no Docker access needed). Set a
        server name, install/update the files from the Install Server Files panel below,
        then use Start above to launch it for the first time; the server generates its own
        config on first boot, which will appear in Server Files below once it does.
      </p>

      <div className="settings-grid">
        <div className="setting">
          <label>Server Name</label>
          <input
            type="text" value={name} onChange={(e) => setName(e.target.value)}
            onBlur={saveName} disabled={savingName} placeholder="servertest"
          />
        </div>
      </div>
    </section>
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

const BUILD_VERSION = "0.4.1";

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

// Rendered inside the .ini editor's Network tab (see IniEditor below), alongside
// the RCONPort/RCONPassword fields that already live there - styled to match
// SettingsEditor's own field rows (.sandbox-field/-label/-control) even though
// this isn't a schema-driven .ini field. RCON Host is a webui-only override
// (stored in its own db, see rcon_config.py), independent of the .ini file, so
// it can't just be another entry in the .ini schema itself.
function RconHostField({
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
    <>
      {!rcon?.password_set && (
        <div className="notice notice-warning" style={{ marginBottom: 10 }}>
          <AlertTriangle size={14} />
          RCON isn't configured. Set RCON Port and RCON Password above, restart the
          server, then test the connection below.
        </div>
      )}

      <div className="sandbox-field">
        <div className="sandbox-field-label">
          <label>RCON Host</label>
          <small>Container name or IP the WebUI uses to reach RCON - separate from the game's own network settings above.</small>
        </div>
        <div className="sandbox-field-control">
          <input
            type="text" value={hostInput} placeholder="container name or IP"
            onChange={(e) => setHostInput(e.target.value)}
            onBlur={saveHost}
          />
        </div>
      </div>

      <div className="sandbox-field">
        <div className="sandbox-field-label">
          <label>RCON Connection Test</label>
          <small>
            {testResult ? (testResult.ok ? "Connected." : `Failed at "${testResult.stage}": ${testResult.detail}`) : "Not tested yet."}
          </small>
        </div>
        <div className="sandbox-field-control">
          <button onClick={test} disabled={testing}>{testing ? "Testing…" : "Test Connection"}</button>
        </div>
      </div>
    </>
  );
}

function IniEditor({
  setToast, rcon, onRconChange,
}: {
  setToast: (msg: string) => void;
  rcon: RconConfig | null;
  onRconChange: (c: RconConfig) => void;
}) {
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
      extraFieldsByCategory={{
        network: <RconHostField rcon={rcon} onChange={onRconChange} setToast={setToast} />,
      }}
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
          : "No in-game stop/restart warning is sent (RCON isn't configured) - players will be disconnected without notice. Set it up in the Server .ini editor's Network tab below."}
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
