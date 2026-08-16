import { useEffect, useState } from "react";
import { AlertTriangle, ExternalLink, GraduationCap, Wrench } from "lucide-react";
import { getPerks, getPlayers, sendRconCommand, setPlayerSkill } from "../api";
import { ItemPicker } from "../components/ItemPicker";
import { COMMAND_GROUPS, SERVER_COMMANDS } from "../serverCommands";
import type { Perk } from "../types";

export function RconTools({ setToast }: { setToast: (msg: string) => void }) {
  return (
    <>
      <WorldToolsPanel setToast={setToast} />
      <AdjustSkillsPanel setToast={setToast} />
    </>
  );
}

const COMMON_COMMANDS: { label: string; command: string; danger?: boolean; confirm?: string }[] = [
  { label: "Save World", command: "save" },
  { label: "List Players", command: "players" },
  { label: "Show Options", command: "showoptions" },
  { label: "Help", command: "help" },
  { label: "Trigger Gunshot", command: "gunshot" },
];

function WorldToolsPanel({ setToast }: { setToast: (msg: string) => void }) {
  const [customCommand, setCustomCommand] = useState("");
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState<string | null>(null);

  async function send(command: string, confirmMessage?: string) {
    if (!command.trim()) return;
    if (confirmMessage && !window.confirm(confirmMessage)) return;
    setSending(true);
    try {
      const r = await sendRconCommand(command);
      setResponse(r.response);
      setToast(`Sent: ${command}`);
    } catch (e: any) {
      setToast(e.message || "Command failed.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>World Tools</span><Wrench size={16} /></div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        {COMMON_COMMANDS.map((c) => (
          <button
            key={c.command}
            className={c.danger ? "danger" : undefined}
            disabled={sending}
            onClick={() => send(c.command, c.confirm)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <CommandBuilder onSend={send} sending={sending} />

      <div className="panel-title" style={{ marginTop: 20 }}><span>Custom Command</span></div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          type="text" placeholder="Custom RCON command…" value={customCommand}
          onChange={(e) => setCustomCommand(e.target.value)}
          style={{ flex: 1 }}
          onKeyDown={(e) => { if (e.key === "Enter") send(customCommand); }}
        />
        <button onClick={() => send(customCommand)} disabled={sending || !customCommand.trim()}>Send</button>
      </div>

      {response !== null && (
        <pre
          style={{
            marginTop: 14, background: "#080b0d", border: "1px solid #20272c", borderRadius: 9,
            padding: 12, maxHeight: 200, overflow: "auto", color: "#b8c2c9", fontSize: 12,
            whiteSpace: "pre-wrap", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          }}
        >
          {response}
        </pre>
      )}
    </section>
  );
}

function CommandBuilder({
  onSend, sending,
}: {
  onSend: (command: string, confirmMessage?: string) => Promise<void>;
  sending: boolean;
}) {
  const [group, setGroup] = useState(COMMAND_GROUPS[0]);
  const [commandId, setCommandId] = useState(SERVER_COMMANDS.find((c) => c.group === COMMAND_GROUPS[0])!.id);
  const [values, setValues] = useState<Record<string, string>>({});
  const [online, setOnline] = useState<string[]>([]);

  useEffect(() => {
    getPlayers().then((r) => setOnline(r.online.map((p) => p.name))).catch(() => {});
  }, []);

  const inGroup = SERVER_COMMANDS.filter((c) => c.group === group);
  const def = SERVER_COMMANDS.find((c) => c.id === commandId) ?? inGroup[0];

  function pickGroup(g: string) {
    setGroup(g);
    const first = SERVER_COMMANDS.find((c) => c.group === g);
    if (first) { setCommandId(first.id); setValues({}); }
  }

  function pickCommand(id: string) {
    setCommandId(id);
    setValues({});
  }

  function setField(key: string, val: string) {
    setValues((prev) => ({ ...prev, [key]: val }));
  }

  const missingRequired = def.fields.some((f) => {
    const optional = f.type.endsWith("-optional") || f.type === "bool-flag";
    return !optional && !values[f.key]?.trim();
  });

  async function run() {
    if (missingRequired) return;
    const built = def.build(values);
    const confirmMessage = def.danger
      ? `Send "${built}"? This is a destructive/moderation command - double check the target before confirming.`
      : undefined;
    await onSend(built, confirmMessage);
  }

  return (
    <div style={{ marginBottom: 14 }}>
      <div className="panel-title" style={{ marginTop: 6 }}><span>Command Builder</span></div>

      <div className="settings-grid">
        <div className="setting">
          <label>Category</label>
          <select value={group} onChange={(e) => pickGroup(e.target.value)}>
            {COMMAND_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div className="setting">
          <label>Command</label>
          <select value={def.id} onChange={(e) => pickCommand(e.target.value)}>
            {inGroup.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>
      </div>

      <small className="muted" style={{ display: "block", marginTop: 8 }}>{def.description}</small>
      {def.confidence === "low" && (
        <div className="notice notice-warning" style={{ marginTop: 8 }}>
          <AlertTriangle size={14} />
          Undocumented/low-confidence command - the server's own help output doesn't
          describe its real arguments. Test carefully.
        </div>
      )}

      {def.fields.length > 0 && (
        <div className="settings-grid" style={{ marginTop: 10 }}>
          {def.fields.map((f) => (
            <div className="setting" key={f.key}>
              <label>{f.label}</label>
              {f.type === "player" || f.type === "player-optional" ? (
                <select value={values[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)}>
                  <option value="">{f.type === "player-optional" ? "(none)" : "Choose a player…"}</option>
                  {online.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
              ) : f.type === "bool-flag" ? (
                <select value={values[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)}>
                  <option value="">(default)</option>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : f.type === "select" ? (
                <select value={values[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)}>
                  <option value="" disabled>Choose…</option>
                  {(f.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : f.type === "item" ? (
                <>
                  <ItemPicker value={values[f.key] ?? ""} onChange={(v) => setField(f.key, v)} />
                  <a
                    href="https://pzwiki.net/wiki/PZwiki:Item_list"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="muted"
                    style={{ display: "inline-flex", alignItems: "center", gap: 5, marginTop: 6, fontSize: 12 }}
                  >
                    <ExternalLink size={12} /> Full item list (PZwiki)
                  </a>
                </>
              ) : (
                <input
                  type={f.type.startsWith("number") ? "number" : "text"}
                  value={values[f.key] ?? ""}
                  placeholder={f.placeholder}
                  onChange={(e) => setField(f.key, e.target.value)}
                />
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <button className={def.danger ? "danger" : "primary"} onClick={run} disabled={sending || missingRequired}>
          Send
        </button>
      </div>
    </div>
  );
}

function AdjustSkillsPanel({ setToast }: { setToast: (msg: string) => void }) {
  const [online, setOnline] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [perks, setPerks] = useState<Perk[]>([]);
  const [maxLevel, setMaxLevel] = useState(10);
  const [perk, setPerk] = useState("");
  const [level, setLevel] = useState(5);
  const [settingSkill, setSettingSkill] = useState(false);

  useEffect(() => {
    getPlayers().then((r) => setOnline(r.online.map((p) => p.name))).catch(() => {});
  }, []);

  // `online` loads asynchronously (empty on first render) - keep the selection
  // synced to a valid choice whenever the roster changes, same reasoning as the
  // player pickers elsewhere in this app.
  useEffect(() => {
    if (!selected || !online.includes(selected)) setSelected(online[0] ?? null);
  }, [online]);

  useEffect(() => {
    getPerks().then((r) => {
      setPerks(r.perks);
      setMaxLevel(r.max_level);
      setPerk((p) => p || r.perks[0]?.id || "");
    }).catch(() => {});
  }, []);

  async function grantSkill() {
    if (!selected || !perk) return;
    setSettingSkill(true);
    try {
      const r = await setPlayerSkill(selected, perk, level);
      setToast(r.response ? `Adjust skill: ${r.response}` : "Adjust skill sent.");
    } catch (e: any) {
      setToast(e.message || "Adjust skill failed.");
    } finally {
      setSettingSkill(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-title"><span>Adjust Skills</span><GraduationCap size={16} /></div>

      {!online.length ? (
        <div className="empty">No players online to act on.</div>
      ) : (
        <>
          <div className="settings-grid">
            <div className="setting">
              <label>Player</label>
              <select value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}>
                {online.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
          </div>

          <div className="notice notice-warning" style={{ marginTop: 14 }}>
            <AlertTriangle size={14} />
            Grants XP
          </div>

          <div className="settings-grid" style={{ marginTop: 10 }}>
            <div className="setting">
              <label>Skill</label>
              <select value={perk} onChange={(e) => setPerk(e.target.value)}>
                {perks.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
            <div className="setting">
              <label>XP to Add</label>
              <select value={level} onChange={(e) => setLevel(Number(e.target.value))}>
                {Array.from({ length: maxLevel }, (_, i) => i + 1).map((lvl) => (
                  <option key={lvl} value={lvl}>{lvl}</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <button onClick={grantSkill} disabled={!perk || settingSkill}>
              {settingSkill ? "Granting…" : "Add Levels"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
