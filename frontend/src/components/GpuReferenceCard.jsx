/**
 * GpuReferenceCard
 *
 * Mostra la GPU rilevata dell'utente + il confronto con il reference PassMark/3DMark.
 * Include il bottone per lanciare il Full Benchmark (multi-thread CPU + RAM hierarchy
 * + Disk multi-QD + thermal trace, ~3 min).
 *
 * Casi UI:
 * - GPU non rilevata (no /pc-specs) -> nascosto
 * - GPU rilevata ma non nel catalogo (~50 modelli oggi) -> mostra solo il bottone Full Bench + hint
 * - GPU in catalogo -> mostra classe, score G3D reference, tuo score, health status
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Gauge, Cpu, Zap, AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";
import api from "@/lib/api";
import { toast } from "sonner";

const STATUS_COLORS = {
  ok: { border: "border-[#00FF66]/40", text: "text-[#00FF66]", bg: "bg-[#00FF66]/5" },
  overperforming: { border: "border-[#00E0FF]/40", text: "text-[#00E0FF]", bg: "bg-[#00E0FF]/5" },
  borderline: { border: "border-[#E5FF00]/40", text: "text-[#E5FF00]", bg: "bg-[#E5FF00]/5" },
  underperforming: { border: "border-[#FF3B30]/40", text: "text-[#FF3B30]", bg: "bg-[#FF3B30]/5" },
  unknown: { border: "border-zinc-700", text: "text-zinc-400", bg: "bg-zinc-900/40" },
};

export default function GpuReferenceCard() {
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "").startsWith("en");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data: d } = await api.get("/gpu-reference");
        setData(d);
      } catch (e) {
        // 404 = no specs yet → il componente si nasconde
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const launchFullBench = async () => {
    if (launching) return;
    setLaunching(true);
    try {
      const { data: u } = await api.get("/agent/launch-uri?mode=fullbench");
      if (u && u.uri) {
        window.location.href = u.uri; // apre il protocol handler `frameforge://`
        toast.success(en ? "Full Benchmark started — check the FrameForge Agent window (~3 min)" : "Full Benchmark avviato — controlla la finestra FrameForge Agent (~3 min)");
      } else {
        toast.error(en ? "Cannot start benchmark. Is the agent installed?" : "Impossibile avviare il benchmark. L'agent e' installato?");
      }
    } catch (e) {
      toast.error(en ? "Launch failed. Open FrameForge Agent page to install." : "Avvio fallito. Apri la pagina FrameForge Agent per installare.");
    } finally {
      // Lascia il flag su per 3s per evitare double-click.
      setTimeout(() => setLaunching(false), 3000);
    }
  };

  if (loading) return null;
  // No specs at all: componente nascosto (l'utente e' su un altro flow, il FirstScanBanner gestisce quello)
  if (!data || data.reason === "no_specs") return null;

  const gpuStr = data.gpu_string || (en ? "GPU not detected" : "GPU non rilevata");
  const ref = data.reference;
  const health = data.health;
  const statusKey = health?.status || "unknown";
  const colors = STATUS_COLORS[statusKey] || STATUS_COLORS.unknown;

  const statusLabels = en
    ? {
        ok: "Performing as expected",
        overperforming: "Overperforming — great cooling!",
        borderline: "Borderline — check drivers & temps",
        underperforming: "Underperforming — action needed",
        unknown: "Run a benchmark to compare",
      }
    : {
        ok: "In linea con il reference",
        overperforming: "Sopra la media — ottimo raffreddamento!",
        borderline: "Al limite — controlla driver e temperature",
        underperforming: "Sotto le aspettative — serve intervento",
        unknown: "Fai un benchmark per confrontare",
      };

  const StatusIcon = statusKey === "underperforming" ? AlertTriangle :
                     statusKey === "borderline" ? AlertTriangle :
                     statusKey === "unknown" ? HelpCircle : CheckCircle2;

  return (
    <div className={`border ${colors.border} ${colors.bg} p-5`} data-testid="gpu-reference-card">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0 flex-1">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">
            {en ? "// gpu vs reference" : "// gpu vs reference"}
          </div>
          <h3 className="font-display font-black text-lg text-zinc-100 truncate" data-testid="gpu-ref-name">
            {gpuStr}
          </h3>
        </div>
        {ref?.class && (
          <span className={`text-[10px] font-mono uppercase tracking-widest px-2 py-1 border ${colors.border} ${colors.text}`} data-testid="gpu-ref-class">
            {ref.class}
          </span>
        )}
      </div>

      {ref ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-xs">
            <div className="bg-black/40 border border-[#2A2A35] p-2">
              <div className="text-zinc-500 text-[10px] uppercase">{en ? "PassMark G3D" : "PassMark G3D"}</div>
              <div className="text-zinc-100 font-bold text-sm mt-0.5" data-testid="gpu-ref-g3d">{ref.g3d?.toLocaleString() || "n/d"}</div>
            </div>
            <div className="bg-black/40 border border-[#2A2A35] p-2">
              <div className="text-zinc-500 text-[10px] uppercase">3DMark Time Spy</div>
              <div className="text-zinc-100 font-bold text-sm mt-0.5">{ref.timespy?.toLocaleString() || "n/d"}</div>
            </div>
            <div className="bg-black/40 border border-[#2A2A35] p-2">
              <div className="text-zinc-500 text-[10px] uppercase">VRAM</div>
              <div className="text-zinc-100 font-bold text-sm mt-0.5">{ref.vram_gb ? `${ref.vram_gb} GB` : "n/d"}</div>
            </div>
            <div className="bg-black/40 border border-[#2A2A35] p-2">
              <div className="text-zinc-500 text-[10px] uppercase">TDP</div>
              <div className="text-zinc-100 font-bold text-sm mt-0.5">{ref.tdp_w ? `${ref.tdp_w} W` : "n/d"}</div>
            </div>
          </div>

          <div className={`flex items-start gap-2 border-l-2 ${colors.border} pl-3 mb-4`}>
            <StatusIcon size={16} className={`shrink-0 mt-0.5 ${colors.text}`} />
            <div className="min-w-0 flex-1">
              <div className={`text-sm font-bold ${colors.text}`} data-testid="gpu-ref-status">
                {statusLabels[statusKey]}
              </div>
              {health && health.expected_perf != null && data.measured_perf > 0 && (
                <div className="text-xs text-zinc-500 mt-1">
                  {en ? "Your score" : "Il tuo punteggio"}: <span className="text-zinc-200 font-semibold">{data.measured_perf}</span>
                  {" · "}
                  {en ? "expected" : "atteso"}: <span className="text-zinc-200 font-semibold">{health.expected_perf_min}-{health.expected_perf_max}</span>
                  {" · "}
                  <span className={colors.text}>
                    Δ {health.delta > 0 ? `+${health.delta}` : health.delta}
                  </span>
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="bg-black/40 border border-[#2A2A35] p-3 text-xs text-zinc-400 mb-4">
          {en
            ? `Your GPU "${gpuStr}" is not in our reference catalog yet. Only the local benchmark applies.`
            : `La tua GPU "${gpuStr}" non e' ancora nel nostro catalogo di reference. Solo il benchmark locale si applica.`}
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-center">
        <button
          onClick={launchFullBench}
          disabled={launching}
          data-testid="gpu-ref-full-bench-btn"
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold text-xs px-3 py-2 hover:bg-[#D4EE00] disabled:opacity-50 transition-colors"
        >
          <Gauge size={14} />
          {launching
            ? (en ? "Starting…" : "Avvio…")
            : (en ? "Run Full Benchmark (~3 min)" : "Avvia Full Benchmark (~3 min)")}
        </button>
        <span className="text-[10px] text-zinc-500 max-w-md">
          <Cpu size={10} className="inline mr-1" />
          {en
            ? "Multi-thread CPU + RAM hierarchy + Disk multi-QD + thermal trace. Chiudi giochi & app pesanti prima."
            : "CPU multi-thread + RAM L2/L3/DRAM + Disk multi-QD + thermal trace. Chiudi giochi e app pesanti prima."}
        </span>
      </div>
    </div>
  );
}
