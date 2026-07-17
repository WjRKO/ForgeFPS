import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { LayoutDashboard, Radio, Sparkles, FileBarChart, Cpu, Gauge, Thermometer, MemoryStick, Gamepad2, Lock, ArrowRight, Check, TrendingUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { HealthRing } from "@/components/hud";

const COPY = {
  it: {
    banner: "Stai vedendo una demo con dati di esempio (sola lettura).",
    unlock: "Registrati per usarlo sul tuo PC",
    eyebrow: "// demo interattiva · sola lettura",
    title: "FrameForge in azione",
    sub: "Esplora l'interfaccia con dati di esempio. Collega il tuo PC per dati reali e ottimizzazioni.",
    tabs: { dash: "Dashboard", live: "Live", advisor: "AI Advisor", report: "Report" },
    health: "Salute PC", healthSub: "Punteggio complessivo",
    stat: { cpu: "CPU", gpu: "GPU", ram: "RAM", fps: "FPS" },
    checklist: "Checklist salute",
    checks: [
      { t: "Piano energetico Ultimate", ok: true },
      { t: "Game Mode attivo", ok: true },
      { t: "HAGS attivo", ok: true },
      { t: "Driver GPU aggiornati", ok: false },
      { t: "App all'avvio ridotte", ok: false },
    ],
    liveTitle: "Telemetria in tempo reale",
    chartTitle: "Andamento (esempio)",
    advisorTitle: "AI Advisor",
    advisorCtx: "RTX 3070 Ti · Ryzen 7 5800X3D · 32GB",
    userMsg: "Come aumento gli FPS in Warzone senza cambiare hardware?",
    aiMsg: "In base al tuo hardware, ecco le 3 azioni a maggior impatto:",
    aiPoints: ["Attiva NVIDIA Reflex On+Boost (−12ms input lag)", "Piano energetico Ultimate Performance", "Chiudi le app in background prima del match"],
    reportTitle: "Report Prima / Dopo",
    before: "Prima", after: "Dopo",
    metrics: [
      { k: "FPS medi", b: "96", a: "132", d: "+36" },
      { k: "Input lag", b: "24ms", a: "11ms", d: "−13ms" },
      { k: "Health Score", b: "71", a: "89", d: "+18" },
      { k: "Bufferbloat", b: "C", a: "A", d: "↑" },
    ],
    locked: "Azione disponibile dopo la registrazione",
    cta: "Inizia gratis",
  },
  en: {
    banner: "You're viewing a demo with sample data (read-only).",
    unlock: "Sign up to use it on your PC",
    eyebrow: "// interactive demo · read-only",
    title: "FrameForge in action",
    sub: "Explore the interface with sample data. Connect your PC for real data and optimizations.",
    tabs: { dash: "Dashboard", live: "Live", advisor: "AI Advisor", report: "Report" },
    health: "PC Health", healthSub: "Overall score",
    stat: { cpu: "CPU", gpu: "GPU", ram: "RAM", fps: "FPS" },
    checklist: "Health checklist",
    checks: [
      { t: "Ultimate power plan", ok: true },
      { t: "Game Mode on", ok: true },
      { t: "HAGS enabled", ok: true },
      { t: "GPU drivers up to date", ok: false },
      { t: "Startup apps reduced", ok: false },
    ],
    liveTitle: "Real-time telemetry",
    chartTitle: "Trend (sample)",
    advisorTitle: "AI Advisor",
    advisorCtx: "RTX 3070 Ti · Ryzen 7 5800X3D · 32GB",
    userMsg: "How do I boost FPS in Warzone without changing hardware?",
    aiMsg: "Based on your hardware, here are the 3 highest-impact actions:",
    aiPoints: ["Enable NVIDIA Reflex On+Boost (−12ms input lag)", "Ultimate Performance power plan", "Close background apps before the match"],
    reportTitle: "Before / After Report",
    before: "Before", after: "After",
    metrics: [
      { k: "Avg FPS", b: "96", a: "132", d: "+36" },
      { k: "Input lag", b: "24ms", a: "11ms", d: "−13ms" },
      { k: "Health Score", b: "71", a: "89", d: "+18" },
      { k: "Bufferbloat", b: "C", a: "A", d: "↑" },
    ],
    locked: "Available after sign-up",
    cta: "Start free",
  },
};

const CHART = Array.from({ length: 24 }, (_, i) => ({
  i,
  cpu: 45 + Math.round(20 * Math.sin(i / 3) + Math.random() * 8),
  gpu: 70 + Math.round(15 * Math.sin(i / 2 + 1) + Math.random() * 6),
  fps: 130 + Math.round(15 * Math.sin(i / 4) + Math.random() * 6),
}));

const Stat = ({ icon: Icon, label, value, unit, accent }) => (
  <div className="bg-[#0F0F12] border border-[#2A2A35] p-4">
    <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-zinc-500 mb-2"><Icon size={14} className={accent} /> {label}</div>
    <div className="font-display font-black text-3xl tabular-nums">{value}<span className="text-base text-zinc-500 ml-1">{unit}</span></div>
  </div>
);

const LockedBtn = ({ children, testid }) => {
  const lang = useLang();
  const c = COPY[lang];
  return (
    <div className="relative group inline-block" data-testid={testid}>
      <button disabled className="flex items-center gap-2 bg-[#1A1A24] text-zinc-500 font-bold px-4 py-2 text-sm cursor-not-allowed">
        <Lock size={14} /> {children}
      </button>
      <span className="absolute -top-8 left-0 whitespace-nowrap text-[10px] bg-black border border-[#2A2A35] text-zinc-400 px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity">{c.locked}</span>
    </div>
  );
};

export default function DemoApp() {
  const lang = useLang();
  const c = COPY[lang];
  const [tab, setTab] = useState("dash");

  const TABS = [
    { id: "dash", label: c.tabs.dash, icon: LayoutDashboard },
    { id: "live", label: c.tabs.live, icon: Radio },
    { id: "advisor", label: c.tabs.advisor, icon: Sparkles },
    { id: "report", label: c.tabs.report, icon: FileBarChart },
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-white" data-testid="demo-app">
      <MarketingNav />

      {/* Demo banner */}
      <div className="fixed top-16 w-full z-40 bg-[#E5FF00] text-black" data-testid="demo-banner">
        <div className="max-w-6xl mx-auto px-6 py-2 flex items-center justify-between gap-3 text-sm">
          <span className="font-semibold flex items-center gap-2"><Lock size={14} /> {c.banner}</span>
          <Link to="/register" data-testid="demo-unlock-cta" className="shrink-0 font-bold underline hover:no-underline flex items-center gap-1">
            {c.unlock} <ArrowRight size={14} />
          </Link>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 pt-36 pb-16">
        <div className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-2">{c.eyebrow}</div>
        <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter">{c.title}</h1>
        <p className="text-zinc-500 text-sm mt-2 max-w-2xl">{c.sub}</p>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2 mt-6 mb-8 border-b border-[#1A1A24] pb-3">
          {TABS.map((tb) => (
            <button key={tb.id} onClick={() => setTab(tb.id)} data-testid={`demo-tab-${tb.id}`}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold transition-colors ${tab === tb.id ? "bg-[#E5FF00] text-black" : "text-zinc-400 hover:text-white border border-[#2A2A35]"}`}>
              <tb.icon size={15} /> {tb.label}
            </button>
          ))}
        </div>

        <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          {tab === "dash" && (
            <div className="grid lg:grid-cols-3 gap-5" data-testid="demo-dash">
              <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 flex flex-col items-center justify-center">
                <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-4">{c.health}</div>
                <HealthRing score={87} label={c.healthSub} />
              </div>
              <div className="lg:col-span-2 grid grid-cols-2 gap-4">
                <Stat icon={Cpu} label={c.stat.cpu} value="42" unit="%" accent="text-[#E5FF00]" />
                <Stat icon={Gauge} label={c.stat.gpu} value="88" unit="%" accent="text-[#00E0FF]" />
                <Stat icon={MemoryStick} label={c.stat.ram} value="58" unit="%" accent="text-[#B388FF]" />
                <Stat icon={Gamepad2} label={c.stat.fps} value="144" unit="" accent="text-[#00FF66]" />
              </div>
              <div className="lg:col-span-3 bg-[#0F0F12] border border-[#2A2A35] p-5">
                <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-3">{c.checklist}</div>
                <div className="grid sm:grid-cols-2 gap-2">
                  {c.checks.map((ck, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className={`w-5 h-5 flex items-center justify-center ${ck.ok ? "bg-[#00FF66]/15 text-[#00FF66]" : "bg-[#FF6B00]/15 text-[#FF6B00]"}`}>
                        {ck.ok ? <Check size={12} /> : "!"}
                      </span>
                      <span className={ck.ok ? "text-zinc-300" : "text-zinc-400"}>{ck.t}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {tab === "live" && (
            <div data-testid="demo-live">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
                <Stat icon={Gamepad2} label="FPS" value="144" unit="" accent="text-[#00FF66]" />
                <Stat icon={Cpu} label="CPU" value="62" unit="%" accent="text-[#E5FF00]" />
                <Stat icon={Gauge} label="GPU" value="88" unit="%" accent="text-[#00E0FF]" />
                <Stat icon={Thermometer} label={lang === "en" ? "GPU temp" : "Temp GPU"} value="67" unit="°C" accent="text-[#FF6B00]" />
              </div>
              <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
                <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-4">{c.chartTitle}</div>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={CHART}>
                    <CartesianGrid stroke="#1A1A24" strokeDasharray="3 3" />
                    <XAxis dataKey="i" tick={{ fill: "#52525b", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#52525b", fontSize: 10 }} domain={[0, 160]} />
                    <Tooltip contentStyle={{ background: "#0A0A0C", border: "1px solid #2A2A35", fontSize: 12 }} />
                    <Line type="monotone" dataKey="cpu" name="CPU %" stroke="#E5FF00" dot={false} strokeWidth={2} isAnimationActive={false} />
                    <Line type="monotone" dataKey="gpu" name="GPU %" stroke="#00E0FF" dot={false} strokeWidth={2} isAnimationActive={false} />
                    <Line type="monotone" dataKey="fps" name="FPS" stroke="#00FF66" dot={false} strokeWidth={2} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {tab === "advisor" && (
            <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 max-w-2xl" data-testid="demo-advisor">
              <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-[#E5FF00] border border-[#E5FF00]/30 px-2 py-1 mb-5">
                <Sparkles size={11} /> {c.advisorCtx}
              </div>
              <div className="flex justify-end mb-4">
                <div className="bg-[#E5FF00] text-black text-sm font-medium px-4 py-2.5 max-w-md">{c.userMsg}</div>
              </div>
              <div className="flex justify-start mb-4">
                <div className="bg-black border border-[#2A2A35] text-sm text-zinc-200 px-4 py-3 max-w-md">
                  <p className="mb-2">{c.aiMsg}</p>
                  <ul className="space-y-1.5">
                    {c.aiPoints.map((p, i) => (
                      <li key={i} className="flex items-start gap-2 text-zinc-300"><span className="text-[#00FF66] mt-0.5">→</span> {p}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="flex items-center gap-2 border-t border-[#1A1A24] pt-4">
                <input disabled placeholder={lang === "en" ? "Ask the AI..." : "Chiedi all'AI..."} className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-sm text-zinc-500 cursor-not-allowed" />
                <LockedBtn testid="demo-advisor-send">{lang === "en" ? "Send" : "Invia"}</LockedBtn>
              </div>
            </div>
          )}

          {tab === "report" && (
            <div className="bg-[#0A0A0C] border border-[#2A2A35] max-w-2xl" data-testid="demo-report">
              <div className="bg-[#E5FF00] text-black px-5 py-3 font-display font-black tracking-tight flex items-center justify-between">
                <span>{c.reportTitle}</span><span className="text-xs font-mono">FRAMEFORGE</span>
              </div>
              <div className="p-5 space-y-3">
                {c.metrics.map((m, i) => (
                  <div key={i} className="grid grid-cols-4 items-center gap-2 bg-black border border-[#1A1A24] px-4 py-3">
                    <span className="text-sm text-zinc-300 col-span-1">{m.k}</span>
                    <span className="text-center text-zinc-500 font-display font-bold">{m.b}</span>
                    <span className="text-center text-white font-display font-black">{m.a}</span>
                    <span className="text-right"><span className="inline-flex items-center gap-1 text-[#00FF66] text-sm font-bold"><TrendingUp size={13} /> {m.d}</span></span>
                  </div>
                ))}
                <div className="flex justify-between text-[10px] font-mono uppercase tracking-widest text-zinc-600 px-4">
                  <span /> <span>{c.before}</span> <span>{c.after}</span> <span />
                </div>
              </div>
            </div>
          )}
        </motion.div>

        {/* Bottom CTA */}
        <div className="mt-12 bg-gradient-to-r from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/30 p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="font-display font-black text-xl">{c.unlock}</div>
            <p className="text-sm text-zinc-500 mt-1">{c.sub}</p>
          </div>
          <Link to="/register" data-testid="demo-bottom-cta"
            className="shrink-0 flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3 hover:bg-[#D4EC00] transition-colors btn-volt uppercase tracking-wide text-sm">
            {c.cta} <ArrowRight size={16} />
          </Link>
        </div>
      </div>

      <MarketingFooter />
    </div>
  );
}
