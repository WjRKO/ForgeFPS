import { motion } from "framer-motion";
import { MonitorDown, Lock, BrainCircuit, ArrowRight, ArrowDown, ShieldCheck, KeyRound, EyeOff, FileSignature, GitBranch } from "lucide-react";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { SecureInstaller } from "@/components/SecureInstaller";
import { TrustBar } from "@/components/TrustBar";
import { SecurityFaq } from "@/components/SecurityFaq";
import { usePageMeta } from "@/hooks/usePageMeta";

const COPY = {
  it: {
    meta_t: "Sicurezza — FrameForge | Architettura local-first e binari firmati",
    meta_d: "Come FrameForge protegge il tuo PC: architettura local-first, nessuna raccolta password, binari firmati, changelog trasparente e installer verificabile.",
    eyebrow: "// security",
    title: "Security-first, per costruzione.",
    sub: "FrameForge non è un finto 'FPS booster'. È un prodotto trasparente: agent locale, API cifrata, nessun dato personale raccolto.",
    arch_title: "Architettura",
    arch: [
      { icon: MonitorDown, t: "Windows Agent", d: "Gira in locale, con privilegi minimi. Backup prima di ogni modifica, rollback sempre disponibile." },
      { icon: Lock, t: "API cifrata", d: "Solo metriche hardware anonime vengono inviate su connessione cifrata (HTTPS). Mai file o credenziali." },
      { icon: BrainCircuit, t: "AI Analysis", d: "L'AI elabora solo il contesto hardware per generare consigli. Le chiavi API restano lato server." },
    ],
    badges_title: "Garanzie",
    badges: [
      { icon: MonitorDown, t: "Local-first architecture" },
      { icon: KeyRound, t: "No password collection" },
      { icon: EyeOff, t: "No telemetry selling" },
      { icon: FileSignature, t: "Signed binaries" },
      { icon: GitBranch, t: "Transparent changelog" },
    ],
  },
  en: {
    meta_t: "Security — FrameForge | Local-first architecture & signed binaries",
    meta_d: "How FrameForge protects your PC: local-first architecture, no password collection, signed binaries, transparent changelog and a verifiable installer.",
    eyebrow: "// security",
    title: "Security-first, by design.",
    sub: "FrameForge is not a fake 'FPS booster'. It's a transparent product: local agent, encrypted API, no personal data collected.",
    arch_title: "Architecture",
    arch: [
      { icon: MonitorDown, t: "Windows Agent", d: "Runs locally, least-privilege. Backup before every change, rollback always available." },
      { icon: Lock, t: "Encrypted API", d: "Only anonymous hardware metrics are sent over an encrypted (HTTPS) connection. Never files or credentials." },
      { icon: BrainCircuit, t: "AI Analysis", d: "The AI only processes hardware context to generate advice. API keys stay server-side." },
    ],
    badges_title: "Guarantees",
    badges: [
      { icon: MonitorDown, t: "Local-first architecture" },
      { icon: KeyRound, t: "No password collection" },
      { icon: EyeOff, t: "No telemetry selling" },
      { icon: FileSignature, t: "Signed binaries" },
      { icon: GitBranch, t: "Transparent changelog" },
    ],
  },
};

export default function Security() {
  const lang = useLang();
  const c = COPY[lang];
  usePageMeta(c.meta_t, c.meta_d);
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <MarketingNav />
      <main className="max-w-6xl mx-auto px-6 pt-28 pb-20">
        <div className="grid-bg absolute inset-x-0 top-0 h-[400px] opacity-30 -z-0 pointer-events-none" />
        <div className="relative">
          <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-3">{c.eyebrow}</div>
          <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter mb-4 max-w-2xl">{c.title}</h1>
          <p className="text-zinc-400 text-base sm:text-lg max-w-xl leading-relaxed mb-14">{c.sub}</p>
        </div>

        {/* Architecture */}
        <section className="mb-16">
          <h2 className="font-display font-black text-2xl tracking-tight mb-6">{c.arch_title}</h2>
          <div className="grid md:grid-cols-3 gap-4 items-stretch relative">
            {c.arch.map((a, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.12 }}
                className="relative bg-[#0F0F12] border border-[#2A2A35] p-6" data-testid={`arch-node-${i}`}>
                <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center text-[#E5FF00] mb-4"><a.icon size={20} /></div>
                <h3 className="font-display font-bold text-lg mb-2">{a.t}</h3>
                <p className="text-zinc-500 text-sm leading-relaxed">{a.d}</p>
                {i < c.arch.length - 1 && (
                  <>
                    <ArrowRight className="hidden md:block absolute -right-[26px] top-1/2 -translate-y-1/2 text-[#E5FF00] z-10" size={18} />
                    <ArrowDown className="md:hidden mx-auto text-[#E5FF00] mt-3" size={18} />
                  </>
                )}
              </motion.div>
            ))}
          </div>
        </section>

        {/* Trust badges */}
        <section className="mb-16">
          <h2 className="font-display font-black text-2xl tracking-tight mb-6">{c.badges_title}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {c.badges.map((b, i) => (
              <div key={i} className="flex items-center gap-3 bg-[#0F0F12] border border-[#1A1A24] px-4 py-4" data-testid={`trust-badge-${i}`}>
                <div className="w-4 h-4 border border-[#00FF66] flex items-center justify-center shrink-0"><ShieldCheck size={11} className="text-[#00FF66]" /></div>
                <span className="text-sm text-zinc-200">{b.t}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Security FAQ */}
        <section className="mb-16">
          <SecurityFaq />
        </section>

        {/* Secure installer */}
        <section>
          <SecureInstaller />
        </section>
      </main>
      <MarketingFooter />
    </div>
  );
}
