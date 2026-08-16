export type TabItem = { id: string; title: string; count?: number };

export function TabBar({
  items, activeId, onSelect,
}: {
  items: TabItem[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="sandbox-tabs">
      {items.map((item) => (
        <button
          key={item.id}
          className={item.id === activeId ? "sandbox-tab active" : "sandbox-tab"}
          onClick={() => onSelect(item.id)}
        >
          {item.title}
          {item.count !== undefined && <span className="sandbox-tab-count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}
