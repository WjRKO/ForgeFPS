import { useState, useRef, useEffect } from "react";
import { Cpu, Wind, Zap } from "lucide-react";

const VIDEO_SRC = "/assets/agent-preview.mp4";
const GIF_SRC = "/assets/agent-preview.gif";

/**
 * Preview della GUI Edge del Desktop Agent.
 * Ordine di fallback:
 *   1) <video> autoplay muted loop → /assets/agent-preview.mp4
 *   2) <img> → /assets/agent-preview.gif
 *   3) Mock animato CSS (finestra "FrameForge Agent" con tweak che si spuntano)
 *
 * Per sostituire il mock con la registrazione reale della GUI Edge,
 * carica il file in `/app/frontend/public/assets/agent-preview.mp4`
 * (consigliato H.264, 800×500, <2MB, muted, 6-10s in loop) oppure `.gif`.
 */
export default function AgentPreview({ label = "Anteprima GUI live" }) {
  const [stage, setStage] = useState("probe"); // probe → video → gif → mock
  const videoRef = useRef(null);

  // Probe rapido: verifica se esiste un .mp4, altrimenti parte diretto dal .gif
  useEffect(() => {
    if (stage !== "probe") return;
    let cancelled = false;
    fetch(VIDEO_SRC, { method: "HEAD" })
      .then((r) => {
        if (cancelled) return;
        setStage(r.ok && r.headers.get("content-type")?.includes("video") ? "video" : "gif");
      })
      .catch(() => !cancelled && setStage("gif"));
    return () => {
      cancelled = true;
    };
  }, [stage]);

  // Safety net: se il video non parte entro 1.5s → gif
  useEffect(() => {
    if (stage !== "video") return;
    const t = setTimeout(() => {
      const v = videoRef.current;
      if (!v || v.readyState < 2) setStage("gif");
    }, 1500);
    return () => clearTimeout(t);
  }, [stage]);

  return (
    <div
      className="relative overflow-hidden border border-[#2A2A35] bg-black aspect-[16/10] mb-4"
      data-testid="agent-preview-card"
    >
      <div className="absolute top-2 left-2 z-20 flex items-center gap-1.5 bg-black/70 border border-[#00E0FF]/40 px-2 py-0.5">
        <span className="w-1.5 h-1.5 rounded-full bg-[#00FF66] animate-pulse" />
        <span className="text-[9px] font-mono uppercase tracking-widest text-[#00E0FF]">
          {label}
        </span>
      </div>

      {stage === "video" && (
        <video
          ref={videoRef}
          src={VIDEO_SRC}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          onError={() => setStage("gif")}
          onLoadedData={(e) => {
            // se dura 0 (nessun frame reale) → gif
            if (!e.currentTarget.duration) setStage("gif");
          }}
          className="w-full h-full object-cover"
          data-testid="agent-preview-video"
        />
      )}

      {stage === "gif" && (
        <img
          src={GIF_SRC}
          alt="FrameForge Agent GUI preview"
          onError={() => setStage("mock")}
          className="w-full h-full object-cover"
          data-testid="agent-preview-gif"
        />
      )}

      {stage === "mock" && <MockGui />}
      {stage === "probe" && <MockGui />}
    </div>
  );
}

/* --- Mock CSS animato (fallback) --- */
const TWEAKS = [
  { icon: Zap, label: "GPU MSI mode", delay: 0 },
  { icon: Wind, label: "Timer resolution 0.5ms", delay: 0.6 },
  { icon: Cpu, label: "MPO off (fix OBS)", delay: 1.2 },
  { icon: Zap, label: "Ultimate Performance", delay: 1.8 },
  { icon: Wind, label: "Nagle off (latenza)", delay: 2.4 },
  { icon: Cpu, label: "Debloat telemetria", delay: 3.0 },
];

function MockGui() {
  return (
    <div
      className="w-full h-full bg-gradient-to-br from-[#0A0A10] via-[#0F0F18] to-[#0A0A10] p-3 flex flex-col"
      data-testid="agent-preview-mock"
    >
      {/* title bar */}
      <div className="flex items-center gap-1.5 pb-2 border-b border-[#1A1A24]">
        <span className="w-2 h-2 rounded-full bg-[#ff5f57]" />
        <span className="w-2 h-2 rounded-full bg-[#febc2e]" />
        <span className="w-2 h-2 rounded-full bg-[#28c840]" />
        <span className="ml-2 text-[9px] font-mono text-zinc-500">
          FrameForge Agent — Ottimizzazione
        </span>
      </div>

      <div className="grid grid-cols-[80px_1fr] gap-2 mt-2 flex-1 min-h-0">
        {/* sidebar */}
        <div className="flex flex-col gap-1">
          {["Gaming", "Latenza", "Rete", "Sistema"].map((tab, i) => (
            <div
              key={tab}
              className={`text-[9px] font-mono px-1.5 py-1 border ${
                i === 0
                  ? "border-[#E5FF00]/60 bg-[#E5FF00]/10 text-[#E5FF00]"
                  : "border-[#1A1A24] text-zinc-500"
              }`}
            >
              {tab}
            </div>
          ))}
        </div>

        {/* tweaks column */}
        <div className="flex flex-col gap-1 overflow-hidden">
          {TWEAKS.map((tw, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 border border-[#1A1A24] bg-[#0A0A10] px-1.5 py-1 opacity-0 preview-row"
              style={{ animationDelay: `${tw.delay}s` }}
            >
              <tw.icon size={9} className="text-[#00E0FF] shrink-0" />
              <span className="text-[9px] text-zinc-300 flex-1 truncate">
                {tw.label}
              </span>
              <span
                className="text-[8px] font-mono text-[#00FF66] border border-[#00FF66]/40 px-1 opacity-0 preview-check"
                style={{ animationDelay: `${tw.delay + 0.5}s` }}
              >
                GIÀ ATTIVO
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* progress bar */}
      <div className="mt-2 h-1 bg-[#1A1A24] overflow-hidden">
        <div className="h-full bg-gradient-to-r from-[#00E0FF] via-[#E5FF00] to-[#00FF66] preview-progress" />
      </div>

      <style>{`
        @keyframes preview-fade-in {
          0% { opacity: 0; transform: translateX(-6px); }
          100% { opacity: 1; transform: translateX(0); }
        }
        @keyframes preview-check-in {
          0% { opacity: 0; transform: scale(0.85); }
          60% { opacity: 1; transform: scale(1.05); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes preview-progress-loop {
          0% { width: 0%; }
          70% { width: 100%; }
          100% { width: 100%; }
        }
        .preview-row {
          animation: preview-fade-in 0.4s ease-out forwards, preview-loop 4.2s ease-in-out infinite;
        }
        .preview-check {
          animation: preview-check-in 0.5s ease-out forwards, preview-loop 4.2s ease-in-out infinite;
        }
        .preview-progress {
          animation: preview-progress-loop 4.2s ease-in-out infinite;
        }
        @keyframes preview-loop {
          0%, 85% { opacity: 1; }
          95% { opacity: 0; }
          100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
