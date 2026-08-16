import { useEffect, useState } from "react";
import { Database, Download, History, RotateCw, Trash2 } from "lucide-react";
import {
  createBackup, deleteBackup, getBackups, getConfigHistory, restoreBackup,
  restoreConfigChange, setRetentionPolicy,
} from "../api";
import { TabBar } from "../components/TabBar";
import type { Backup, ConfigChange, RetentionPolicy } from "../types";

const KIND_LABEL: Record<string, string> = {
  manual: "Manual", scheduled: "Scheduled", "pre-change": "Pre-change",
  "pre-restore-safety": "Safety snapshot",
};

export function Backups({ setToast }: { setToast: (msg: string) => void }) {
  const [tab, setTab] = useState("backups");
  return (
    <>
      <TabBar
        items={[{ id: "backups", title: "Backups" }, { id: "history", title: "Configuration History" }]}
        activeId={tab}
        onSelect={setTab}
      />
      {tab === "backups" ? <BackupsPanel setToast={setToast} /> : <HistoryPanel setToast={setToast} />}
    </>
  );
}

function BackupsPanel({ setToast }: { setToast: (msg: string) => void }) {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [retention, setRetention] = useState<RetentionPolicy | null>(null);
  const [includeSave, setIncludeSave] = useState(false);
  const [creating, setCreating] = useState(false);

  async function load() {
    try {
      const data = await getBackups();
      setBackups(data.backups);
      setRetention(data.retention_policy);
    } catch (e: any) {
      setToast(e.message || "Could not load backups.");
    }
  }

  useEffect(() => { load(); }, []);

  async function create() {
    setCreating(true);
    try {
      await createBackup({ kind: "manual", include_save: includeSave });
      setToast("Backup created.");
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not create backup.");
    } finally {
      setCreating(false);
    }
  }

  async function restore(id: number) {
    if (!window.confirm("Restore this backup? A safety snapshot of the current state will be created first.")) return;
    try {
      await restoreBackup(id);
      setToast("Restored. A safety backup of the prior state was created. Restart the server to apply.");
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not restore backup.");
    }
  }

  async function remove(id: number) {
    if (!window.confirm("Delete this backup permanently?")) return;
    try {
      await deleteBackup(id);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not delete backup.");
    }
  }

  async function saveRetention(patch: Partial<RetentionPolicy>) {
    try {
      setRetention(await setRetentionPolicy(patch));
    } catch (e: any) {
      setToast(e.message || "Could not save retention policy.");
    }
  }

  return (
    <>
      <section className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title"><span>Create Backup</span><Database size={16} /></div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <input type="checkbox" checked={includeSave} onChange={(e) => setIncludeSave(e.target.checked)} />
          Include save data (slower, larger archive)
        </label>
        <button className="primary" onClick={create} disabled={creating}>
          {creating ? "Creating…" : "Create Backup"}
        </button>
      </section>

      {retention && (
        <section className="panel" style={{ marginBottom: 18 }}>
          <div className="panel-title"><span>Retention</span></div>
          <div className="settings-grid">
            {(["hourly", "daily", "weekly", "monthly"] as const).map((k) => (
              <div className="setting" key={k}>
                <label>{k[0].toUpperCase() + k.slice(1)} kept</label>
                <input
                  type="number" min={0} value={retention[k]}
                  onChange={(e) => saveRetention({ [k]: Number(e.target.value) } as any)}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-title"><span>Backups</span></div>
        {!backups.length && <div className="empty">No backups yet.</div>}
        {backups.map((b) => (
          <div className="profile-card" key={b.id}>
            <div className="profile-name">
              {new Date(b.created_at).toLocaleString()}
              <span className="pill">{KIND_LABEL[b.kind] || b.kind}</span>
              {b.includes_save_data && <span className="pill pill-muted">+save data</span>}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
              <small className="muted">{(b.size_bytes / 1024 / 1024).toFixed(1)} MB{b.note ? ` · ${b.note}` : ""}</small>
              <div style={{ display: "flex", gap: 8 }}>
                <a className="icon-btn" href={`/api/backups/${b.id}/download`} title="Download"><Download size={15} /></a>
                <button className="icon-btn" onClick={() => restore(b.id)} title="Restore"><RotateCw size={15} /></button>
                <button className="icon-btn" onClick={() => remove(b.id)} title="Delete"><Trash2 size={15} /></button>
              </div>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}

function HistoryPanel({ setToast }: { setToast: (msg: string) => void }) {
  const [changes, setChanges] = useState<ConfigChange[]>([]);

  async function load() {
    try {
      setChanges((await getConfigHistory()).changes);
    } catch (e: any) {
      setToast(e.message || "Could not load configuration history.");
    }
  }

  useEffect(() => { load(); }, []);

  async function restore(id: number) {
    if (!window.confirm("Revert this setting to its previous value?")) return;
    try {
      await restoreConfigChange(id);
      setToast("Reverted. Restart the server for changes to take effect.");
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not revert this change.");
    }
  }

  return (
    <section className="panel">
      <div className="panel-title"><span>Configuration History</span><History size={16} /></div>
      {!changes.length && <div className="empty">No configuration changes recorded yet.</div>}
      {changes.map((c) => (
        <div className="profile-card" key={c.id}>
          <div className="profile-name">
            {c.key}
            <span className="pill pill-muted">{c.source}</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <small className="muted">
              {new Date(c.changed_at).toLocaleString()} · {JSON.stringify(c.old_value)} → {JSON.stringify(c.new_value)}
            </small>
            <button className="icon-btn" onClick={() => restore(c.id)}>Revert</button>
          </div>
        </div>
      ))}
    </section>
  );
}
