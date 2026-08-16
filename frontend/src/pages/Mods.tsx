import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Download, Package, Trash2, X } from "lucide-react";
import {
  disableMod, enableMod, getMods, lookupWorkshopItem, queueWorkshopItems, removeModReference,
  reorderMods, unqueueWorkshopItem,
} from "../api";
import type { ModsResponse, WorkshopItem } from "../types";

const fmtBytes = (n: number) => {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
};

export function Mods({ setToast }: { setToast: (msg: string) => void }) {
  const [data, setData] = useState<ModsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setData(await getMods());
    } catch (e: any) {
      setToast(e.message || "Could not load mods.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function toggle(modId: string, enabled: boolean) {
    try {
      await (enabled ? disableMod(modId) : enableMod(modId));
      setToast(enabled ? `Disabled ${modId}.` : `Enabled ${modId}.`);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not update mod state.");
    }
  }

  async function move(modId: string, dir: -1 | 1) {
    if (!data) return;
    const order = [...data.load_order];
    const i = order.indexOf(modId);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j], order[i]];
    try {
      await reorderMods(order);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not reorder mods.");
    }
  }

  async function remove(modId: string) {
    if (!window.confirm(`Remove ${modId} from the server config? Mod files stay on disk.`)) return;
    try {
      await removeModReference(modId);
      setToast(`Removed ${modId} from the server config.`);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not remove mod reference.");
    }
  }

  async function cancelPending(workshopId: string) {
    try {
      await unqueueWorkshopItem(workshopId);
      setToast(`Cancelled Workshop item ${workshopId}.`);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not cancel.");
    }
  }

  const enabledMods = data?.load_order ?? [];
  const orphaned = data ? data.load_order.filter((id) => !data.installed.some((m) => m.mod_id === id)) : [];
  const pendingDownloads = data
    ? data.workshop_items.filter((wid) => !data.installed.some((m) => m.workshop_id === wid))
    : [];

  return (
    <>
      <AddModPanel setToast={setToast} onQueued={load} />

      {pendingDownloads.length > 0 && (
        <section className="panel" style={{ marginBottom: 18 }}>
          <div className="panel-title"><span>Pending Download</span></div>
          <small className="muted" style={{ display: "block", marginBottom: 10 }}>
            Queued via Workshop ID - not on disk yet. Restart the server to download these,
            then they'll move into Installed Mods below.
          </small>
          {pendingDownloads.map((wid) => (
            <div className="mod-row" key={wid}>
              <div className="mod-row-info"><div>Workshop ID: {wid}</div></div>
              <div className="mod-row-actions">
                <button className="icon-btn" onClick={() => cancelPending(wid)} title="Cancel"><X size={15} /></button>
              </div>
            </div>
          ))}
        </section>
      )}

      {loading && !data ? (
        <section className="panel"><div className="empty">Loading mods…</div></section>
      ) : !data || (!data.installed.length && !data.load_order.length) ? (
        <section className="empty large">
          <Package size={42} />
          <h2>No mods detected</h2>
          <p>Nothing was found on disk or referenced in the server .ini yet. Add one above.</p>
        </section>
      ) : (
        <section className="panel">
          <div className="panel-title">
            <span>Installed Mods</span>
            <span className="muted">{data.ini_path}</span>
          </div>

          {data.installed.map((m) => {
            const idx = enabledMods.indexOf(m.mod_id);
            return (
              <div className="mod-row" key={m.mod_id}>
                <label className="switch">
                  <input type="checkbox" checked={m.enabled} onChange={() => toggle(m.mod_id, m.enabled)} />
                  <span className="switch-track"><span className="switch-thumb" /></span>
                </label>
                <div className="mod-row-info">
                  <div>{m.name} <span className="muted">· {m.mod_id}</span></div>
                  <small>Workshop ID: {m.workshop_id}</small>
                </div>
                {m.enabled && (
                  <div className="mod-row-actions">
                    <button className="icon-btn" disabled={idx <= 0} onClick={() => move(m.mod_id, -1)}><ArrowUp size={15} /></button>
                    <button className="icon-btn" disabled={idx < 0 || idx >= enabledMods.length - 1} onClick={() => move(m.mod_id, 1)}><ArrowDown size={15} /></button>
                    <button className="icon-btn" onClick={() => remove(m.mod_id)}><Trash2 size={15} /></button>
                  </div>
                )}
              </div>
            );
          })}

          {orphaned.length > 0 && (
            <>
              <div className="panel-title" style={{ marginTop: 20 }}><span>Referenced but not found on disk</span></div>
              {orphaned.map((id) => (
                <div className="mod-row" key={id}>
                  <span className="pill pill-muted">missing</span>
                  <div className="mod-row-info"><div>{id}</div></div>
                  <div className="mod-row-actions">
                    <button className="icon-btn" onClick={() => remove(id)}><Trash2 size={15} /></button>
                  </div>
                </div>
              ))}
            </>
          )}
        </section>
      )}
    </>
  );
}

function AddModPanel({
  setToast, onQueued,
}: {
  setToast: (msg: string) => void;
  onQueued: () => void;
}) {
  const [query, setQuery] = useState("");
  const [looking, setLooking] = useState(false);
  const [result, setResult] = useState<WorkshopItem | null>(null);
  const [selectedDeps, setSelectedDeps] = useState<Set<string>>(new Set());
  const [queuing, setQueuing] = useState(false);

  async function lookup() {
    if (!query.trim()) return;
    setLooking(true);
    setResult(null);
    try {
      const r = await lookupWorkshopItem(query.trim());
      setResult(r);
      setSelectedDeps(new Set(
        r.dependencies.filter((d) => !d.already_installed && !d.already_queued).map((d) => d.workshop_id)
      ));
    } catch (e: any) {
      setToast(e.message || "Lookup failed.");
    } finally {
      setLooking(false);
    }
  }

  function toggleDep(id: string) {
    setSelectedDeps((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function queue() {
    if (!result) return;
    setQueuing(true);
    try {
      const ids = [result.workshop_id, ...selectedDeps];
      const r = await queueWorkshopItems(ids);
      setToast(r.added.length ? `Queued ${r.added.length} item(s) - ${r.note}` : r.note);
      setResult(null);
      setQuery("");
      onQueued();
    } catch (e: any) {
      setToast(e.message || "Could not queue mod.");
    } finally {
      setQueuing(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Add Mod</span><Download size={16} /></div>
      <small className="muted" style={{ display: "block", marginBottom: 10 }}>
        Paste a Steam Workshop URL or item ID to look it up. Queueing adds it to
        WorkshopItems= - the server downloads queued items itself the next time it
        starts, they won't show up in Installed Mods until then.
      </small>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          type="text"
          placeholder="https://steamcommunity.com/sharedfiles/filedetails/?id=… or a numeric id"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1 }}
          onKeyDown={(e) => { if (e.key === "Enter") lookup(); }}
        />
        <button onClick={lookup} disabled={looking || !query.trim()}>{looking ? "Looking up…" : "Look Up"}</button>
      </div>

      {result && (
        <div className="mod-row" style={{ marginTop: 14, alignItems: "flex-start" }}>
          {result.preview_url && (
            <img
              src={result.preview_url} alt=""
              style={{ width: 96, height: 54, objectFit: "cover", borderRadius: 6, flex: "none" }}
            />
          )}
          <div className="mod-row-info">
            <div>{result.title}</div>
            <small>
              Workshop ID: {result.workshop_id}
              {result.file_size ? ` · ${fmtBytes(result.file_size)}` : ""}
              {result.tags.length ? ` · ${result.tags.join(", ")}` : ""}
            </small>

            {result.description && (
              <p
                style={{
                  marginTop: 8, marginBottom: 0, color: "#9fb0ba", fontSize: 12,
                  maxHeight: 120, overflow: "auto", whiteSpace: "pre-wrap",
                }}
              >
                {result.description}
              </p>
            )}

            {result.already_installed && (
              <div className="notice" style={{ marginTop: 10 }}>Already installed on disk.</div>
            )}
            {!result.already_installed && result.already_queued && (
              <div className="notice" style={{ marginTop: 10 }}>Already queued for download.</div>
            )}

            {result.dependencies.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <small className="muted">Requires:</small>
                {result.dependencies.map((d) => (
                  <label key={d.workshop_id} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, fontSize: 13 }}>
                    <input
                      type="checkbox"
                      checked={selectedDeps.has(d.workshop_id)}
                      disabled={d.already_installed || d.already_queued}
                      onChange={() => toggleDep(d.workshop_id)}
                    />
                    {d.title}
                    {d.already_installed && <span className="pill">installed</span>}
                    {!d.already_installed && d.already_queued && <span className="pill pill-muted">queued</span>}
                  </label>
                ))}
              </div>
            )}

            {!result.already_installed && (
              <div style={{ marginTop: 12 }}>
                <button className="primary" onClick={queue} disabled={queuing || result.already_queued}>
                  {queuing ? "Queuing…" : result.already_queued ? "Already Queued" : "Queue for Download"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
