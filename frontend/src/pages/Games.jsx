import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Gauge, Loader2, Swords, MonitorDown, Search, Sparkles, RefreshCw, Settings2, Save, Zap } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { SecureRunBlock } from "@/components/SecureRunBlock";

const RES = ["1080p", "1440p", "4K"];

// Mappa dei nomi di processo Windows -> nome visualizzato all'utente.
// La lista candidata e' definita in ps_agent.py Get-RunningApps (whitelist di
// app closable: browser, chat, media, cloud, launcher, misc). Aggiungere qui
// per estendere la mappatura visiva.
const APP_LABELS = {
  chrome: "Chrome",
  msedge: "Edge",
  firefox: "Firefox",
  opera: "Opera",
  brave: "Brave",
  Discord: "Discord",
  Slack: "Slack",
  Teams: "Teams",
  Telegram: "Telegram",
  WhatsApp: "WhatsApp",
  Skype: "Skype",
  SkypeApp: "Skype (UWP)",
  Spotify: "Spotify",
  "Music.UI": "Groove Music",
  OneDrive: "OneDrive",
  GoogleDriveFS: "Google Drive",
  Dropbox: "Dropbox",
  EpicGamesLauncher: "Epic Games Launcher",
  CCleaner: "CCleaner",
  Cortana: "Cortana",
  YourPhone: "Your Phone",
  PhoneExperienceHost: "Phone Link",
};

export default function Games() {
  const { t } = useTranslation();
  const [games, setGames] = useState([]);
  const [specs, setSpecs] = useState(null);
  const [token, setToken] = useState("");

  const [game, setGame] = useState("");
  const [res, setRes] = useState("1440p");
  const [loading, setLoading] = useState(false);
  const [fps, setFps] = useState(null);
  const [err, setErr] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const [runningApps, setRunningApps] = useState([]);
  const [runningAt, setRunningAt] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [catalog, setCatalog] = useState([]);

  // Booster: config e sessioni. close_apps e' un Set di process names (es. "chrome").
  const [showBoostCfg, setShowBoostCfg] = useState(false);
  const [boostCloseApps, setBoostCloseApps] = useState(new Set());
  const [boostCfg, setBoostCfg] = useState({ set_power: true, boost_priority: true, purge_ram: true });
  const [savingBoost, setSavingBoost] = useState(false);
  const [boostSessions, setBoostSessions] = useState([]);

  const loadGames = async () => {
    try { const { data } = await api.get("/games"); setGames(data.games || []); } catch (e) { console.error("loadGames failed", e); }
  };
  // Le running_apps sono esposte dall'endpoint /prematch (legacy), le riusiamo
  // per il Booster: mostrano quali app in background stanno girando sul PC
  // dell'utente al momento dell'ultima sync.
  const loadRunningApps = async () => {
    try {
      const { data } = await api.get("/prematch");
      setRunningApps(data.running_apps || []);
      setRunningAt(data.running_at || null);
    } catch (e) { console.error("loadRunningApps failed", e); }
  };
  useEffect(() => {
    loadGames();
    loadRunningApps();
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch((e) => console.error("load pc-specs failed", e));
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch((e) => console.error("load agent token failed", e));
    api.get("/profiles/templates").then(({ data }) => { setTemplates(data.templates || []); setCatalog(data.catalog || []); }).catch((e) => console.error("load templates failed", e));
    api.get("/booster").then(({ data }) => {
      setBoostCfg({ set_power: data.set_power !== false, boost_priority: data.boost_priority !== false, purge_ram: data.purge_ram !== false });
      setBoostCloseApps(new Set(data.close_apps || []));
    }).catch((e) => console.error("load booster failed", e));
    api.get("/booster/sessions").then(({ data }) => setBoostSessions(data.sessions || [])).catch((e) => console.error("load booster sessions failed", e));
  }, []);

  const toggleBoostApp = (proc) => {
    setBoostCloseApps((prev) => {
      const s = new Set(prev);
      if (s.has(proc)) s.delete(proc); else s.add(proc);
      return s;
    });
  };

  const saveBoostConfig = async () => {
    setSavingBoost(true);
    const close_apps = Array.from(boostCloseApps);
    try { await api.put("/booster", { close_apps, ...boostCfg }); toast.success(t("games.save_ok")); }
    catch { toast.error(t("games.save_err")); }
    finally { setSavingBoost(false); }
  };

  const recTpl = useMemo(() => {
    const g = game.trim().toLowerCase();
    if (!g || !templates.length) return null;
    return templates.find((t) => (t.match || []).some((m) => g.includes(m)))
      || templates.find((t) => t.id === "tpl_balanced") || null;
  }, [game, templates]);

  // Precompute the tweak-name chips shown for the recommended preset (was inline filter/map/slice in JSX)
  const recTweakNames = useMemo(() => {
    if (!recTpl || !catalog.length) return [];
    return recTpl.tweak_ids
      .map((id) => catalog.find((c) => c.id === id)?.name)
      .filter(Boolean)
      .slice(0, 8);
  }, [recTpl, catalog]);

  const hasSpecs = !!specs?.data?.cpu;

  const estimate = async (g) => {
    const name = (g ?? game).trim();
    if (!name) return;
    setGame(name); setLoading(true); setErr(""); setFps(null);
    try { const { data } = await api.post("/fps/estimate", { game: name, resolution: res }); setFps(data); }
    catch (e) { setErr(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  const refresh = async () => { setRefreshing(true); await loadGames(); setRefreshing(false); toast.success(t("games.list_updated")); };

  const maxFps = useMemo(() => (fps ? Math.max(...fps.estimates.map((e) => e.fps), 1) : 1), [fps]);

  return (
    <div className="max-w-5xl mx-auto fade-up" data-testid="games-page">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("games.eyebrow")}</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">{t("games.title")}</h1>
        <p className="text-zinc-500 text-sm mt-1">{t("games.subtitle")}</p>
      </div>

      {/* Game Booster: consolidato (ex Pre-match rimosso, il Booster fa lo stesso in automatico) */}
      <div className="bg-gradient-to-br from-[#00E0FF]/10 to-transparent border border-[#00E0FF]/40 p-5 mb-5" data-testid="booster-card">
        <div className="flex items-center gap-2 text-sm font-bold mb-1 text-[#00E0FF]"><Zap size={16} /> {t("games.booster_title")}</div>
        <p className="text-xs text-zinc-400 mb-3 leading-relaxed">{t("games.booster_desc")}</p>
        <SecureRunBlock token={token} mode="booster" testid="booster-run-cmd" />

        <button onClick={() => setShowBoostCfg((v) => !v)} data-testid="booster-config-toggle"
          className="mt-3 inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-[#00E0FF] transition-colors">
          <Settings2 size={13} /> {showBoostCfg ? t("games.hide_customize") : t("games.customize")}
        </button>

        {showBoostCfg && (
          <div className="mt-3 bg-black/50 border border-[#2A2A35] p-4" data-testid="booster-config">
            <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none mb-2" data-testid="booster-priority-toggle">
              <input type="checkbox" checked={boostCfg.boost_priority} onChange={(e) => setBoostCfg((s) => ({ ...s, boost_priority: e.target.checked }))} className="accent-[#00E0FF] w-4 h-4" />
              {t("games.booster_priority")}
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none mb-2" data-testid="booster-power-toggle">
              <input type="checkbox" checked={boostCfg.set_power} onChange={(e) => setBoostCfg((s) => ({ ...s, set_power: e.target.checked }))} className="accent-[#00E0FF] w-4 h-4" />
              {t("games.booster_power_toggle")}
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none mb-3" data-testid="booster-purge-toggle">
              <input type="checkbox" checked={boostCfg.purge_ram} onChange={(e) => setBoostCfg((s) => ({ ...s, purge_ram: e.target.checked }))} className="accent-[#00E0FF] w-4 h-4" />
              {t("games.booster_purge")}
            </label>
            {/* App in esecuzione da chiudere - lista dinamica (non piu' categorie generiche) */}
            <div className="border-t border-[#2A2A35] pt-3 mb-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs uppercase tracking-widest text-zinc-500">{t("games.booster_close")}</div>
                <button onClick={loadRunningApps} data-testid="booster-refresh-running"
                  className="text-[10px] text-zinc-500 hover:text-[#00E0FF] transition-colors inline-flex items-center gap-1">
                  <RefreshCw size={11} /> {t("games.refresh_short") || "aggiorna"}
                </button>
              </div>

              {runningApps.length === 0 ? (
                <div className="bg-black/30 border border-[#2A2A35] px-3 py-4 text-xs text-zinc-500 text-center leading-relaxed" data-testid="booster-no-running">
                  {t("games.booster_no_running") || "Nessuna app in background rilevata. Avvia il FrameForge Agent con Ottimizza o Sync per aggiornare la lista."}
                </div>
              ) : (
                <>
                  <div className="text-[11px] text-[#00FF66] mb-2 flex items-center gap-1.5" data-testid="booster-running-summary">
                    <span className="w-2 h-2 rounded-full bg-[#00FF66] animate-pulse" />
                    {(t("games.booster_running_count", { count: runningApps.length }) || `${runningApps.length} app in background rilevate`)}
                    {runningAt ? <span className="text-zinc-500"> · {new Date(runningAt).toLocaleString(undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span> : null}
                  </div>
                  <div className="grid sm:grid-cols-2 gap-1.5 mb-2" data-testid="booster-running-list">
                    {runningApps.map((proc) => {
                      const label = APP_LABELS[proc] || proc;
                      const checked = boostCloseApps.has(proc);
                      return (
                        <label key={proc} data-testid={`booster-app-${proc}`}
                          className={`flex items-center gap-2 text-sm cursor-pointer select-none px-2 py-1.5 border transition-colors ${
                            checked
                              ? "bg-[#00E0FF]/10 border-[#00E0FF]/40 text-white"
                              : "border-[#1A1A24] text-zinc-300 hover:border-[#2A2A35]"
                          }`}>
                          <input type="checkbox" checked={checked} onChange={() => toggleBoostApp(proc)}
                            className="accent-[#00E0FF] w-4 h-4" />
                          <span className="flex-1 truncate">{label}</span>
                          <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">{proc}</span>
                        </label>
                      );
                    })}
                  </div>
                  {boostCloseApps.size > 0 && (
                    <div className="text-[10px] text-zinc-500 mb-1" data-testid="booster-selected-count">
                      {(t("games.booster_will_close", { count: boostCloseApps.size }) || `Al prossimo boost chiuderemo ${boostCloseApps.size} app.`)}
                    </div>
                  )}
                </>
              )}
            </div>
            <button onClick={saveBoostConfig} disabled={savingBoost} data-testid="booster-save"
              className="inline-flex items-center gap-2 bg-[#00E0FF] text-black font-bold px-4 py-2 text-sm hover:bg-[#00C8E0] transition-colors disabled:opacity-60">
              {savingBoost ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} {t("games.save_settings")}
            </button>
          </div>
        )}

        {boostSessions.length > 0 && (
          <div className="mt-3 border-t border-[#2A2A35] pt-3" data-testid="booster-sessions">
            <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{t("games.booster_sessions")}</div>
            <div className="space-y-1">
              {boostSessions.slice(0, 5).map((s, i) => (
                <div key={s.session_id || `${s.game}-${s.started_at || i}`} className="flex items-center justify-between text-xs bg-black/40 border border-[#1A1A24] px-3 py-1.5" data-testid={`booster-session-${i}`}>
                  <span className="text-zinc-200 font-semibold">{s.game}</span>
                  <span className="text-zinc-500">{Math.round((s.duration_s || 0) / 60)} {t("games.booster_min")} · {(s.actions || []).length} {t("games.booster_actions")}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-[1fr_1.1fr] gap-4">
        {/* Detected games */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs uppercase tracking-widest text-zinc-500 flex items-center gap-2"><Swords size={14} className="text-[#E5FF00]" /> {t("games.detected")} ({games.length})</div>
            <button onClick={refresh} data-testid="games-refresh" className="text-zinc-500 hover:text-[#E5FF00] transition-colors"><RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /></button>
          </div>

          {games.length === 0 ? (
            <div className="text-sm text-zinc-400 leading-relaxed">
              <div className="flex items-center gap-2 text-zinc-300 mb-2"><MonitorDown size={16} className="text-[#E5FF00]" /> {t("games.no_games")}</div>
              <p className="text-xs text-zinc-500 mb-3">{t("games.no_games_hint")}</p>
              <SecureRunBlock token={token} mode="sync" testid="games-sync-cmd" />
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {games.map((g, i) => (
                <button key={g} data-testid={`game-chip-${i}`} onClick={() => estimate(g)}
                  className={`text-xs px-3 py-1.5 border transition-colors ${game === g ? "bg-[#E5FF00] text-black border-[#E5FF00] font-bold" : "border-[#2A2A35] text-zinc-300 hover:border-[#E5FF00]"}`}>
                  {g}
                </button>
              ))}
            </div>
          )}

          <div className="mt-4 pt-4 border-t border-[#2A2A35]">
            <label className="text-xs uppercase tracking-widest text-zinc-500">{t("games.analyze_title")}</label>
            <div className="flex gap-2 mt-1">
              <input data-testid="game-input" value={game} onChange={(e) => setGame(e.target.value)} placeholder={t("games.analyze_ph")}
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
            {!hasSpecs && <p className="text-[11px] text-zinc-500 mt-2">{t("games.no_specs_hint")} <Link to="/app/pc" className="text-[#E5FF00] hover:underline">{t("nav.pc")}</Link>.</p>}
          </div>
        </div>

        {/* FPS result */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2"><Gauge size={14} className="text-[#E5FF00]" /> {t("games.analysis")}</div>
          {err && <div className="text-xs text-[#FF3B30]">{err}</div>}
          {!fps && !loading && !err && (
            <div className="h-56 flex flex-col items-center justify-center text-center text-zinc-600">
              <Sparkles size={28} className="text-[#E5FF00] mb-3" />
              <p className="text-sm text-zinc-500 max-w-xs">{t("games.empty_hint")}</p>
            </div>
          )}
          {loading && <div className="h-56 flex items-center justify-center"><Loader2 size={24} className="animate-spin text-[#E5FF00]" /></div>}
          {fps && !loading && (
            <div className="fade-up" data-testid="fps-result">
              <div className="text-sm text-zinc-300 mb-3">{fps.game} · {fps.resolution} <span className="text-xs text-zinc-500">({t("common.reliability")} {fps.confidence})</span></div>
              <div className="space-y-2">
                {fps.estimates.map((e, i) => (
                  <div key={e.preset || i} data-testid={`fps-bar-${i}`}>
                    <div className="flex justify-between text-xs mb-1"><span className="text-zinc-400">{e.preset}</span><span className="font-bold text-zinc-100">{e.fps} FPS</span></div>
                    <div className="h-2 bg-black border border-[#1A1A24]">
                      <div className="h-full" style={{ width: `${(e.fps / maxFps) * 100}%`, background: e.fps >= 60 ? "#00FF66" : e.fps >= 30 ? "#E5FF00" : "#FF3B30" }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 text-sm"><span className="text-zinc-500">{t("games.recommended_preset")} </span><span className="text-[#E5FF00] font-bold">{fps.recommended_preset}</span></div>
              <p className="text-xs text-zinc-500 mt-2 leading-relaxed">{fps.notes}</p>
            </div>
          )}
        </div>
      </div>

      {recTpl && (
        <div className="mt-4 bg-gradient-to-br from-[#00E0FF]/10 to-transparent border border-[#00E0FF]/40 p-5" data-testid="rec-preset-card">
          <div className="flex items-center gap-2 text-sm font-bold mb-1 text-[#00E0FF]">
            <Settings2 size={16} /> {t("games.rec_title")}
          </div>
          <p className="text-xs text-zinc-400 mb-3">
            {t("games.rec_for")} <span className="text-zinc-200 font-semibold">{game}</span>: <span className="text-[#00E0FF] font-bold">{recTpl.game_name}</span>
            <span className="text-zinc-500"> · {recTpl.preset_label}</span>
          </p>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {recTweakNames.map((n) => (
              <span key={n} className="text-[11px] bg-black border border-[#1A1A24] px-2 py-0.5 text-zinc-400">{n}</span>
            ))}
            {recTpl.tweak_ids.length > 8 && <span className="text-[11px] text-zinc-600 px-1">+{recTpl.tweak_ids.length - 8}</span>}
          </div>
          <SecureRunBlock token={token} mode="optimize" profile={recTpl.id} testid="rec-preset-run" />
          <p className="text-[11px] text-zinc-500 mt-2">{t("games.rec_hint")}</p>
        </div>
      )}
    </div>
  );
}
