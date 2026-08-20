import { useEffect, useState } from "react";
import {
  AlertTriangle, CheckCircle2, Crosshair, Download, Map as MapIcon, Settings as SettingsIcon, X,
} from "lucide-react";
import { BaseMapView } from "../components/BaseMapView";
import {
  cancelBaseMapTile, cancelMapRender, clearCalibration, getBaseMapStatus, getCalibration,
  getMapRenderStatus, getMapSetupStatus, getServer, getSteamStatus, setCalibration, setupLiveMap,
  startBaseMapTile, startMapRender, startSteamInstall,
} from "../api";
import { usePolling } from "../hooks/usePolling";
import type {
  BaseMapStatus, Calibration, CalibrationPoint, MapRenderStatus, MapSetupStatus, SteamStatus,
} from "../types";

export function Settings({ setToast }: { setToast: (msg: string) => void }) {
  const [status, setStatus] = useState<MapSetupStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [renderStatus, setRenderStatus] = useState<MapRenderStatus | null>(null);
  const [baseMapStatus, setBaseMapStatus] = useState<BaseMapStatus | null>(null);
  const [calibration, setCalibrationState] = useState<Calibration | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const [confirmedPoints, setConfirmedPoints] = useState<CalibrationPoint[]>([]);
  const [awaitingPoint, setAwaitingPoint] = useState<{ pixel_x: number; pixel_y: number } | null>(null);
  const [worldXInput, setWorldXInput] = useState("");
  const [worldYInput, setWorldYInput] = useState("");
  const [calibrationBusy, setCalibrationBusy] = useState(false);
  const [steamStatus, setSteamStatus] = useState<SteamStatus | null>(null);
  // Deploy-time setting, not something that changes at runtime - one fetch
  // on mount is enough, same reasoning as Server.tsx's own copy of this.
  const [serverMode, setServerMode] = useState<"external" | "bundled">("external");

  async function load() {
    try {
      setStatus(await getMapSetupStatus());
    } catch (e: any) {
      setToast(e.message || "Could not load setup status.");
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    getServer().then((s) => setServerMode(s.server_mode)).catch(() => {});
  }, []);

  usePolling(async () => {
    try {
      setRenderStatus(await getMapRenderStatus());
    } catch {
      // non-critical
    }
  }, 3000);

  usePolling(async () => {
    try {
      setBaseMapStatus(await getBaseMapStatus());
    } catch {
      // non-critical
    }
  }, 3000);

  usePolling(async () => {
    try {
      setSteamStatus(await getSteamStatus());
    } catch {
      // non-critical
    }
  }, 3000);

  const baseMapReady = !!baseMapStatus?.tiles_available;

  useEffect(() => {
    if (baseMapReady) getCalibration().then(setCalibrationState).catch(() => {});
  }, [baseMapReady]);

  const modInstalled = !!status?.mod_installed;
  const enabled = !!status?.enabled;
  const allSet = modInstalled && enabled;

  async function install() {
    setBusy(true);
    try {
      const r = await setupLiveMap();
      setToast(r.ok ? "ZHDPositionTracker mod installed and Live Map enabled." : (r.detail || "Setup failed."));
      await load();
    } catch (e: any) {
      setToast(e.message || "Setup failed.");
    } finally {
      setBusy(false);
    }
  }

  async function enableOnly() {
    // Mod's already installed - this only needs to flip Live Map on. setup()
    // is idempotent about the mod copy either way, but the button/labeling
    // here deliberately doesn't say "install" since there's nothing to install.
    setBusy(true);
    try {
      const r = await setupLiveMap();
      setToast(r.ok ? "Live Map enabled." : (r.detail || "Could not enable Live Map."));
      await load();
    } catch (e: any) {
      setToast(e.message || "Could not enable Live Map.");
    } finally {
      setBusy(false);
    }
  }

  async function installSteamFiles() {
    try {
      const r = await startSteamInstall();
      if (r.ok) {
        setSteamStatus(r.status);
        setToast("Installing/updating server files via steamcmd…");
      } else {
        setToast(r.detail || "Could not start the install.");
      }
    } catch (e: any) {
      setToast(e.message || "Could not start the install.");
    }
  }

  async function tileBaseMap() {
    if (!window.confirm(
      "Tile the vanilla base map image? This slices a very large source image into "
      + "map tiles - can take a while depending on hardware. Continue?"
    )) return;
    try {
      const r = await startBaseMapTile();
      if (r.ok) {
        if (r.status) setBaseMapStatus(r.status);
        setToast("Base map tiling started.");
      } else {
        setToast(r.detail || "Could not start tiling.");
      }
    } catch (e: any) {
      setToast(e.message || "Could not start tiling.");
    }
  }

  async function cancelTileBaseMap() {
    if (!window.confirm("Cancel the running tiling job?")) return;
    try {
      const r = await cancelBaseMapTile();
      if (r.ok) {
        if (r.status) setBaseMapStatus(r.status);
        setToast("Tiling cancelled.");
      } else {
        setToast(r.detail || "Could not cancel tiling.");
      }
    } catch (e: any) {
      setToast(e.message || "Could not cancel tiling.");
    }
  }

  function startCalibration() {
    setCalibrating(true);
    setConfirmedPoints([]);
    setAwaitingPoint(null);
    setToast("Click a landmark on the map below, then enter the in-game X/Y a player standing there reports. Repeat 3 times.");
  }

  function cancelCalibration() {
    setCalibrating(false);
    setConfirmedPoints([]);
    setAwaitingPoint(null);
  }

  function handleMapClick(pixelX: number, pixelY: number) {
    if (awaitingPoint) return;
    setAwaitingPoint({ pixel_x: pixelX, pixel_y: pixelY });
    setWorldXInput("");
    setWorldYInput("");
  }

  async function confirmPoint() {
    if (!awaitingPoint) return;
    const worldX = parseFloat(worldXInput);
    const worldY = parseFloat(worldYInput);
    if (Number.isNaN(worldX) || Number.isNaN(worldY)) {
      setToast("Enter valid numbers for World X and World Y.");
      return;
    }
    const next = [...confirmedPoints, { ...awaitingPoint, world_x: worldX, world_y: worldY }];
    setAwaitingPoint(null);

    if (next.length < 3) {
      setConfirmedPoints(next);
      setToast(`Point ${next.length} of 3 recorded - click the next landmark.`);
      return;
    }

    setCalibrationBusy(true);
    try {
      const result = await setCalibration(next);
      setCalibrationState(result);
      setToast("Map calibrated - player positions should now appear on the Live Map tab.");
    } catch (e: any) {
      setToast(e.message || "Calibration failed - those 3 points may be too close to a straight line.");
    } finally {
      setCalibrationBusy(false);
      setCalibrating(false);
      setConfirmedPoints([]);
    }
  }

  async function handleClearCalibration() {
    if (!window.confirm("Clear the current map calibration? Player markers will disappear from the Live Map tab until you recalibrate.")) return;
    try {
      await clearCalibration();
      setCalibrationState({ points: [], transform: null });
      setToast("Calibration cleared.");
    } catch (e: any) {
      setToast(e.message || "Could not clear calibration.");
    }
  }

  async function render() {
    if (!window.confirm(
      "Render the map in top-down mode? This is a heavy job that can take a while "
      + "depending on world size and hardware. Continue?"
    )) return;
    try {
      const r = await startMapRender();
      if (r.ok) {
        setRenderStatus(r.status);
        setToast("Map render started.");
      } else {
        setToast(r.detail || "Could not start the render.");
      }
    } catch (e: any) {
      setToast(e.message || "Could not start the render.");
    }
  }

  async function cancelRender() {
    if (!window.confirm("Cancel the running render? You can restart it later - it should pick back up close to where it left off.")) return;
    try {
      const r = await cancelMapRender();
      if (r.ok) {
        if (r.status) setRenderStatus(r.status);
        setToast("Render cancelled.");
      } else {
        setToast(r.detail || "Could not cancel the render.");
      }
    } catch (e: any) {
      setToast(e.message || "Could not cancel the render.");
    }
  }

  return (
    <>
      <section className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title"><span>Live Map Setup</span><SettingsIcon size={16} /></div>

        <p className="muted" style={{ marginTop: 0 }}>
          One-click setup for the Live Map tab: copies the ZHDPositionTracker
          companion mod onto your server, enables it, and turns Live Map on.
          You'll still need to restart the server for the mod to actually load,
          and set up a map below before there's anything to see on the Live
          Map tab.
        </p>

        <div className="mod-row" style={{ marginBottom: 10 }}>
          <div className="mod-row-info">
            <div>ZHDPositionTracker mod</div>
            <small className="muted">{modInstalled ? "Installed" : "Not installed"}</small>
          </div>
        </div>
        <div className="mod-row" style={{ marginBottom: 14 }}>
          <div className="mod-row-info">
            <div>Live Map</div>
            <small className="muted">{enabled ? "Enabled" : "Disabled"}</small>
          </div>
        </div>

        {allSet && (
          <div className="notice">
            <CheckCircle2 size={14} />
            Live Map is set up. Restart the server if you haven't since installing
            the mod, then set up a map below.
          </div>
        )}
        {!allSet && modInstalled && !enabled && (
          <div className="notice">
            <CheckCircle2 size={14} />
            Mod already installed - just needs enabling.
          </div>
        )}

        {!modInstalled && (
          <button className="primary" onClick={install} disabled={busy}>
            {busy ? "Setting up…" : "Install Mod & Enable Live Map"}
          </button>
        )}
        {modInstalled && !enabled && (
          <button className="primary" onClick={enableOnly} disabled={busy}>
            {busy ? "Enabling…" : "Enable Live Map"}
          </button>
        )}
        {allSet && (
          <button onClick={install} disabled={busy}>
            {busy ? "Re-running…" : "Re-run Setup"}
          </button>
        )}
      </section>

      <section className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title"><span>Base Map (Vanilla, Isometric)</span><MapIcon size={16} /></div>

        <p className="muted" style={{ marginTop: 0 }}>
          Slices the maintainer-supplied vanilla B42 map image into tiles for the
          Live Map tab - no game files, steamcmd, or multi-hour render needed.
        </p>

        {baseMapStatus?.error && (
          <div className="notice notice-warning">
            <AlertTriangle size={14} />
            {baseMapStatus.error}
          </div>
        )}

        {!baseMapStatus?.running && baseMapStatus?.cancelled && (
          <div className="notice notice-warning">
            <AlertTriangle size={14} />
            Tiling was cancelled.
          </div>
        )}

        {baseMapStatus?.running && (
          <div className="mod-row" style={{ marginBottom: 12 }}>
            <div className="mod-row-info">
              <div>Tiling…</div>
              {baseMapStatus.last_line && <small className="muted">{baseMapStatus.last_line}</small>}
            </div>
          </div>
        )}

        {!baseMapStatus?.running && baseMapStatus?.done_at && !baseMapStatus?.error && !baseMapStatus?.cancelled && (
          <small className="muted" style={{ display: "block", marginBottom: 12 }}>
            Last tiled {new Date(baseMapStatus.done_at).toLocaleString()}
            {baseMapStatus.width && baseMapStatus.height
              ? ` (${baseMapStatus.width}×${baseMapStatus.height}px, zoom 0-${baseMapStatus.max_zoom})`
              : ""}.
          </small>
        )}

        <div style={{ display: "flex", gap: 10 }}>
          <button className="danger" onClick={tileBaseMap} disabled={!!baseMapStatus?.running}>
            {baseMapStatus?.running ? "Tiling…" : "Tile Base Map"}
          </button>
          {baseMapStatus?.running && (
            <button onClick={cancelTileBaseMap}>Cancel</button>
          )}
        </div>
      </section>

      {baseMapReady && (
        <section className="panel" style={{ marginBottom: 18 }}>
          <div className="panel-title"><span>Map Calibration</span><Crosshair size={16} /></div>

          <p className="muted" style={{ marginTop: 0 }}>
            Player markers on the Live Map tab need to know how in-game
            coordinates map onto this image's pixels. Pick 3 landmarks: click
            each one on the map below, then enter the X/Y a player standing
            there sees in their live position (Live Map tab's Player
            Positions panel, or in-game debug coordinates).
          </p>

          {calibration?.transform && !calibrating && (
            <div className="notice" style={{ marginBottom: 12 }}>
              <CheckCircle2 size={14} />
              Map is calibrated - player markers are active on the Live Map tab.
            </div>
          )}

          {calibrating && (
            <div className="notice notice-warning" style={{ marginBottom: 12 }}>
              <AlertTriangle size={14} />
              Calibrating: point {confirmedPoints.length + (awaitingPoint ? 1 : 0)} of 3.
              {awaitingPoint ? " Enter its in-game coordinates below." : " Click a landmark on the map."}
            </div>
          )}

          {awaitingPoint && (
            <div className="settings-grid" style={{ marginBottom: 12 }}>
              <div className="setting">
                <label>World X</label>
                <input
                  type="number" value={worldXInput}
                  onChange={(e) => setWorldXInput(e.target.value)}
                  placeholder="e.g. 10534"
                />
              </div>
              <div className="setting">
                <label>World Y</label>
                <input
                  type="number" value={worldYInput}
                  onChange={(e) => setWorldYInput(e.target.value)}
                  placeholder="e.g. 9876"
                />
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
                <button className="primary" onClick={confirmPoint} disabled={calibrationBusy}>
                  {calibrationBusy ? "Saving…" : "Confirm Point"}
                </button>
                <button onClick={() => setAwaitingPoint(null)}><X size={14} /> Cancel Point</button>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
            {!calibrating && (
              <button className="primary" onClick={startCalibration}>
                {calibration?.transform ? "Recalibrate" : "Calibrate Map"}
              </button>
            )}
            {calibrating && <button onClick={cancelCalibration}>Cancel Calibration</button>}
            {calibration?.transform && !calibrating && (
              <button onClick={handleClearCalibration}>Clear Calibration</button>
            )}
          </div>

          <BaseMapView
            status={baseMapStatus!}
            players={[]}
            transform={calibration?.transform ?? null}
            calibrating={calibrating}
            onMapClick={handleMapClick}
          />
        </section>
      )}

      <section className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title"><span>Install Server Files</span><Download size={16} /></div>

        <p className="muted" style={{ marginTop: 0 }}>
          Downloads/updates the PZ dedicated server files via steamcmd into
          GAME_FILES_DATA. Used to actually host a server in
          <code> SERVER_MODE=bundled</code>, and separately needed to populate
          map/texture data for the Map Rendering panel below.
        </p>

        {serverMode === "external" && (
          <div className="notice notice-warning">
            <AlertTriangle size={14} />
            You have an external server configured (<code>SERVER_MODE=external</code>) -
            this won't touch it. It downloads a separate, standalone copy of the game
            files into <code>GAME_FILES_DATA</code>, used here purely for map
            rendering's texture data. You could also use this same install to stand up
            an entirely separate bundled server instance later, by switching
            <code> SERVER_MODE</code> to <code>bundled</code> - the two aren't linked.
          </div>
        )}

        {steamStatus?.error && (
          <div className="notice notice-warning">
            <AlertTriangle size={14} />
            {steamStatus.error}
          </div>
        )}

        {steamStatus?.running && (
          <div className="mod-row" style={{ marginBottom: 12 }}>
            <div className="mod-row-info">
              <div>
                Installing… {steamStatus.progress_pct != null ? `${steamStatus.progress_pct.toFixed(0)}%` : ""}
              </div>
              {steamStatus.last_line && <small className="muted">{steamStatus.last_line}</small>}
            </div>
          </div>
        )}

        {!steamStatus?.running && steamStatus?.done_at && !steamStatus?.error && (
          <small className="muted" style={{ display: "block", marginBottom: 12 }}>
            Last installed/updated {new Date(steamStatus.done_at).toLocaleString()}.
          </small>
        )}

        <button className="primary" onClick={installSteamFiles} disabled={!!steamStatus?.running}>
          {steamStatus?.running ? "Installing…" : "Install / Update Server Files"}
        </button>
      </section>

      <section className="panel">
        <div className="panel-title"><span>Map Rendering</span><MapIcon size={16} /></div>

        <p className="muted" style={{ marginTop: 0 }}>
          Renders a top-down map for the Live Map tab, using the game's own map/
          texture data (installed via the Server tab's dedicated server panel).
        </p>

        {renderStatus?.error && (
          <div className="notice notice-warning">
            <AlertTriangle size={14} />
            {renderStatus.error}
          </div>
        )}

        {!renderStatus?.running && renderStatus?.cancelled && (
          <div className="notice notice-warning">
            <AlertTriangle size={14} />
            Render was cancelled. Restarting it should pick back up close to where it left off.
          </div>
        )}

        {renderStatus?.running && (
          <div className="mod-row" style={{ marginBottom: 12, flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <div className="mod-row-info">
              <div>
                {renderStatus.step ? `Rendering (${renderStatus.step})…` : "Rendering…"}
                {renderStatus.progress_pct != null ? ` ${renderStatus.progress_pct.toFixed(0)}%` : ""}
              </div>
              {renderStatus.last_line && <small className="muted">{renderStatus.last_line}</small>}
            </div>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${renderStatus.progress_pct ?? 0}%` }} />
            </div>
          </div>
        )}

        {!renderStatus?.running && renderStatus?.done_at && !renderStatus?.error && !renderStatus?.cancelled && (
          <small className="muted" style={{ display: "block", marginBottom: 12 }}>
            Last render finished {new Date(renderStatus.done_at).toLocaleString()}.
          </small>
        )}

        <div style={{ display: "flex", gap: 10 }}>
          <button className="danger" onClick={render} disabled={!!renderStatus?.running}>
            {renderStatus?.running ? "Rendering…" : "Render Map (Top-Down)"}
          </button>
          {renderStatus?.running && (
            <button onClick={cancelRender}>Cancel</button>
          )}
        </div>
      </section>
    </>
  );
}
