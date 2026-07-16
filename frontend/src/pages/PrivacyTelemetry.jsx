import { Check, X, HardDrive, Cloud, Crown, Server } from "lucide-react";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { usePageMeta } from "@/hooks/usePageMeta";

const COPY = {
  it: {
    meta_t: "Privacy & Telemetria — FrameForge | Cosa raccogliamo (e cosa no)",
    meta_d: "Trasparenza totale: quali metriche hardware raccoglie FrameForge, cosa non raccoglie mai, e la modalità LOCAL ONLY per usare l'app senza inviare dati al cloud.",
    eyebrow: "// privacy & telemetry",
    title: "Sai sempre cosa esce dal tuo PC.",
    sub: "Raccogliamo solo le metriche hardware necessarie a migliorare le prestazioni. Niente dati personali, mai venduti a terzi.",
    collected: "Raccolto",
    never: "Mai raccolto",
    collected_list: ["Modello CPU", "Modello GPU", "RAM", "Temperature", "Benchmark FPS", "Metriche di performance"],
    never_list: ["Password", "Cronologia browser", "File", "Documenti", "Account di gioco", "Contenuti personali"],
    local_title: "Modalità LOCAL ONLY",
    local_d: "Puoi usare FrameForge senza inviare alcun dato al cloud: analisi hardware e ottimizzazioni girano interamente in locale sul tuo PC. I consigli AI e lo storico richiedono un account, ma restano opzionali.",
    tiers_title: "Cosa gira dove",
    tiers: [
      { icon: HardDrive, t: "Free", tag: "Local", items: ["Analisi locale", "Health score base", "Ottimizzazioni base"] },
      { icon: Cloud, t: "Cloud AI", tag: "Account", items: ["Consigli avanzati", "Storico", "Sincronizzazione account"] },
      { icon: Crown, t: "Pro", tag: "Full", items: ["Agent completo", "Automazioni", "Profili"] },
    ],
  },
  en: {
    meta_t: "Privacy & Telemetry — FrameForge | What we collect (and what we don't)",
    meta_d: "Full transparency: which hardware metrics FrameForge collects, what it never collects, and the LOCAL ONLY mode to use the app without sending any data to the cloud.",
    eyebrow: "// privacy & telemetry",
    title: "You always know what leaves your PC.",
    sub: "We only collect the hardware metrics needed to improve performance. No personal data, never sold to third parties.",
    collected: "Collected",
    never: "Never collected",
    collected_list: ["CPU model", "GPU model", "RAM", "Temperature", "FPS benchmark", "Performance metrics"],
    never_list: ["Password", "Browser history", "Files", "Documents", "Game accounts", "Personal content"],
    local_title: "LOCAL ONLY mode",
    local_d: "You can use FrameForge without sending any data to the cloud: hardware analysis and optimizations run entirely locally on your PC. AI advice and history require an account, but stay optional.",
    tiers_title: "What runs where",
    tiers: [
      { icon: HardDrive, t: "Free", tag: "Local", items: ["Local analysis", "Basic health score", "Basic optimizations"] },
      { icon: Cloud, t: "Cloud AI", tag: "Account", items: ["Advanced advice", "History", "Account sync"] },
      { icon: Crown, t: "Pro", tag: "Full", items: ["Full agent", "Automations", "Profiles"] },
    ],
  },
};

export default function PrivacyTelemetry() {
  const lang = useLang();
  const c = COPY[lang];
  usePageMeta(c.meta_t, c.meta_d);
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <MarketingNav />
      <main className="max-w-6xl mx-auto px-6 pt-28 pb-20">
        <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-3">{c.eyebrow}</div>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter mb-4 max-w-2xl">{c.title}</h1>
        <p className="text-zinc-400 text-base sm:text-lg max-w-xl leading-relaxed mb-14">{c.sub}</p>

        {/* Collected vs Never */}
        <div className="grid md:grid-cols-2 gap-4 mb-16">
          <div className="bg-[#0F0F12] border border-[#00FF66]/30 border-l-2 border-l-[#00FF66] p-6" data-testid="collected-col">
            <div className="text-xs font-mono uppercase tracking-widest text-[#00FF66] mb-4">{c.collected}</div>
            <ul className="space-y-3">
              {c.collected_list.map((it, i) => (
                <li key={i} className="flex items-center gap-3 text-sm text-zinc-200">
                  <span className="w-5 h-5 border border-[#00FF66] flex items-center justify-center shrink-0"><Check size={12} className="text-[#00FF66]" /></span>{it}
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-[#0F0F12] border border-[#FF3B30]/30 border-l-2 border-l-[#FF3B30] p-6" data-testid="never-col">
            <div className="text-xs font-mono uppercase tracking-widest text-[#FF3B30] mb-4">{c.never}</div>
            <ul className="space-y-3">
              {c.never_list.map((it, i) => (
                <li key={i} className="flex items-center gap-3 text-sm text-zinc-200">
                  <span className="w-5 h-5 border border-[#FF3B30] flex items-center justify-center shrink-0"><X size={12} className="text-[#FF3B30]" /></span>{it}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Local only */}
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-16 flex items-start gap-4" data-testid="local-only">
          <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center text-[#E5FF00] shrink-0"><Server size={20} /></div>
          <div>
            <h2 className="font-display font-black text-xl tracking-tight mb-2">{c.local_title}</h2>
            <p className="text-zinc-400 text-sm leading-relaxed max-w-2xl">{c.local_d}</p>
          </div>
        </div>

        {/* Tiers */}
        <h2 className="font-display font-black text-2xl tracking-tight mb-6">{c.tiers_title}</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {c.tiers.map((tier, i) => (
            <div key={i} className="bg-[#0F0F12] border border-[#1A1A24] p-6" data-testid={`tier-${tier.t.toLowerCase()}`}>
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 border border-[#2A2A35] flex items-center justify-center text-[#E5FF00]"><tier.icon size={18} /></div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 border border-[#1A1A24] px-2 py-1">[ {tier.tag} ]</span>
              </div>
              <h3 className="font-display font-bold text-lg mb-3">{tier.t}</h3>
              <ul className="space-y-2">
                {tier.items.map((it, j) => (
                  <li key={j} className="flex items-center gap-2 text-sm text-zinc-400"><Check size={13} className="text-[#00FF66] shrink-0" /> {it}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
