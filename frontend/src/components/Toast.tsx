import { X } from "lucide-react";

export function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  if (!message) return null;
  return (
    <div className="toast">
      {message}
      <button onClick={onClose}><X size={14} /></button>
    </div>
  );
}
