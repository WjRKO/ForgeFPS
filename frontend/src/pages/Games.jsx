import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Gauge, Loader2, Swords, Copy, Check, Rocket, MonitorDown, Search, Sparkles, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const RES = ["1080p", "1440p", "4K"];

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

  const loadGames = async () => {
    try { const { data } = await api.get("/games"); setGames(data.games || []); } catch {}
  };
  useEffect(() => {
    loadGames();
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
  }, []);

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
