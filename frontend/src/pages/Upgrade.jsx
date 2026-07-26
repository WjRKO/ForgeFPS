import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Rocket, Loader2, TrendingUp, Gauge, Cpu, LineChart as LineIcon, CheckCircle2, MonitorDown, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api, { formatApiErrorDetail } from "@/lib/api";
import { PageHeader } from "@/components/hud";

const RES = ["1080p", "1440p", "4K"];
const PRIO = { alta: "bg-[#FF3B30]/20 text-[#FF3B30]", media: "bg-[#E5FF00]/20 text-[#E5FF00]", bassa: "bg-[#00FF66]/20 text-[#00FF66]" };

const sv = (v) => (typeof v === "string" ? v : typeof v === "number" ? String(v) : v?.name || "");

export default function Upgrade() {
  const { t } = useTranslation();
  const [hasSpecs, setHasSpecs] = useState(null);
  const [specs, setSpecs] = useState(null);
  const [games, setGames] = useState([]);
  const [budget, setBudget] = useState(600);
  const [goal, setGoal] = useState(t("upgrade.goal_default"));
  const [loading, setLoading] = useState(false);
  const [upg, setUpg] = useState(null);
  const [tracking, setTracking] = useState(false);
  const [err, setErr] = useState("");

  const [game, setGame] = useState("");
  const [res, setRes] = useState("1440p");
  const [fpsLoading, setFpsLoading] = useState(false);
  const [fps, setFps] = useState(null);
  const [fpsErr, setFpsErr] = useState("");

  const [ba, setBa] = useState(null);
  const [baLoading, setBaLoading] = useState(false);
  const [baErr, setBaErr] = useState("");

  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => {
      setSpecs(data?.data || null);
      setHasSpecs(!!data?.data?.cpu);
    }).catch(() => setHasSpecs(false));
    api.get("/games").then(({ data }) => setGames((data?.games || []).map(sv).filter(Boolean))).catch(() => {});
  }, []);

  const analyze = async () => {
    setLoading(true); setErr(""); setUpg(null); setBa(null); setBaErr("");
    try { const { data } = await api.post("/upgrade/analyze", { budget, goal }); setUpg(data); }
    catch (e) { setErr(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  const trackParts = async () => {
    if (!upg) return;
    setTracking(true);
    try {
      const { data } = await api.post("/upgrade/track", { group: `Upgrade: ${upg.bottleneck}`, components: upg.recommendations });
      toast.success(t("upgrade.toast_tracked", { count: data.tracked }));
    } catch { toast.error(t("upgrade.toast_err")); } finally { setTracking(false); }
  };

  const estimate = async () => {
    if (!game.trim()) return;
    setFpsLoading(true); setFpsErr(""); setFps(null);
    try { const { data } = await api.post("/fps/estimate", { game, resolution: res }); setFps(data); }
    catch (e) { setFpsErr(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setFpsLoading(false); }
  };

  const compareBA = async () => {
    if (!game.trim() || !upg || baLoading) return;
    setBaLoading(true); setBaErr(""); setBa(null);
    try {
      const ups = (upg.recommendations || []).map((r) => `${r.category}: ${r.suggested}`);
      const { data } = await api.post("/fps/upgrade-compare", { game, resolution: res, upgrades: ups });
      setBa(data);
    } catch (e) { setBaErr(formatApiErrorDetail(e.response?.data?.detail) || t("upgrade.ba_err")); }
    finally { setBaLoading(false); }
  };

  const maxFps = fps ? Math.max(...fps.estimates.map((e) => e.fps), 1) : 1;
  const baMax = ba ? Math.max(...ba.estimates.flatMap((e) => [e.before || 0, e.after || 0]), 1) : 1;

  const GameChips = ({ testPrefix }) => games.length > 0 && (
    <div className="mb-4">
      <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-1.5">{t("upgrade.games_quick")}</div>
      <div className="flex flex-wrap gap-1.5">
        {games.slice(0, 10).map((g) => (
          <button key={g} data-testid={`${testPrefix}-chip-${g}`} type="button" onClick={() => setGame(g)}
            className={`px-2.5 py-1 text-xs border transition-colors ${game === g ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/10" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-500"}`}>
            {g}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <PageHeader eyebrow={t("upgrade.eyebrow")} title={t("upgrade.title")} />

      {specs && (sv(specs.cpu) || sv(specs.gpu)) && (
        <div className="bg-[#0F0F12] border border-[#1A1A24] px-4 py-3 mb-4 flex flex-wrap items-center gap-x-6 gap-y-1.5" data-testid="hw-header">
          <span className="text-[10px] uppercase tracking-[0.2em] text-zinc-600">{t("upgrade.hw_title")}</span>
          {sv(specs.cpu) && <span className="flex items-center gap-1.5 font-mono text-xs text-zinc-300"><Cpu size={13} className="text-[#E5FF00]" />{sv(specs.cpu)}</span>}
          {sv(specs.gpu) && <span className="flex items-center gap-1.5 font-mono text-xs text-zinc-300"><Gauge size={13} className="text-[#00E0FF]" />{sv(specs.gpu)}</span>}
          {specs.ram != null && <span className="font-mono text-xs text-zinc-300">RAM {typeof specs.ram === "number" ? `${specs.ram} GB` : sv(specs.ram)}</span>}
        </div>
      )}

      {hasSpecs === false && (
        <div className="bg-[#0F0F12] border border-[#E5FF00]/40 p-4 mb-4 text-sm text-zinc-300 flex items-center gap-3">
          <MonitorDown size={18} className="text-[#E5FF00]" />
          {t("upgrade.no_specs_pre")} <Link to="/app/pc" className="text-[#E5FF00] hover:underline">{t("upgrade.mypc_link")}</Link> {t("upgrade.no_specs_post")}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        {/* UPGRADE */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4 flex items-center gap-2"><Rocket size={14} className="text-[#E5FF00]" /> {t("upgrade.advice_title")}</div>
          <div className="mb-4">
            <div className="flex justify-between text-xs uppercase tracking-widest text-zinc-500 mb-2"><span>{t("upgrade.budget")}</span><span className="text-[#E5FF00] font-bold">€{budget}</span></div>
            <input data-testid="upgrade-budget" type="range" min="100" max="3000" step="50" value={budget} onChange={(e) => setBudget(Number(e.target.value))} className="w-full accent-[#E5FF00]" />
          </div>
          <label className="text-xs uppercase tracking-widest text-zinc-500">{t("upgrade.goal")}</label>
          <input data-testid="upgrade-goal" value={goal} onChange={(e) => setGoal(e.target.value)}
            className="w-full bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 mt-1 mb-4 text-sm" />
          <button data-testid="analyze-upgrade-btn" onClick={analyze} disabled={loading || !hasSpecs}
            className="w-full flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors disabled:opacity-60 btn-volt">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <TrendingUp size={16} />} {t("upgrade.analyze")}
          </button>
          {!hasSpecs && <p className="text-xs text-zinc-500 mt-2">{t("upgrade.requires_specs")}</p>}
          {err && <div className="mt-3 text-xs text-[#FF3B30]">{err}</div>}

          {upg && (
            <div className="mt-5 fade-up">
              <div className="bg-black border border-[#2A2A35] p-4 mb-3">
                <div className="text-xs uppercase tracking-widest text-zinc-500">{t("upgrade.bottleneck")}</div>
                <div className="font-display font-bold text-lg text-[#FF3B30]">{upg.bottleneck}</div>
                <p className="text-sm text-zinc-400 mt-2">{upg.assessment}</p>
              </div>
              {upg.recommendations.map((r, i) => (
                <div key={`${r.category}-${i}`} className="border border-[#1A1A24] p-3 mb-2 row-hover" data-testid={`upg-rec-${i}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs uppercase tracking-widest text-[#E5FF00]">{r.category}</span>
                    <span className={`text-xs font-bold uppercase px-2 py-0.5 ${PRIO[r.priority] || "bg-zinc-700/30 text-zinc-400"}`}>{t(`upgrade.prio.${r.priority}`, r.priority)}</span>
                  </div>
                  <div className="text-sm text-zinc-100">{r.suggested} <span className="text-zinc-500">· €{r.price}</span></div>
                  <div className="text-xs text-zinc-500 mt-1">{r.reason}</div>
                  {r.expected_gain && <div className="text-xs text-[#00FF66] mt-1">▲ {r.expected_gain}</div>}
                </div>
              ))}
              {upg.keep?.length > 0 && (
                <div className="text-xs text-zinc-500 mt-2 flex items-start gap-2"><CheckCircle2 size={13} className="text-[#00FF66] mt-0.5" /> {t("upgrade.keep_ok")} {upg.keep.join(", ")}</div>
              )}
              <div className="flex items-center justify-between mt-4">
                <div className="font-display font-black text-lg">{t("upgrade.total")} <span className="text-[#E5FF00]">€{upg.estimated_total}</span></div>
                <button data-testid="track-upgrade-btn" onClick={trackParts} disabled={tracking}
                  className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] transition-colors disabled:opacity-60">
                  {tracking ? <Loader2 size={14} className="animate-spin" /> : <LineIcon size={14} />} {t("upgrade.track_parts")}
                </button>
              </div>

              {/* ===== Prima vs Dopo l'upgrade ===== */}
              <div className="mt-5 border-t border-[#1A1A24] pt-4" data-testid="before-after-block">
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1 flex items-center gap-2">
                  <Gauge size={13} className="text-[#00E0FF]" /> {t("upgrade.ba_title")}
                </div>
                <p className="text-xs text-zinc-600 mb-3">{t("upgrade.ba_hint")}</p>
                <div className="flex gap-2 mb-2">
                  <input data-testid="ba-game-input" value={game} onChange={(e) => setGame(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && compareBA()}
                    placeholder={t("upgrade.game_ph")}
                    className="flex-1 bg-black border border-[#2A2A35] focus:border-[#00E0FF] outline-none px-3 py-2 text-sm" />
                  <button data-testid="ba-compare-btn" onClick={compareBA} disabled={baLoading || !game.trim()}
                    className="flex items-center gap-2 border border-[#00E0FF]/60 text-[#00E0FF] px-4 py-2 text-xs font-bold uppercase tracking-widest hover:bg-[#00E0FF] hover:text-black transition-colors disabled:opacity-50">
                    {baLoading ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />} {t("upgrade.ba_btn")}
                  </button>
                </div>
                <GameChips testPrefix="ba" />
                {baErr && <div className="text-xs text-[#FF3B30]" data-testid="ba-error">{baErr}</div>}

                {ba && (
                  <div className="fade-up" data-testid="ba-result">
                    <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                      <div className="text-sm text-zinc-300">{ba.game} · {ba.resolution} <span className="text-xs text-zinc-500">({ba.upgrade_summary})</span></div>
                      {ba.gain_pct != null && (
                        <span className="bg-[#00FF66]/15 border border-[#00FF66]/50 text-[#00FF66] px-2.5 py-1 text-xs font-bold font-mono" data-testid="ba-gain">
                          +{ba.gain_pct}% {t("upgrade.ba_gain")}
                        </span>
                      )}
                    </div>
                    <div className="space-y-3">
                      {ba.estimates.map((e, i) => (
                        <div key={e.preset || i} data-testid={`ba-row-${i}`}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-zinc-400">{e.preset}</span>
                            <span className="font-mono tabular-nums">
                              <span className="text-zinc-500">{e.before}</span>
                              <span className="text-zinc-600"> → </span>
                              <span className="text-[#00FF66] font-bold">{e.after} FPS</span>
                            </span>
                          </div>
                          <div className="h-1.5 bg-black border border-[#1A1A24] mb-1">
                            <div className="h-full bg-zinc-600" style={{ width: `${((e.before || 0) / baMax) * 100}%` }} />
                          </div>
                          <div className="h-1.5 bg-black border border-[#1A1A24]">
                            <div className="h-full bg-[#00FF66]" style={{ width: `${((e.after || 0) / baMax) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-[10px] uppercase tracking-widest text-zinc-600">
                      <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-1.5 bg-zinc-600" /> {t("upgrade.ba_before")}</span>
                      <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-1.5 bg-[#00FF66]" /> {t("upgrade.ba_after")}</span>
                    </div>
                    {ba.notes && <p className="text-xs text-zinc-500 mt-3">{ba.notes}</p>}
                    <button data-testid="ba-track-btn" onClick={trackParts} disabled={tracking}
                      className="mt-4 w-full flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-2.5 text-sm hover:bg-[#D4EC00] transition-colors disabled:opacity-60 btn-volt">
                      {tracking ? <Loader2 size={14} className="animate-spin" /> : <LineIcon size={14} />} {t("upgrade.ba_track")}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* FPS */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 h-fit">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4 flex items-center gap-2"><Gauge size={14} className="text-[#E5FF00]" /> {t("upgrade.fps_title")}</div>
          <label className="text-xs uppercase tracking-widest text-zinc-500">{t("upgrade.game")}</label>
          <input data-testid="fps-game-input" value={game} onChange={(e) => setGame(e.target.value)} placeholder={t("upgrade.game_ph")}
            onKeyDown={(e) => e.key === "Enter" && estimate()}
            className="w-full bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 mt-1 mb-3 text-sm" />
          <GameChips testPrefix="fps" />
          <label className="text-xs uppercase tracking-widest text-zinc-500">{t("build.resolution")}</label>
          <div className="flex gap-2 mt-1 mb-4">
            {RES.map((r) => (
              <button key={r} data-testid={`fps-res-${r}`} onClick={() => setRes(r)}
                className={`flex-1 py-2 text-sm border transition-colors ${res === r ? "bg-[#E5FF00] text-black border-[#E5FF00] font-bold" : "border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>{r}</button>
            ))}
          </div>
          <button data-testid="estimate-fps-btn" onClick={estimate} disabled={fpsLoading}
            className="w-full flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors disabled:opacity-60 btn-volt">
            {fpsLoading ? <Loader2 size={16} className="animate-spin" /> : <Gauge size={16} />} {t("upgrade.estimate_fps")}
          </button>
          {fpsErr && <div className="mt-3 text-xs text-[#FF3B30]">{fpsErr}</div>}

          {fps && (
            <div className="mt-5 fade-up">
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
              <div className="mt-4 text-sm"><span className="text-zinc-500">{t("upgrade.recommended")} </span><span className="text-[#E5FF00] font-bold">{fps.recommended_preset}</span></div>
              <p className="text-xs text-zinc-500 mt-2">{fps.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
