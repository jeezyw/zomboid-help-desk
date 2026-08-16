import { AlertTriangle, Check } from "lucide-react";

export function PendingBar({
  count, saving, onDiscard, onApply,
}: {
  count: number;
  saving: boolean;
  onDiscard: () => void;
  onApply: () => void;
}) {
  if (count === 0) return null;
  return (
    <div className="pending-bar">
      <div className="pending-info">
        <AlertTriangle size={16} />
        {count} pending change{count === 1 ? "" : "s"}
      </div>
      <div className="pending-actions">
        <button onClick={onDiscard} disabled={saving}>Discard</button>
        <button className="primary" onClick={onApply} disabled={saving}>
          <Check size={16} /> {saving ? "Applying…" : "Apply Changes"}
        </button>
      </div>
    </div>
  );
}
