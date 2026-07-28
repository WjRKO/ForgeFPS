import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Stethoscope, Loader2, AlertTriangle, CheckCircle2, Wrench } from "lucide-react";
import api from "@/lib/api";

const SEV = {
  high: "border-[#FF3B30]/40 text-[#FF3B30]",
  medium: "border-[#FF6B00]/40 text-[#FF6B00]",
  low: "border-[#E5FF00]/30 text-[#E5FF00]",
};
const HEALTH = {
  good: "text-[#00FF87]",
  minor: "text-[#E5FF00]",
  bad: "text-[#FF3B30]",
};

function Issue({ issue, t }) {
  const sev = SEV[issue.severity] || SEV.low;
  return (
    <div className={`border ${sev.split(" ")[0]} bg-black/50 p-4`} data-testid={`gd-issue-${issue.type}`}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 font-bold text-sm text-zinc-100">
          <AlertTriangle size={14} className={sev.split(" ")[1]} /> {issue.title}
        </div>
        <span className={`text-[10px] uppercase tracking-widest border px-2 py-0.5 ${sev}`}>{issue.severity}</span>
      </div>
      <p className="text-xs text-zinc-500 mb-1"><span className="text-zinc-400 font-semibold">{t("live.gd_evidence")}:</span> {issue.evidence}</p>
      <p className="text-xs text-zinc-500 mb-2"><span className="text-zinc-400 font-semibold">{t("live.gd_cause")}:</span> {issue.cause}</p>
      <p className="text-xs text-zinc-300">{issue.fix}</p>
      {issue.gui_tweak && (
        <div className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-[#E5FF00] border border-[#E5FF00]/30 px-2 py-1" data-testid="gd-tweak-badge">
          <Wrench size={11} /> {t("live.gd_tweak_available")}: <span className="font-mono">{issue.gui_tweak}</span>
        </div>
      )}
    </div>
  );
}

export default function GameplayDoctor() {
  const { t, i18n } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [doc, setDoc] = useState(null);

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
      const msg = e?.response?.data?.detail || t("live.gd_err");
      toast.error(typeof msg === "string" ? msg : t("live.gd_err"));
    } finally {
      setBusy(false);
    }
  };

  const rep = doc?.report;
  const stats = doc?.stats;

  return (
    <div className="border border-[#1A1A24] bg-[#0E0E12]" data-testid="gameplay-doctor">
      <div className="flex items-center justify-between gap-3 p-4 border-b border-[#1A1A24]">
        <div>
          <div className="text-[10px] uppercase tracking-[0.25em] text-[#E5FF00] font-mono">// Gameplay Doctor</div>
          <div className="text-sm font-bold text-zinc-100 mt-0.5 flex items-center gap-2">
            <Stethoscope size={15} className="text-[#E5FF00]" /> {t("live.gd_title")}
          </div>
        </div>
        <button
          onClick={analyze}
          disabled={busy}
          data-testid="gd-analyze-btn"
          className="flex items-center gap-2 bg-[#E5FF00] text-black font-bold text-xs uppercase tracking-widest px-4 py-2.5 hover:bg-[#c9e000] transition-colors disabled:opacity-60"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Stethoscope size={13} />}
          {busy ? t("live.gd_loading") : t("live.gd_btn")}
        </button>
      </div>
      <div className="p-4">
        {!rep && !busy && <p className="text-xs text-zinc-500" data-testid="gd-empty">{t("live.gd_none")}</p>}
        {busy && <p className="text-xs text-zinc-500 animate-pulse">{t("live.gd_loading_hint")}</p>}
        {rep && !busy && (
          <div className="space-y-3" data-testid="gd-report">
            <div className="flex items-start justify-between gap-4">
              <p className="text-sm text-zinc-300 flex-1">{rep.verdict}</p>
              {typeof rep.score === "number" && (
                <div className="text-center shrink-0" data-testid="gd-score">
                  <div className={`font-display font-black text-3xl leading-none ${HEALTH[rep.health] || "text-zinc-100"}`}>{rep.score}</div>
                  <div className="text-[9px] uppercase tracking-widest text-zinc-600 mt-1">{t("live.gd_score")}</div>
                </div>
              )}
            </div>
            {stats && (
              <div className="text-[11px] text-zinc-600 font-mono">
                {stats.game ? `${stats.game} · ` : ""}{stats.duration_min != null ? `${stats.duration_min} min · ` : ""}
                {stats.fps_avg != null ? `${stats.fps_avg} FPS avg · ` : ""}
                {stats.fps_1pct_low != null ? `1% low ${stats.fps_1pct_low} · ` : ""}
                {stats.hitch_total != null ? `${stats.hitch_total} hitch` : ""}
              </div>
            )}
            {(rep.issues || []).length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-[#00FF87]" data-testid="gd-clean">
                <CheckCircle2 size={15} /> {t("live.gd_clean")}
              </div>
            ) : (
              <div className="space-y-2">{rep.issues.map((it, i) => <Issue key={i} issue={it} t={t} />)}</div>
            )}
            {rep.positive && <p className="text-xs text-[#00FF87]/80">✓ {rep.positive}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
