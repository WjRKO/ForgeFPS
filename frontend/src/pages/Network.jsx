import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Gauge, Wifi, Activity, ArrowDownToLine, ArrowUpToLine, Waves, AlertTriangle, ShieldCheck } from "lucide-react";
import api from "@/lib/api";
import { PageHeader, SkeletonCard } from "@/components/hud";
import { SecureRunBlock } from "@/components/SecureRunBlock";

const GRADE_COLOR = {
  "A+": "#00FF66", "A": "#00FF66", "B": "#E5FF00", "C": "#FF9500", "D": "#FF6B00", "F": "#FF3B30",
};
const gradeColor = (g) => GRADE_COLOR[g] || "#6B7280";

function Metric({ icon: Icon, label, value, unit, sub, accent, testid }) {
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-4" data-testid={testid}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-zinc-500 mb-2"><Icon size={14} className={accent} /> {label}</div>
      <div className="font-display font-black text-2xl">{value ?? "--"}<span className="text-sm text-zinc-500 ml-1">{value != null ? unit : ""}</span></div>
      {sub && <div className="text-[11px] text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function Network() {
  const { t } = useTranslation();
  const [token, setToken] = useState("");
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(true);
  const timer = useRef(null);

  useEffect(() => {
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
    const load = async () => {
      try { const { data } = await api.get("/net-result"); setRes(data.available ? data.result : null); } catch {}
      setLoading(false);
    };
    load();
    timer.current = setInterval(load, 5000);
    return () => clearInterval(timer.current);
  }, []);

  const grade = res?.grade;
  const gc = gradeColor(grade);
  const tips = [];
  if (res) {
    if (["B", "C", "D", "F"].includes(grade)) {
      tips.push(t("network.tip_sqm"), t("network.tip_ethernet"), t("network.tip_uploads"), t("network.tip_qos"));
    }
    if (res.base_quality === "fair" || res.base_quality === "poor") tips.push(t("network.tip_server"));
    if ((res.loss_pct || 0) > 1) tips.push(t("network.tip_loss"));
    if (tips.length === 0) tips.push(t("network.tip_great"));
  }

  return (
    <div data-testid="network-page">
      <PageHeader eyebrow="// NETWORK" title={t("network.title")} subtitle={t("network.subtitle")} />

      {/* Run test */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 mb-6" data-testid="network-run">
        <div className="flex items-center gap-2 text-sm font-bold mb-1"><Waves size={16} className="text-[#00E0FF]" /> {t("network.run_title")}</div>
        <p className="text-xs text-zinc-400 mb-3">{t("network.run_desc")}</p>
        <SecureRunBlock token={token} mode="bufferbloat" testid="network-run-cmd" />
        <p className="text-[11px] text-zinc-500 mt-2">{t("network.run_hint")}</p>
      </div>

      {loading ? (
        <SkeletonCard className="h-48" />
      ) : !res ? (
        <div className="bg-[#0F0F12] border border-dashed border-[#2A2A35] p-8 text-center text-zinc-500" data-testid="network-empty">
          <Activity size={28} className="mx-auto mb-3 text-zinc-600" />
          {t("network.empty")}
        </div>
      ) : (
        <>
          {/* Grade */}
          <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6 flex items-center gap-6 flex-wrap" data-testid="network-grade">
            <div className="flex flex-col items-center justify-center w-32 h-32 border-2" style={{ borderColor: gc }}>
              <div className="text-[10px] uppercase tracking-widest text-zinc-500">{t("network.grade")}</div>
              <div className="font-display font-black text-6xl leading-none" style={{ color: gc }} data-testid="network-grade-value">{grade || "?"}</div>
            </div>
            <div className="flex-1 min-w-[200px]">
              <div className="text-sm text-zinc-300 mb-1">{t("network.bloat_label")}</div>
              <div className="font-display font-black text-3xl mb-2">+{res.bufferbloat_ms ?? "--"}<span className="text-base text-zinc-500 ml-1">ms</span></div>
              <p className="text-xs text-zinc-500">{t("network.bloat_desc")}</p>
            </div>
          </div>

          {/* Metrics */}
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <Metric icon={Activity} label={t("network.idle")} value={res.idle_ms} unit="ms" sub={`${t(`network.q_${res.base_quality}`)}${res.idle_min != null ? ` · min ${res.idle_min}ms` : ""}`} accent="text-[#00FF66]" testid="net-idle" />
            <Metric icon={ArrowDownToLine} label={t("network.down_loaded")} value={res.down_ms} unit="ms" sub={`${res.down_grade ? `${t("network.grade")} ${res.down_grade}` : ""}${res.down_p95 != null ? ` · p95 ${res.down_p95}ms` : ""}`} accent="text-[#00E0FF]" testid="net-down" />
            <Metric icon={ArrowUpToLine} label={t("network.up_loaded")} value={res.up_ms} unit="ms" sub={`${res.up_grade ? `${t("network.grade")} ${res.up_grade}` : ""}${res.up_p95 != null ? ` · p95 ${res.up_p95}ms` : ""}`} accent="text-[#E5FF00]" testid="net-up" />
            <Metric icon={Wifi} label={t("network.jitter")} value={res.jitter_ms} unit="ms" sub={`${t("network.loss")}: ${res.loss_pct ?? 0}%`} accent="text-[#B388FF]" testid="net-jitter" />
          </div>

          {/* Recommendations */}
          <div className="bg-[#0F0F12] border border-[#2A2A35] p-5" data-testid="network-tips">
            <div className="flex items-center gap-2 text-sm font-bold mb-3">
              {["A+", "A"].includes(grade) ? <ShieldCheck size={16} className="text-[#00FF66]" /> : <AlertTriangle size={16} className="text-[#FF9500]" />}
              {t("network.tips_title")}
            </div>
            <ul className="space-y-2">
              {tips.map((tip, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-zinc-300" data-testid={`net-tip-${i}`}>
                  <span className="text-[#00E0FF] mt-0.5">→</span> {tip}
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
