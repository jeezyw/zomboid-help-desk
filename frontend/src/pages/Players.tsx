import { useEffect, useState } from "react";
import { AlertTriangle, Users } from "lucide-react";
import {
  banPlayer, getPlayers, getRconConfig, kickPlayer, sendAnnouncement,
  setPlayerGodmode, teleportPlayer,
} from "../api";
import { usePolling } from "../hooks/usePolling";
import type { PlayersResponse, RconConfig } from "../types";

function fmtDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function Players({ setToast }: { setToast: (msg: string) => void }) {
  const [data, setData] = useState<PlayersResponse | null>(null);
  const [rcon, setRcon] = useState<RconConfig | null>(null);

  usePolling(async () => {
    setData(await getPlayers());
  }, 10000);

  useEffect(() => {
    // Only used to gate whether the RCON-backed tool sections below are shown -
    // RCON is configured on the Server page now, not here.
    getRconConfig().then(setRcon).catch(() => {});
  }, []);

  const online = data?.online.map((p) => p.name) ?? [];

  return (
    <>
      {data?.source === "log" && (
        <div className="notice notice-warning">
          <AlertTriangle size={14} />
          {data.disclaimer}
          {!data.poller_healthy && " The log poller hasn't reported in recently - this data may be stale."}
        </div>
      )}

      <OnlineSection data={data} setToast={setToast} rconConfigured={rcon?.password_set ?? false} />

      {rcon?.password_set && <AdminToolsPanel online={online} setToast={setToast} />}
      {rcon?.password_set && <PlayerToolsPanel online={online} setToast={setToast} />}

      <section className="panel">
        <div className="panel-title"><span>Recent Activity</span></div>
        {!data?.recent.length && <div className="empty">No recent activity recorded.</div>}
        {data?.recent.map((p, i) => (
          <div className="health" key={`${p.name}-${p.connected_at}-${i}`}>
            <span className="dot" />
            <span>{p.name}</span>
            <span className="health-right">
              {p.disconnected_at ? new Date(p.disconnected_at).toLocaleTimeString() : ""} · {fmtDuration(p.duration_seconds)}
            </span>
          </div>
        ))}
      </section>
    </>
  );
}

function OnlineSection({
  data, setToast, rconConfigured,
}: {
  data: PlayersResponse | null;
  setToast: (msg: string) => void;
  rconConfigured: boolean;
}) {
  const [announceText, setAnnounceText] = useState("");
  const [sending, setSending] = useState(false);
  // RCON has no query for a player's CURRENT godmode state (confirmed against the
  // real command list - see rcon_commands.py), so this can only ever reflect what
  // this app last told the server, not verified live truth - it resets on reload
  // and won't notice the state being changed some other way (a player's own debug
  // menu, another admin tool, a reconnect, etc).
  const [godmode, setGodmode] = useState<Record<string, boolean>>({});
  const [togglingGodmode, setTogglingGodmode] = useState<Set<string>>(new Set());

  async function announce() {
    if (!announceText.trim()) return;
    setSending(true);
    try {
      const r = await sendAnnouncement(announceText);
      setToast(r.response ? `Announcement: ${r.response}` : "Announcement sent.");
      setAnnounceText("");
    } catch (e: any) {
      setToast(e.message || "Announcement failed.");
    } finally {
      setSending(false);
    }
  }

  async function setGodmodeFor(name: string, enabled: boolean) {
    if (godmode[name] === enabled || togglingGodmode.has(name)) return;
    setTogglingGodmode((prev) => new Set(prev).add(name));
    try {
      await setPlayerGodmode(name, enabled);
      setGodmode((prev) => ({ ...prev, [name]: enabled }));
      setToast(`Godmode ${enabled ? "enabled" : "disabled"} for ${name}.`);
    } catch (e: any) {
      setToast(e.message || "Could not change godmode.");
    } finally {
      setTogglingGodmode((prev) => {
        const s = new Set(prev);
        s.delete(name);
        return s;
      });
    }
  }

  const GODMODE_COL_WIDTH = 132;

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Online ({data?.online.length ?? 0})</span><Users size={16} /></div>
      {!data?.online.length && <div className="empty">No players currently online.</div>}

      {rconConfigured && !!data?.online.length && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <small className="muted" style={{ width: GODMODE_COL_WIDTH, textAlign: "center" }}>Godmode</small>
        </div>
      )}
      {data?.online.map((p) => {
        const state = godmode[p.name]; // undefined = unknown/never set here, not "off"
        return (
          <div className="health" key={p.name}>
            <span className="dot online" />
            <span>{p.name}</span>
            <span className="health-right">{p.connected_at ? fmtDuration(p.duration_seconds) : "—"}</span>
            {rconConfigured && (
              <div
                style={{ display: "flex", gap: 6, width: GODMODE_COL_WIDTH, justifyContent: "center", marginLeft: 12 }}
                title="As last set here - RCON can't report a player's real current godmode state"
              >
                <button
                  className={state === true ? "primary" : undefined}
                  disabled={togglingGodmode.has(p.name)}
                  onClick={() => setGodmodeFor(p.name, true)}
                >
                  On
                </button>
                <button
                  className={state === false ? "primary" : undefined}
                  disabled={togglingGodmode.has(p.name)}
                  onClick={() => setGodmodeFor(p.name, false)}
                >
                  Off
                </button>
              </div>
            )}
          </div>
        );
      })}

      <div className="panel-title" style={{ marginTop: 20 }}><span>Announce</span></div>
      <textarea
        value={announceText}
        onChange={(e) => setAnnounceText(e.target.value)}
        placeholder="Message to broadcast to all connected players…"
        rows={2}
        style={{ width: "100%", background: "#0d1215", border: "1px solid #273039", color: "#e8edf2", borderRadius: 8, padding: 10, font: "inherit" }}
      />
      <div style={{ marginTop: 10 }}>
        <button className="primary" onClick={announce} disabled={!announceText.trim() || sending}>
          {sending ? "Sending…" : "Send Announcement"}
        </button>
      </div>
    </section>
  );
}

function AdminToolsPanel({
  online, setToast,
}: {
  online: string[];
  setToast: (msg: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(online[0] ?? null);
  const [banIp, setBanIp] = useState(false);
  const [banReason, setBanReason] = useState("");

  // See PlayerToolsPanel's identical effect below for why this is needed - `online`
  // arrives after this component's first render, so the useState default above
  // resolves to null and the <select> looks populated but isn't really selected.
  useEffect(() => {
    if (!selected || !online.includes(selected)) setSelected(online[0] ?? null);
  }, [online]);

  async function run(fn: () => Promise<any>, label: string) {
    try {
      const r = await fn();
      setToast(r.response ? `${label}: ${r.response}` : `${label} sent.`);
    } catch (e: any) {
      setToast(e.message || `${label} failed.`);
    }
  }

  async function kick() {
    if (!selected) return;
    if (!window.confirm(`Kick ${selected}?`)) return;
    await run(() => kickPlayer(selected), "Kick");
  }

  async function ban() {
    if (!selected) return;
    if (!window.confirm(`Ban ${selected}${banIp ? " (including IP)" : ""}?`)) return;
    await run(() => banPlayer(selected, banIp, banReason || undefined), "Ban");
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Admin Tools</span></div>

      {!online.length ? (
        <div className="empty">No players online to act on.</div>
      ) : (
        <>
          <div className="settings-grid">
            <div className="setting">
              <label>Player</label>
              <select value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}>
                {online.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
            <button className="danger" onClick={kick}>Kick</button>
          </div>

          <div className="mod-row" style={{ marginTop: 10 }}>
            <div className="mod-row-info">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={banIp} onChange={(e) => setBanIp(e.target.checked)} />
                Also ban IP
              </label>
              <input type="text" placeholder="reason (optional)" value={banReason} onChange={(e) => setBanReason(e.target.value)} />
            </div>
            <button className="danger" onClick={ban}>Ban</button>
          </div>
        </>
      )}
    </section>
  );
}

function PlayerToolsPanel({
  online, setToast,
}: {
  online: string[];
  setToast: (msg: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(online[0] ?? null);
  const [teleportTarget, setTeleportTarget] = useState("");

  // `online` loads asynchronously (empty on first render), so the useState default
  // above almost always resolves to null and never gets a real player - the <select>
  // visually shows a name anyway (browsers default to the first <option> when the
  // controlled value matches none), which made this look selected while `selected`
  // stayed null underneath. Keep it synced to a valid choice whenever the roster changes.
  useEffect(() => {
    if (!selected || !online.includes(selected)) setSelected(online[0] ?? null);
  }, [online]);

  async function run(fn: () => Promise<any>, label: string) {
    try {
      const r = await fn();
      setToast(r.response ? `${label}: ${r.response}` : `${label} sent.`);
    } catch (e: any) {
      setToast(e.message || `${label} failed.`);
    }
  }

  async function teleport() {
    if (!selected || !teleportTarget) return;
    await run(() => teleportPlayer(selected, teleportTarget), "Teleport");
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Player Tools</span></div>

      {!online.length ? (
        <div className="empty">No players online to act on.</div>
      ) : (
        <>
          <div className="settings-grid">
            <div className="setting">
              <label>Player</label>
              <select value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}>
                {online.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
          </div>

          <div className="mod-row" style={{ marginTop: 10 }}>
            <div className="mod-row-info">
              <select value={teleportTarget} onChange={(e) => setTeleportTarget(e.target.value)}>
                <option value="" disabled>Teleport to…</option>
                {online.filter((n) => n !== selected).map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
            <button onClick={teleport} disabled={!teleportTarget}>Teleport</button>
          </div>
        </>
      )}
    </section>
  );
}
