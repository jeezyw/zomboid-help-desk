import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, ListTree, Search, Settings, Star, X } from "lucide-react";
import type { SettingCategory, SettingField } from "../types";
import { TabBar } from "./TabBar";
import { PendingBar } from "./PendingBar";

/** Generic tabbed category/field editor shared by the SandboxVars.lua editor (Sandbox
 * page) and the server .ini editor (Server page) - both backend schemas produce the
 * exact same {categories: [{id,title,fields}]} shape. Favoriting (Priority Vars) and
 * Sort Mode (manual category reassignment) are Sandbox-only: the .ini editor usage
 * simply omits onToggleFavorite/onSetCategory/allCategories, which hides both. */
export function SettingsEditor({
  categories, path, loading, error, emptyTitle, emptyBody, onApply,
  onToggleFavorite, onSetCategory, allCategories, extraFieldsByCategory,
}: {
  categories: SettingCategory[];
  path: string;
  loading: boolean;
  error: string;
  emptyTitle: string;
  emptyBody: string;
  onApply: (changes: Record<string, any>) => Promise<any>;
  onToggleFavorite?: (key: string, favorite: boolean) => void;
  onSetCategory?: (key: string, category: string | null) => void;
  allCategories?: { id: string; title: string }[];
  // Non-schema content (e.g. the RCON Host override, which lives in the webui's
  // own db, not the .ini file) appended to the end of a specific category's field
  // list - keyed by category id. Lets a caller bolt extra, differently-persisted
  // fields onto a schema-driven category without SettingsEditor needing to know
  // anything about them.
  extraFieldsByCategory?: Record<string, ReactNode>;
}) {
  const [pending, setPending] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);
  const [activeCat, setActiveCat] = useState<string>("");
  const [sortMode, setSortMode] = useState(false);
  const [search, setSearch] = useState("");

  const allFields = useMemo(() => categories.flatMap((c) => c.fields), [categories]);
  const fieldsByKey = useMemo(() => {
    const m: Record<string, SettingField> = {};
    for (const f of allFields) m[f.key] = f;
    return m;
  }, [allFields]);
  const categoryTitleById = useMemo(() => {
    const m: Record<string, string> = {};
    for (const c of categories) m[c.id] = c.title;
    return m;
  }, [categories]);

  // Search spans every category, not just the active tab - the whole point is
  // finding a setting when you don't already know which tab it lives under.
  const searchResults = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return null;
    return allFields.filter((f) =>
      f.label.toLowerCase().includes(q)
      || f.key.toLowerCase().includes(q)
      || f.description.toLowerCase().includes(q)
    );
  }, [search, allFields]);

  useEffect(() => {
    if (categories.length && !activeCat) setActiveCat(categories[0].id);
    if (categories.length && !categories.find((c) => c.id === activeCat)) {
      setActiveCat(categories[0].id);
    }
    setPending({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categories]);

  function setValue(key: string, value: any) {
    const original = fieldsByKey[key]?.value;
    setPending((prev) => {
      const next = { ...prev };
      if (String(original) === String(value)) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }

  async function apply() {
    if (!Object.keys(pending).length) return;
    setSaving(true);
    try {
      await onApply(pending);
      setPending({});
    } catch {
      // toast already set by caller
    } finally {
      setSaving(false);
    }
  }

  if (error) {
    return (
      <section className="empty large">
        <AlertTriangle size={42} />
        <h2>Can't load settings</h2>
        <p>{error}</p>
      </section>
    );
  }

  if (loading && !categories.length) {
    return <section className="panel"><div className="empty">Loading…</div></section>;
  }

  if (!categories.length) {
    return (
      <section className="empty large">
        <Settings size={42} />
        <h2>{emptyTitle}</h2>
        <p>{emptyBody}</p>
      </section>
    );
  }

  const active = categories.find((c) => c.id === activeCat) || categories[0];

  return (
    <div className="sandbox-editor">
      <div className="settings-search">
        <Search size={15} />
        <input
          type="text"
          placeholder="Search settings by name, key, or description…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button className="icon-btn" onClick={() => setSearch("")} title="Clear search">
            <X size={14} />
          </button>
        )}
      </div>

      {searchResults ? (
        <section className="panel">
          <div className="panel-title">
            <span>Search Results ({searchResults.length})</span>
            <span className="muted">{path}</span>
          </div>
          <div className="sandbox-fields">
            {searchResults.length === 0 && <div className="empty">No settings match "{search}".</div>}
            {searchResults.map((f) => (
              <SettingFieldRow
                key={f.key}
                field={f}
                pendingValue={f.key in pending ? pending[f.key] : undefined}
                onChange={(v) => setValue(f.key, v)}
                sortMode={false}
                allCategories={allCategories}
                onToggleFavorite={onToggleFavorite}
                onSetCategory={onSetCategory}
                categoryLabel={categoryTitleById[f.category]}
              />
            ))}
          </div>
        </section>
      ) : (
        <>
          <TabBar
            items={categories.map((c) => ({ id: c.id, title: c.title, count: c.fields.length }))}
            activeId={active.id}
            onSelect={setActiveCat}
          />

          <section className="panel">
            <div className="panel-title">
              <span>{active.title}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="muted">{path}</span>
                {onSetCategory && allCategories && (
                  <button
                    className={sortMode ? "sort-mode-toggle active" : "sort-mode-toggle"}
                    onClick={() => setSortMode((s) => !s)}
                  >
                    <ListTree size={14} /> {sortMode ? "Done Sorting" : "Sort Mode"}
                  </button>
                )}
              </div>
            </div>
            <div className="sandbox-fields">
              {active.fields.map((f) => (
                <SettingFieldRow
                  key={f.key}
                  field={f}
                  pendingValue={f.key in pending ? pending[f.key] : undefined}
                  onChange={(v) => setValue(f.key, v)}
                  sortMode={sortMode}
                  allCategories={allCategories}
                  onToggleFavorite={onToggleFavorite}
                  onSetCategory={onSetCategory}
                />
              ))}
              {extraFieldsByCategory?.[active.id]}
            </div>
          </section>
        </>
      )}

      <PendingBar count={Object.keys(pending).length} saving={saving} onDiscard={() => setPending({})} onApply={apply} />
    </div>
  );
}

function SettingFieldRow({
  field, pendingValue, onChange, sortMode, allCategories, onToggleFavorite, onSetCategory, categoryLabel,
}: {
  field: SettingField;
  pendingValue: any;
  onChange: (v: any) => void;
  sortMode: boolean;
  allCategories?: { id: string; title: string }[];
  onToggleFavorite?: (key: string, favorite: boolean) => void;
  onSetCategory?: (key: string, category: string | null) => void;
  categoryLabel?: string;
}) {
  const current = pendingValue !== undefined ? pendingValue : field.value;
  const dirty = pendingValue !== undefined;
  const missing = field.value === undefined || field.value === null;

  let control: ReactNode;

  if (sortMode && allCategories && onSetCategory) {
    // Sort Mode swaps the value editor for a category picker - the row's control
    // switches purpose entirely rather than gaining a second control alongside it.
    control = (
      <div className="slider-row">
        <select value={field.category} onChange={(e) => onSetCategory(field.key, e.target.value)}>
          {allCategories.map((c) => (
            <option key={c.id} value={c.id}>{c.title}</option>
          ))}
        </select>
        {field.category_overridden && (
          <button className="icon-btn" onClick={() => onSetCategory(field.key, null)}>Reset</button>
        )}
      </div>
    );
  } else if (field.type === "select" && field.options) {
    control = (
      <select value={current ?? ""} onChange={(e) => onChange(Number(e.target.value))}>
        {missing && <option value="">—</option>}
        {field.options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    );
  } else if (field.type === "toggle") {
    control = (
      <label className="switch">
        <input type="checkbox" checked={!!current} onChange={(e) => onChange(e.target.checked)} />
        <span className="switch-track"><span className="switch-thumb" /></span>
      </label>
    );
  } else if (field.type === "slider" && field.min !== null && field.max !== null) {
    control = (
      <div className="slider-row">
        <input
          type="range" min={field.min} max={field.max} step={field.step ?? 1}
          value={current ?? field.min} onChange={(e) => onChange(Number(e.target.value))}
        />
        <input
          type="number" className="slider-number" min={field.min} max={field.max} step={field.step ?? 1}
          value={current ?? ""} onChange={(e) => onChange(Number(e.target.value))}
        />
      </div>
    );
  } else if (field.type === "number") {
    control = <input type="number" value={current ?? ""} onChange={(e) => onChange(Number(e.target.value))} />;
  } else {
    control = (
      <input
        type={field.sensitive ? "password" : "text"}
        autoComplete="off"
        value={current ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  return (
    <div className={dirty ? "sandbox-field dirty" : "sandbox-field"}>
      <div className="sandbox-field-label">
        <label>
          {onToggleFavorite && (
            <button
              className={field.favorite ? "favorite-star active" : "favorite-star"}
              onClick={() => onToggleFavorite(field.key, !field.favorite)}
              title={field.favorite ? "Remove from Priority Vars" : "Add to Priority Vars"}
            >
              <Star size={14} />
            </button>
          )}
          {field.label}
        </label>
        {categoryLabel && <span className="pill pill-muted">{categoryLabel}</span>}
        {!field.known && !field.description && <span className="pill">detected</span>}
        {missing && <span className="pill pill-muted">not in file</span>}
        {field.description && <small>{field.description}</small>}
      </div>
      <div className="sandbox-field-control">{control}</div>
    </div>
  );
}
