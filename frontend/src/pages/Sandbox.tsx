import { useEffect, useState } from "react";
import { AlertTriangle, Layers, Trash2 } from "lucide-react";
import {
  applySandboxPreset, deleteSandboxPreset, getSandboxFields, getSandboxPresets, putSandbox,
  saveSandboxPreset, serverAction, setSandboxCategory, setSandboxFavorite,
} from "../api";
import { SettingsEditor } from "../components/SettingsEditor";
import type { SandboxPreset, SettingCategory } from "../types";

export function Sandbox({ setToast }: { setToast: (msg: string) => void }) {
  const [categories, setCategories] = useState<SettingCategory[]>([]);
  const [allCategories, setAllCategories] = useState<{ id: string; title: string }[]>([]);
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await getSandboxFields();
      setCategories(data.categories);
      setAllCategories(data.all_categories);
      setPath(data.path);
      setError("");
    } catch (e: any) {
      setCategories([]);
      setError(e.message || "SandboxVars.lua was not found.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function apply(changes: Record<string, any>) {
    try {
      const data = await putSandbox(changes);
      setToast("Saved. Backup created. Restart the server for changes to take effect.");
      await load();
      return data;
    } catch (e: any) {
      setToast(e.message || "Could not save changes.");
      throw e;
    }
  }

  async function toggleFavorite(key: string, favorite: boolean) {
    try {
      const data = await setSandboxFavorite(key, favorite);
      setCategories(data.categories);
    } catch (e: any) {
      setToast(e.message || "Could not update Priority Vars.");
    }
  }

  async function reassignCategory(key: string, category: string | null) {
    try {
      const data = await setSandboxCategory(key, category);
      setCategories(data.categories);
    } catch (e: any) {
      setToast(e.message || "Could not change category.");
    }
  }

  return (
    <>
      <PresetsPanel setToast={setToast} onApplied={load} />
      <SettingsEditor
        categories={categories}
        path={path}
        loading={loading}
        error={error}
        emptyTitle="No SandboxVars.lua found"
        emptyBody="Nothing was detected under your configured Zomboid data path yet."
        onApply={apply}
        onToggleFavorite={toggleFavorite}
        onSetCategory={reassignCategory}
        allCategories={allCategories}
      />
    </>
  );
}

const RESTART_DELAY_OPTIONS = Array.from({ length: 31 }, (_, i) => i); // 0-30 minutes

function PresetsPanel({
  setToast, onApplied,
}: {
  setToast: (msg: string) => void;
  onApplied: () => void;
}) {
  const [presets, setPresets] = useState<SandboxPreset[]>([]);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [applyingId, setApplyingId] = useState<number | null>(null);
  const [restartPromptFor, setRestartPromptFor] = useState<string | null>(null);
  const [restartDelay, setRestartDelay] = useState(1);
  const [restarting, setRestarting] = useState(false);

  async function load() {
    try {
      const data = await getSandboxPresets();
      setPresets(data.presets);
    } catch (e: any) {
      setToast(e.message || "Could not load presets.");
    }
  }

  useEffect(() => { load(); }, []);

  async function save() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await saveSandboxPreset(name.trim());
      setName("");
      setToast("Preset saved.");
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not save preset.");
    } finally {
      setSaving(false);
    }
  }

  async function apply(preset: SandboxPreset) {
    if (!window.confirm(`Apply preset "${preset.name}"? This overwrites current sandbox settings with the preset's saved values.`)) return;
    setApplyingId(preset.id);
    try {
      const result = await applySandboxPreset(preset.id);
      setToast(
        result.skipped.length
          ? `Applied ${result.applied_count} setting(s) from "${preset.name}" - ${result.skipped.length} no longer exist in this file and were skipped.`
          : `Applied ${result.applied_count} setting(s) from "${preset.name}".`
      );
      onApplied();
      setRestartDelay(1);
      setRestartPromptFor(preset.name);
    } catch (e: any) {
      setToast(e.message || "Could not apply preset.");
    } finally {
      setApplyingId(null);
    }
  }

  async function remove(preset: SandboxPreset) {
    if (!window.confirm(`Delete preset "${preset.name}"?`)) return;
    try {
      await deleteSandboxPreset(preset.id);
      setToast("Preset deleted.");
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not delete preset.");
    }
  }

  async function restartNow() {
    setRestarting(true);
    try {
      const result = await serverAction("restart", restartDelay);
      if (result.pending) {
        const mins = result.pending.warning_minutes;
        setToast(
          mins > 0
            ? `Restart warning sent - restarting in ${mins} minute${mins !== 1 ? "s" : ""}.`
            : "Server restart request complete."
        );
      } else {
        setToast(result.detail || "Could not restart the server.");
      }
    } catch (e: any) {
      setToast(e.message || "Restart failed.");
    } finally {
      setRestarting(false);
      setRestartPromptFor(null);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Sandbox Presets</span><Layers size={16} /></div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <input
          type="text" placeholder="Preset name…" value={name}
          onChange={(e) => setName(e.target.value)} style={{ flex: 1 }}
          onKeyDown={(e) => { if (e.key === "Enter") save(); }}
        />
        <button className="primary" onClick={save} disabled={saving || !name.trim()}>
          {saving ? "Saving…" : "Save Current as Preset"}
        </button>
      </div>

      {!presets.length && <div className="empty">No saved presets yet.</div>}
      {presets.map((p) => (
        <div className="mod-row" key={p.id}>
          <div className="mod-row-info">
            <div>{p.name}</div>
            <small>{p.field_count} settings · saved {new Date(p.created_at).toLocaleString()} · profile: {p.profile}</small>
          </div>
          <div className="mod-row-actions">
            <button onClick={() => apply(p)} disabled={applyingId === p.id}>
              {applyingId === p.id ? "Applying…" : "Apply"}
            </button>
            <button className="icon-btn" onClick={() => remove(p)} title="Delete"><Trash2 size={15} /></button>
          </div>
        </div>
      ))}

      {restartPromptFor && (
        <div className="notice notice-warning" style={{ marginTop: 14, flexWrap: "wrap" }}>
          <AlertTriangle size={14} />
          <span style={{ flex: 1 }}>
            Preset "{restartPromptFor}" applied - restart the server for it to take effect.
          </span>
          <select
            value={restartDelay} onChange={(e) => setRestartDelay(Number(e.target.value))}
            disabled={restarting} style={{ width: 110 }}
          >
            {RESTART_DELAY_OPTIONS.map((m) => (
              <option key={m} value={m}>{m === 0 ? "Instant" : `${m} min${m !== 1 ? "s" : ""}`}</option>
            ))}
          </select>
          <button className="primary" onClick={restartNow} disabled={restarting}>
            {restarting ? "Restarting…" : "Restart"}
          </button>
          <button onClick={() => setRestartPromptFor(null)} disabled={restarting}>Not Now</button>
        </div>
      )}
    </section>
  );
}
