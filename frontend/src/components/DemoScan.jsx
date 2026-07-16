import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { Cpu, MonitorPlay, AlertTriangle, TrendingUp, Loader2, ScanLine, ArrowRight, Check } from "lucide-react";
import { useLang } from "@/components/MarketingChrome";

const COPY = {
  it: {
    eyebrow: "// demo · nessuna installazione",
    title: "Scansione demo",
    sub: "Prova una diagnostica dimostrativa su una build di esempio. I dati sono illustrativi.",
    rig: "Build di esempio",
    run: "Avvia scansione gratuita",
    scanning: "Scansione in corso...",
    problems: "Problemi trovati",
    improvement: "Miglioramento stimato",
    cta: "Analizza il mio PC",
    steps: ["Rilevamento hardware", "Analisi processi in background", "Controllo impostazioni latenza", "Verifica configurazione streaming"],
    probs: [
      { t: "Processi in background", d: "7 app non necessarie occupano CPU/RAM durante il gioco." },
      { t: "Impostazioni latenza NVIDIA", d: "Low Latency Mode e Reflex non ottimizzati." },
      { t: "Configurazione OBS", d: "Encoder e priorità non ideali per lo streaming 1080p60." },
    ],
    fps: "+12–18 FPS", lat: "−8 ms latenza", note: "Basato su hardware simile. Risultati reali dopo la scansione con l'agent.",
  },
  en: {
    eyebrow: "// demo · no install",
    title: "Demo scan",
    sub: "Try a demonstrative diagnostic on a sample build. Data is illustrative.",
    rig: "Sample build",
    run: "Run free scan",
    scanning: "Scanning...",
    problems: "Problems found",
    improvement: "Estimated improvement",
    cta: "Analyze my PC",
    steps: ["Hardware detection", "Background process analysis", "Latency settings check", "Streaming config verification"],
    probs: [
      { t: "Background processes", d: "7 unnecessary apps consuming CPU/RAM during gameplay." },
      { t: "NVIDIA latency settings", d: "Low Latency Mode and Reflex not optimized." },
      { t: "OBS configuration", d: "Encoder and priority not ideal for 1080p60 streaming." },
    ],
    fps: "+12–18 FPS", lat: "−8 ms latency", note: "Based on similar hardware. Real results after scanning with the agent.",
  },
};

export const DemoScan = () => {
  const lang = useLang();
  const c = COPY[lang];
  const [state, setState] = useState("idle"); // idle | scanning | done
  const [step, setStep] = useState(0);

  const run = () => {
    setState("scanning"); setStep(0);
    let i = 0;
    const iv = setInterval(() => {
      i += 1; setStep(i);
      if (i >= c.steps.length) { clearInterval(iv); setTimeout(() => setState("done"), 500); }
    }, 650);
  };

  return (
    <div className="bg-[#0A0A0C] border border-[#2A2A35] relative overflow-hidden" data-testid="demo-scan">
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-[#1A1A24]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#FF3B30]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#E5FF00]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#00FF66]" />
        <span className="ml-2 text-[10px] font-mono uppercase tracking-widest text-zinc-500">forgefps://scan</span>
      </div>

      <div className="p-6">
        <div className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-2">{c.eyebrow}</div>
        <h3 className="font-display font-black text-2xl tracking-tight mb-4">{c.title}</h3>

        {/* Sample rig */}
        <div className="grid grid-cols-2 gap-2 mb-5">
          <div className="bg-black border border-[#1A1A24] p-3">
            <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest text-zinc-500"><Cpu size={11} className="text-[#00FF66]" /> CPU</div>
            <div className="font-display font-bold text-sm mt-1">Ryzen 7 5800X</div>
          </div>
          <div className="bg-black border border-[#1A1A24] p-3">
            <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest text-zinc-500"><MonitorPlay size={11} className="text-[#00E0FF]" /> GPU</div>
            <div className="font-display font-bold text-sm mt-1">RTX 4070</div>
          </div>
        </div>

        {state === "idle" && (
          <button onClick={run} data-testid="demo-scan-run"
            className="w-full flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors btn-volt uppercase tracking-wide text-sm">
            <ScanLine size={16} /> {c.run}
          </button>
        )}

        {state === "scanning" && (
          <div className="relative border border-[#1A1A24] bg-black p-4" data-testid="demo-scan-scanning">
            <motion.div className="absolute left-0 right-0 h-[2px] bg-[#E5FF00]/70"
              initial={{ top: 0 }} animate={{ top: ["0%", "100%", "0%"] }} transition={{ duration: 1.3, repeat: Infinity, ease: "linear" }} />
            <div className="flex items-center gap-2 text-sm text-[#E5FF00] font-mono mb-3"><Loader2 size={14} className="animate-spin" /> {c.scanning}</div>
            <ul className="space-y-1.5 font-mono text-xs">
              {c.steps.map((s, i) => (
                <li key={i} className={`flex items-center gap-2 ${i < step ? "text-[#00FF66]" : i === step ? "text-zinc-300" : "text-zinc-600"}`}>
                  {i < step ? <Check size={12} /> : <span className="w-3 text-center">{i === step ? ">" : "·"}</span>} {s}
                </li>
              ))}
            </ul>
          </div>
        )}

        <AnimatePresence>
          {state === "done" && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} data-testid="demo-scan-results">
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">{c.problems}</div>
              <div className="space-y-2 mb-5">
                {c.probs.map((p, i) => (
                  <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.12 }}
                    className="flex items-start gap-3 bg-black border border-[#1A1A24] border-l-2 border-l-[#E5FF00] px-3 py-2.5">
                    <AlertTriangle size={15} className="text-[#E5FF00] shrink-0 mt-0.5" />
                    <div>
                      <div className="text-sm text-zinc-100 font-semibold">{p.t}</div>
                      <div className="text-xs text-zinc-500 leading-relaxed">{p.d}</div>
                    </div>
                  </motion.div>
                ))}
              </div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">{c.improvement}</div>
              <div className="grid grid-cols-2 gap-2 mb-4">
                <div className="bg-[#00FF66]/10 border border-[#00FF66]/30 p-3">
                  <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest text-[#00FF66]"><TrendingUp size={11} /> FPS</div>
                  <div className="font-display font-black text-xl text-[#00FF66] mt-1">{c.fps}</div>
                </div>
                <div className="bg-[#00E0FF]/10 border border-[#00E0FF]/30 p-3">
                  <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest text-[#00E0FF]"><TrendingUp size={11} /> LAT</div>
                  <div className="font-display font-black text-xl text-[#00E0FF] mt-1">{c.lat}</div>
                </div>
              </div>
              <p className="text-[11px] text-zinc-600 mb-4 leading-relaxed">{c.note}</p>
              <Link to="/register" data-testid="demo-scan-cta"
                className="group w-full flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors btn-volt uppercase tracking-wide text-sm">
                {c.cta} <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
              </Link>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
