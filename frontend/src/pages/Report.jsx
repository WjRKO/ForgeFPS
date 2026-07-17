import { useEffect, useRef, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { toPng } from "html-to-image";
import { toast } from "sonner";
import { Zap, HeartPulse, Gauge, Activity, Cpu, Share2, RotateCcw, Loader2, Camera, ArrowRight, TrendingUp, TrendingDown, Minus } from "lucide-react";
import api, { formatApiErrorDetail } from "@/lib/api";

const DICT = {
  it: {
    eyebrow: "// report cliente",
    title: "Report Prima / Dopo",
    sub: "Cattura lo stato del PC prima e dopo il boost, poi esporta un report brandizzato FrameForge da mostrare al cliente.",
    how: "Come funziona",
    step1: "Cattura PRIMA del boost",
    step1d: "Registra Health Score, bufferbloat, FPS medi e benchmark attuali.",
    step2: "Esegui l'ottimizzazione",
    step2d: "Applica i tweak dall'agent, esegui il test bufferbloat e una sessione di gioco.",
    step3: "Cattura DOPO",
    step3d: "Registra i nuovi valori: il report calcola i miglioramenti in automatico.",
    capture_before: "Cattura PRIMA",
    capture_after: "Cattura DOPO",
    reset: "Reset",
    export: "Esporta PNG",
    exported: "Report esportato!",
    captured: "Snapshot salvato",
    err: "Errore",
    report_title: "Report Ottimizzazione PC",
    before: "Prima",
    after: "Dopo",
    delta: "Variazione",
    health: "Health Score",
    bufferbloat: "Bufferbloat",
    fps: "FPS medi",
    bench: "Benchmark",
    no_data: "Nessun dato",
    tip_before: "Prima cattura il PRIMA, poi il DOPO.",
    footer: "frameforge · report performance per gamer & streamer",
    grade: "Voto",
    pts: "pt",
    improved: "migliorato",
    worse: "peggiorato",
    same: "invariato",
  },
  en: {
    eyebrow: "// client report",
    title: "Before / After Report",
    sub: "Capture the PC state before and after the boost, then export a FrameForge-branded report to show your client.",
    how: "How it works",
    step1: "Capture BEFORE the boost",
    step1d: "Record current Health Score, bufferbloat, average FPS and benchmark.",
    step2: "Run the optimization",
    step2d: "Apply the agent tweaks, run the bufferbloat test and a gaming session.",
    step3: "Capture AFTER",
    step3d: "Record the new values: the report computes the improvements automatically.",
    capture_before: "Capture BEFORE",
    capture_after: "Capture AFTER",
    reset: "Reset",
    export: "Export PNG",
    exported: "Report exported!",
    captured: "Snapshot saved",
    err: "Error",
    report_title: "PC Optimization Report",
    before: "Before",
    after: "After",
    delta: "Change",
    health: "Health Score",
    bufferbloat: "Bufferbloat",
    fps: "Avg FPS",
    bench: "Benchmark",
    no_data: "No data",
    tip_before: "Capture BEFORE first, then AFTER.",
    footer: "frameforge · performance reports for gamers & streamers",
    grade: "Grade",
    pts: "pt",
    improved: "improved",
    worse: "worse",
    same: "unchanged",
  },
};

// higherBetter: true => increase is good. For bufferbloat, lower is better.
const METRICS = [
  { key: "health_score", labelKey: "health", icon: HeartPulse, unit: "", accent: "text-[#00FF66]", higherBetter: true },
  { key: "bufferbloat_ms", labelKey: "bufferbloat", icon: Gauge, unit: "ms", accent: "text-[#00E0FF]", higherBetter: false },
  { key: "fps_avg", labelKey: "fps", icon: Zap, unit: "FPS", accent: "text-[#E5FF00]", higherBetter: true },
  { key: "bench_overall", labelKey: "bench", icon: Cpu, unit: "", accent: "text-[#B388FF]", higherBetter: true },
];

function DeltaBadge({ value, higherBetter, c }) {
  if (value == null) return <span className="text-zinc-600 text-sm">—</span>;
  if (value === 0) return <span className="inline-flex items-center gap-1 text-zinc-500 text-sm"><Minus size={13} /> {c.same}</span>;
  const good = higherBetter ? value > 0 : value < 0;
  const Icon = value > 0 ? TrendingUp : TrendingDown;
  const color = good ? "text-[#00FF66]" : "text-[#FF3B30]";
  const sign = value > 0 ? "+" : "";
  return (
    <span className={`inline-flex items-center gap-1 text-sm font-bold ${color}`}>
      <Icon size={14} /> {sign}{value}
    </span>
  );
}

function Cell({ value, unit }) {
  return (
    <div className="font-display font-black text-2xl leading-none tabular-nums">
      {value ?? <span className="text-zinc-600 text-xl">--</span>}
      {value != null && unit ? <span className="text-xs text-zinc-500 ml-1">{unit}</span> : null}
    </div>
  );
}

export default function Report() {
  const { i18n } = useTranslation();
  const c = DICT[i18n.language && i18n.language.startsWith("en") ? "en" : "it"];
  const cardRef = useRef(null);
  const [report, setReport] = useState({ before: null, after: null, deltas: {} });
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try { const { data } = await api.get("/report"); setReport(data); } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const capture = async (phase) => {
    setBusy(phase);
    try { await api.post("/report/snapshot", { phase }); await load(); toast.success(c.captured); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || c.err); }
    finally { setBusy(""); }
  };
  const reset = async () => {
    setBusy("reset");
    try { await api.delete("/report"); setReport({ before: null, after: null, deltas: {} }); }
    catch { toast.error(c.err); } finally { setBusy(""); }
  };

  const exportPng = async () => {
    if (!cardRef.current) return;
    setBusy("export");
    try {
      const dataUrl = await toPng(cardRef.current, { pixelRatio: 2, backgroundColor: "#0A0A0C", cacheBust: true });
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], "frameforge-report.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "FrameForge", text: c.report_title });
      } else {
        const a = document.createElement("a");
        a.href = dataUrl; a.download = "frameforge-report.png"; a.click();
      }
      toast.success(c.exported);
    } catch { toast.error(c.err); } finally { setBusy(""); }
  };

  const { before, after, deltas } = report;
  const now = new Date();

  return (
    <div className="space-y-6" data-testid="report-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.25em] text-[#E5FF00] mb-1">{c.eyebrow}</div>
        <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tight">{c.title}</h1>
        <p className="text-zinc-500 text-sm mt-2 max-w-2xl">{c.sub}</p>
      </div>

      {/* How it works */}
      <div className="grid sm:grid-cols-3 gap-3">
        {[["1", c.step1, c.step1d], ["2", c.step2, c.step2d], ["3", c.step3, c.step3d]].map(([n, t, d]) => (
          <div key={n} className="bg-[#0F0F12] border border-[#2A2A35] p-4 hover:border-[#E5FF00]/40 transition-colors" data-testid={`report-step-${n}`}>
            <div className="w-7 h-7 bg-[#E5FF00] text-black font-black flex items-center justify-center mb-2">{n}</div>
            <div className="font-semibold text-sm mb-1">{t}</div>
            <p className="text-xs text-zinc-500 leading-relaxed">{d}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => capture("before")} disabled={!!busy} data-testid="capture-before-btn"
          className="inline-flex items-center gap-2 border border-[#00E0FF]/50 text-[#00E0FF] px-4 py-2.5 hover:bg-[#00E0FF]/10 transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
          {busy === "before" ? <Loader2 size={15} className="animate-spin" /> : <Camera size={15} />} {c.capture_before}
        </button>
        <button onClick={() => capture("after")} disabled={!!busy} data-testid="capture-after-btn"
          className="inline-flex items-center gap-2 border border-[#00FF66]/50 text-[#00FF66] px-4 py-2.5 hover:bg-[#00FF66]/10 transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
          {busy === "after" ? <Loader2 size={15} className="animate-spin" /> : <Camera size={15} />} {c.capture_after}
        </button>
        <div className="flex-1" />
        <button onClick={reset} disabled={!!busy || (!before && !after)} data-testid="report-reset-btn"
          className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-400 px-4 py-2.5 hover:border-white transition-colors text-sm uppercase tracking-wide disabled:opacity-40">
          <RotateCcw size={15} /> {c.reset}
        </button>
        <button onClick={exportPng} disabled={!!busy || (!before && !after)} data-testid="report-export-btn"
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 hover:bg-[#c9e000] transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
          {busy === "export" ? <Loader2 size={15} className="animate-spin" /> : <Share2 size={15} />} {c.export}
        </button>
      </div>

      {/* Branded report card (exported) */}
      <div ref={cardRef} className="relative overflow-hidden bg-[#0A0A0C] border border-[#2A2A35] p-6" data-testid="report-card"
        style={{ backgroundImage: "radial-gradient(circle at 12% 0%, rgba(229,255,0,0.10), transparent 45%), radial-gradient(circle at 100% 100%, rgba(0,255,102,0.08), transparent 40%)" }}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#E5FF00] flex items-center justify-center"><Zap size={18} className="text-black" fill="black" /></div>
            <span className="font-display font-black text-xl tracking-tight">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-[0.25em] text-[#E5FF00]">{c.report_title}</div>
            <div className="text-[10px] text-zinc-500">{now.toLocaleDateString()} · {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
          </div>
        </div>

        {/* Header row */}
        <div className="grid grid-cols-[1.4fr_1fr_auto_1fr_1fr] items-center gap-3 px-3 pb-2 text-[10px] uppercase tracking-widest text-zinc-500">
          <div>Metric</div>
          <div className="text-center text-[#00E0FF]">{c.before}</div>
          <div />
          <div className="text-center text-[#00FF66]">{c.after}</div>
          <div className="text-right">{c.delta}</div>
        </div>

        <div className="space-y-2">
          {METRICS.map((m) => {
            const bv = before?.[m.key];
            const av = after?.[m.key];
            const dv = deltas?.[m.key];
            const Icon = m.icon;
            return (
              <div key={m.key} className="grid grid-cols-[1.4fr_1fr_auto_1fr_1fr] items-center gap-3 bg-black/50 border border-[#1A1A24] px-3 py-3" data-testid={`report-metric-${m.key}`}>
                <div className="flex items-center gap-2 text-sm text-zinc-300">
                  <Icon size={16} className={m.accent} /> {c[m.labelKey]}
                </div>
                <div className="text-center"><Cell value={bv} unit={m.unit} /></div>
                <div className="text-zinc-700"><ArrowRight size={16} /></div>
                <div className="text-center"><Cell value={av} unit={m.unit} /></div>
                <div className="text-right"><DeltaBadge value={dv} higherBetter={m.higherBetter} c={c} /></div>
              </div>
            );
          })}
        </div>

        {/* grades line */}
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-zinc-500">
          {(before?.health_grade || after?.health_grade) && (
            <span>{c.health} {c.grade}: <b className="text-zinc-300">{before?.health_grade || "—"}</b> <ArrowRight size={11} className="inline" /> <b className="text-[#00FF66]">{after?.health_grade || "—"}</b></span>
          )}
          {(before?.bufferbloat_grade || after?.bufferbloat_grade) && (
            <span>{c.bufferbloat} {c.grade}: <b className="text-zinc-300">{before?.bufferbloat_grade || "—"}</b> <ArrowRight size={11} className="inline" /> <b className="text-[#00E0FF]">{after?.bufferbloat_grade || "—"}</b></span>
          )}
          {!before && !after && <span className="italic">{c.tip_before}</span>}
        </div>

        <div className="mt-5 pt-3 border-t border-[#1A1A24] flex items-center justify-between text-[10px] text-zinc-600">
          <span className="flex items-center gap-1"><Activity size={11} /> {c.footer}</span>
          <span>{before?.captured_at ? new Date(before.captured_at).toLocaleDateString() : ""}</span>
        </div>
      </div>
    </div>
  );
}
