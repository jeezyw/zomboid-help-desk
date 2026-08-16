import { useState, type FormEvent } from "react";
import { Lock } from "lucide-react";
import { login } from "../api";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true);
    setError("");
    try {
      await login(username.trim(), password);
      onSuccess();
    } catch (e: any) {
      setError(e.message || "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
    }}>
      <form className="panel" onSubmit={submit} style={{ width: 340 }}>
        <div className="panel-title"><span>Zomboid Help Desk</span><Lock size={16} /></div>

        <div className="setting" style={{ marginBottom: 10 }}>
          <label>Username</label>
          <input
            type="text"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="setting" style={{ marginBottom: 14 }}>
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && <div className="notice notice-warning" style={{ marginBottom: 14 }}>{error}</div>}

        <button
          type="submit"
          className="primary"
          style={{ width: "100%", justifyContent: "center" }}
          disabled={busy || !username.trim() || !password}
        >
          {busy ? "Signing in…" : "Sign In"}
        </button>
      </form>
    </div>
  );
}
