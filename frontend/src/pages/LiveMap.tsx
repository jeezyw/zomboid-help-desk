import { useEffect, useState } from "react";
import { AlertTriangle, MapPin, Users } from "lucide-react";
import { BaseMapView } from "../components/BaseMapView";
import { getBaseMapStatus, getCalibration, getMapConfig, getMapPlayers, getMapRenderStatus } from "../api";
import { usePolling } from "../hooks/usePolling";
import type { BaseMapStatus, Calibration, MapConfig, MapPlayer, MapRenderStatus } from "../types";

export function LiveMap({ setToast }: { setToast: (msg: string) => void }) {
  const [config, setConfig] = useState<MapConfig | null>(null);
  const [players, setPlayers] = useState<MapPlayer[]>([]);
  const [stale, setStale] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<MapRenderStatus | null>(null);
  const [baseMapStatus, setBaseMapStatus] = useState<BaseMapStatus | null>(null);
  const [calibration, setCalibrationState] = useState<Calibration | null>(null);

  useEffect(() => {
    getMapConfig().then(setConfig).catch(() => setConfig({ enabled: false, tiles_available: false }));
  }, []);

  const baseMapReady = !!baseMapStatus?.tiles_available;
  const ready = !!config?.enabled && (!!config?.tiles_available || baseMapReady);

  useEffect(() => {
    if (config?.enabled) getMapRenderStatus().then(setRenderStatus).catch(() => {});
  }, [config?.enabled]);

  usePolling(async () => {
    if (!config?.enabled) return;
    try {
      setRenderStatus(await getMapRenderStatus());
    } catch {
      // non-critical
    }
  }, 3000, !!config?.enabled);

  useEffect(() => {
    if (config?.enabled) getBaseMapStatus().then(setBaseMapStatus).catch(() => {});
  }, [config?.enabled]);

  usePolling(async () => {
    if (!config?.enabled) return;
    try {
      setBaseMapStatus(await getBaseMapStatus());
    } catch {
      // non-critical
    }
  }, 3000, !!config?.enabled);

  useEffect(() => {
    if (baseMapReady) getCalibration().then(setCalibrationState).catch(() => {});
  }, [baseMapReady]);

  usePolling(async () => {
    if (!ready) return;
    try {
      const r = await getMapPlayers();
      setPlayers(r.players);
      setStale(r.stale);
      setUpdatedAt(r.updated_at);
    } catch (e: any) {
      setToast(e.message || "Could not load player positions.");
    }
  }, 5000, ready);

  if (!config) return null;

  return (
    <>
      {!config.enabled && (
        <section className="panel" style={{ marginBottom: 18 }}>
          <div className="panel-title"><span>Live Map</span><MapPin size={16} /></div>
          <div className="notice notice-warning">
            <AlertTriangle size={14} />
            Live Map is disabled. Head to the Settings tab and click "Install Mod
            &amp; Enable Live Map" - it installs the ZHDPositionTracker companion
            mod on your server and turns this on in one step.
          </div>
        </section>
      )}

      {config.enabled && (
        <section className="panel" style={{ marginBottom: 18 }}>
          <div className="panel-title"><span>Live Map</span><MapPin size={16} /></div>

          {!baseMapReady && !config.tiles_available ? (
            <div className="empty">No map tiles yet - set one up from the Settings tab.</div>
          ) : baseMapReady ? (
            <>
              {!calibration?.transform && (
                <p className="muted" style={{ marginTop: 0 }}>
                  Player positions aren't plotted on the map yet - use the
                  Map Calibration panel on the Settings tab to set that up
                  (see the player list below in the meantime).
                </p>
              )}
              <BaseMapView
                status={baseMapStatus!}
                players={players}
                transform={calibration?.transform ?? null}
                calibrating={false}
              />
            </>
          ) : (
            <>
              <p className="muted" style={{ marginTop: 0 }}>
                Player positions aren't plotted directly on the map yet (see the
                player list below instead) - the rendered map's own viewer has an
                internal marker system this app doesn't integrate with, to avoid
                guessing at an undocumented API and getting positions subtly
                wrong.
              </p>
              <iframe
                src="/map-tiles/html/pzmap.html"
                title="Project Zomboid Map"
                className="live-map"
                style={{ border: 0 }}
              />
            </>
          )}
        </section>
      )}

      {ready && (
        <section className="panel">
          <div className="panel-title"><span>Player Positions ({players.length})</span><Users size={16} /></div>

          {stale && (
            <div className="notice notice-warning" style={{ marginBottom: 10 }}>
              <AlertTriangle size={14} />
              Position data looks stale{updatedAt ? ` (last updated ${new Date(updatedAt).toLocaleTimeString()})` : ""} -
              check that the ZHDPositionTracker mod is installed, enabled, and the server is running.
              Not showing any players until fresh data comes in.
            </div>
          )}

          {!players.length && <div className="empty">No player position data yet.</div>}
          {players.map((p) => (
            <div className="health" key={p.username}>
              <span className="dot online" />
              <span>{p.username}</span>
              <span className="health-right">x={p.x.toFixed(0)}, y={p.y.toFixed(0)}, z={p.z.toFixed(0)}</span>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
