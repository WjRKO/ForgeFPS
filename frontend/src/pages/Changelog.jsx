import { Plus, Wrench, RefreshCw, Github, Map } from "lucide-react";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { usePageMeta } from "@/hooks/usePageMeta";

const TAGS = {
  added: { icon: Plus, color: "#00FF66", it: "Aggiunto", en: "Added" },
  fixed: { icon: Wrench, color: "#00E0FF", it: "Risolto", en: "Fixed" },
  changed: { icon: RefreshCw, color: "#E5FF00", it: "Modificato", en: "Changed" },
};

const RELEASES = [
  {
    version: "0.4.5", date: "2026-07-17",
    added: { it: ["Scansione demo reale dal browser: hardware + test bufferbloat, senza account né download", "Demo interattiva dell'app in sola lettura", "Badge VirusTotal e trust bar di sicurezza", "Sezione FAQ \"È sicuro?\""], en: ["Real in-browser demo scan: hardware + bufferbloat test, no account or download", "Read-only interactive app demo", "VirusTotal badge and security trust bar", "\"Is it safe?\" FAQ section"] },
    fixed: { it: ["Consiglio RAM nella scansione rapida"], en: ["RAM tip in the quick scan"] },
    changed: { it: ["Consenso cookie (Consent Mode v2) per una misurazione conforme al GDPR"], en: ["Cookie consent (Consent Mode v2) for GDPR-compliant measurement"] },
  },
  {
    version: "0.4.2", date: "2026-07-09",
    added: { it: ["Supporto GPU RTX serie 50", "Rilevamento temperatura Ryzen", "Ottimizzazione OBS per streaming"], en: ["RTX 50 series GPU support", "Ryzen temperature detection", "OBS streaming optimization"] },
    fixed: { it: ["Blocco file durante il rilevamento FPS", "Etichette Health Score mancanti"], en: ["File lock during FPS detection", "Missing Health Score labels"] },
    changed: { it: ["Installer sicuro senza script remoti"], en: ["Secure installer without remote scripts"] },
  },
  {
    version: "0.4.0", date: "2026-06-28",
    added: { it: ["Test Bufferbloat & latenza di rete (voto A–F)", "Input lag reale via PresentMon", "Riepilogo sessione condivisibile"], en: ["Bufferbloat & network latency test (A–F grade)", "Real input lag via PresentMon", "Shareable session summary"] },
    fixed: { it: ["Auto-detect giochi (Steam, Epic, EA, Riot, GOG)"], en: ["Game auto-detection (Steam, Epic, EA, Riot, GOG)"] },
    changed: { it: ["Telemetria live con polling a 1s"], en: ["Live telemetry with 1s polling"] },
  },
  {
    version: "0.3.0", date: "2026-06-10",
    added: { it: ["AI Advisor contestuale sull'hardware", "Price tracker con notifiche push"], en: ["Hardware-aware AI Advisor", "Price tracker with push notifications"] },
    fixed: { it: [], en: [] },
    changed: { it: ["Health score con diagnostica per componente"], en: ["Health score with per-component diagnostics"] },
  },
];

const COPY = {
  it: { meta_t: "Changelog — FrameForge | Note di rilascio", meta_d: "Tutte le novità di FrameForge versione per versione: nuove funzioni, correzioni e miglioramenti. Roadmap e issue tracker pubblici.", eyebrow: "// changelog", title: "Cosa cambia, versione per versione.", sub: "Aggiornamenti trasparenti. Ogni release è documentata: nuove funzioni, fix e modifiche.", roadmap: "Roadmap pubblica", issues: "Issue tracker" },
  en: { meta_t: "Changelog — FrameForge | Release notes", meta_d: "Everything new in FrameForge version by version: new features, fixes and improvements. Public roadmap and issue tracker.", eyebrow: "// changelog", title: "What changes, version by version.", sub: "Transparent updates. Every release is documented: new features, fixes and changes.", roadmap: "Public roadmap", issues: "Issue tracker" },
};

const Section = ({ tagKey, items, lang }) => {
  if (!items || !items.length) return null;
  const tg = TAGS[tagKey];
  return (
    <div className="mb-3">
      <div className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-widest mb-1.5" style={{ color: tg.color }}>
        <tg.icon size={12} /> {tg[lang]}
      </div>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i} className="text-sm text-zinc-300 flex gap-2"><span className="text-zinc-600">—</span>{it}</li>
        ))}
      </ul>
    </div>
  );
};

export default function Changelog() {
  const lang = useLang();
  const c = COPY[lang];
  usePageMeta(c.meta_t, c.meta_d);
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <MarketingNav />
      <main className="max-w-4xl mx-auto px-6 pt-28 pb-20">
        <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-3">{c.eyebrow}</div>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter mb-4">{c.title}</h1>
        <p className="text-zinc-400 text-base sm:text-lg max-w-xl leading-relaxed mb-8">{c.sub}</p>

        <div className="flex flex-wrap gap-3 mb-14">
          <a href="https://github.com" target="_blank" rel="noreferrer" data-testid="roadmap-link"
            className="inline-flex items-center gap-2 border border-[#2A2A35] px-4 py-2 text-sm hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors"><Map size={15} /> {c.roadmap}</a>
          <a href="https://github.com" target="_blank" rel="noreferrer" data-testid="issues-link"
            className="inline-flex items-center gap-2 border border-[#2A2A35] px-4 py-2 text-sm hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors"><Github size={15} /> {c.issues}</a>
        </div>

        <div className="relative border-l border-[#1A1A24] pl-6 ml-1 space-y-10">
          {RELEASES.map((r, i) => (
            <div key={i} className="relative" data-testid={`release-${r.version}`}>
              <span className="absolute -left-[29px] top-1.5 w-3 h-3 bg-[#E5FF00]" />
              <div className="flex items-baseline gap-3 mb-4">
                <span className="font-display font-black text-xl tracking-tight">v{r.version}</span>
                <span className="text-xs font-mono text-zinc-500">{r.date}</span>
              </div>
              <div className="bg-[#0F0F12] border border-[#1A1A24] p-5">
                <Section tagKey="added" items={r.added[lang]} lang={lang} />
                <Section tagKey="fixed" items={r.fixed[lang]} lang={lang} />
                <Section tagKey="changed" items={r.changed[lang]} lang={lang} />
              </div>
            </div>
          ))}
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
