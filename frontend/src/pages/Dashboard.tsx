import { useRef, useState } from "react";
import { AlertTriangle, Activity, HardDrive, Server as ServerIcon, Users } from "lucide-react";
import { getPlayers, getServer } from "../api";
import { usePolling } from "../hooks/usePolling";
import { Metric } from "../components/Metric";
import { Health } from "../components/Health";
import type { PlayersResponse, ServerInfo } from "../types";

const fmtBytes = (n: number) => {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
};

export function Dashboard({ setToast }: { setToast: (msg: string) => void }) {
  const [server, setServer] = useState<ServerInfo | null>(null);
  const [players, setPlayers] = useState<PlayersResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const wasFailingRef = useRef(false);

  usePolling(async () => {
    try {
      setServer(await getServer());
      setStatusError(null);
      wasFailingRef.current = false;
    } catch (e: any) {
      const detail = e.message || "Unable to read server status.";
      setStatusError(detail);
      // Toast only on the transition into failure, not on every 5s poll while it
      // stays down - repeating the same toast every tick reads as spam and, worse,
      // buries the actual cause (e.g. "Control agent unavailable: ...", a bad
      // token, or a container name mismatch) behind a generic message.
      if (!wasFailingRef.current) setToast(detail);
      wasFailingRef.current = true;
    }
  }, 5000);

  usePolling(async () => {
    try {
      setPlayers(await getPlayers());
    } catch {
      // non-critical, dashboard still works without the player tile
    }
  }, 8000);

  const mem = server?.host.memory;
  const disk = server?.host.disk;

  return (
    <div>
      {statusError && (
        <div className="notice notice-warning">
          <AlertTriangle size={14} />
          Can't reach the WebUI API: {statusError}
        </div>
      )}

      <div className="cards">
        <Metric
          title="CPU"
          value={`${server?.host.cpu_percent?.toFixed(0) ?? "—"}%`}
          sub={server?.process.cpu_percent != null ? `Server: ${server.process.cpu_percent.toFixed(0)}%` : ""}
          icon={<Activity />}
        />
        <Metric
          title="MEMORY"
          value={mem ? fmtBytes(mem.used) : "—"}
          sub={
            mem
              ? `${mem.percent.toFixed(0)}% of ${fmtBytes(mem.total)}`
                + (server?.process.memory_bytes != null ? ` · Server: ${fmtBytes(server.process.memory_bytes)}` : "")
              : ""
          }
          icon={<ServerIcon />}
        />
        <Metric
          title="DATA SIZE"
          value={
            disk && disk.zomboid_data_bytes !== null
              ? fmtBytes(disk.zomboid_data_bytes + (disk.workshop_bytes ?? 0))
              : "—"
          }
          sub={
            disk && disk.zomboid_data_bytes === null
              ? "calculating…"
              : disk
              ? `Host disk: ${(disk.used / disk.total * 100).toFixed(0)}% used`
              : ""
          }
          icon={<HardDrive />}
        />
        <Metric title="PLAYERS" value={players ? String(players.online.length) : "—"} sub={players ? (players.source === "rcon" ? "RCON-verified" : "log-derived, best-effort") : ""} icon={<Users />} />
      </div>

      {players && players.online.length > 0 && (
        <section className="panel" style={{ marginBottom: 18 }}>
          <div className="panel-title"><span>Players Online</span></div>
          {players.online.map((p) => (
            <div className="health" key={p.name}>
              <span className="dot online" />
              <span>{p.name}</span>
              <span className="health-right">{Math.floor(p.duration_seconds / 60)}m</span>
            </div>
          ))}
        </section>
      )}

      <section className="panel">
        <div className="panel-title"><span>Server Health</span><span className="muted">Live</span></div>
        <Health label="Zomboid data mounted" ok={true} />
        <Health label="Workshop storage mounted" ok={true} />
        <Health label="WebUI API" ok={true} />
      </section>
    </div>
  );
}
