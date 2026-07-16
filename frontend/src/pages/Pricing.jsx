import { Link } from "react-router-dom";
import { Check, HardDrive, Zap, Video, ArrowRight } from "lucide-react";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { usePageMeta } from "@/hooks/usePageMeta";

const COPY = {
  it: {
    meta_t: "Prezzi — FrameForge | Free, Pro e Creator",
    meta_d: "Piani FrameForge: Free (scan hardware, health score), Pro a 9,99€/mese (AI advisor, ottimizzazioni avanzate, storico, profili) e Creator a 19,99€/mese (ottimizzazione OBS, streaming health, alert).",
    eyebrow: "// pricing",
    title: "Prezzi chiari. Nessun trucco.",
    sub: "Inizia gratis, in locale. Passa a Pro o Creator quando vuoi più potenza. Prezzi informativi — i pagamenti arrivano presto.",
    per_month: "/mese",
    soon: "Presto disponibile",
    free_cta: "Inizia gratis",
    recommended: "Consigliato",
    tiers: [
      { key: "free", icon: HardDrive, name: "Free", price: "€0", accent: "#A1A1AA", items: ["Scan hardware", "Health score", "Raccomandazioni base"], cta: "start" },
      { key: "pro", icon: Zap, name: "Pro", price: "€9,99", accent: "#E5FF00", items: ["AI advisor", "Ottimizzazione avanzata", "Storico", "Profili"], cta: "soon", best: true },
      { key: "creator", icon: Video, name: "Creator", price: "€19,99", accent: "#00E0FF", items: ["Tutto di Pro", "Ottimizzazione OBS", "Streaming health", "Alert"], cta: "soon" },
    ],
  },
  en: {
    meta_t: "Pricing — FrameForge | Free, Pro and Creator",
    meta_d: "FrameForge plans: Free (hardware scan, health score), Pro at €9.99/mo (AI advisor, advanced optimization, history, profiles) and Creator at €19.99/mo (OBS optimization, streaming health, alerts).",
    eyebrow: "// pricing",
    title: "Clear pricing. No gimmicks.",
    sub: "Start free, locally. Move to Pro or Creator when you want more power. Informational pricing — payments coming soon.",
    per_month: "/mo",
    soon: "Coming soon",
    free_cta: "Start free",
    recommended: "Recommended",
    tiers: [
      { key: "free", icon: HardDrive, name: "Free", price: "€0", accent: "#A1A1AA", items: ["Hardware scan", "Health score", "Basic recommendations"], cta: "start" },
      { key: "pro", icon: Zap, name: "Pro", price: "€9.99", accent: "#E5FF00", items: ["AI advisor", "Advanced optimization", "History", "Profiles"], cta: "soon", best: true },
      { key: "creator", icon: Video, name: "Creator", price: "€19.99", accent: "#00E0FF", items: ["Everything in Pro", "OBS optimization", "Streaming health", "Alerts"], cta: "soon" },
    ],
  },
};

export default function Pricing() {
  const lang = useLang();
  const c = COPY[lang];
  usePageMeta(c.meta_t, c.meta_d);
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <MarketingNav />
      <main className="max-w-6xl mx-auto px-6 pt-28 pb-20">
        <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-3">{c.eyebrow}</div>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter mb-4">{c.title}</h1>
        <p className="text-zinc-400 text-base sm:text-lg max-w-xl leading-relaxed mb-14">{c.sub}</p>

        <div className="grid md:grid-cols-3 gap-4 items-stretch">
          {c.tiers.map((t) => (
            <div key={t.key} data-testid={`pricing-${t.key}`}
              className={`relative flex flex-col bg-[#0F0F12] p-7 ${t.best ? "border-2 border-[#E5FF00]" : "border border-[#2A2A35]"}`}>
              {t.best && (
                <span className="absolute -top-3 left-7 bg-[#E5FF00] text-black text-[10px] font-mono uppercase tracking-widest px-2 py-1">{c.recommended}</span>
              )}
              <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center mb-4" style={{ color: t.accent }}><t.icon size={20} /></div>
              <h2 className="font-display font-black text-2xl tracking-tight mb-1">{t.name}</h2>
              <div className="flex items-baseline gap-1 mb-6">
                <span className="font-display font-black text-4xl" style={{ color: t.accent }}>{t.price}</span>
                {t.key !== "free" && <span className="text-sm text-zinc-500">{c.per_month}</span>}
              </div>
              <ul className="space-y-2.5 mb-8 flex-1">
                {t.items.map((it, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-zinc-300"><Check size={15} className="shrink-0 mt-0.5" style={{ color: t.accent }} /> {it}</li>
                ))}
              </ul>
              {t.cta === "start" ? (
                <Link to="/register" data-testid={`pricing-cta-${t.key}`}
                  className="group inline-flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors btn-volt uppercase tracking-wide text-sm">
                  {c.free_cta} <ArrowRight size={15} className="group-hover:translate-x-1 transition-transform" />
                </Link>
              ) : (
                <button disabled data-testid={`pricing-cta-${t.key}`}
                  className="inline-flex items-center justify-center gap-2 border border-[#2A2A35] text-zinc-500 py-3 uppercase tracking-wide text-sm cursor-not-allowed">
                  {c.soon}
                </button>
              )}
            </div>
          ))}
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
