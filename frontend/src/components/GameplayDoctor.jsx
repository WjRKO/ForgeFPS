import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Stethoscope, Loader2, AlertTriangle, CheckCircle2, Wrench, Share2, ChevronDown, TrendingUp, TrendingDown } from "lucide-react";
import api from "@/lib/api";

const SEV = { high: "#FF3B30", medium: "#FF6B00", low: "#E5FF00" };
const HEALTH = { good: "text-[#00FF87]", minor: "text-[#E5FF00]", bad: "text-[#FF3B30]" };
const CONF = { high: "text-[#00FF87] border-[#00FF87]/40", medium: "text-[#E5FF00] border-[#E5FF00]/40", low: "text-zinc-400 border-zinc-600" };

function Timeline({ timeline, onEvent, t }) {
  const fps = (timeline?.fps || []).filter((p) => typeof p.fps === "number");
  if (fps.length < 10) return null;
  const W = 760, H = 90, P = 6;
  const maxM = Math.max(...fps.map((p) => p.m), 1);
  const maxF = Math.max(...fps.map((p) => p.fps), 1);
  const x = (m) => P + (m / maxM) * (W - 2 * P);
  const y = (f) => H - P - (f / maxF) * (H - 2 * P);
  const pts = fps.map((p) => `${x(p.m).toFixed(1)},${y(p.fps).toFixed(1)}`).join(" ");
  return (
    <div data-testid="gd-timeline">
      <div className="text-[11px] uppercase tracking-widest text-zinc-600 font-mono mb-1">{t("live.gd_timeline")} · FPS</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-24 bg-black/40 border border-[#1A1A24]">
        <polyline points={pts} fill="none" stroke="#E5FF00" strokeWidth="1.5" opacity="0.85" />
        {(timeline?.events || []).map((e, i) => (
          <circle key={i} cx={x(e.m)} cy={H - 12} r="4.5" fill={e.type === "hitch" ? "#FF3B30" : "#FF6B00"}
            className="cursor-pointer" data-testid={`gd-marker-${i}`}
            onClick={() => onEvent(e)}>
            <title>{`${e.type} @ ${e.m.toFixed(1)} min — ${e.cause}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

function Issue({ issue, t, expanded, onToggle, onApply }) {
  const sev = SEV[issue.severity] || SEV.low;
  const alts = issue.fix?.alternatives || [];
  return (
    <div className="border bg-black/50" style={{ borderColor: sev + "55" }} data-testid={`gd-issue-${issue.id || issue.type}`}>
      <button onClick={onToggle} className="w-full text-left p-4 pb-3" data-testid={`gd-issue-toggle-${issue.id || issue.type}`}>
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-2 font-bold text-sm text-zinc-100">
            <AlertTriangle size={14} style={{ color: sev }} /> {issue.title}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {typeof issue.impact_pct === "number" && (
              <span className="text-[11px] font-mono text-zinc-500">{issue.impact_pct}% {t("live.gd_of_session")}</span>
            )}
            <span className={`text-[11px] uppercase tracking-widest border px-1.5 py-0.5 ${CONF[issue.confidence] || CONF.medium}`} data-testid="gd-confidence">
              {t("live.gd_conf")} {issue.confidence}
            </span>
            <ChevronDown size={14} className={`text-zinc-500 transition-transform ${expanded ? "rotate-180" : ""}`} />
          </div>
        </div>
        <p className="text-xs text-zinc-300">{issue.simple_text}</p>
        {issue.pattern && issue.occurrences ? (
          <p className="text-[11px] font-mono text-zinc-600 mt-1">{issue.occurrences}x · pattern: {issue.pattern}</p>
        ) : null}
      </button>
      {expanded && (
        <div className="px-4 pb-3 space-y-1.5 border-t border-[#1A1A24] pt-2" data-testid="gd-tech-detail">
          <p className="text-xs text-zinc-500"><span className="text-zinc-400 font-semibold">{t("live.gd_evidence")}:</span> {issue.evidence}</p>
          <p className="text-xs text-zinc-500"><span className="text-zinc-400 font-semibold">{t("live.gd_diagnosis")}:</span> {issue.diagnosis}</p>
          {issue.tech_detail && <p className="text-xs text-zinc-600 font-mono">{issue.tech_detail}</p>}
          {alts.length > 0 && (
            <details className="text-xs text-zinc-500">
              <summary className="cursor-pointer text-zinc-400">{t("live.gd_alt_fixes")} ({alts.length})</summary>
              <ul className="mt-1 space-y-1 list-disc pl-4">
                {alts.map((a, i) => <li key={i}>{a.text}{a.gui_tweak ? ` [${a.gui_tweak}]` : ""}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
      <div className="px-4 pb-4 flex items-center gap-2 flex-wrap">
        {issue.fix?.primary?.text && (
          <span className="text-xs text-zinc-300 flex-1 min-w-[200px]">→ {issue.fix.primary.text}</span>
        )}
        {issue.fix?.primary?.gui_tweak && (
          <button onClick={() => onApply(issue.fix.primary.gui_tweak)} data-testid={`gd-apply-${issue.id || issue.type}`}
            className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest bg-[#E5FF00] text-black px-3 py-1.5 hover:bg-[#c9e000] transition-colors">
            <Wrench size={11} /> {t("live.gd_apply_gui")}: {issue.fix.primary.gui_tweak}
          </button>
        )}
        {issue.fix?.impact_estimate && (
          <span className="text-[11px] text-[#00FF87]/70 font-mono">{issue.fix.impact_estimate}</span>
        )}
      </div>
    </div>
  );
}

export default function GameplayDoctor() {
  const { t, i18n } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [doc, setDoc] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const shareRef = useRef(null);

  useEffect(() => {
    api.get("/advisor/gameplay-doctor/latest").then((r) => setDoc(r.data?.report || null)).catch(() => {});
  }, []);

  const analyze = async () => {
    setBusy(true);
    try {
      const r = await api.post("/advisor/gameplay-doctor", { lang: i18n.language || "it" });
      setDoc(r.data);
      toast.success(t("live.gd_done"));
    } catch (e) {
      const msg = e?.response?.data?.detail;
      toast.error(typeof msg === "string" ? msg : t("live.gd_err"));
    } finally {
      setBusy(false);
    }
  };

  const openGui = async () => {
    try {
      const r = await api.get("/agent/launch-uri", { params: { mode: "optimize", silent: 0 } });
      if (r.data?.uri) window.location.href = r.data.uri;
    } catch {
      toast.error(t("live.gd_err"));
    }
  };

  const share = async () => {
    if (!shareRef.current) return;
    setSharing(true);
    try {
      const { toPng } = await import("html-to-image");
      const dataUrl = await toPng(shareRef.current, { pixelRatio: 2, backgroundColor: "#0A0A0C", cacheBust: true });
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], "frameforge-gameplay-doctor.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "FrameForge — Gameplay Doctor", text: t("live.gd_share_text") });
      } else {
        const a = document.createElement("a");
        a.href = dataUrl; a.download = "frameforge-gameplay-doctor.png"; a.click();
      }
      toast.success(t("live.session_shared"));
    } catch {
      toast.error(t("live.save_err"));
    } finally {
      setSharing(false);
    }
  };

  const rep = doc?.report;
  const stats = doc?.stats;
  const ex = rep?.executive_summary;
  const topIssue = (rep?.issues || [])[0];
  const onEventClick = (e) => {
    const idx = (rep?.issues || []).findIndex((i) => i.id === e.cause);
    if (idx >= 0) setExpanded(rep.issues[idx].id || rep.issues[idx].type);
  };
  const deltaBadge = (v, invert = false) => {
    if (typeof v !== "number") return null;
    const good = invert ? v < 0 : v > 0;
    return (
      <span className={`inline-flex items-center gap-0.5 font-mono ${good ? "text-[#00FF87]" : "text-[#FF3B30]"}`}>
        {good ? <TrendingUp size={10} /> : <TrendingDown size={10} />}{v > 0 ? "+" : ""}{v}%
      </span>
    );
  };

  return (
    <div className="border border-[#1A1A24] bg-[#0E0E12]" data-testid="gameplay-doctor">
      <div className="flex items-center justify-between gap-3 p-4 border-b border-[#1A1A24]">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-[#E5FF00] font-mono">// Gameplay Doctor</div>
          <div className="text-sm font-bold text-zinc-100 mt-0.5 flex items-center gap-2">
            <Stethoscope size={15} className="text-[#E5FF00]" /> {t("live.gd_title")}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {rep && !busy && (
            <button onClick={share} disabled={sharing} data-testid="gd-share-btn" title={t("live.gd_share")}
              className="flex items-center gap-2 border border-[#2A2A35] text-zinc-300 font-bold text-xs uppercase tracking-widest px-3 py-2.5 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors disabled:opacity-60">
              {sharing ? <Loader2 size={13} className="animate-spin" /> : <Share2 size={13} />}
              <span className="hidden sm:inline">{t("live.gd_share")}</span>
            </button>
          )}
          <button onClick={analyze} disabled={busy} data-testid="gd-analyze-btn"
            className="flex items-center gap-2 bg-[#E5FF00] text-black font-bold text-xs uppercase tracking-widest px-4 py-2.5 hover:bg-[#c9e000] transition-colors disabled:opacity-60">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Stethoscope size={13} />}
            {busy ? t("live.gd_loading") : t("live.gd_btn")}
          </button>
        </div>
      </div>
      <div className="p-4 space-y-4">
        {!rep && !busy && <p className="text-xs text-zinc-500" data-testid="gd-empty">{t("live.gd_none")}</p>}
        {busy && <p className="text-xs text-zinc-500 animate-pulse">{t("live.gd_loading_hint")}</p>}
        {rep && !busy && (
          <>
            {/* Executive summary */}
            <div className="flex items-start gap-4 border border-[#1A1A24] bg-black/40 p-4" data-testid="gd-exec-summary">
              {typeof rep.score === "number" && (
                <div className="text-center shrink-0" data-testid="gd-score">
                  <div className={`font-display font-black text-4xl leading-none ${HEALTH[rep.health] || "text-zinc-100"}`}>{rep.score}</div>
                  <div className="text-[11px] uppercase tracking-widest text-zinc-600 mt-1">{t("live.gd_score")}</div>
                </div>
              )}
              <div className="flex-1 space-y-1 text-sm">
                {ex?.main_problem && <p className="text-zinc-200"><span className="text-zinc-500 text-xs uppercase tracking-wider">{t("live.gd_main_problem")}: </span>{ex.main_problem}</p>}
                {ex?.main_fix && <p className="text-zinc-200"><span className="text-zinc-500 text-xs uppercase tracking-wider">{t("live.gd_main_fix")}: </span>{ex.main_fix}</p>}
                {!ex && <p className="text-zinc-300">{rep.verdict}</p>}
                {stats && (
                  <p className="text-[11px] text-zinc-600 font-mono pt-1">
                    {stats.game ? `${stats.game} · ` : ""}{stats.duration_min != null ? `${stats.duration_min} min · ` : ""}
                    {stats.fps_avg != null ? `${stats.fps_avg} FPS avg · ` : ""}
                    {stats.fps_1pct_low != null ? `1% low ${stats.fps_1pct_low}${stats.exact_percentiles ? "" : "~"} · ` : ""}
                    {stats.fps_01pct_low != null ? `0.1% low ${stats.fps_01pct_low} · ` : ""}
                    {stats.hitch_total != null ? `${stats.hitch_total} hitch` : ""}
                  </p>
                )}
              </div>
            </div>

            {/* Badge risolti + baseline */}
            {(doc.resolved || []).length > 0 && (
              <div className="flex items-center gap-2 flex-wrap" data-testid="gd-resolved">
                {doc.resolved.map((r) => (
                  <span key={r} className="inline-flex items-center gap-1 text-[11px] text-[#00FF87] border border-[#00FF87]/30 px-2 py-1">
                    <CheckCircle2 size={11} /> {t("live.gd_resolved")}: {r}
                  </span>
                ))}
              </div>
            )}
            {doc.baseline && (
              <div className="text-[11px] text-zinc-500 font-mono flex items-center gap-3 flex-wrap" data-testid="gd-baseline">
                <span className="text-zinc-600 uppercase tracking-wider">{t("live.gd_vs_baseline")} ({doc.baseline.sessions} sess.):</span>
                {doc.baseline.fps_avg_delta_pct != null && <span>FPS avg {deltaBadge(doc.baseline.fps_avg_delta_pct)}</span>}
                {doc.baseline.fps_1low_delta_pct != null && <span>1% low {deltaBadge(doc.baseline.fps_1low_delta_pct)}</span>}
                {doc.baseline.hitch_delta_pct != null && <span>hitch {deltaBadge(doc.baseline.hitch_delta_pct, true)}</span>}
                {rep.comparison && <span className="text-zinc-500 basis-full">{rep.comparison}</span>}
              </div>
            )}

            <Timeline timeline={doc.timeline} onEvent={onEventClick} t={t} />

            {(rep.issues || []).length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-[#00FF87]" data-testid="gd-clean">
                <CheckCircle2 size={15} /> {t("live.gd_clean")}
              </div>
            ) : (
              <div className="space-y-2" data-testid="gd-report">
                {rep.issues.map((it, i) => (
                  <Issue key={i} issue={it} t={t}
                    expanded={expanded === (it.id || it.type)}
                    onToggle={() => setExpanded(expanded === (it.id || it.type) ? null : (it.id || it.type))}
                    onApply={openGui} />
                ))}
              </div>
            )}
            {rep.positive && <p className="text-xs text-[#00FF87]/80">✓ {rep.positive}</p>}

            {/* Card compatta per condivisione (off-screen, esportata dal bottone Share) */}
            <div className="fixed -left-[2000px] top-0 w-[600px] p-8 bg-[#0A0A0C]" ref={shareRef} aria-hidden="true">
              <div className="text-[11px] uppercase tracking-[0.3em] text-[#E5FF00] font-mono mb-4">// GAMEPLAY DOCTOR</div>
              <div className="flex items-center gap-6 mb-5">
                <div className={`font-display font-black text-7xl leading-none ${HEALTH[rep.health] || "text-zinc-100"}`}>{rep.score}</div>
                <div>
                  <div className="text-zinc-100 font-bold text-xl">{stats?.game || "PC Gaming"}</div>
                  <div className="text-zinc-500 text-sm font-mono">
                    {stats?.fps_avg != null ? `${stats.fps_avg} FPS avg` : ""}{stats?.fps_1pct_low != null ? ` · 1% low ${stats.fps_1pct_low}` : ""}
                  </div>
                </div>
              </div>
              {topIssue ? (
                <div className="border-l-2 pl-3 mb-2" style={{ borderColor: SEV[topIssue.severity] || SEV.low }}>
                  <div className="text-zinc-200 text-sm font-bold">{topIssue.title}</div>
                  <div className="text-zinc-500 text-xs">{topIssue.simple_text}</div>
                </div>
              ) : (
                <div className="text-[#00FF87] text-sm mb-2">✓ {t("live.gd_clean")}</div>
              )}
              {ex?.main_fix && <div className="text-zinc-400 text-xs mb-5">→ {ex.main_fix}</div>}
              <div className="flex items-center justify-between pt-3 border-t border-[#1A1A24]">
                <span className="text-[11px] font-mono uppercase tracking-[0.25em] text-zinc-500">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
                <span className="text-[11px] font-mono text-zinc-600">forgefps.dev</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
