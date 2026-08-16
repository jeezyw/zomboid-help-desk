import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, ListChecks, Trash2 } from "lucide-react";
import {
  addTodo, deleteTodo, getTodos, reorderTodos, setTodoBlocker, setTodoPriority, setTodoStatus,
} from "../api";
import type { TodoItem, TodoPriority, TodoStatus } from "../types";

// Wish is deliberately excluded - it has no background tint, just dimmed text
// (handled inline below), per the "less visible" spec rather than a color.
const TINT_CLASS: Record<string, string> = {
  urgent: "objective-urgent",
  moderate: "objective-moderate",
  low: "objective-low",
};

// Complete is deliberately excluded - those objectives move to the Completed
// panel below and don't get a status border at all.
const STATUS_CLASS: Record<string, string> = {
  planned: "objective-status-planned",
  in_progress: "objective-status-in_progress",
  blocked: "objective-status-blocked",
};

// Auto-sort rank for the active list - lower sorts first (Urgent at the top).
// Anything unrecognized falls in with Wish rather than vanishing from the list.
const PRIORITY_RANK: Record<string, number> = { urgent: 0, moderate: 1, low: 2, wish: 3 };
const priorityRank = (p: string) => PRIORITY_RANK[p] ?? PRIORITY_RANK.wish;

export function Objectives({ setToast }: { setToast: (msg: string) => void }) {
  const [items, setItems] = useState<TodoItem[]>([]);
  const [statuses, setStatuses] = useState<TodoStatus[]>([]);
  const [priorities, setPriorities] = useState<TodoPriority[]>([]);
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState("");
  const [priority, setPriority] = useState("moderate");
  const [adding, setAdding] = useState(false);
  // Local drafts for the Blocker note input - keyed by objective id, so typing in
  // one row doesn't get clobbered by a `load()` triggered from another row's edit,
  // and the field doesn't fight the user's cursor while they're still typing.
  const [blockerDrafts, setBlockerDrafts] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    try {
      const data = await getTodos();
      setItems(data.items);
      setStatuses(data.statuses);
      setPriorities(data.priorities);
    } catch (e: any) {
      setToast(e.message || "Could not load objectives.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function add() {
    if (!text.trim()) return;
    setAdding(true);
    try {
      await addTodo(text.trim(), priority);
      setText("");
      setToast("Objective added.");
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not add objective.");
    } finally {
      setAdding(false);
    }
  }

  async function changeStatus(item: TodoItem, status: string) {
    try {
      await setTodoStatus(item.id, status);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not update objective.");
    }
  }

  async function changePriority(item: TodoItem, newPriority: string) {
    try {
      await setTodoPriority(item.id, newPriority);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not update priority.");
    }
  }

  function blockerValue(item: TodoItem): string {
    return item.id in blockerDrafts ? blockerDrafts[item.id] : item.blocker;
  }

  async function saveBlocker(item: TodoItem) {
    const value = blockerValue(item);
    if (value === item.blocker) return;
    try {
      await setTodoBlocker(item.id, value);
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not save the blocker note.");
    }
  }

  const activeItems = items.filter((i) => i.status !== "complete");
  // Stable sort - JS Array.prototype.sort is guaranteed stable, so items sharing a
  // priority keep their existing relative (manually-reordered) order.
  const sortedActiveItems = [...activeItems].sort(
    (a, b) => priorityRank(a.priority) - priorityRank(b.priority)
  );

  async function move(id: string, dir: -1 | 1) {
    // The list auto-sorts by priority (Urgent to Wish) - manual reordering only
    // makes sense WITHIN a priority tier now (swapping across tiers would just get
    // silently undone by the sort on the next render), so a move is rejected if
    // the neighbor in the sorted view isn't the same priority. The backend still
    // just stores a flat order with no concept of priority - the sorted view is
    // saved back as the new order, completed ids appended after it unchanged
    // (reorder requires the FULL id list - it validates an exact reshuffle).
    const sorted = sortedActiveItems;
    const i = sorted.findIndex((x) => x.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= sorted.length) return;
    if (sorted[j].priority !== sorted[i].priority) return;

    const newSorted = [...sorted];
    [newSorted[i], newSorted[j]] = [newSorted[j], newSorted[i]];
    const completedIds = items.filter((x) => x.status === "complete").map((x) => x.id);
    try {
      const result = await reorderTodos([...newSorted.map((x) => x.id), ...completedIds]);
      setItems(result.items);
    } catch (e: any) {
      setToast(e.message || "Could not reorder objectives.");
    }
  }

  async function remove(item: TodoItem) {
    if (!window.confirm(`Remove "${item.text}"?`)) return;
    try {
      await deleteTodo(item.id);
      setToast("Objective removed.");
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not remove objective.");
    }
  }

  const completedItems = [...items.filter((i) => i.status === "complete")]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

  return (
    <>
      <section className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title"><span>Add Objective</span><ListChecks size={16} /></div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            placeholder="What's the objective? e.g. Clear the Rosewood fire station of zombies"
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ flex: 1 }}
            onKeyDown={(e) => { if (e.key === "Enter") add(); }}
          />
          <select value={priority} onChange={(e) => setPriority(e.target.value)} style={{ width: 130 }}>
            {priorities.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
          <button className="primary" onClick={add} disabled={adding || !text.trim()}>
            {adding ? "Adding…" : "Add Objective"}
          </button>
        </div>
      </section>

      <section className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title">
          <span>Objectives ({sortedActiveItems.length})</span>
          <span className="muted">Auto-sorted by priority - ↑↓ reorder within a priority</span>
        </div>
        {loading && !items.length && <div className="empty">Loading…</div>}
        {!loading && !sortedActiveItems.length && <div className="empty">No active objectives - add one above.</div>}
        {sortedActiveItems.map((item, idx) => (
          <div className={`mod-row ${TINT_CLASS[item.priority] ?? ""} ${STATUS_CLASS[item.status] ?? ""}`} key={item.id}>
            <div className="mod-row-info">
              <div style={item.priority === "wish" ? { opacity: 0.55 } : undefined}>{item.text}</div>
              <small>Updated {new Date(item.updated_at).toLocaleString()}</small>
              {item.status === "blocked" && (
                <input
                  type="text"
                  className="objective-blocker-note"
                  placeholder="What's blocking this?"
                  value={blockerValue(item)}
                  onChange={(e) => setBlockerDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))}
                  onBlur={() => saveBlocker(item)}
                />
              )}
            </div>
            <select value={item.priority} onChange={(e) => changePriority(item, e.target.value)} style={{ width: 110 }}>
              {priorities.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
            <select value={item.status} onChange={(e) => changeStatus(item, e.target.value)} style={{ width: 130 }}>
              {statuses.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>
            <div className="mod-row-actions">
              <button
                className="icon-btn"
                disabled={idx === 0 || sortedActiveItems[idx - 1].priority !== item.priority}
                onClick={() => move(item.id, -1)} title="Move up (within this priority)"
              ><ArrowUp size={15} /></button>
              <button
                className="icon-btn"
                disabled={idx === sortedActiveItems.length - 1 || sortedActiveItems[idx + 1].priority !== item.priority}
                onClick={() => move(item.id, 1)} title="Move down (within this priority)"
              ><ArrowDown size={15} /></button>
              <button className="icon-btn" onClick={() => remove(item)} title="Remove"><Trash2 size={15} /></button>
            </div>
          </div>
        ))}
      </section>

      {completedItems.length > 0 && (
        <section className="panel">
          <div className="panel-title"><span>Completed ({completedItems.length})</span></div>
          {completedItems.map((item) => (
            <div className={`mod-row ${TINT_CLASS[item.priority] ?? ""}`} key={item.id}>
              <div className="mod-row-info">
                <div style={{ textDecoration: "line-through", opacity: item.priority === "wish" ? 0.45 : 0.6 }}>{item.text}</div>
                <small>Completed {new Date(item.updated_at).toLocaleString()}</small>
              </div>
              <select value={item.priority} onChange={(e) => changePriority(item, e.target.value)} style={{ width: 110 }}>
                {priorities.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
              <select value={item.status} onChange={(e) => changeStatus(item, e.target.value)} style={{ width: 130 }}>
                {statuses.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
              </select>
              <div className="mod-row-actions">
                <button className="icon-btn" onClick={() => remove(item)} title="Remove"><Trash2 size={15} /></button>
              </div>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
