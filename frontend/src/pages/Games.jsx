import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Gauge, Loader2, Swords, Copy, Check, Rocket, MonitorDown, Search, Sparkles, RefreshCw, Settings2, Save } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const RES = ["1080p", "1440p", "4K"];

const APP_GROUPS = [
  { id: "browser", label: "Browser", procs: ["chrome", "msedge", "firefox", "opera", "brave"] },
  { id: "chat", label: "Chat & Voce (Discord, Teams...)", procs: ["Discord", "Slack", "Teams", "Telegram", "WhatsApp", "Skype", "SkypeApp"] },
  { id: "media", label: "Musica & Media (Spotify...)", procs: ["Spotify", "Music.UI"] },
  { id: "cloud", label: "Sync cloud (OneDrive, Drive...)", procs: ["OneDrive", "GoogleDriveFS", "Dropbox"] },
  { id: "launcher", label: "Launcher (Epic Games)", procs: ["EpicGamesLauncher"] },
  { id: "other", label: "Utility (CCleaner, Cortana...)", procs: ["CCleaner", "Cortana", "YourPhone", "PhoneExperienceHost"] },
];

export default function Games() {
  const [games, setGames] = useState([]);
  const [specs, setSpecs] = useState(null);
  const [token, setToken] = useState("");
  const [copied, setCopied] = useState(false);

  const [game, setGame] = useState("");
  const [res, setRes] = useState("1440p");
  const [loading, setLoading] = useState(false);
  const [fps, setFps] = useState(null);
  const [err, setErr] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const [showConfig, setShowConfig] = useState(false);
  const [groups, setGroups] = useState(() => Object.fromEntries(APP_GROUPS.map((g) => [g.id, true])));
  const [setPower, setSetPower] = useState(true);
  const [savingCfg, setSavingCfg] = useState(false);
  const [runningApps, setRunningApps] = useState([]);
  const [runningAt, setRunningAt] = useState(null);

  const loadGames = async () => {
    try { const { data } = await api.get("/games"); setGames(data.games || []); } catch {}
  };
  const loadPrematch = async () => {
    try {
      const { data } = await api.get("/prematch");
      setSetPower(data.set_power !== false);
      const apps = data.close_apps || [];
      setGroups(Object.fromEntries(APP_GROUPS.map((g) => [g.id, g.procs.every((p) => apps.includes(p))])));
      setRunningApps(data.running_apps || []);
      setRunningAt(data.running_at || null);
    } catch {}
  };
  useEffect(() => {
    loadGames();
    loadPrematch();
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
  }, []);

  const saveConfig = async () => {
    setSavingCfg(true);
    const close_apps = APP_GROUPS.filter((g) => groups[g.id]).flatMap((g) => g.procs);
    try { await api.put("/prematch", { close_apps, set_power: setPower }); toast.success("Impostazioni salvate! Il comando è aggiornato."); }
    catch { toast.error("Errore nel salvataggio"); }
    finally { setSavingCfg(false); }
  };

  const hasSpecs = !!specs?.data?.cpu;
  const prematchCmd = `irm "${BACKEND}/api/agent/script?t=${token || "IL_TUO_TOKEN"}&mode=prematch" | iex`;
  const syncCmd = `irm "${BACKEND}/api/agent/script?t=${token || "IL_TUO_TOKEN"}&mode=sync" | iex`;

  const copyCmd = async (text) => {
    try { await navigator.clipboard.writeText(text); } catch { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success("Comando copiato!"); setTimeout(() => setCopied(false), 2000);
  };

  const estimate = async (g) => {
    const name = (g ?? game).trim();
    if (!name) return;
    setGame(name); setLoading(true); setErr(""); setFps(null);
    try { const { data } = await api.post("/fps/estimate", { game: name, resolution: res }); setFps(data); }
    catch (e) { setErr(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  const refresh = async () => { setRefreshing(true); await loadGames(); setRefreshing(false); toast.success("Elenco aggiornato"); };

  const maxFps = useMemo(() => (fps ? Math.max(...fps.estimates.map((e) => e.fps), 1) : 1), [fps]);

  return (
    <div className="max-w-5xl mx-auto fade-up" data-testid="games-page">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Giochi</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">I miei giochi</h1>
        <p className="text-zinc-500 text-sm mt-1">FPS attesi e impostazioni consigliate per i tuoi giochi, in base al tuo hardware.</p>
      </div>

      {/* Prima del match */}
      <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-5 mb-5" data-testid="prematch-card">
        <div className="flex items-center gap-2 text-sm font-bold mb-1 text-[#E5FF00]"><Rocket size={16} /> Modalità "Prima del match"</div>
        <p className="text-xs text-zinc-400 mb-3 leading-relaxed">Boost 1-click reversibile: attiva il piano prestazioni elevate e chiude le app in background (browser, Discord, Spotify...). A fine partita premi INVIO e ripristini tutto. Esegui in PowerShell.</p>
        <div className="flex items-stretch gap-2">
          <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="prematch-cmd">{prematchCmd}</code>
          <button onClick={() => copyCmd(prematchCmd)} data-testid="prematch-copy"
            className="shrink-0 flex items-center justify-center border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors">
            {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
          </button>
        </div>

        <button onClick={() => setShowConfig((v) => !v)} data-testid="prematch-config-toggle"
          className="mt-3 inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-[#E5FF00] transition-colors">
          <Settings2 size={13} /> {showConfig ? "Nascondi personalizzazione" : "Personalizza cosa chiudere"}
        </button>

        {showConfig && (
          <div className="mt-3 bg-black/50 border border-[#2A2A35] p-4" data-testid="prematch-config">
            {runningApps.length > 0 ? (
              <div className="text-xs text-[#00FF66] mb-3 flex items-center gap-1.5" data-testid="running-summary">
                <span className="w-2 h-2 rounded-full bg-[#00FF66] animate-pulse" /> {runningApps.length} app in esecuzione rilevate sul PC{runningAt ? ` · ultimo sync ${new Date(runningAt).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}` : ""}
              </div>
            ) : (
              <div className="text-xs text-zinc-500 mb-3">Avvia il comando <span className="text-zinc-300">sync</span> del Desktop Agent per vedere quali app sono realmente in esecuzione ora.</div>
            )}
            <div className="text-xs text-zinc-500 mb-2">Scegli quali app chiudere prima del match:</div>
            <div className="grid sm:grid-cols-2 gap-2 mb-3">
              {APP_GROUPS.map((g) => {
                const run = g.procs.filter((p) => runningApps.includes(p));
                return (
                  <label key={g.id} data-testid={`prematch-group-${g.id}`}
                    className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none">
                    <input type="checkbox" checked={!!groups[g.id]} onChange={(e) => setGroups((s) => ({ ...s, [g.id]: e.target.checked }))}
                      className="accent-[#E5FF00] w-4 h-4" />
                    <span>{g.label}</span>
                    {run.length > 0 && (
                      <span title={run.join(", ")} data-testid={`running-badge-${g.id}`}
                        className="inline-flex items-center gap-1 text-[10px] font-bold text-[#00FF66] border border-[#00FF66]/40 bg-[#00FF66]/10 px-1.5 py-0.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#00FF66]" /> {run.length} attiva{run.length > 1 ? "e" : ""}
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none border-t border-[#2A2A35] pt-3" data-testid="prematch-power-toggle">
              <input type="checkbox" checked={setPower} onChange={(e) => setSetPower(e.target.checked)} className="accent-[#E5FF00] w-4 h-4" />
              Attiva il piano "Prestazioni elevate" (ripristinato a fine partita)
            </label>
            <button onClick={saveConfig} disabled={savingCfg} data-testid="prematch-save"
              className="mt-3 inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EC00] transition-colors disabled:opacity-60">
              {savingCfg ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Salva impostazioni
            </button>
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-[1fr_1.1fr] gap-4">
        {/* Detected games */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs uppercase tracking-widest text-zinc-500 flex items-center gap-2"><Swords size={14} className="text-[#E5FF00]" /> Giochi rilevati ({games.length})</div>
            <button onClick={refresh} data-testid="games-refresh" className="text-zinc-500 hover:text-[#E5FF00] transition-colors"><RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /></button>
          </div>

          {games.length === 0 ? (
            <div className="text-sm text-zinc-400 leading-relaxed">
              <div className="flex items-center gap-2 text-zinc-300 mb-2"><MonitorDown size={16} className="text-[#E5FF00]" /> Nessun gioco rilevato.</div>
              <p className="text-xs text-zinc-500 mb-3">Avvia il Desktop Agent (comando "sync") per rilevare automaticamente i giochi installati su Steam ed Epic.</p>
              <div className="flex items-stretch gap-2">
                <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-[11px] text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="games-sync-cmd">{syncCmd}</code>
                <button onClick={() => copyCmd(syncCmd)} className="shrink-0 flex items-center justify-center border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors"><Copy size={14} /></button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {games.map((g, i) => (
                <button key={i} data-testid={`game-chip-${i}`} onClick={() => estimate(g)}
                  className={`text-xs px-3 py-1.5 border transition-colors ${game === g ? "bg-[#E5FF00] text-black border-[#E5FF00] font-bold" : "border-[#2A2A35] text-zinc-300 hover:border-[#E5FF00]"}`}>
                  {g}
                </button>
              ))}
            </div>
          )}

          <div className="mt-4 pt-4 border-t border-[#2A2A35]">
            <label className="text-xs uppercase tracking-widest text-zinc-500">Analizza un gioco</label>
            <div className="flex gap-2 mt-1">
              <input data-testid="game-input" value={game} onChange={(e) => setGame(e.target.value)} placeholder="es. Cyberpunk 2077..."
                onKeyDown={(e) => e.key === "Enter" && estimate()}
                className="flex-1 bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm" />
              <button data-testid="game-search-btn" onClick={() => estimate()} disabled={loading}
                className="bg-[#E5FF00] text-black px-4 font-bold hover:bg-[#D4EC00] transition-colors disabled:opacity-60 flex items-center">
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              </button>
            </div>
            <div className="flex gap-2 mt-3">
              {RES.map((r) => (
                <button key={r} data-testid={`res-${r}`} onClick={() => setRes(r)}
                  className={`flex-1 py-1.5 text-xs border transition-colors ${res === r ? "bg-[#E5FF00] text-black border-[#E5FF00] font-bold" : "border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>{r}</button>
              ))}
            </div>
            {!hasSpecs && <p className="text-[11px] text-zinc-500 mt-2">Senza hardware rilevato la stima è generica. Aggiungi le specifiche in <Link to="/app/pc" className="text-[#E5FF00] hover:underline">Il mio PC</Link>.</p>}
          </div>
        </div>

        {/* FPS result */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2"><Gauge size={14} className="text-[#E5FF00]" /> Analisi</div>
          {err && <div className="text-xs text-[#FF3B30]">{err}</div>}
          {!fps && !loading && !err && (
            <div className="h-56 flex flex-col items-center justify-center text-center text-zinc-600">
              <Sparkles size={28} className="text-[#E5FF00] mb-3" />
              <p className="text-sm text-zinc-500 max-w-xs">Seleziona un gioco rilevato o scrivi un titolo per vedere gli FPS attesi e le impostazioni consigliate.</p>
            </div>
          )}
          {loading && <div className="h-56 flex items-center justify-center"><Loader2 size={24} className="animate-spin text-[#E5FF00]" /></div>}
          {fps && !loading && (
            <div className="fade-up" data-testid="fps-result">
              <div className="text-sm text-zinc-300 mb-3">{fps.game} · {fps.resolution} <span className="text-xs text-zinc-500">(affidabilità {fps.confidence})</span></div>
              <div className="space-y-2">
                {fps.estimates.map((e, i) => (
                  <div key={i} data-testid={`fps-bar-${i}`}>
                    <div className="flex justify-between text-xs mb-1"><span className="text-zinc-400">{e.preset}</span><span className="font-bold text-zinc-100">{e.fps} FPS</span></div>
                    <div className="h-2 bg-black border border-[#1A1A24]">
                      <div className="h-full" style={{ width: `${(e.fps / maxFps) * 100}%`, background: e.fps >= 60 ? "#00FF66" : e.fps >= 30 ? "#E5FF00" : "#FF3B30" }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 text-sm"><span className="text-zinc-500">Preset consigliato: </span><span className="text-[#E5FF00] font-bold">{fps.recommended_preset}</span></div>
              <p className="text-xs text-zinc-500 mt-2 leading-relaxed">{fps.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
