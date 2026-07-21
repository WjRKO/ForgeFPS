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
      it: ["Firma digitale dell'agent (SignPath) — elimina l'avviso antivirus", "Bottleneck detector real-time nella pagina Live"],
      en: ["Agent code signing (SignPath) — removes the antivirus warning", "Real-time bottleneck detector on the Live page"],
    },
  },
  planned: {
    icon: CircleDot, color: "#00E0FF", it: "Pianificato", en: "Planned",
    items: {
      it: ["Alert salute PC: avviso quando il punteggio scende sotto la media 30 giorni", "Storico sessioni gaming con analisi post-match", "Abbonamenti Free / Pro / Creator con checkout"],
      en: ["PC health alerts: notify when the score drops below the 30-day average", "Gaming session history with post-match analysis", "Free / Pro / Creator plans with checkout"],
    },
  },
  exploring: {
    icon: Lightbulb, color: "#B388FF", it: "In valutazione", en: "Exploring",
    items: {
      it: ["Testimonianze utenti e contatore stelle GitHub", "Overlay in-game con FPS/temperature/latenza"],
      en: ["User testimonials and live GitHub stars counter", "In-game overlay with FPS/temperature/latency"],
    },
  },
};

const RELEASES = [
  {
    version: "0.7.2 (web + agent)", date: "2026-02-22",
    added: {
      it: [
        "**Monitor lifecycle**: pannello REC live con durata, sample count e gioco rilevato. Il bottone \u00abFerma\u00bb chiude il monitor sul PC in 1-2 secondi senza dover toccare la finestra locale.",
        "**Pre-flight checklist**: prima di avviare il monitor, una modal verifica agent, gioco in esecuzione, app in background e alert push. Zero sorprese durante il match.",
        "**Fase 3 \u2014 Benchmark contestuale**: card \u00abClassifica FrameForge\u00bb con percentile del tuo punteggio vs. la flotta e vs. utenti con CPU/GPU simile al tuo. Badge \u0394 before/after tweak.",
        "**Fase 4 \u2014 Storico visual**: sparkline 30 giorni del benchmark direttamente nell'header della pagina Benchmark; heatmap 7 giorni delle sync in \u00abIl mio PC\u00bb per gamification.",
        "**Guardrails benchmark**: se un gioco, OBS o un recorder sono attivi, il benchmark avvisa prima del lancio (evita run inquinati).",
        "**Sync Ambient v2**: auto-sync alla apertura della tab dopo pi\u00f9 di 24h e al ritorno di focus dopo 4h di idle. La dashboard \u00e8 sempre fresca senza cliccare nulla.",
        "**Fix caratteri glitchati nella GUI locale** (UTF-8 BOM aggiunto al payload PowerShell)."
      ],
      en: [
        "**Monitor lifecycle**: live REC panel with duration, sample count, and detected game. The \u00abStop\u00bb button closes the monitor on your PC within 1-2 seconds \u2014 no need to touch the local window.",
        "**Pre-flight checklist**: before launching the monitor, a modal checks agent, running game, background apps and push alerts. Zero surprises during the match.",
        "**Phase 3 \u2014 Contextual benchmark**: \u00abFrameForge leaderboard\u00bb card with your score percentile vs. the fleet and vs. users with similar CPU/GPU. \u0394 badge before/after tweak.",
        "**Phase 4 \u2014 Visual history**: 30-day benchmark sparkline right in the Benchmark page header; 7-day sync heatmap in \u00abMy PC\u00bb for gamification.",
        "**Benchmark guardrails**: if a game, OBS or a recorder is running, the benchmark warns you before launch (prevents polluted runs).",
        "**Ambient sync v2**: auto-sync when reopening the tab after 24h+ and on focus return after 4h idle. The dashboard is always fresh with zero clicks.",
        "**Fix garbled characters in the local GUI** (UTF-8 BOM added to the PowerShell payload)."
      ],
    },
    fixed: { it: [], en: [] },
    changed: { it: [], en: [] },
  },
  {
    version: "0.7.1 (agent)", date: "2026-02-19",
    added: {
      it: [
        "**Modalit\u00e0 silent**: le azioni Sync e Benchmark girano in background senza aprire la GUI Edge (bandiera `silent=1` nel URI firmato).",
        "**Auto-registrazione con `--backend`** nel comando di lancio: il protocollo `frameforge://` funziona anche se hai cambiato l'URL del backend (multi-ambiente).",
        "Hint informativo sotto ai bottoni: spiega perch\u00e9 il browser mostra il popup \u00abApri con FrameForge?\u00bb la prima volta (con dismiss persistente)."
      ],
      en: [
        "**Silent mode**: Sync and Benchmark run in the background without opening the Edge GUI (`silent=1` flag in the signed URI).",
        "**Auto-registration with `--backend`** in the launch command: the `frameforge://` protocol works even if you changed the backend URL (multi-environment).",
        "Informational hint under the buttons: explains why the browser shows the \u00abOpen with FrameForge?\u00bb popup on first use (dismissible)."
      ],
    },
    fixed: { it: [], en: [] },
    changed: { it: [], en: [] },
  },
  {
    version: "0.7.0 (agent)", date: "2026-02-15",
    added: {
      it: [
        "**Protocollo `frameforge://`**: al primo avvio dell'.exe viene registrato in HKCU. Da l\u00ec in poi i bottoni della dashboard (\u00abOttimizza\u00bb, \u00abBenchmark\u00bb, \u00abMonitor\u00bb) aprono la GUI locale direttamente sull'azione senza scaricare nulla.",
        "**Zero-download UX**: dopo l'installazione una tantum non serve pi\u00f9 copiare comandi PowerShell o token \u2014 tutto \u00e8 pilotato dal browser tramite URI firmato HMAC (scade in 60 secondi).",
        "Rimossa la modalit\u00e0 \u00abPrematch\u00bb e il menu interattivo CLI: la lista app viene ora gestita direttamente dal Booster."
      ],
      en: [
        "**`frameforge://` custom protocol**: registered in HKCU on first .exe launch. From then on the dashboard buttons (\u00abOptimize\u00bb, \u00abBenchmark\u00bb, \u00abMonitor\u00bb) open the local GUI straight to the action \u2014 no download needed.",
        "**Zero-download UX**: after a one-off install you no longer copy PowerShell commands or tokens \u2014 everything is driven from the browser via HMAC-signed URI (60s TTL).",
        "Removed the \u00abPrematch\u00bb mode and interactive CLI menu: the app list is now handled directly by the Booster."
      ],
    },
    fixed: { it: [], en: [] },
    changed: { it: [], en: [] },
  },
  {
    version: "0.6.8 (agent)", date: "2026-01-28",
    added: {
      it: [
        "**Token persistente** in `%APPDATA%\\FrameForge\\token.dat`: il primo lancio chiede il token una sola volta, poi la GUI parte istantanea senza prompt su ogni riavvio.",
        "Sync automatica di hardware e running_apps ad ogni apertura dell'agent (non solo su richiesta)."
      ],
      en: [
        "**Persistent token** in `%APPDATA%\\FrameForge\\token.dat`: the first launch asks for the token once, then the GUI starts instantly without prompts on every reboot.",
        "Automatic hardware + running_apps sync on every agent launch (not only on demand)."
      ],
    },
    fixed: { it: [], en: [] },
    changed: { it: [], en: [] },
  },
  {
    version: "0.6.7 (agent)", date: "2026-01-20",
    added: { it: [], en: [] },
    fixed: {
      it: [
        "**Falsi positivi Windows Defender eliminati**: passaggio dal pacchetto `--onefile` a `--onedir` (cartella + DLL). Bootloader PyInstaller non pi\u00f9 flaggato euristicamente.",
        "Download ora \u00e8 uno ZIP contenente `forgefps-agent.exe` + DLL + `Avvia-FrameForge.bat` per il primo lancio."
      ],
      en: [
        "**Windows Defender false positives gone**: switched from `--onefile` to `--onedir` bundle (folder + DLLs). PyInstaller bootloader is no longer heuristically flagged.",
        "Download is now a ZIP containing `forgefps-agent.exe` + DLLs + `Avvia-FrameForge.bat` for first launch."
      ],
    },
    changed: { it: [], en: [] },
  },
  {
    version: "0.6.5", date: "2026-07-19",
    added: {
      it: [
        "**La Diagnosi PC si ricorda**: torni sulla pagina Advisor e ritrovi l'ultima diagnosi salvata, con badge \u00abgenerata Xh fa\u00bb",
        "**Feedback \ud83d\udc4d/\ud83d\udc4e** su ogni azione della diagnosi e su ogni risposta della chat AI: sistema che migliora nel tempo",
        "**\u00abGi\u00e0 attivo\u00bb badge**: segna un tweak come gi\u00e0 applicato e l'AI non lo riproporr\u00e0 nelle prossime diagnosi",
        "**Come verificare**: ogni azione della diagnosi include ora una mini-guida espandibile con percorso Windows / comando PowerShell",
        "**Community insights**: l'AI riceve un riassunto dei tweak applicati dagli altri utenti con hardware simile al tuo",
        "**Outcome tracking**: badge \u00abDopo l'ultima diagnosi: +N punti benchmark\u00bb quando l'AI vede miglioramenti misurabili",
        "**Chat multi-modale**: allega uno screenshot (Task Manager, MSI Afterburner, BSOD, gioco) e l'AI lo analizza in vision",
        "**Modalit\u00e0 Coach**: 5 personas selezionabili dalla chat (Default, \ud83c\udfae FPS, \ud83c\udfac Streaming, \ud83d\udee0\ufe0f Troubleshoot, \ud83d\udcb0 Build)",
        "**Follow-up chips**: 3 suggerimenti cliccabili generati dall'AI dopo ogni risposta",
        "**Rigenera / Copia** su ogni risposta AI",
      ],
      en: [
        "**PC Diagnosis remembers itself**: come back to the Advisor page and find the last diagnosis restored, with \u00abgenerated Xh ago\u00bb badge",
        "**Feedback \ud83d\udc4d/\ud83d\udc4e** on every diagnosis action and AI chat response: continuous improvement loop",
        "**\u00abAlready active\u00bb badge**: mark a tweak as applied and the AI will stop suggesting it in future diagnoses",
        "**How to verify**: each diagnosis action now includes an expandable mini-guide with Windows path / PowerShell command",
        "**Community insights**: the AI receives a summary of tweaks applied by other users with similar hardware",
        "**Outcome tracking**: \u00abAfter last diagnosis: +N benchmark points\u00bb badge when measurable improvements are detected",
        "**Multi-modal chat**: attach a screenshot (Task Manager, MSI Afterburner, BSOD, game) and the AI analyzes it via vision",
        "**Coach modes**: 5 selectable personas in the chat (Default, \ud83c\udfae FPS, \ud83c\udfac Streaming, \ud83d\udee0\ufe0f Troubleshoot, \ud83d\udcb0 Build)",
        "**Follow-up chips**: 3 clickable suggestions generated by the AI after each response",
        "**Regenerate / Copy** on every AI response",
      ],
    },
    fixed: { it: [], en: [] },
    changed: { it: [], en: [] },
  },
  {
    version: "0.6.4", date: "2026-07-19",
    added: {
      it: [
        "**AI Advisor \u00abDiagnosi PC\u00bb**: un click e l'AI produce 3-5 azioni prioritizzate su misura del tuo hardware, con impatto stimato (+X FPS, -Y ms), difficolt\u00e0 e CTA per applicarle subito con l'agent",
        "L'AI Advisor ora riceve anche il trend degli ultimi benchmark, i problemi di salute attivi e il numero di prodotti nel tracker: le risposte sono molto pi\u00f9 personali",
        "Pulsante \u00abSalva per dopo\u00bb sulle azioni AI: crea una lista di todo che ritroverai in Dashboard",
        "Nuovi slash command Discord: **/help** (rich), **/come-iniziare**, **/ruoli**, **/canali** \u2014 mini-guide interattive per i nuovi membri",
        "Nuovo comando **/apply-creator** con approvazione staff: candidati al ruolo Creator Verified inviando un link Twitch/YouTube/Kick",
        "Ruolo **Boosted PC** ora si sincronizza automaticamente anche se colleghi Discord dopo aver linkato l'account",
      ],
      en: [
        "**AI Advisor \u00abPC Diagnosis\u00bb**: one click and the AI produces 3-5 prioritized actions tailored to your hardware, with estimated impact (+X FPS, -Y ms), difficulty and one-tap CTA to apply them with the agent",
        "AI Advisor now also receives benchmark trend, active health issues and tracker product count: replies are much more personal",
        "\u00abSave for later\u00bb button on AI actions: creates a todo list you'll find in the Dashboard",
        "New Discord slash commands: **/help** (rich), **/come-iniziare**, **/ruoli**, **/canali** \u2014 interactive mini-guides for new members",
        "New **/apply-creator** command with staff approval: apply for Creator Verified role by submitting a Twitch/YouTube/Kick link",
        "**Boosted PC** role now auto-syncs even if you link Discord after signing up",
      ],
    },
    fixed: {
      it: ["Email di contatto footer: sostituita con quella ufficiale forgefps.support@gmail.com. Al click ora copia negli appunti + toast, cos\u00ec funziona anche senza client di posta"],
      en: ["Contact email in footer: replaced with the official forgefps.support@gmail.com. Click now copies to clipboard + toast, so it works even without a mail client"],
    },
    changed: { it: [], en: [] },
  },
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
