import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { Cpu, MonitorPlay, MemoryStick, MonitorSmartphone, AlertTriangle, Loader2, ScanLine, ArrowRight, Check, Gauge, Wifi } from "lucide-react";
import { useLang } from "@/components/MarketingChrome";
import { detectBrowserSpecs } from "@/lib/detectSpecs";
import { runNetTest } from "@/lib/netTest";
import { buildAdvice } from "@/lib/quickAdvice";
import { trackConversion } from "@/lib/gtag";

const COPY = {
  it: {
    eyebrow: "// scansione reale · nessun account",
    title: "Scansiona il tuo PC",
    sub: "Analisi reale dal browser: hardware, qualità di rete e consigli su misura. Nessun download, nessun account.",
    run: "Avvia scansione gratuita",
    scanning: "Scansione in corso...",
    steps: ["Rilevamento hardware", "Latenza di rete (a riposo)", "Test bufferbloat sotto carico", "Consigli su misura"],
    hw: "Il tuo hardware",
    net: "Qualità di rete",
    idle: "Latenza", load: "Sotto carico", bloat: "Bufferbloat", down: "Download",
    unknown: "Non rilevato",
    netfail: "Test di rete non disponibile (bloccato dal browser o rete). Consigli comunque su misura qui sotto.",
    advice: "Consigli per te",
    note: "Dati reali rilevati dal tuo browser. Temperature, FPS in-game e ottimizzazioni reali richiedono l'agent (dopo la registrazione).",
    cta: "Ottimizza davvero — registrati",
    demo: "Esplora la demo dell'app",
  },
  en: {
    eyebrow: "// real scan · no account",
    title: "Scan your PC",
    sub: "Real in-browser analysis: hardware, network quality and tailored tips. No download, no account.",
    run: "Run free scan",
    scanning: "Scanning...",
    steps: ["Hardware detection", "Idle network latency", "Bufferbloat under load", "Tailored recommendations"],
    hw: "Your hardware",
    net: "Network quality",
    idle: "Latency", load: "Under load", bloat: "Bufferbloat", down: "Download",
    unknown: "Not detected",
    netfail: "Network test unavailable (blocked by browser or network). Tailored tips still shown below.",
    advice: "Recommendations for you",
    note: "Real data detected from your browser. Temperatures, in-game FPS and real optimizations require the agent (after sign-up).",
    cta: "Optimize for real — sign up",
    demo: "Explore the app demo",
  },
};

const gradeColor = (g) => {
  if (!g) return "text-zinc-400";
  if (g.startsWith("A")) return "text-[#00FF66]";
  if (g === "B") return "text-[#E5FF00]";
  if (g === "C") return "text-[#FF6B00]";
  return "text-[#FF3B30]";
};

export const DemoScan = () => {
  const lang = useLang();
  const c = COPY[lang];
  const [state, setState] = useState("idle"); // idle | scanning | done
  const [step, setStep] = useState(0);
  const [specs, setSpecs] = useState(null);
  const [net, setNet] = useState(null);
  const [advice, setAdvice] = useState([]);

  const run = async () => {
    setState("scanning"); setStep(0); setNet(null);
    // 1. Hardware (real, instant)
    const hw = detectBrowserSpecs();
    setSpecs(hw);
    await new Promise((r) => setTimeout(r, 500));
    setStep(1);
    // 2 + 3. Network test (real, client-side)
    let netRes = null;
    try {
      await new Promise((r) => setTimeout(r, 300));
      setStep(2);
      netRes = await runNetTest();
    } catch {
      netRes = null;
    }
    setNet(netRes);
    setStep(3);
    // 4. Advice (rules)
    const adv = buildAdvice(hw, netRes, lang);
    setAdvice(adv);
    await new Promise((r) => setTimeout(r, 400));
    setStep(4);
    setState("done");
    trackConversion("demo_scan");
  };

  const HwCell = ({ icon: Icon, label, value, color }) => (
    <div className="bg-black border border-[#1A1A24] p-3" data-testid={`demo-hw-${label.toLowerCase()}`}>
      <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest text-zinc-500"><Icon size={11} className={color} /> {label}</div>
      <div className="font-display font-bold text-sm mt-1 truncate">{value || c.unknown}</div>
    </div>
  );

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
        <h3 className="font-display font-black text-2xl tracking-tight mb-2">{c.title}</h3>
        <p className="text-sm text-zinc-500 mb-5 leading-relaxed">{c.sub}</p>

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
              {/* Real hardware */}
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">{c.hw}</div>
              <div className="grid grid-cols-2 gap-2 mb-5">
                <HwCell icon={MonitorPlay} label="GPU" value={specs?.gpu} color="text-[#00E0FF]" />
                <HwCell icon={Cpu} label="CPU" value={specs?.cpu_threads ? `${specs.cpu_threads} ${lang === "en" ? "threads" : "thread"}` : ""} color="text-[#00FF66]" />
                <HwCell icon={MemoryStick} label="RAM" value={specs?.ram} color="text-[#B388FF]" />
                <HwCell icon={MonitorSmartphone} label="OS" value={specs?.os} color="text-[#E5FF00]" />
              </div>

              {/* Real network */}
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">{c.net}</div>
              {net ? (
                <div className="grid grid-cols-4 gap-2 mb-5" data-testid="demo-net-result">
                  <div className="bg-black border border-[#1A1A24] p-3 text-center">
                    <div className="text-[9px] uppercase tracking-widest text-zinc-500 flex items-center justify-center gap-1"><Gauge size={10} /> {c.bloat}</div>
                    <div className={`font-display font-black text-2xl mt-1 ${gradeColor(net.grade)}`}>{net.grade || "--"}</div>
                  </div>
                  <div className="bg-black border border-[#1A1A24] p-3 text-center">
                    <div className="text-[9px] uppercase tracking-widest text-zinc-500">{c.idle}</div>
                    <div className="font-display font-black text-lg mt-1 text-zinc-100">{net.idleMs}<span className="text-xs text-zinc-500">ms</span></div>
                  </div>
                  <div className="bg-black border border-[#1A1A24] p-3 text-center">
                    <div className="text-[9px] uppercase tracking-widest text-zinc-500">{c.load}</div>
                    <div className="font-display font-black text-lg mt-1 text-zinc-100">{net.loadedMs ?? "--"}<span className="text-xs text-zinc-500">ms</span></div>
                  </div>
                  <div className="bg-black border border-[#1A1A24] p-3 text-center">
                    <div className="text-[9px] uppercase tracking-widest text-zinc-500 flex items-center justify-center gap-1"><Wifi size={10} /> {c.down}</div>
                    <div className="font-display font-black text-lg mt-1 text-zinc-100">{net.downloadMbps ?? "--"}<span className="text-xs text-zinc-500"> Mb</span></div>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-zinc-500 border border-[#1A1A24] bg-black px-3 py-2.5 mb-5">{c.netfail}</p>
              )}

              {/* Rule-based advice */}
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">{c.advice}</div>
              <div className="space-y-2 mb-4">
                {advice.map((p, i) => (
                  <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }}
                    className="flex items-start gap-3 bg-black border border-[#1A1A24] border-l-2 border-l-[#E5FF00] px-3 py-2.5" data-testid={`demo-advice-${i}`}>
                    <AlertTriangle size={15} className="text-[#E5FF00] shrink-0 mt-0.5" />
                    <div>
                      <div className="text-sm text-zinc-100 font-semibold">{p.t}</div>
                      <div className="text-xs text-zinc-500 leading-relaxed">{p.d}</div>
                    </div>
                  </motion.div>
                ))}
              </div>

              <p className="text-[11px] text-zinc-600 mb-4 leading-relaxed">{c.note}</p>
              <div className="flex flex-col gap-2">
                <Link to="/register" data-testid="demo-scan-cta"
                  className="group w-full flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors btn-volt uppercase tracking-wide text-sm">
                  {c.cta} <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link to="/demo" data-testid="demo-scan-explore"
                  className="w-full flex items-center justify-center gap-2 border border-[#2A2A35] text-zinc-300 font-semibold py-2.5 hover:border-[#E5FF00]/50 hover:text-white transition-colors text-sm">
                  {c.demo}
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
