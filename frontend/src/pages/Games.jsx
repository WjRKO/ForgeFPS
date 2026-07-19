import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Gauge, Loader2, Swords, Rocket, MonitorDown, Search, Sparkles, RefreshCw, Settings2, Save, Zap, Target, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { SecureRunBlock } from "@/components/SecureRunBlock";

const RES = ["1080p", "1440p", "4K"];
const BOOST_MODE_KEY = "ff_boost_mode_v1";

const APP_GROUPS = [
  { id: "browser", procs: ["chrome", "msedge", "firefox", "opera", "brave"] },
  { id: "chat", procs: ["Discord", "Slack", "Teams", "Telegram", "WhatsApp", "Skype", "SkypeApp"] },
  { id: "media", procs: ["Spotify", "Music.UI"] },
  { id: "cloud", procs: ["OneDrive", "GoogleDriveFS", "Dropbox"] },
  { id: "launcher", procs: ["EpicGamesLauncher"] },
  { id: "other", procs: ["CCleaner", "Cortana", "YourPhone", "PhoneExperienceHost"] },
];

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

  const [showConfig, setShowConfig] = useState(false);
  const [groups, setGroups] = useState(() => Object.fromEntries(APP_GROUPS.map((g) => [g.id, true])));
  const [setPower, setSetPower] = useState(true);
  const [savingCfg, setSavingCfg] = useState(false);
  const [runningApps, setRunningApps] = useState([]);
  const [runningAt, setRunningAt] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [catalog, setCatalog] = useState([]);

  const [showBoostCfg, setShowBoostCfg] = useState(false);
  const [boostGroups, setBoostGroups] = useState(() => Object.fromEntries(APP_GROUPS.map((g) => [g.id, false])));
  const [boostCfg, setBoostCfg] = useState({ set_power: true, boost_priority: true, purge_ram: true });
  const [savingBoost, setSavingBoost] = useState(false);
  const [boostSessions, setBoostSessions] = useState([]);

  // Wizard: "auto" (Game Booster) | "manual" (Pre-match) | null (chiedi)
  const [boostMode, setBoostMode] = useState(() => {
    try { return typeof window !== "undefined" ? window.localStorage.getItem(BOOST_MODE_KEY) : null; } catch { return null; }
  });
  const chooseMode = (m) => {
    try { window.localStorage.setItem(BOOST_MODE_KEY, m); } catch (e) { console.error("boost mode save failed", e); }
    setBoostMode(m);
    if (m === "auto") setShowBoostCfg(true);
    if (m === "manual") setShowConfig(true);
  };
  const resetMode = () => {
    try { window.localStorage.removeItem(BOOST_MODE_KEY); } catch (e) { console.error("boost mode reset failed", e); }
    setBoostMode(null);
  };

  const loadGames = async () => {
    try { const { data } = await api.get("/games"); setGames(data.games || []); } catch (e) { console.error("loadGames failed", e); }
  };
  const loadPrematch = async () => {
    try {
      const { data } = await api.get("/prematch");
      setSetPower(data.set_power !== false);
      const apps = data.close_apps || [];
      setGroups(Object.fromEntries(APP_GROUPS.map((g) => [g.id, g.procs.every((p) => apps.includes(p))])));
      setRunningApps(data.running_apps || []);
      setRunningAt(data.running_at || null);
    } catch (e) { console.error("loadPrematch failed", e); }
  };
  useEffect(() => {
    loadGames();
    loadPrematch();
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
    api.get("/profiles/templates").then(({ data }) => { setTemplates(data.templates || []); setCatalog(data.catalog || []); }).catch(() => {});
    api.get("/booster").then(({ data }) => {
      setBoostCfg({ set_power: data.set_power !== false, boost_priority: data.boost_priority !== false, purge_ram: data.purge_ram !== false });
      const apps = data.close_apps || [];
      setBoostGroups(Object.fromEntries(APP_GROUPS.map((g) => [g.id, g.procs.every((p) => apps.includes(p)) && g.procs.length > 0])));
    }).catch(() => {});
    api.get("/booster/sessions").then(({ data }) => setBoostSessions(data.sessions || [])).catch(() => {});
  }, []);

  const saveBoostConfig = async () => {
    setSavingBoost(true);
    const close_apps = APP_GROUPS.filter((g) => boostGroups[g.id]).flatMap((g) => g.procs);
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

  const saveConfig = async () => {
    setSavingCfg(true);
    const close_apps = APP_GROUPS.filter((g) => groups[g.id]).flatMap((g) => g.procs);
    try { await api.put("/prematch", { close_apps, set_power: setPower }); toast.success(t("games.save_ok")); }
    catch { toast.error(t("games.save_err")); }
    finally { setSavingCfg(false); }
  };

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

      {/* Boost mode wizard - primo utilizzo */}
      {!boostMode && (
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-5" data-testid="boost-wizard">
          <div className="mb-5">
            <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-[#E5FF00] mb-2">{t("games.wizard_eyebrow")}</div>
            <h2 className="font-display font-black text-2xl tracking-tight text-white mb-1">{t("games.wizard_title")}</h2>
            <p className="text-zinc-500 text-sm">{t("games.wizard_sub")}</p>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <button
              onClick={() => chooseMode("auto")}
              data-testid="boost-mode-auto"
              className="group text-left bg-gradient-to-br from-[#00E0FF]/10 to-transparent border border-[#00E0FF]/40 p-5 hover:border-[#00E0FF] hover:from-[#00E0FF]/20 transition-all">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-9 h-9 flex items-center justify-center bg-[#00E0FF] text-black shrink-0">
                  <Zap size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-[#00E0FF]">{t("games.wizard_recommended")}</div>
                  <div className="font-bold text-white text-base">{t("games.wizard_auto_title")}</div>
                </div>
              </div>
              <p className="text-sm text-zinc-300 leading-relaxed mb-3">{t("games.wizard_auto_desc")}</p>
              <ul className="space-y-1 text-xs text-zinc-400">
                <li className="flex gap-2"><span className="text-[#00E0FF]">+</span> {t("games.wizard_auto_p1")}</li>
                <li className="flex gap-2"><span className="text-[#00E0FF]">+</span> {t("games.wizard_auto_p2")}</li>
                <li className="flex gap-2"><span className="text-[#00E0FF]">+</span> {t("games.wizard_auto_p3")}</li>
              </ul>
              <div className="mt-4 inline-flex items-center gap-1.5 text-xs font-bold text-[#00E0FF] uppercase tracking-widest border-b border-[#00E0FF]/40 pb-0.5 group-hover:border-[#00E0FF]">
                {t("games.wizard_choose")} <ChevronDown size={12} className="rotate-[-90deg]" />
              </div>
            </button>
            <button
              onClick={() => chooseMode("manual")}
              data-testid="boost-mode-manual"
              className="group text-left bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-5 hover:border-[#E5FF00] hover:from-[#E5FF00]/20 transition-all">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-9 h-9 flex items-center justify-center bg-[#E5FF00] text-black shrink-0">
                  <Target size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-[#E5FF00]">{t("games.wizard_advanced")}</div>
                  <div className="font-bold text-white text-base">{t("games.wizard_manual_title")}</div>
                </div>
              </div>
              <p className="text-sm text-zinc-300 leading-relaxed mb-3">{t("games.wizard_manual_desc")}</p>
              <ul className="space-y-1 text-xs text-zinc-400">
                <li className="flex gap-2"><span className="text-[#E5FF00]">+</span> {t("games.wizard_manual_p1")}</li>
                <li className="flex gap-2"><span className="text-[#E5FF00]">+</span> {t("games.wizard_manual_p2")}</li>
                <li className="flex gap-2"><span className="text-[#E5FF00]">+</span> {t("games.wizard_manual_p3")}</li>
              </ul>
              <div className="mt-4 inline-flex items-center gap-1.5 text-xs font-bold text-[#E5FF00] uppercase tracking-widest border-b border-[#E5FF00]/40 pb-0.5 group-hover:border-[#E5FF00]">
                {t("games.wizard_choose")} <ChevronDown size={12} className="rotate-[-90deg]" />
              </div>
            </button>
          </div>
        </div>
      )}

      {/* Riepilogo scelta con link "cambia" */}
      {boostMode && (
        <div className="flex items-center justify-between gap-3 mb-4 text-xs" data-testid="boost-mode-summary">
          <div className="flex items-center gap-2 text-zinc-400">
            {boostMode === "auto" ? <Zap size={13} className="text-[#00E0FF]" /> : <Target size={13} className="text-[#E5FF00]" />}
            <span>{t("games.wizard_using")}</span>
            <span className="font-bold" style={{ color: boostMode === "auto" ? "#00E0FF" : "#E5FF00" }}>
              {boostMode === "auto" ? t("games.wizard_auto_title") : t("games.wizard_manual_title")}
            </span>
          </div>
          <button onClick={resetMode} data-testid="boost-mode-reset"
            className="inline-flex items-center gap-1.5 text-zinc-500 hover:text-[#E5FF00] transition-colors">
            <RotateCcw size={12} /> {t("games.wizard_change")}
          </button>
        </div>
      )}

      {/* Game Booster (AUTO) - visibile solo se scelto o mode == null */}
      {(boostMode === "auto" || !boostMode) && (
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
            <div className="text-xs text-zinc-500 mb-2 border-t border-[#2A2A35] pt-3">{t("games.booster_close")}</div>
            <div className="grid sm:grid-cols-2 gap-2 mb-3">
              {APP_GROUPS.map((g) => (
                <label key={g.id} data-testid={`booster-group-${g.id}`}
                  className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none">
                  <input type="checkbox" checked={!!boostGroups[g.id]} onChange={(e) => setBoostGroups((s) => ({ ...s, [g.id]: e.target.checked }))}
                    className="accent-[#00E0FF] w-4 h-4" />
                  <span>{t(`grp.${g.id}`)}</span>
                </label>
              ))}
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
                <div key={i} className="flex items-center justify-between text-xs bg-black/40 border border-[#1A1A24] px-3 py-1.5" data-testid={`booster-session-${i}`}>
                  <span className="text-zinc-200 font-semibold">{s.game}</span>
                  <span className="text-zinc-500">{Math.round((s.duration_s || 0) / 60)} {t("games.booster_min")} · {(s.actions || []).length} {t("games.booster_actions")}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      )}

      {/* Pre-match (MANUAL) */}
      {(boostMode === "manual" || !boostMode) && (
      <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-5 mb-5" data-testid="prematch-card">
        <div className="flex items-center gap-2 text-sm font-bold mb-1 text-[#E5FF00]"><Rocket size={16} /> {t("games.prematch_title")}</div>
        <p className="text-xs text-zinc-400 mb-3 leading-relaxed">{t("games.prematch_desc")}</p>
        <SecureRunBlock token={token} mode="prematch" testid="prematch-run-cmd" />

        <button onClick={() => setShowConfig((v) => !v)} data-testid="prematch-config-toggle"
          className="mt-3 inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-[#E5FF00] transition-colors">
          <Settings2 size={13} /> {showConfig ? t("games.hide_customize") : t("games.customize")}
        </button>

        {showConfig && (
          <div className="mt-3 bg-black/50 border border-[#2A2A35] p-4" data-testid="prematch-config">
            {runningApps.length > 0 ? (
              <div className="text-xs text-[#00FF66] mb-3 flex items-center gap-1.5" data-testid="running-summary">
                <span className="w-2 h-2 rounded-full bg-[#00FF66] animate-pulse" /> {t("games.running_summary", { count: runningApps.length })}{runningAt ? ` · ${t("games.last_sync")} ${new Date(runningAt).toLocaleString(undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}` : ""}
              </div>
            ) : (
              <div className="text-xs text-zinc-500 mb-3">{t("games.run_hint")}</div>
            )}
            <div className="text-xs text-zinc-500 mb-2">{t("games.choose_close")}</div>
            <div className="grid sm:grid-cols-2 gap-2 mb-3">
              {APP_GROUPS.map((g) => {
                const run = g.procs.filter((p) => runningApps.includes(p));
                return (
                  <label key={g.id} data-testid={`prematch-group-${g.id}`}
                    className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none">
                    <input type="checkbox" checked={!!groups[g.id]} onChange={(e) => setGroups((s) => ({ ...s, [g.id]: e.target.checked }))}
                      className="accent-[#E5FF00] w-4 h-4" />
                    <span>{t(`grp.${g.id}`)}</span>
                    {run.length > 0 && (
                      <span title={run.join(", ")} data-testid={`running-badge-${g.id}`}
                        className="inline-flex items-center gap-1 text-[10px] font-bold text-[#00FF66] border border-[#00FF66]/40 bg-[#00FF66]/10 px-1.5 py-0.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#00FF66]" /> {run.length} {t("games.active")}
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none border-t border-[#2A2A35] pt-3" data-testid="prematch-power-toggle">
              <input type="checkbox" checked={setPower} onChange={(e) => setSetPower(e.target.checked)} className="accent-[#E5FF00] w-4 h-4" />
              {t("games.power_toggle")}
            </label>
            <button onClick={saveConfig} disabled={savingCfg} data-testid="prematch-save"
              className="mt-3 inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EC00] transition-colors disabled:opacity-60">
              {savingCfg ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} {t("games.save_settings")}
            </button>
          </div>
        )}
      </div>
      )}

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
                <button key={i} data-testid={`game-chip-${i}`} onClick={() => estimate(g)}
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
                  <div key={i} data-testid={`fps-bar-${i}`}>
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
            {recTpl.tweak_ids.map((id) => catalog.find((c) => c.id === id)?.name).filter(Boolean).slice(0, 8).map((n, i) => (
              <span key={i} className="text-[11px] bg-black border border-[#1A1A24] px-2 py-0.5 text-zinc-400">{n}</span>
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
