import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Gauge, TrendingUp, TrendingDown, Minus, Sparkles, Share2, Loader2, CheckCircle2, Zap } from "lucide-react";
import { toast } from "sonner";
import i18n from "@/i18n";
import api, { formatApiErrorDetail } from "@/lib/api";
import { PageHeader } from "@/components/hud";
import { useSilentLaunch } from "@/hooks/useSilentLaunch";
import BrowserPopupHint from "@/components/BrowserPopupHint";

const BENCH_METRICS = [
  { key: "score", lk: "m_score", unit: "/100", higherBetter: true },
  { key: "overall", lk: "m_overall", unit: "", higherBetter: true },
  { key: "cpu_score", lk: "m_cpu", unit: "", higherBetter: true },
  { key: "ram_mbps", lk: "m_ram", unit: "MB/s", higherBetter: true },
  { key: "disk_write_mbps", lk: "m_disk_w", unit: "MB/s", higherBetter: true },
  { key: "disk_read_mbps", lk: "m_disk_r", unit: "MB/s", higherBetter: true },
  { key: "iops_4k", lk: "m_iops", unit: "IOPS", higherBetter: true },
  { key: "dpc_ms", lk: "m_dpc", unit: "ms", higherBetter: false },
  { key: "ping_ms", lk: "m_ping", unit: "ms", higherBetter: false },
  { key: "jitter_ms", lk: "m_jitter", unit: "ms", higherBetter: false },
  { key: "boot_s", lk: "m_boot", unit: "s", higherBetter: false },
  { key: "free_ram_pct", lk: "m_free_ram", unit: "%", higherBetter: true },
];

function ScoreSparkline({ history }) {
  const { t } = useTranslation();
  const pts = (history || [])
    .slice()
    .reverse()
    .map((h) => h?.after?.score ?? h?.score ?? null)
    .filter((v) => v != null);
  if (pts.length < 2) return null;
  const w = 260, h = 48, min = Math.min(...pts), max = Math.max(...pts);
  const span = Math.max(max - min, 1);
  const coords = pts.map((v, i) => `${(i / (pts.length - 1)) * w},${h - 4 - ((v - min) / span) * (h - 8)}`).join(" ");
  return (
    <div className="mt-4 border-t border-[#1A1A24] pt-3" data-testid="bench-history-chart">
      <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{t("mypcpage.bench_history")} ({pts.length})</div>
      <div className="flex items-center gap-3">
        <svg width={w} height={h} className="shrink-0">
          <polyline fill="none" stroke="#00E0FF" strokeWidth="2" points={coords} />
          {pts.map((v, i) => (
            <circle key={i} cx={(i / (pts.length - 1)) * w} cy={h - 4 - ((v - min) / span) * (h - 8)} r="2.5" fill={i === pts.length - 1 ? "#E5FF00" : "#00E0FF"} />
          ))}
        </svg>
        <div className="text-xs text-zinc-500">
          <div>min <span className="text-zinc-300 font-bold">{min}</span></div>
          <div>max <span className="text-zinc-300 font-bold">{max}</span></div>
        </div>
      </div>
    </div>
  );
}

function BenchmarkCard({ bench }) {
  const { t } = useTranslation();
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [explainErr, setExplainErr] = useState("");
  const [sharing, setSharing] = useState(false);
  const [shared, setShared] = useState(false);
  const latest = bench?.latest;
  if (!latest) return null;
  const before = latest.before;
  const after = latest.after || latest;
  const hasCompare = !!before;

  const shareOnDiscord = async () => {
    setSharing(true);
    try {
      await api.post("/discord/share-score", {
        kind: "benchmark",
        score: after?.score || after?.overall || 0,
        metrics: { dpc_us: after?.dpc_us, iops: after?.iops, jitter_ms: after?.jitter_ms },
      });
      setShared(true);
      toast.success(t("mypcpage.share_ok"));
    } catch (e) {
      const msg = e.response?.data?.detail || "";
      if (msg === "Discord not linked") toast.error(t("mypcpage.share_link_first"));
      else if (msg === "Share channel not configured") toast.error(t("mypcpage.share_not_configured"));
      else toast.error(formatApiErrorDetail(msg) || t("mypcpage.share_err"));
    } finally { setSharing(false); }
  };

  const explain = async () => {
    setExplaining(true); setExplainErr("");
    try {
      const lang = (i18n.resolvedLanguage || i18n.language || "it").slice(0, 2);
      const { data } = await api.post("/benchmark/explain", { lang });
      setExplanation((data.explanation || "").replace(/^\s*#{1,6}[^\n]*\n/, "").trim());
    } catch (e) {
      setExplainErr(formatApiErrorDetail(e.response?.data?.detail) || t("mypcpage.bench_explain_err"));
    } finally { setExplaining(false); }
  };

  const deltaIcon = (delta) => {
    if (delta > 0) return <TrendingUp size={13} />;
    if (delta < 0) return <TrendingDown size={13} />;
    return <Minus size={13} />;
  };
  const cellBorderClass = (key) => {
    if (key === "score") return "sm:col-span-2 border-[#E5FF00]/50";
    if (key === "overall") return "sm:col-span-2 border-[#00E0FF]/40";
    return "";
  };
  const valueClass = (key) => {
    if (key === "score") return "text-2xl text-[#E5FF00]";
    if (key === "overall") return "text-2xl text-[#00E0FF]";
    return "text-lg text-zinc-100";
  };
  const shareIcon = () => {
    if (sharing) return <Loader2 size={14} className="animate-spin" />;
    if (shared) return <CheckCircle2 size={14} />;
    return <Share2 size={14} />;
  };
  const shareLabel = () => {
    if (sharing) return t("mypcpage.share_sending");
    if (shared) return t("mypcpage.share_done");
    return t("mypcpage.share_discord");
  };

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick p-6 mb-4" data-testid="benchmark-card">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4 flex items-center gap-2">
        <Gauge size={14} className="text-[#00E0FF]" /> {t("mypcpage.bench")} {hasCompare ? t("mypcpage.bench_compare") : t("mypcpage.bench_last")}
      </div>
      {!hasCompare && (
        <p className="text-xs text-zinc-500 mb-4">{t("mypcpage.bench_hint")}</p>
      )}
      <div className="grid sm:grid-cols-2 gap-2">
        {BENCH_METRICS.map((m) => {
          const av = after?.[m.key];
          if (av == null) return null;
          const bv = before?.[m.key];
          let delta = null, improved = null;
          if (hasCompare && bv != null && bv !== 0) {
            delta = Math.round(((av - bv) / bv) * 100);
            improved = m.higherBetter ? av >= bv : av <= bv;
          }
          return (
            <div key={m.key} className={`bg-black border border-[#1A1A24] p-3 ${cellBorderClass(m.key)}`} data-testid={`bench-${m.key}`}>
              <div className="flex items-center justify-between">
                <div className="text-xs uppercase tracking-widest text-zinc-500">{t(`mypcpage.${m.lk}`)}</div>
                {delta != null && (
                  <div className={`flex items-center gap-1 text-xs font-bold ${improved ? "text-[#00FF66]" : "text-[#FF3B30]"}`}>
                    {deltaIcon(delta)}
                    {delta > 0 ? "+" : ""}{delta}%
                  </div>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                {hasCompare && bv != null && <span className="text-sm text-zinc-600 line-through">{bv}{m.unit}</span>}
                <span className={`font-display font-black ${valueClass(m.key)}`}>{av}{m.unit}</span>
              </div>
            </div>
          );
        })}
      </div>
      <ScoreSparkline history={bench?.history} />
      <div className="mt-4 border-t border-[#1A1A24] pt-3">
        <div className="flex flex-wrap gap-2 mb-3">
          {!explanation && (
            <button onClick={explain} disabled={explaining} data-testid="bench-explain-btn"
              className="inline-flex items-center gap-2 bg-[#00E0FF]/10 border border-[#00E0FF]/50 text-[#00E0FF] px-4 py-2 text-xs font-bold hover:bg-[#00E0FF]/20 transition-colors disabled:opacity-60">
              {explaining ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {explaining ? t("mypcpage.bench_explaining") : t("mypcpage.bench_explain")}
            </button>
          )}
          <button onClick={shareOnDiscord} disabled={sharing || shared} data-testid="bench-share-btn"
            className={`inline-flex items-center gap-2 border px-4 py-2 text-xs font-bold transition-colors disabled:opacity-60 ${shared ? "bg-[#00FF66]/10 border-[#00FF66]/50 text-[#00FF66]" : "bg-[#5865F2]/10 border-[#5865F2]/50 text-[#5865F2] hover:bg-[#5865F2]/20"}`}>
            {shareIcon()}
            {shareLabel()}
          </button>
        </div>
        {explainErr && <div className="text-xs text-[#FF3B30] mt-2" data-testid="bench-explain-err">{explainErr}</div>}
        {explanation && (
          <div className="bg-black border border-[#00E0FF]/30 p-4 mt-1" data-testid="bench-explanation">
            <div className="text-xs uppercase tracking-widest text-[#00E0FF] mb-2 flex items-center gap-1.5"><Sparkles size={12} /> {t("mypcpage.bench_explain_title")}</div>
            <div className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{explanation.replace(/\*\*/g, "")}</div>
          </div>
        )}
      </div>
      {latest.ts && (
        <div className="mt-3 text-xs text-zinc-600 border-t border-[#1A1A24] pt-3">
          {t("mypcpage.last_run")} {(() => { try { return new Date(latest.ts).toLocaleString((i18n.resolvedLanguage || i18n.language || "en").slice(0, 2)); } catch { return new Date(latest.ts).toLocaleString(); } })()}
        </div>
      )}
    </div>
  );
}

export default function Benchmark() {
  const { t } = useTranslation();
  const [bench, setBench] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/pc-benchmark");
      setBench(data.latest ? data : null);
    } catch (e) {
      console.error("load benchmark failed", e);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const baselineTs = useRef(bench?.latest?.ts || null);
  useEffect(() => { baselineTs.current = bench?.latest?.ts || null; }, [bench?.latest?.ts]);

  const benchLaunch = useSilentLaunch({
    mode: "benchmark",
    timeoutMs: 180000,
    labels: {
      starting: t("bench.silent_start", { defaultValue: "Benchmark in avvio..." }),
      running: t("bench.silent_running", { defaultValue: "Benchmark in corso (~1-2 min)..." }),
      done: t("bench.silent_done", { defaultValue: "Benchmark completato." }),
      failed: t("bench.silent_failed", { defaultValue: "Benchmark non risponde. Hai installato FrameForge?" }),
    },
    detectDone: async () => {
      const { data } = await api.get("/pc-benchmark");
      const newTs = data?.latest?.ts;
      if (newTs && newTs !== baselineTs.current) {
        setBench(data);
        return true;
      }
      return false;
    },
  });

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <PageHeader eyebrow={t("bench.eyebrow", { defaultValue: "// benchmark" })} title={t("bench.title", { defaultValue: "Benchmark del sistema" })}
        actions={<>
          <button data-testid="silent-bench-btn" onClick={benchLaunch.launch} disabled={benchLaunch.running}
            className="flex items-center gap-2 border border-[#E5FF00]/50 text-[#E5FF00] px-3 py-2 text-sm hover:bg-[#E5FF00]/10 disabled:opacity-60 transition-colors">
            {benchLaunch.running ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
            {t("bench.run_now", { defaultValue: "Benchmark ora" })}
          </button>
          <button data-testid="refresh-bench-btn" onClick={load} disabled={loading}
            className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] btn-ghost">
            <Loader2 size={15} className={loading ? "animate-spin" : "hidden"} />
            <Sparkles size={15} className={loading ? "hidden" : ""} />
            {t("bench.refresh", { defaultValue: "Ricarica" })}
          </button>
        </>} />

      <BrowserPopupHint testid="bench-popup-hint" />

      {bench && bench.latest ? (
        <BenchmarkCard bench={bench} />
      ) : (
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-8 text-center" data-testid="bench-empty">
          <Gauge size={40} className="mx-auto text-zinc-600 mb-3" />
          <div className="text-sm text-zinc-300 font-semibold mb-1">
            {t("bench.empty_title", { defaultValue: "Nessun benchmark ancora" })}
          </div>
          <p className="text-xs text-zinc-500 max-w-lg mx-auto leading-relaxed mb-4">
            {t("bench.empty_desc", { defaultValue: "Esegui il benchmark per misurare CPU, RAM, disco e latenza di rete. Ripeti dopo un'ottimizzazione per vedere il confronto prima/dopo." })}
          </p>
          <button onClick={benchLaunch.launch} disabled={benchLaunch.running} data-testid="bench-cta"
            className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2.5 text-sm hover:bg-[#D4EE00] disabled:opacity-60 transition-colors">
            {benchLaunch.running ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
            {t("bench.run_first", { defaultValue: "Esegui il primo benchmark" })}
          </button>
        </div>
      )}
    </div>
  );
}
