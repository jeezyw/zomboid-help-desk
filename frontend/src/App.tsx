import { useEffect, useState } from "react";
import {
  Activity, Database, ListChecks, LogOut, Package, Server as ServerIcon, Settings, Terminal, Users,
  Wrench,
} from "lucide-react";
import { Toast } from "./components/Toast";
import { Dashboard } from "./pages/Dashboard";
import { Sandbox } from "./pages/Sandbox";
import { Server } from "./pages/Server";
import { Mods } from "./pages/Mods";
import { Backups } from "./pages/Backups";
import { Console } from "./pages/Console";
import { Players } from "./pages/Players";
import { RconTools } from "./pages/RconTools";
import { Objectives } from "./pages/Objectives";
import { Login } from "./pages/Login";
import { getAuthStatus, logout, setUnauthorizedHandler } from "./api";
import type { Page } from "./types";

const NAV: [Page, any][] = [
  ["Dashboard", Activity], ["Sandbox", Settings], ["Server", ServerIcon],
  ["Mods", Package], ["Players", Users], ["RCON Tools", Wrench], ["To-Do", ListChecks],
  ["Console", Terminal], ["Backups", Database],
];

export function App() {
  const [page, setPage] = useState<Page>("Dashboard");
  const [toast, setToast] = useState("");
  // null while the initial /api/auth/status check is in flight - avoids a flash
  // of the login screen (or the main app) before we actually know which applies.
  const [secureMode, setSecureMode] = useState(false);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    getAuthStatus()
      .then((s) => { setSecureMode(s.secure_mode); setAuthenticated(s.authenticated); })
      .catch(() => setAuthenticated(true)); // fail open locally - matches secure_mode defaulting off
    setUnauthorizedHandler(() => setAuthenticated(false));
    return () => setUnauthorizedHandler(null);
  }, []);

  async function doLogout() {
    try { await logout(); } catch { /* clearing local state either way */ }
    setAuthenticated(false);
  }

  if (authenticated === null) return null;
  if (secureMode && !authenticated) return <Login onSuccess={() => setAuthenticated(true)} />;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <img src="/logo.png" alt="Zomboid Help Desk" className="brand-icon" />
        </div>
        {NAV.map(([name, Icon]) => (
          <button className={page === name ? "nav active" : "nav"} onClick={() => setPage(name)} key={name}>
            <Icon size={18} />{name}
          </button>
        ))}
      </aside>

      <main>
        <header>
          <div>
            <div className="eyebrow">PROJECT ZOMBOID · B42</div>
            <h1>{page}</h1>
          </div>
          {secureMode && (
            <div className="header-actions">
              <button onClick={doLogout}><LogOut size={16} /> Log Out</button>
            </div>
          )}
        </header>

        <Toast message={toast} onClose={() => setToast("")} />

        {page === "Dashboard" && <Dashboard setToast={setToast} />}
        {page === "Sandbox" && <Sandbox setToast={setToast} />}
        {page === "Server" && <Server setToast={setToast} />}
        {page === "Mods" && <Mods setToast={setToast} />}
        {page === "Players" && <Players setToast={setToast} />}
        {page === "RCON Tools" && <RconTools setToast={setToast} />}
        {page === "To-Do" && <Objectives setToast={setToast} />}
        {page === "Console" && <Console />}
        {page === "Backups" && <Backups setToast={setToast} />}
      </main>
    </div>
  );
}
