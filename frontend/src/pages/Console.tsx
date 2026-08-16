import { useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { getLogs } from "../api";
import { usePolling } from "../hooks/usePolling";
import { TabBar } from "../components/TabBar";
import type { LogCategory, LogLine } from "../types";

const CATEGORIES: (LogCategory | "ALL")[] = ["ALL", "INFO", "WARN", "ERROR", "PLAYER", "MOD", "SYSTEM"];
const MAX_BUFFERED_LINES = 2000;

export function Console() {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [filter, setFilter] = useState<LogCategory | "ALL">("ALL");
  const [paused, setPaused] = useState(false);
  const [path, setPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cursorRef = useRef<string | null>(null);

  usePolling(async () => {
    const { lines: batch, cursor, path: logPath, error: logError } = await getLogs(cursorRef.current, 300);
    setPath(logPath);
    setError(logError);
    if (!batch.length) return;

    // Reads are exact byte-offset ranges from the source file - no overlap between
    // polls, so unlike the old docker-logs-based cursor there's no boundary line to
    // de-duplicate here.
    cursorRef.current = cursor;
    setLines((prev) => [...prev, ...batch].slice(-MAX_BUFFERED_LINES));
  }, 4500, !paused);

  function clear() {
    setLines([]);
  }

  function download() {
    const blob = new Blob([lines.map((l) => l.text).join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "zomboid-console.log";
    a.click();
    URL.revokeObjectURL(url);
  }

  const shown = filter === "ALL" ? lines : lines.filter((l) => l.category === filter);

  return (
    <section className="panel console">
      <div className="panel-title">
        <span>Console {path && <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>· {path}</span>}</span>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={clear}>Clear</button>
          <button onClick={download}>Download Log</button>
          <button onClick={() => setPaused((p) => !p)}>{paused ? "Resume" : "Pause"}</button>
        </div>
      </div>
      {error && (
        <div className="notice notice-warning">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}
      <TabBar items={CATEGORIES.map((c) => ({ id: c, title: c }))} activeId={filter} onSelect={(id) => setFilter(id as any)} />
      <pre>
        {shown.length
          ? shown.map((l, i) => (
              <div key={i} className={`log-line log-line-${l.category}`}>{l.text}</div>
            ))
          : "No logs available."}
      </pre>
    </section>
  );
}
