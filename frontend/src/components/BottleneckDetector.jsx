import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Zap, Cpu, Gpu, Database, CheckCircle2, Moon, AlertTriangle } from "lucide-react";
import api from "@/lib/api";

/**
 * Real-time bottleneck detector.
 * Reads the latest telemetry sample and classifies the system state:
 *   - CPU-BOUND  → CPU >= 90% & GPU <= 60%
 *   - GPU-BOUND  → GPU >= 90% & CPU <= 60%
 *   - RAM        → RAM >= 90%
 *   - BALANCED   → CPU >= 75% & GPU >= 75%
 *   - IDLE       → both < 20%
 *   - MIXED      → neither of the above
 *
 * Sample must be < 60s old to be considered "live". Otherwise renders nothing.
 * Closes the landing promise "find the bottlenecks".
 */
export default function BottleneckDetector({ compact = false }) {
  const { t } = useTranslation();
  const [state, setState] = useState(null);

  useEffect(() => {
    let alive = true;
    let timer;
    const tick = async () => {
      try {
        const { data } = await api.get("/pc-telemetry");
        if (!alive) return;
        const samples = data?.samples || [];
        const last = samples[samples.length - 1];
        if (!last) { setState({ available: false }); return; }
        const ageMs = last.ts ? Date.now() - new Date(last.ts).getTime() : Infinity;
        if (ageMs > 60000) { setState({ available: false, stale: true }); return; }
        setState({ available: true, sample: last });
      } catch { if (alive) setState({ available: false }); }
      timer = setTimeout(tick, 4000);
    };
    tick();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, []);

  if (!state?.available) return null;
  const s = state.sample;
  const cpu = Number(s.cpu_util ?? 0);
  const gpu = Number(s.gpu_util ?? 0);
  const ram = Number(s.ram_used_pct ?? 0);

  const classify = () => {
    if (ram >= 90) return "ram";
    if (cpu >= 90 && gpu <= 60) return "cpu";
    if (gpu >= 90 && cpu <= 60) return "gpu";
    if (cpu >= 75 && gpu >= 75) return "balanced";
    if (cpu < 20 && gpu < 20) return "idle";
    return "mixed";
  };
  const kind = classify();

  const PALETTES = {
    cpu:      { color: "#FF3B30", bg: "bg-[#FF3B30]/10", border: "border-[#FF3B30]/50", icon: Cpu, glow: "shadow-[0_0_28px_rgba(255,59,48,0.15)]" },
    gpu:      { color: "#00E0FF", bg: "bg-[#00E0FF]/10", border: "border-[#00E0FF]/50", icon: Gpu, glow: "shadow-[0_0_28px_rgba(0,224,255,0.15)]" },
    ram:      { color: "#FFAA00", bg: "bg-[#FFAA00]/10", border: "border-[#FFAA00]/50", icon: Database, glow: "shadow-[0_0_28px_rgba(255,170,0,0.15)]" },
    balanced: { color: "#00FF66", bg: "bg-[#00FF66]/10", border: "border-[#00FF66]/50", icon: CheckCircle2, glow: "shadow-[0_0_28px_rgba(0,255,102,0.15)]" },
    idle:     { color: "#7D7D8A", bg: "bg-[#1A1A24]",    border: "border-[#2A2A35]",    icon: Moon,          glow: "" },
    mixed:    { color: "#E5FF00", bg: "bg-[#E5FF00]/10", border: "border-[#E5FF00]/50", icon: Zap,           glow: "shadow-[0_0_28px_rgba(229,255,0,0.15)]" },
  };
  const COPY = {
    cpu:      { title: t("bottleneck.cpu_title", { defaultValue: "CPU-BOUND" }),
                hint:  t("bottleneck.cpu_hint",  { defaultValue: "La CPU è al {{cpu}}% ma la GPU è ferma al {{gpu}}%. Chiudi app in background (Chrome, Discord, Spotify) per liberare thread.", cpu: cpu.toFixed(0), gpu: gpu.toFixed(0) }) },
    gpu:      { title: t("bottleneck.gpu_title", { defaultValue: "GPU-BOUND" }),
                hint:  t("bottleneck.gpu_hint",  { defaultValue: "La GPU è al {{gpu}}% ma la CPU è solo al {{cpu}}%. Situazione ottimale per il gaming — o considera un upgrade GPU se vuoi più FPS.", cpu: cpu.toFixed(0), gpu: gpu.toFixed(0) }) },
    ram:      { title: t("bottleneck.ram_title", { defaultValue: "MEMORIA SATURA" }),
                hint:  t("bottleneck.ram_hint",  { defaultValue: "La RAM è al {{ram}}%. Rischio di stutter grave. Chiudi browser/app pesanti o considera più RAM.", ram: ram.toFixed(0) }) },
    balanced: { title: t("bottleneck.balanced_title", { defaultValue: "SISTEMA BILANCIATO" }),
                hint:  t("bottleneck.balanced_hint",  { defaultValue: "CPU {{cpu}}% e GPU {{gpu}}% lavorano insieme. Configurazione ottimale.", cpu: cpu.toFixed(0), gpu: gpu.toFixed(0) }) },
    idle:     { title: t("bottleneck.idle_title", { defaultValue: "SISTEMA IN IDLE" }),
                hint:  t("bottleneck.idle_hint",  { defaultValue: "Nessun carico rilevato. Avvia un gioco o un'app pesante per l'analisi bottleneck." }) },
    mixed:    { title: t("bottleneck.mixed_title", { defaultValue: "CARICO MISTO" }),
                hint:  t("bottleneck.mixed_hint",  { defaultValue: "CPU {{cpu}}% · GPU {{gpu}}% · RAM {{ram}}%. Nessun collo di bottiglia evidente.", cpu: cpu.toFixed(0), gpu: gpu.toFixed(0), ram: ram.toFixed(0) }) },
  };
  const p = PALETTES[kind];
  const c = COPY[kind];
  const Icon = p.icon;

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-2 border ${p.border} ${p.bg} px-3 py-1.5 text-xs uppercase tracking-widest`} data-testid={`bottleneck-badge-${kind}`}>
        <Icon size={13} style={{ color: p.color }} />
        <span style={{ color: p.color }} className="font-bold">{c.title}</span>
      </div>
    );
  }

  return (
    <div className={`border ${p.border} ${p.bg} ${p.glow} p-4 mb-4`} data-testid={`bottleneck-${kind}`}>
      <div className="flex items-start gap-4">
        <div className="shrink-0 mt-1"><Icon size={26} style={{ color: p.color }} /></div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="text-[10px] uppercase tracking-[0.2em]" style={{ color: p.color }}>{t("bottleneck.eyebrow", { defaultValue: "// bottleneck detector · live" })}</span>
          </div>
          <div className="font-display font-black text-xl leading-tight" style={{ color: p.color }}>{c.title}</div>
          <p className="text-sm text-zinc-400 mt-1 leading-relaxed">{c.hint}</p>
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-mono text-zinc-500">
            <span data-testid="bottleneck-chip-cpu">CPU <span className="text-zinc-200">{cpu.toFixed(0)}%</span></span>
            <span className="text-zinc-700">·</span>
            <span data-testid="bottleneck-chip-gpu">GPU <span className="text-zinc-200">{gpu.toFixed(0)}%</span></span>
            <span className="text-zinc-700">·</span>
            <span data-testid="bottleneck-chip-ram">RAM <span className="text-zinc-200">{ram.toFixed(0)}%</span></span>
            {s.cpu_temp != null && <><span className="text-zinc-700">·</span><span>CPU°C <span className="text-zinc-200">{s.cpu_temp}</span></span></>}
            {s.gpu_temp != null && <><span className="text-zinc-700">·</span><span>GPU°C <span className="text-zinc-200">{s.gpu_temp}</span></span></>}
          </div>
        </div>
      </div>
    </div>
  );
}
