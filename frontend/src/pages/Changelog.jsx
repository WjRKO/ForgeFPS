import { Plus, Wrench, RefreshCw, Github, Map, Loader2, CircleDot, Lightbulb } from "lucide-react";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { usePageMeta } from "@/hooks/usePageMeta";
import { AGENT_REPO_URL } from "@/config/agent";

const TAGS = {
  added: { icon: Plus, color: "#00FF66", it: "Aggiunto", en: "Added" },
  fixed: { icon: Wrench, color: "#00E0FF", it: "Risolto", en: "Fixed" },
  changed: { icon: RefreshCw, color: "#E5FF00", it: "Modificato", en: "Changed" },
};

const ROADMAP = {
  progress: {
    icon: Loader2, color: "#E5FF00", it: "In corso", en: "In progress",
    items: {
      it: ["Firma digitale dell'agent (SignPath) — elimina l'avviso antivirus", "Build \u00ab--onedir\u00bb per ridurre i falsi positivi \u201cdropper\u201d"],
      en: ["Agent code signing (SignPath) — removes the antivirus warning", "\u00ab--onedir\u00bb build to reduce \u201cdropper\u201d false positives"],
    },
  },
  planned: {
    icon: CircleDot, color: "#00E0FF", it: "Pianificato", en: "Planned",
    items: {
      it: ["Alert salute PC: avviso quando il punteggio scende sotto soglia", "Report PDF completo con grafico storico e checklist", "Abbonamenti Free / Pro / Creator con checkout"],
      en: ["PC health alerts: notify when the score drops below a threshold", "Full PDF report with historical chart and checklist", "Free / Pro / Creator plans with checkout"],
    },
  },
  exploring: {
    icon: Lightbulb, color: "#B388FF", it: "In valutazione", en: "Exploring",
    items: {
      it: ["Testimonianze utenti e contatore stelle GitHub", "Conversioni avanzate per una misurazione pi\u00f9 precisa"],
      en: ["User testimonials and live GitHub stars counter", "Enhanced conversions for more accurate measurement"],
    },
  },
};

const RELEASES = [
  {
    version: "0.6.3", date: "2026-07-18",
    added: {
      it: [
        "Footer ridisegnato con nuova colonna \u00abCommunity\u00bb: Discord con contatore live (\u00abXX online adesso\u00bb tramite widget del server), GitHub, Segnala un bug, email di contatto",
        "Nuova pagina \u00abTermini di servizio\u00bb (/terms): 9 sezioni chiare su cos'\u00e8 FrameForge, uso dell'agent, contenuti AI, prezzi, limitazione di responsabilit\u00e0 (IT + EN)",
        "Legal row nel footer: copyright, cookie policy, termini di servizio, privacy — tutto sempre a portata di click",
        "Firma \u00abCostruito con \u2764\ufe0f da un gamer per gamer\u00bb per una nota umana in fondo alla pagina",
        "Link \u00abGuida\u00bb nella colonna Prodotto del footer: rende scoperta la nuova pagina di onboarding",
      ],
      en: [
        "Redesigned footer with new \u00abCommunity\u00bb column: Discord with live counter (\u00abXX online now\u00bb via server widget), GitHub, Report a bug, contact email",
        "New \u00abTerms of service\u00bb page (/terms): 9 clear sections on what FrameForge is, agent usage, AI content, pricing, liability (IT + EN)",
        "Legal row in the footer: copyright, cookie policy, terms of service, privacy — always one click away",
        "\u00abBuilt with \u2764\ufe0f by a gamer for gamers\u00bb signature for a human touch at the bottom of the page",
        "\u00abGuide\u00bb link in the footer Product column: makes the new onboarding page discoverable",
      ],
    },
    fixed: {
      it: [
        "Pulsante \u00abApri il server\u00bb nella Dashboard: ora punta all'invito Discord reale (era un placeholder non valido)",
        "Annunci changelog duplicati su Discord: attivati controlli anti-duplicato con env var dedicata (l'annuncio parte solo dalla produzione)",
      ],
      en: [
        "\u00abOpen the server\u00bb button in the Dashboard: now points to the real Discord invite (was an invalid placeholder)",
        "Duplicate changelog announcements on Discord: added anti-duplicate controls via dedicated env var (only production announces)",
      ],
    },
    changed: { it: [], en: [] },
  },
  {
    version: "0.6.2", date: "2026-07-18",
    added: {
      it: [
        "Dashboard \u00abCommand Center\u00bb ridisegnata: Health Score del PC in evidenza, trend benchmark con mini-grafico e delta % vs precedente, feed attivit\u00e0 unificato (cali di prezzo + benchmark + nuove versioni agent)",
        "Checklist di onboarding sempre visibile nella Dashboard: 5 step (collega PC, primo benchmark, traccia prodotto, collega Discord, attiva 2FA) con barra di progresso animata che si nasconde quando completi tutto",
        "Preview video/GIF della GUI dell'agent nella pagina Desktop Agent: vedi l'app in azione prima di scaricarla, con fallback automatico a mock animato",
        "Empty state migliorati in Dashboard: nuovi utenti vedono 3 CTA giganti (Fai il primo scan, Genera una build, Traccia un prodotto) invece di card vuote",
        "Saluto contestuale in Dashboard: mostra il tuo health score o il totale risparmiato non appena hai dati",
      ],
      en: [
        "Redesigned \u00abCommand Center\u00bb Dashboard: PC Health Score front and center, benchmark trend with sparkline and % delta vs previous, unified activity feed (price drops + benchmarks + new agent releases)",
        "Always-visible onboarding checklist in the Dashboard: 5 steps (connect PC, first benchmark, track a product, link Discord, enable 2FA) with animated progress bar that hides once complete",
        "Live GIF/video preview of the agent GUI on the Desktop Agent page: see the app in action before downloading, with automatic fallback to an animated mock",
        "Improved Dashboard empty states: new users see 3 giant CTAs (Run first scan, Generate a build, Track a product) instead of empty cards",
        "Context-aware greeting on the Dashboard: shows your health score or total savings as soon as data is available",
      ],
    },
    fixed: { it: [], en: [] },
    changed: {
      it: [
        "Discord: bottone \u00abCondividi score\u00bb ora accessibile direttamente dalla Dashboard (prima solo dalla pagina Il mio PC)",
      ],
      en: [
        "Discord: \u00abShare score\u00bb button now accessible directly from the Dashboard (previously only from the My PC page)",
      ],
    },
  },
  {
    version: "0.6.1", date: "2026-07-18",
    added: {
      it: [
        "Nuova pagina Guida (/guida): 5 tutorial passo-passo per primo boost, setup gaming, streaming OBS, benchmark e ripristino",
        "Tour interattivo di benvenuto: al primo accesso ti facciamo un giro guidato di 60 secondi sulle sezioni principali",
        "Pulsante \u00abRifai il tour\u00bb nella pagina Account per riavviarlo quando vuoi",
      ],
      en: [
        "New Guide page (/guide): 5 step-by-step tutorials for first boost, gaming setup, OBS streaming, benchmark and restore",
        "Interactive onboarding tour: on first login we give you a 60-second guided walkthrough of the main sections",
        "\u00abRestart tour\u00bb button on the Account page to relaunch it anytime",
      ],
    },
    fixed: { it: [], en: [] },
    changed: { it: [], en: [] },
  },
  {
    version: "0.6.0", date: "2026-07-18",
    added: {
      it: [
        "Nuova interfaccia moderna dell'agent Windows: si apre in una finestra Edge dedicata (dark theme, ricerca tweak, animazioni fluide)",
        "Motore boost ADATTIVO: 35 ottimizzazioni che si adattano al tuo hardware (laptop vs desktop, SSD/HDD, RAM, GPU)",
        "Benchmark avanzato con punteggio 0-100 (latenza DPC, IOPS disco, jitter di rete) + spiegazione AI dei risultati",
        "Game Booster real-time OPT-IN: sospende le app pesanti quando lanci un gioco e le ripristina alla chiusura",
        "Badge \u00abGI\u00c0 ATTIVO\u00bb sui tweak gi\u00e0 ottimizzati: nessuna azione inutile, contatore \u00abda fare / totali\u00bb per categoria",
      ],
      en: [
        "New modern Windows agent interface: opens in a dedicated Edge window (dark theme, tweak search, smooth animations)",
        "ADAPTIVE boost engine: 35 tweaks that adapt to your hardware (laptop vs desktop, SSD/HDD, RAM, GPU)",
        "Advanced benchmark with 0-100 score (DPC latency, disk IOPS, network jitter) + AI explanation of results",
        "Real-time Game Booster (OPT-IN): suspends heavy apps when a game starts and restores them on exit",
        "\u00abALREADY ACTIVE\u00bb badge on already-optimized tweaks: no wasted actions, \u00abto-do / total\u00bb counter per category",
      ],
    },
    fixed: {
      it: ["Riconoscimento della finestra Edge quando \u00e8 gi\u00e0 aperto un browser (evita errore di connessione)"],
      en: ["Edge window detection when a browser is already open (avoids connection error)"],
    },
    changed: {
      it: [
        "Metadati exe (nome prodotto, editore, versione): riduce i falsi positivi degli antivirus",
        "Preset (Competitivo/Streaming/Completo) saltano automaticamente le ottimizzazioni gi\u00e0 attive",
      ],
      en: [
        "Exe metadata (product name, publisher, version): reduces antivirus false positives",
        "Presets (Competitive/Streaming/Complete) automatically skip already-active optimizations",
      ],
    },
  },
  {
    version: "0.4.5", date: "2026-07-17",
    added: { it: ["Roadmap pubblica e issue tracker collegati", "Scansione demo reale dal browser: hardware + test bufferbloat, senza account né download", "Demo interattiva dell'app in sola lettura", "Badge VirusTotal e trust bar di sicurezza", "Sezione FAQ \"È sicuro?\""], en: ["Public roadmap and issue tracker linked", "Real in-browser demo scan: hardware + bufferbloat test, no account or download", "Read-only interactive app demo", "VirusTotal badge and security trust bar", "\"Is it safe?\" FAQ section"] },
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
  it: { meta_t: "Changelog — FrameForge | Note di rilascio", meta_d: "Tutte le novità di FrameForge versione per versione: nuove funzioni, correzioni e miglioramenti. Roadmap e issue tracker pubblici.", eyebrow: "// changelog", title: "Cosa cambia, versione per versione.", sub: "Aggiornamenti trasparenti. Ogni release è documentata: nuove funzioni, fix e modifiche.", roadmap: "Roadmap pubblica", issues: "Issue tracker", roadmap_title: "Roadmap pubblica", roadmap_sub: "Su cosa stiamo lavorando e cosa arriverà. Trasparenza totale, come il resto del prodotto." },
  en: { meta_t: "Changelog — FrameForge | Release notes", meta_d: "Everything new in FrameForge version by version: new features, fixes and improvements. Public roadmap and issue tracker.", eyebrow: "// changelog", title: "What changes, version by version.", sub: "Transparent updates. Every release is documented: new features, fixes and changes.", roadmap: "Public roadmap", issues: "Issue tracker", roadmap_title: "Public roadmap", roadmap_sub: "What we're working on and what's coming. Full transparency, like the rest of the product." },
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
          <a href="#roadmap" data-testid="roadmap-link"
            className="inline-flex items-center gap-2 border border-[#2A2A35] px-4 py-2 text-sm hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors"><Map size={15} /> {c.roadmap}</a>
          <a href={`${AGENT_REPO_URL}/issues`} target="_blank" rel="noreferrer" data-testid="issues-link"
            className="inline-flex items-center gap-2 border border-[#2A2A35] px-4 py-2 text-sm hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors"><Github size={15} /> {c.issues}</a>
        </div>

        {/* Public roadmap */}
        <section id="roadmap" className="scroll-mt-24 mb-16" data-testid="roadmap-section">
          <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tight mb-2">{c.roadmap_title}</h2>
          <p className="text-zinc-500 text-sm mb-6 max-w-xl">{c.roadmap_sub}</p>
          <div className="grid md:grid-cols-3 gap-4">
            {["progress", "planned", "exploring"].map((key) => {
              const col = ROADMAP[key];
              return (
                <div key={key} className="bg-[#0F0F12] border border-[#1A1A24] p-5" data-testid={`roadmap-col-${key}`}>
                  <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest mb-4" style={{ color: col.color }}>
                    <col.icon size={13} className={key === "progress" ? "animate-spin" : ""} /> {col[lang]}
                  </div>
                  <ul className="space-y-3">
                    {col.items[lang].map((it, i) => (
                      <li key={i} className="text-sm text-zinc-300 flex gap-2 leading-relaxed">
                        <span className="mt-1.5 w-1.5 h-1.5 shrink-0" style={{ backgroundColor: col.color }} />
                        {it}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </section>

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
