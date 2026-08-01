import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { Gauge, Wifi, Activity, ArrowDownToLine, ArrowUpToLine, Waves, AlertTriangle, ShieldCheck } from "lucide-react";
import api from "@/lib/api";
import { PageHeader, SkeletonCard } from "@/components/hud";
import { SecureRunBlock } from "@/components/SecureRunBlock";
import OneClickLaunchButton from "@/components/OneClickLaunchButton";
import PlanUpgradeBanner from "@/components/PlanUpgradeBanner";
import TechTerm from "@/components/TechTerm";
import { MissionContextStrip } from "@/components/MissionContextStrip";

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

function SubGrade({ label, grade, value, unit, unitPrefix = "", hint, colorFn, testid }) {
  const c = colorFn(grade);
  return (
    <div className="flex items-center gap-3 bg-black/40 border-l-4 border border-[#2A2A35] px-4 py-3 flex-1 min-w-[170px]" style={{ borderLeftColor: c }} data-testid={testid}>
      <div className="font-display font-black text-4xl leading-none" style={{ color: c }} data-testid={`${testid}-grade`}>{grade || "?"}</div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono">{label}</div>
        <div className="text-sm text-zinc-200 font-semibold" data-testid={`${testid}-value`}>
          {value != null ? `${unitPrefix}${value}` : "--"}<span className="text-zinc-500 text-xs ml-0.5">{value != null ? unit : ""}</span>
        </div>
        {hint && <div className="text-[10px] text-zinc-600 truncate">{hint}</div>}
      </div>
    </div>
  );
}

function buildLoadedSub(g, p95, p99, t) {
  const parts = [];
  if (g) parts.push(`${t("network.grade")} ${g}`);
  if (p95 != null) parts.push(`p95 ${p95}ms`);
  if (p99 != null) parts.push(`p99 ${p99}ms`);
  return parts.join(" · ");
}

export default function Network() {
  const { t } = useTranslation();
  const [token, setToken] = useState("");
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const timer = useRef(null);
  const launchTs = useRef(null);

  useEffect(() => {
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
    const load = async () => {
      try {
        const { data } = await api.get("/net-result");
        setRes(data.available ? data.result : null);
      } catch (e) {
        if (e?.response?.status === 402) { setLocked(true); clearInterval(timer.current); }
        else console.error("load net-result failed", e);
      }
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

  if (locked) {
    return (
      <div data-testid="network-page">
        <PageHeader eyebrow="// NETWORK" title={t("network.title")} subtitle={t("network.subtitle")} />
        <PlanUpgradeBanner tier="pro" compact title={t("plan_banner.advtweaks.title")}
          description={t("plan_banner.advtweaks.desc")} testid="network-locked" />
      </div>
    );
  }

  return (
    <div data-testid="network-page">
      <PageHeader eyebrow="// NETWORK" title={t("network.title")} subtitle={t("network.subtitle")} />

      <MissionContextStrip metrics={["net_tests"]} />

      {/* Run test */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 mb-6" data-testid="network-run">
        <div className="flex items-center gap-2 text-sm font-bold mb-1"><Waves size={16} className="text-[#00E0FF]" /> {t("network.run_title")}</div>
        <p className="text-xs text-zinc-400 mb-3">{t("network.run_desc")}</p>

        {/* Bottone one-click (usa protocollo frameforge:// via agent installato) */}
        <div className="mb-4">
          <OneClickLaunchButton
            mode="bufferbloat"
            label={i18n.language?.startsWith("en") ? "Run bufferbloat test" : "Avvia test bufferbloat"}
            timeoutMs={90000}
            onLaunch={(ts) => { launchTs.current = ts; }}
            detectDone={async () => {
              try {
                const { data } = await api.get("/net-result");
                if (!data?.available) return false;
                const newTs = data.updated_at;
                if (!newTs) return false;
                if (!launchTs.current) return false;
                return new Date(newTs).getTime() > launchTs.current;
              } catch { return false; }
            }}
            onDone={() => {
              // Ricarica il risultato per popolare la UI
              api.get("/net-result").then(({ data }) => setRes(data.available ? data.result : null)).catch(() => {});
            }}
            testid="network-oneclick"
          />
          <p className="text-[10px] text-zinc-600 mt-2 font-mono uppercase tracking-widest">
            richiede FrameForge Agent installato · <Link to="/app/desktop" className="text-[#00E0FF] hover:underline">scaricalo qui</Link>
          </p>
        </div>

        {/* Fallback manuale (copy-paste PowerShell) per chi non ha ancora l'agent */}
        <details className="border-t border-[#2A2A35] pt-3 mt-2">
          <summary className="text-[11px] text-zinc-500 cursor-pointer hover:text-zinc-300 font-mono uppercase tracking-widest" data-testid="network-manual-toggle">
            oppure esegui manualmente (senza installare l'agent)
          </summary>
          <div className="mt-3">
            <SecureRunBlock token={token} mode="bufferbloat" testid="network-run-cmd" />
          </div>
        </details>
        <p className="text-[11px] text-zinc-500 mt-2">{t("network.run_hint")}</p>
      </div>

      {loading ? (
        <SkeletonCard className="h-48" />
      ) : !res ? (
        <div className="bg-[#0F0F12] border border-dashed border-[#2A2A35] p-8 text-center text-zinc-500" data-testid="network-empty">
          <Activity size={28} className="mx-auto mb-3 text-zinc-600" />
          <p className="mb-4">{t("network.empty")}</p>
          <div className="inline-flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-zinc-400 border-t border-[#1A1A24] pt-4 mt-2">
            <span className="text-[10px] uppercase tracking-widest text-zinc-600">{t("network.glossary_hint", { defaultValue: "Cosa misureremo" })}:</span>
            <TechTerm term="bufferbloat">Bufferbloat</TechTerm>
            <TechTerm term="ping">Ping</TechTerm>
            <TechTerm term="jitter">Jitter</TechTerm>
          </div>
        </div>
      ) : (
        <>
          {/* Grade — 3 sub-grade cards (Idle/Loaded/Consistency) */}
          <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="network-grade">
            <div className="flex flex-wrap items-stretch gap-3">
              <SubGrade
                label="Idle"
                grade={res.idle_grade || grade}
                value={res.idle_ms}
                unit="ms"
                hint="Latenza a riposo"
                colorFn={gradeColor}
                testid="subgrade-idle"
              />
              <SubGrade
                label="Loaded"
                grade={res.loaded_grade || grade}
                value={res.bufferbloat_ms}
                unit="ms"
                unitPrefix="+"
                hint="Bufferbloat sotto carico"
                colorFn={gradeColor}
                testid="subgrade-loaded"
              />
              <SubGrade
                label="Consistency"
                grade={res.consistency_grade || grade}
                value={res.consistency_score}
                unit="/100"
                hint="Jitter + Loss + tail p99"
                colorFn={gradeColor}
                testid="subgrade-consistency"
              />
              <div className="flex-1 min-w-[200px] flex flex-col justify-center bg-black/40 border border-[#2A2A35] p-4">
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1"><TechTerm term="bufferbloat">Bufferbloat</TechTerm> {t("network.bloat_label", { defaultValue: "aumento sotto carico" })}</div>
                <div className="font-display font-black text-2xl">+{res.bufferbloat_ms ?? "--"}<span className="text-sm text-zinc-500 ml-1">ms</span></div>
                {res.tail_spike_ms != null && (
                  <div className="text-[11px] text-zinc-500 mt-1" data-testid="tail-spike">
                    Tail spike (p99): <span className="text-[#FF9500] font-mono">+{res.tail_spike_ms} ms</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Metrics */}
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <Metric icon={Activity} label={t("network.idle")} value={res.idle_ms} unit="ms" sub={`${t(`network.q_${res.base_quality}`)}${res.idle_min != null ? ` · min ${res.idle_min}ms` : ""}`} accent="text-[#00FF66]" testid="net-idle" />
            <Metric icon={ArrowDownToLine} label={t("network.down_loaded")} value={res.down_ms} unit="ms" sub={buildLoadedSub(res.down_grade, res.down_p95, res.down_p99, t)} accent="text-[#00E0FF]" testid="net-down" />
            <Metric icon={ArrowUpToLine} label={t("network.up_loaded")} value={res.up_ms} unit="ms" sub={buildLoadedSub(res.up_grade, res.up_p95, res.up_p99, t)} accent="text-[#E5FF00]" testid="net-up" />
            <Metric icon={Wifi} label={<TechTerm term="jitter">{t("network.jitter")}</TechTerm>} value={res.jitter_ms} unit="ms" sub={`${t("network.loss")}: ${res.loss_pct ?? 0}%`} accent="text-[#B388FF]" testid="net-jitter" />
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
