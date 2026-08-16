import { useMemo, useState } from "react";
import {
  Apple, Backpack, Bomb, Book, Box, Boxes, Crosshair, Fish, Flag, Flame, GraduationCap,
  HeartPulse, Package, Shield, Shirt, Swords, Target, Wrench,
} from "lucide-react";
import { ITEM_CATALOG, ITEM_CATEGORIES } from "../itemCatalog";

const CATEGORY_ICONS: Record<string, any> = {
  "Weapons": Swords,
  "Firearms": Crosshair,
  "Ammo": Package,
  "Weapon Parts": Target,
  "Military": Flag,
  "Armor": Shield,
  "Explosives": Bomb,
  "Tools": Wrench,
  "Medical": HeartPulse,
  "Food & Drink": Apple,
  "Fishing": Fish,
  "Camping": Flame,
  "Materials": Boxes,
  "Skill Books": GraduationCap,
  "Literature": Book,
  "Clothing": Shirt,
  "Backpacks": Backpack,
  "Miscellaneous": Box,
};

/** Graphical item browser for the Give Item tool - a curated catalog (see
 * itemCatalog.ts), not real game icons (see that file's header for why), sorted
 * and filterable by category, with the raw item ID shown on hover and a "Custom
 * ID" fallback for anything not in the curated list. */
export function ItemPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const [mode, setMode] = useState<"browse" | "custom">("browse");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("All");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return ITEM_CATALOG.filter((it) =>
      (category === "All" || it.category === category)
      && (!q || it.name.toLowerCase().includes(q) || it.id.toLowerCase().includes(q))
    );
  }, [search, category]);

  const selectedCatalogItem = ITEM_CATALOG.find((it) => it.id === value);

  return (
    <div className="item-picker">
      <div className="item-picker-tabs">
        <button className={mode === "browse" ? "sandbox-tab active" : "sandbox-tab"} onClick={() => setMode("browse")}>Browse</button>
        <button className={mode === "custom" ? "sandbox-tab active" : "sandbox-tab"} onClick={() => setMode("custom")}>Custom ID</button>
      </div>

      {mode === "custom" ? (
        <input
          type="text" placeholder="item id (e.g. Base.Axe)" value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <>
          <div className="item-picker-controls">
            <input type="text" placeholder="Search items…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="All">All Categories</option>
              {ITEM_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="item-grid">
            {filtered.map((it) => {
              const Icon = CATEGORY_ICONS[it.category] || Box;
              const selected = it.id === value;
              return (
                <button
                  key={it.id}
                  className={selected ? "item-chip selected" : "item-chip"}
                  onClick={() => onChange(it.id)}
                  title={it.id}
                >
                  <Icon size={14} />
                  <span>{it.name}</span>
                </button>
              );
            })}
            {!filtered.length && <div className="empty">No items match.</div>}
          </div>
        </>
      )}

      <small className="muted item-picker-selected">
        {value ? `Selected: ${value}${selectedCatalogItem ? ` (${selectedCatalogItem.name})` : ""}` : "No item selected."}
      </small>
    </div>
  );
}
