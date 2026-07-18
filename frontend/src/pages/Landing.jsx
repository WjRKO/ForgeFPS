import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useInView } from "framer-motion";
import {
  Zap, Cpu, LineChart as LineIcon, MonitorDown, MessageSquareCode, ArrowRight, Gauge,
  Plug, Rocket, Activity, Thermometer, Check, Bell, Terminal, ShieldCheck,
} from "lucide-react";
import { AreaChart, Area, LineChart, Line, ReferenceLine, ResponsiveContainer } from "recharts";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePageMeta } from "@/hooks/usePageMeta";
import { DemoScan } from "@/components/DemoScan";
import { TrustBar } from "@/components/TrustBar";
import { SecureInstaller } from "@/components/SecureInstaller";
import { FooterCommunity, FooterLegal } from "@/components/FooterExtras";

const EASE = [0.16, 1, 0.3, 1];
const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
};

/* ---------- animated count-up ---------- */
function Counter({ value }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const [n, setN] = useState(0);
  const m = String(value).match(/^(\D*)(\d+)(\D*)$/) || ["", "", value, ""];
  const [, prefix, numStr, suffix] = m;
  const target = Number(numStr) || 0;
  useEffect(() => {
    if (!inView || !target) return;
    let raf; const start = performance.now(); const dur = 1200;
    const tick = (t) => {
      const p = Math.min((t - start) / dur, 1);
      setN(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, target]);
  return <span ref={ref}>{prefix}{target ? n : numStr}{suffix}</span>;
}

/* ---------- product mockups ---------- */
const FPS_DATA = [{ v: 116 }, { v: 121 }, { v: 128 }, { v: 140 }, { v: 158 }, { v: 172 }, { v: 184 }];
const PRICE_DATA = [{ p: 749 }, { p: 739 }, { p: 712 }, { p: 699 }, { p: 665 }, { p: 629 }, { p: 599 }];

function HealthRing({ score = 92, size = 120 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const r = 52; const c = 2 * Math.PI * r;
  return (
    <svg ref={ref} width={size} height={size} viewBox="0 0 120 120" className="-rotate-90">
      <circle cx="60" cy="60" r={r} fill="none" stroke="#1A1A24" strokeWidth="8" />
      <motion.circle cx="60" cy="60" r={r} fill="none" stroke="#00FF66" strokeWidth="8" strokeLinecap="round"
        strokeDasharray={c}
        initial={{ strokeDashoffset: c }}
        animate={inView ? { strokeDashoffset: c - (score / 100) * c } : {}}
        transition={{ duration: 1.4, ease: EASE }} />
    </svg>
  );
}

function HeroMockup() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, y: 20 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.8, ease: EASE, delay: 0.15 }}
      className="relative"
    >
      <motion.div animate={{ y: [0, -10, 0] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}>
        {/* main HUD panel */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 relative overflow-hidden">
          <div className="absolute top-0 left-0 h-[2px] w-full bg-gradient-to-r from-[#E5FF00] via-transparent to-transparent" />
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-mono tracking-[0.2em] uppercase text-zinc-500">// live telemetry</span>
            <span className="flex items-center gap-1.5 text-[10px] font-mono text-[#00FF66]"><span className="w-1.5 h-1.5 bg-[#00FF66] rounded-full animate-pulse" /> ONLINE</span>
          </div>
          <div className="flex items-center gap-5">
            <div className="relative shrink-0" style={{ width: 120, height: 120 }}>
              <HealthRing />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-display font-black text-3xl text-[#00FF66]">92</span>
                <span className="text-[9px] uppercase tracking-widest text-zinc-500">Health</span>
              </div>
            </div>
            <div className="flex-1 grid grid-cols-2 gap-2">
              {[
                { l: "CPU", v: "48°C", c: "#00FF66", i: Cpu },
                { l: "GPU", v: "61°C", c: "#00E0FF", i: Thermometer },
                { l: "RAM", v: "38%", c: "#E5FF00", i: Activity },
                { l: "PING", v: "12ms", c: "#00FF66", i: Zap },
              ].map((s) => (
                <div key={s.l} className="bg-black border border-[#1A1A24] p-2">
                  <div className="flex items-center gap-1 text-[9px] uppercase tracking-widest text-zinc-500"><s.i size={10} style={{ color: s.c }} /> {s.l}</div>
                  <div className="font-display font-bold text-sm mt-0.5" style={{ color: s.c }}>{s.v}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-4">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1">
              <span>FPS · Cyberpunk 2077</span><span className="text-[#00FF66]">+58%</span>
            </div>
            <div className="h-16">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={FPS_DATA} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="fpsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00FF66" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#00FF66" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area type="monotone" dataKey="v" stroke="#00FF66" strokeWidth={2} fill="url(#fpsFill)" isAnimationActive />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
        {/* floating badge */}
        <motion.div
          animate={{ y: [0, 8, 0] }} transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
          className="absolute -bottom-5 -left-5 bg-[#E5FF00] text-black px-4 py-2 hidden sm:block shadow-[0_8px_30px_rgba(229,255,0,0.25)]">
          <div className="text-[10px] font-mono uppercase tracking-widest">tweaks applied</div>
          <div className="font-display font-black text-lg leading-none">35 / 35</div>
        </motion.div>
      </motion.div>
    </motion.div>
  );
}

function AdvisorChat() {
  const { t } = useTranslation();
  const msgs = [
    { who: "user", text: t("landing.demo_q") },
    { who: "ai", text: t("landing.demo_a") },
  ];
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] p-4 space-y-3">
      {msgs.map((m, i) => (
        <motion.div key={i} {...fadeUp} transition={{ delay: 0.1 + i * 0.25, ease: EASE }}
          className={`flex ${m.who === "ai" ? "justify-start" : "justify-end"}`}>
          <div className={`max-w-[85%] px-3 py-2 text-xs leading-relaxed border ${m.who === "ai" ? "bg-[#00E0FF]/10 border-[#00E0FF]/30 text-zinc-200" : "bg-black border-[#2A2A35] text-zinc-400"}`}>
            {m.text}
          </div>
        </motion.div>
      ))}
      <div className="flex items-center gap-1 text-[10px] font-mono text-[#00E0FF] pl-1">
        <span className="w-1.5 h-1.5 bg-[#00E0FF] rounded-full animate-pulse" /> AI Advisor
      </div>
    </div>
  );
}

function HealthMockup() {
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] p-5 flex items-center gap-5">
      <div className="relative shrink-0" style={{ width: 110, height: 110 }}>
        <HealthRing score={88} size={110} />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display font-black text-2xl text-[#00FF66]">88</span>
          <span className="text-[9px] uppercase tracking-widest text-zinc-500">Good</span>
        </div>
      </div>
      <div className="flex-1 space-y-2">
        {[["CPU 5800X", "48°C", "#00FF66"], ["RTX 3070", "61°C", "#00E0FF"], ["Boost", "+42% FPS", "#E5FF00"]].map(([a, b, c]) => (
          <div key={a} className="flex items-center justify-between bg-black border border-[#1A1A24] px-3 py-2 text-xs">
            <span className="text-zinc-400">{a}</span><span className="font-bold" style={{ color: c }}>{b}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function BuildMockup() {
  const rows = [
    ["GPU", "RTX 4070 Super"], ["CPU", "Ryzen 7 7800X3D"], ["RAM", "32GB DDR5 6000"], ["SSD", "2TB NVMe Gen4"],
  ];
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-mono tracking-[0.2em] uppercase text-zinc-500">// build · €1500</span>
        <span className="text-[#E5FF00] font-display font-black text-sm">~180 FPS</span>
      </div>
      <div className="space-y-1.5">
        {rows.map(([k, v], i) => (
          <motion.div key={k} {...fadeUp} transition={{ delay: i * 0.12, ease: EASE }}
            className="flex items-center gap-3 bg-black border border-[#1A1A24] px-3 py-2">
            <Check size={14} className="text-[#00FF66] shrink-0" />
            <span className="text-[10px] uppercase tracking-widest text-zinc-500 w-10">{k}</span>
            <span className="text-sm text-zinc-100">{v}</span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function PriceMockup() {
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-zinc-200">RTX 4070 Super</div>
        <div className="flex items-center gap-1.5 text-xs text-[#00FF66]"><Bell size={12} /> -20%</div>
      </div>
      <div className="flex items-end gap-3 mb-2">
        <span className="font-display font-black text-2xl text-[#00E0FF]">€599</span>
        <span className="text-sm text-zinc-600 line-through mb-1">€749</span>
      </div>
      <div className="h-20">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={PRICE_DATA} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
            <ReferenceLine y={620} stroke="#E5FF00" strokeDasharray="4 4" strokeWidth={1} />
            <Line type="monotone" dataKey="p" stroke="#00E0FF" strokeWidth={2} dot={false} isAnimationActive />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">target €620 · reached</div>
    </div>
  );
}

function TerminalMockup() {
  return (
    <div className="bg-black border border-[#1A1A24]">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[#1A1A24]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#FF3B30]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#E5FF00]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#00FF66]" />
        <span className="ml-2 text-[10px] font-mono text-zinc-600">PowerShell</span>
      </div>
      <div className="p-4 font-mono text-xs leading-relaxed">
        <div className="text-zinc-500">PS C:\Users\Streamer&gt; <span className="text-[#00FF66]">.\forgefps-setup.exe --verify</span></div>
        <div className="text-zinc-400 mt-2">[<span className="text-[#00FF66]">✓</span>] SHA256 verified · signed installer</div>
        <div className="text-zinc-400">[<span className="text-[#00FF66]">✓</span>] Hardware detected · RTX 3070</div>
        <div className="text-zinc-400">[<span className="text-[#00FF66]">✓</span>] Power plan · Ultimate</div>
        <div className="text-zinc-400">[<span className="text-[#00FF66]">✓</span>] 35 adaptive tweaks applied · reversible</div>
        <div className="text-[#00FF66] mt-1">Done. <span className="cursor-blink">▊</span></div>
      </div>
    </div>
  );
}

/* ---------- feature row ---------- */
function FeatureRow({ eyebrow, title, desc, bullets, accent, reverse, mockup }) {
  return (
    <motion.div {...fadeUp} transition={{ duration: 0.6, ease: EASE }}
      className={`grid lg:grid-cols-2 gap-10 items-center ${reverse ? "lg:[direction:rtl]" : ""}`}>
      <div className="lg:[direction:ltr]">
        <div className="text-xs font-mono tracking-[0.2em] uppercase mb-3" style={{ color: accent }}>{eyebrow}</div>
        <h3 className="font-display font-black text-2xl sm:text-3xl tracking-tighter mb-4">{title}</h3>
        <p className="text-zinc-400 text-base leading-relaxed mb-5 max-w-lg">{desc}</p>
        <ul className="space-y-2.5">
          {bullets.map((b, i) => (
            <li key={i} className="flex items-center gap-3 text-sm text-zinc-300">
              <span className="w-5 h-5 border flex items-center justify-center shrink-0" style={{ borderColor: accent }}>
                <Check size={12} style={{ color: accent }} />
              </span>
              {b}
            </li>
          ))}
        </ul>
      </div>
      <div className="lg:[direction:ltr]">{mockup}</div>
    </motion.div>
  );
}

export default function Landing() {
  const { t } = useTranslation();
  usePageMeta(
    "FrameForge — AI Performance Command Center per gamer & streamer",
    "FrameForge ottimizza il tuo PC gaming con consigli AI, telemetria live (FPS, temperature, input lag), build su misura e price tracking dei componenti. Gratis, in meno di un minuto.",
  );

  const trust = [
    { v: t("landing.trust_fps_v"), l: t("landing.trust_fps_l"), c: "#00FF66" },
    { v: t("landing.trust_tweaks_v"), l: t("landing.trust_tweaks_l"), c: "#E5FF00" },
    { v: t("landing.trust_stores_v"), l: t("landing.trust_stores_l"), c: "#00E0FF" },
    { v: t("landing.trust_rev_v"), l: t("landing.trust_rev_l"), c: "#FFFFFF" },
  ];

  const steps = [
    { i: Plug, t: t("landing.how1_t"), d: t("landing.how1_d") },
    { i: Cpu, t: t("landing.how2_t"), d: t("landing.how2_d") },
    { i: Rocket, t: t("landing.how3_t"), d: t("landing.how3_d") },
  ];

  const features = [
    { eyebrow: "// AI Advisor", icon: MessageSquareCode, accent: "#00E0FF", t: t("landing.f_advisor_t"), d: t("landing.f_advisor_long"), b: [t("landing.f_advisor_b1"), t("landing.f_advisor_b2"), t("landing.f_advisor_b3")], m: <AdvisorChat /> },
    { eyebrow: "// Telemetry", icon: Gauge, accent: "#00FF66", t: t("landing.f_health_t"), d: t("landing.f_health_long"), b: [t("landing.f_health_b1"), t("landing.f_health_b2"), t("landing.f_health_b3")], m: <HealthMockup /> },
    { eyebrow: "// Build", icon: Cpu, accent: "#E5FF00", t: t("landing.f_build_t"), d: t("landing.f_build_long"), b: [t("landing.f_build_b1"), t("landing.f_build_b2"), t("landing.f_build_b3")], m: <BuildMockup /> },
    { eyebrow: "// Prices", icon: LineIcon, accent: "#FFFFFF", t: t("landing.f_price_t"), d: t("landing.f_price_long"), b: [t("landing.f_price_b1"), t("landing.f_price_b2"), t("landing.f_price_b3")], m: <PriceMockup /> },
    { eyebrow: "// Agent", icon: Terminal, accent: "#FF3B30", t: t("landing.f_agent_t"), d: t("landing.f_agent_long"), b: [t("landing.f_agent_b1"), t("landing.f_agent_b2"), t("landing.f_agent_b3")], m: <TerminalMockup /> },
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100 overflow-x-hidden">
      {/* NAV */}
      <header className="fixed top-0 w-full z-50 bg-[#050505]/80 backdrop-blur-xl border-b border-[#1A1A24]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#E5FF00] flex items-center justify-center"><Zap size={18} className="text-black" /></div>
            <span className="font-display font-black tracking-tighter text-lg">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
          </div>
          <nav className="hidden md:flex items-center gap-1">
            <Link to="/security" data-testid="nav-security" className="text-xs font-mono uppercase tracking-widest px-3 py-2 text-zinc-400 hover:text-white transition-colors">{t("landing.nav_security")}</Link>
            <Link to="/privacy-telemetry" data-testid="nav-privacy" className="text-xs font-mono uppercase tracking-widest px-3 py-2 text-zinc-400 hover:text-white transition-colors">{t("landing.nav_privacy")}</Link>
            <Link to="/changelog" data-testid="nav-changelog" className="text-xs font-mono uppercase tracking-widest px-3 py-2 text-zinc-400 hover:text-white transition-colors">{t("landing.nav_changelog")}</Link>
            <Link to="/pricing" data-testid="nav-pricing" className="text-xs font-mono uppercase tracking-widest px-3 py-2 text-zinc-400 hover:text-white transition-colors">{t("landing.nav_pricing")}</Link>
          </nav>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link to="/login" data-testid="nav-login-link" className="text-sm text-zinc-400 hover:text-white transition-colors px-3 py-2 hidden sm:block">{t("landing.login")}</Link>
            <Link to="/register" data-testid="nav-register-link" className="text-sm bg-[#E5FF00] text-black font-bold px-4 py-2 hover:bg-[#D4EC00] transition-colors btn-volt">{t("landing.start")}</Link>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-[0.4] z-0" />
        <div className="absolute -top-32 -right-32 w-[500px] h-[500px] bg-[#E5FF00]/5 blur-[120px] rounded-full z-0" />
        <div className="relative z-10 max-w-6xl mx-auto grid lg:grid-cols-2 gap-14 items-center">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE }}>
            <div className="inline-flex items-center gap-2 border border-[#2A2A35] bg-black/40 px-3 py-1 mb-6 text-xs font-mono uppercase tracking-widest text-[#E5FF00]">
              <Gauge size={14} /> {t("landing.badge")}
            </div>
            <h1 className="font-display font-black text-4xl sm:text-5xl lg:text-6xl tracking-tighter leading-[0.95] mb-6">
              {t("landing.hero1")}<br /><span className="text-[#E5FF00]">{t("landing.hero2")}</span>
            </h1>
            <p className="text-zinc-400 text-base sm:text-lg max-w-xl mb-8 leading-relaxed">{t("landing.hero_sub")}</p>
            <div className="flex flex-col sm:flex-row gap-3">
              <a href="#demo" data-testid="hero-cta-btn" className="group inline-flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3.5 hover:bg-[#D4EC00] transition-colors btn-volt">
                {t("landing.cta")} <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </a>
              <Link to="/login" className="inline-flex items-center justify-center gap-2 border border-[#2A2A35] px-6 py-3.5 hover:border-[#E5FF00] hover:-translate-y-0.5 transition-all">
                {t("landing.have_account")}
              </Link>
            </div>
          </motion.div>
          <div><HeroMockup /></div>
        </div>
      </section>

      {/* DEMO SCAN + SECURE INSTALLER */}
      <section id="demo" className="max-w-6xl mx-auto px-6 py-20 scroll-mt-20">
        <motion.div {...fadeUp} className="mb-10">
          <div className="text-xs font-mono tracking-[0.2em] uppercase text-zinc-500 mb-3">{t("landing.demo_eyebrow")}</div>
          <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tighter max-w-2xl">{t("landing.demo_title")}</h2>
        </motion.div>
        <div className="grid lg:grid-cols-2 gap-6 items-start">
          <DemoScan />
          <SecureInstaller />
        </div>
      </section>

      {/* TRUST STRIP */}
      <section className="border-y border-[#1A1A24] bg-[#050505]">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4">
          {trust.map((s, i) => (
            <div key={i} className={`p-6 text-center ${i < 3 ? "md:border-r" : ""} ${i < 2 ? "border-r" : ""} ${i < 2 ? "border-b md:border-b-0" : ""} border-[#1A1A24]`}>
              <div className="font-display font-black text-3xl sm:text-4xl tracking-tighter" style={{ color: s.c }}><Counter value={s.v} /></div>
              <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mt-1">{s.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* SECURITY TRUST BAR */}
      <section className="max-w-6xl mx-auto px-6 py-10">
        <TrustBar />
      </section>

      {/* HOW IT WORKS */}
      <section className="max-w-6xl mx-auto px-6 py-24">
        <motion.div {...fadeUp} className="mb-12">
          <div className="text-xs font-mono tracking-[0.2em] uppercase text-zinc-500 mb-3">{t("landing.how_eyebrow")}</div>
          <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tighter">{t("landing.how_title")}</h2>
        </motion.div>
        <div className="grid md:grid-cols-3 gap-4">
          {steps.map((s, i) => (
            <motion.div key={i} {...fadeUp} transition={{ delay: i * 0.12, ease: EASE }}
              className="group bg-[#0F0F12] border border-[#1A1A24] border-l-2 border-l-transparent hover:border-l-[#E5FF00] hover:-translate-y-1 transition-all duration-300 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center text-[#E5FF00]"><s.i size={20} className="icon-pop" /></div>
                <span className="font-display font-black text-4xl text-[#1A1A24] group-hover:text-[#2A2A35] transition-colors">0{i + 1}</span>
              </div>
              <h3 className="font-display font-bold text-lg mb-2">{s.t}</h3>
              <p className="text-zinc-500 text-sm leading-relaxed">{s.d}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* FEATURES SHOWCASE */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <motion.div {...fadeUp} className="mb-16 text-center">
          <div className="text-xs font-mono tracking-[0.2em] uppercase text-zinc-500 mb-3">{t("landing.feat_eyebrow")}</div>
          <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tighter">{t("landing.feat_title")}</h2>
        </motion.div>
        <div className="space-y-20 lg:space-y-28">
          {features.map((f, i) => (
            <FeatureRow key={i} eyebrow={f.eyebrow} title={f.t} desc={f.d} bullets={f.b} accent={f.accent} reverse={i % 2 === 1} mockup={f.m} />
          ))}
        </div>
      </section>

      {/* CLOSING CTA */}
      <section className="relative border-y border-[#2A2A35] bg-[#0F0F12] py-28 px-6 overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-30" />
        <div className="absolute top-6 left-6 w-8 h-8 border-t-2 border-l-2 border-[#E5FF00]/60" />
        <div className="absolute bottom-6 right-6 w-8 h-8 border-b-2 border-r-2 border-[#E5FF00]/60" />
        <motion.div {...fadeUp} className="relative z-10 max-w-2xl mx-auto text-center">
          <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-4">{t("landing.cta_eyebrow")}</div>
          <h2 className="font-display font-black text-3xl sm:text-4xl lg:text-5xl tracking-tighter mb-4">{t("landing.cta_title")}</h2>
          <p className="text-zinc-400 text-base mb-8">{t("landing.cta_sub")}</p>
          <Link to="/register" data-testid="cta-bottom-btn" className="group inline-flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold px-8 py-4 hover:bg-[#D4EC00] transition-colors btn-volt">
            {t("landing.cta_btn")} <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </Link>
        </motion.div>
      </section>

      {/* FOOTER */}
      <footer className="bg-[#050505] border-t border-[#1A1A24] px-6 py-14">
        <div className="max-w-6xl mx-auto grid md:grid-cols-5 gap-10">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 bg-[#E5FF00] flex items-center justify-center"><Zap size={15} className="text-black" /></div>
              <span className="font-display font-black tracking-tighter">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
            </div>
            <p className="text-zinc-500 text-sm max-w-xs leading-relaxed">{t("landing.footer_bio")}</p>
          </div>
          <div>
            <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-4">{t("landing.footer_product")}</div>
            <ul className="space-y-2 text-sm text-zinc-400">
              <li><Link to="/security" className="hover:text-[#E5FF00] transition-colors">{t("landing.nav_security")}</Link></li>
              <li><Link to="/privacy-telemetry" className="hover:text-[#E5FF00] transition-colors">{t("landing.nav_privacy")}</Link></li>
              <li><Link to="/guida" className="hover:text-[#E5FF00] transition-colors">{t("landing.nav_guide")}</Link></li>
              <li><Link to="/changelog" className="hover:text-[#E5FF00] transition-colors">{t("landing.nav_changelog")}</Link></li>
              <li><Link to="/pricing" className="hover:text-[#E5FF00] transition-colors">{t("landing.nav_pricing")}</Link></li>
            </ul>
          </div>
          <FooterCommunity t={t} />
          <div>
            <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-4">{t("landing.footer_account")}</div>
            <ul className="space-y-2 text-sm text-zinc-400">
              <li><Link to="/login" className="hover:text-[#E5FF00] transition-colors">{t("landing.login")}</Link></li>
              <li><Link to="/register" className="hover:text-[#E5FF00] transition-colors">{t("landing.start")}</Link></li>
            </ul>
            <div className="flex items-center gap-2 mt-5 text-xs text-[#00FF66]"><ShieldCheck size={13} /> {t("landing.footer_status")}</div>
          </div>
        </div>
        <FooterLegal t={t} />
      </footer>
    </div>
  );
}
