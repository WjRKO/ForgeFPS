import { useState } from "react";
import { Link } from "react-router-dom";
import { Rocket, Swords, Radio, Gauge, LifeBuoy, Clock, Copy, Check, ChevronRight, Monitor, Globe, BookOpen, PlayCircle } from "lucide-react";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { usePageMeta } from "@/hooks/usePageMeta";

const COPY = {
  it: {
    meta_t: "Guida — FrameForge | Tutorial e walkthrough",
    meta_d: "Impara a usare FrameForge in pochi minuti. Guide pratiche per il primo boost, setup gaming competitivo, streaming OBS, benchmark e ripristino.",
    eyebrow: "// guida",
    title: "Impara FrameForge in pochi minuti.",
    sub: "5 tutorial pratici, passo per passo. Nessun fronzolo: solo quello che ti serve per spingere il PC al massimo.",
    time: "min",
    copy: "Copia",
    copied: "Copiato",
    web: "Sul sito",
    desktop: "Sul PC",
    cta_h: "Pronto per il primo boost?",
    cta_sub: "Apri l'app FrameForge nel browser e segui la guida 1.",
    cta_btn: "Vai all'app",
    cta_agent: "Scarica l'agent",
  },
  en: {
    meta_t: "Guide — FrameForge | Tutorials and walkthroughs",
    meta_d: "Learn to use FrameForge in minutes. Hands-on guides for first boost, competitive gaming, OBS streaming, benchmark and restore.",
    eyebrow: "// guide",
    title: "Learn FrameForge in minutes.",
    sub: "5 hands-on tutorials, step by step. No fluff: just what you need to push your PC to the max.",
    time: "min",
    copy: "Copy",
    copied: "Copied",
    web: "In the app",
    desktop: "On your PC",
    cta_h: "Ready for your first boost?",
    cta_sub: "Open FrameForge in your browser and follow guide #1.",
    cta_btn: "Go to the app",
    cta_agent: "Download the agent",
  },
};

const GUIDES = [
  {
    id: "first-boost",
    icon: Rocket,
    tint: "#E5FF00",
    minutes: 3,
    it: {
      title: "Primo boost in 3 minuti",
      lead: "Dallo zero al primo tweak applicato. Il percorso più veloce per capire come funziona.",
      steps: [
        { where: "web", text: "Accedi all'app e vai su Dashboard → clicca su Il mio PC per vedere lo score attuale (0-100)." },
        { where: "web", text: "Apri la sezione Agent desktop dal menu laterale. Scarica l'eseguibile e copia il tuo Token." },
        { where: "desktop", text: "Apri PowerShell nella cartella dove hai salvato l'exe e lancia:", cmd: '.\\forgefps-agent.exe --token IL_TUO_TOKEN --mode optimize' },
        { where: "desktop", text: "Nella GUI Edge che si apre, clicca sul preset Competitivo. I tweak già attivi sono contrassegnati con GIÀ ATTIVO — non tocca nulla di inutile." },
        { where: "desktop", text: "Clicca Applica selezionati. Attendi il completamento (di solito 30-60s). Chiudi la finestra." },
        { where: "web", text: "Torna sul sito e ricarica Il mio PC: lo score è aggiornato. Se serve, riavvia il PC per consolidare le modifiche." },
      ],
      tips: [
        "Ogni modifica è reversibile: dal desktop puoi cliccare Ripristina tutto in fondo alla GUI.",
        "Il primo boost dura circa 3 minuti — successivi passaggi sono più veloci perché salti i tweak già attivi.",
      ],
    },
    en: {
      title: "First boost in 3 minutes",
      lead: "From zero to your first applied tweak. The fastest path to understanding the flow.",
      steps: [
        { where: "web", text: "Log into the app and go to Dashboard → click My PC to see your current score (0-100)." },
        { where: "web", text: "Open Desktop agent from the sidebar. Download the executable and copy your Token." },
        { where: "desktop", text: "Open PowerShell in the folder where you saved the exe and run:", cmd: '.\\forgefps-agent.exe --token YOUR_TOKEN --mode optimize' },
        { where: "desktop", text: "In the Edge GUI that opens, click the Competitive preset. Tweaks already active are marked ALREADY ACTIVE — nothing useless is touched." },
        { where: "desktop", text: "Click Apply selected. Wait for completion (usually 30-60s). Close the window." },
        { where: "web", text: "Back on the site, reload My PC: the score is updated. Reboot if needed to consolidate changes." },
      ],
      tips: [
        "Every change is reversible: in the desktop GUI you can click Restore all at the bottom.",
        "First boost takes about 3 minutes — later runs are faster because you skip already-active tweaks.",
      ],
    },
  },
  {
    id: "competitive",
    icon: Swords,
    tint: "#FF3355",
    minutes: 5,
    it: {
      title: "Setup gaming competitivo",
      lead: "Massima reattività per FPS/MOBA. Ottimizza input lag, DPC latency e process priority.",
      steps: [
        { where: "web", text: "Vai su Giochi. Aggiungi il tuo titolo principale (es. Valorant, CS2, Fortnite) e attiva il profilo Competitivo." },
        { where: "web", text: "Su Rete, lancia il test bufferbloat. Se il voto è C o peggiore, applica le raccomandazioni QoS/DNS che ti mostra." },
        { where: "desktop", text: "Lancia l'agent con:", cmd: '.\\forgefps-agent.exe --token IL_TUO_TOKEN --mode optimize' },
        { where: "desktop", text: "Nella GUI seleziona il preset Competitivo. Ai tweak base aggiungi manualmente: Mouse pointer precision OFF, Timer resolution 0.5ms, Ulps AMD OFF (se hai AMD)." },
        { where: "desktop", text: "Nel tab Latenza & Input controlla che il Timer resolution mostri 0.500 ms nello stato." },
        { where: "web", text: "Su Giochi attiva Game Booster per il tuo titolo: sospende Chrome/Discord/OneDrive quando lanci il gioco." },
      ],
      tips: [
        "Il Timer resolution 0.5 ms può disturbare app come video-editing/DAW: se le usi, ripristinalo dopo la sessione.",
        "Se hai una GPU NVIDIA, disattiva la telemetria NVIDIA (già presente nei preset).",
      ],
    },
    en: {
      title: "Competitive gaming setup",
      lead: "Max reactivity for FPS/MOBA. Optimizes input lag, DPC latency and process priority.",
      steps: [
        { where: "web", text: "Go to Games. Add your main title (Valorant, CS2, Fortnite, ...) and enable the Competitive profile." },
        { where: "web", text: "On Network, run the bufferbloat test. If the grade is C or worse, apply the QoS/DNS recommendations shown." },
        { where: "desktop", text: "Launch the agent with:", cmd: '.\\forgefps-agent.exe --token YOUR_TOKEN --mode optimize' },
        { where: "desktop", text: "In the GUI select the Competitive preset. Add manually: Mouse pointer precision OFF, Timer resolution 0.5 ms, AMD ULPS OFF (if you have AMD)." },
        { where: "desktop", text: "In the Latency & Input tab check that Timer resolution shows 0.500 ms in state." },
        { where: "web", text: "On Games enable Game Booster for your title: suspends Chrome/Discord/OneDrive when the game launches." },
      ],
      tips: [
        "0.5 ms timer resolution can disturb video-editing/DAW apps: restore it after the session if you use them.",
        "If you have an NVIDIA GPU, disable NVIDIA telemetry (already in the presets).",
      ],
    },
  },
  {
    id: "streaming",
    icon: Radio,
    tint: "#00E0FF",
    minutes: 5,
    it: {
      title: "Setup streaming con OBS",
      lead: "Frame drop a zero, encoder stabile, upload pulito. Il pack completo per streamer Twitch/YouTube.",
      steps: [
        { where: "web", text: "Su Rete verifica la banda upload: minimo 6 Mbps stabili per 1080p60. Se ti serve, applica le raccomandazioni bufferbloat." },
        { where: "desktop", text: "Lancia l'agent:", cmd: '.\\forgefps-agent.exe --token IL_TUO_TOKEN --mode optimize' },
        { where: "desktop", text: "Seleziona il preset Streaming. Verifica che sia attivo: OBS priorità alta, Game DVR OFF, MPO OFF." },
        { where: "desktop", text: "Applica. Alla fine controlla nel log che compaia OBS priorità impostata a HIGH." },
        { where: "web", text: "Vai su Dashboard → Advisor e chiedi: come configuro OBS per il mio hardware? — l'AI ti restituisce bitrate, encoder e keyframe suggeriti." },
      ],
      tips: [
        "Per streamer competitivi: mescola questo preset con i tweak di Latenza & Input della guida 2.",
        "Il preset non tocca microfono/audio: gestisci quelli direttamente in Windows Suoni.",
      ],
    },
    en: {
      title: "OBS streaming setup",
      lead: "Zero frame drop, stable encoder, clean upload. The complete pack for Twitch/YouTube streamers.",
      steps: [
        { where: "web", text: "On Network check upload bandwidth: minimum 6 Mbps stable for 1080p60. Apply bufferbloat fixes if suggested." },
        { where: "desktop", text: "Launch the agent:", cmd: '.\\forgefps-agent.exe --token YOUR_TOKEN --mode optimize' },
        { where: "desktop", text: "Pick the Streaming preset. Verify these are active: OBS priority HIGH, Game DVR OFF, MPO OFF." },
        { where: "desktop", text: "Apply. In the log look for OBS priority set to HIGH at the end." },
        { where: "web", text: "Go to Dashboard → Advisor and ask: how do I configure OBS for my hardware? — the AI returns bitrate, encoder and keyframe suggestions." },
      ],
      tips: [
        "For competitive streamers: mix this preset with the Latency & Input tweaks from guide 2.",
        "The preset does not touch microphone/audio: manage those directly in Windows Sound.",
      ],
    },
  },
  {
    id: "benchmark",
    icon: Gauge,
    tint: "#00FF66",
    minutes: 4,
    it: {
      title: "Leggere il benchmark 0-100",
      lead: "Cosa significano DPC latency, IOPS e jitter — e quali valori dovresti puntare.",
      steps: [
        { where: "desktop", text: "Nella GUI dell'agent attiva la spunta Benchmark PRIMA/DOPO in fondo alla finestra." },
        { where: "desktop", text: "Applica anche un solo tweak: al termine vedrai il punteggio composito e le 4 metriche." },
        { where: "web", text: "Su Il mio PC → Benchmark clicca Spiegami con AI: Claude analizza le tue metriche e ti dice se sono nella media per il tuo hardware." },
        { where: "web", text: "Valori di riferimento — DPC: < 500 μs ottimo, 500-2000 μs medio, > 2000 μs problematico. IOPS 4K R/W: > 30k SSD moderno. Jitter: < 5 ms in gioco." },
      ],
      tips: [
        "Se il DPC latency resta alto anche dopo il boost, quasi sempre è un driver di rete Wi-Fi o audio: aggiornali.",
        "Fai il benchmark sempre a PC riposo (nessuna app aperta) per avere numeri confrontabili.",
      ],
    },
    en: {
      title: "Reading the 0-100 benchmark",
      lead: "What DPC latency, IOPS and jitter mean — and which numbers you should target.",
      steps: [
        { where: "desktop", text: "In the agent GUI enable the Before/After benchmark checkbox at the bottom." },
        { where: "desktop", text: "Apply even a single tweak: at the end you'll see the composite score and the 4 metrics." },
        { where: "web", text: "On My PC → Benchmark click Explain with AI: Claude analyzes your metrics and tells you if they're average for your hardware." },
        { where: "web", text: "Reference values — DPC: < 500 μs great, 500-2000 μs average, > 2000 μs problematic. IOPS 4K R/W: > 30k modern SSD. Jitter: < 5 ms in-game." },
      ],
      tips: [
        "If DPC latency stays high after boost, it's almost always a Wi-Fi or audio driver: update them.",
        "Always run the benchmark on an idle PC (no apps open) for comparable numbers.",
      ],
    },
  },
  {
    id: "restore",
    icon: LifeBuoy,
    tint: "#FFAA00",
    minutes: 2,
    it: {
      title: "Se qualcosa va storto",
      lead: "Come annullare tutto in un click, disinstallare l'agent, o contattare il supporto.",
      steps: [
        { where: "desktop", text: "Nella GUI dell'agent, in basso a destra, clicca Ripristina tutto. Ogni tweak applicato viene revertito dal backup automatico." },
        { where: "desktop", text: "Per disinstallare completamente l'agent: cancella la cartella dove hai messo l'exe. Nessuna registrazione, nessun servizio installato." },
        { where: "web", text: "Su BIOS restore trovi la procedura completa per riportare anche il BIOS ai default (utile dopo overclock)." },
        { where: "web", text: "Se lo score non risale come previsto, apri un ticket su GitHub Issues del progetto (link nel Changelog) o scrivi al supporto." },
      ],
      tips: [
        "L'agent NON modifica MAI Windows Defender, Firewall o servizi di sicurezza: nessuna paura di rendere il PC insicuro.",
        "Il file di backup è in %APPDATA%\\FrameForge\\backup.json — copialo prima di reinstallare Windows se vuoi restore in futuro.",
      ],
    },
    en: {
      title: "When something goes wrong",
      lead: "How to undo everything with one click, uninstall the agent, or contact support.",
      steps: [
        { where: "desktop", text: "In the agent GUI, bottom right, click Restore all. Every applied tweak is reverted from the automatic backup." },
        { where: "desktop", text: "To fully uninstall the agent: delete the folder where you put the exe. No registry entries, no installed service." },
        { where: "web", text: "In BIOS restore you'll find the full procedure to also revert the BIOS to defaults (useful after overclock)." },
        { where: "web", text: "If the score doesn't rise as expected, open a ticket on the project GitHub Issues (link in the Changelog) or contact support." },
      ],
      tips: [
        "The agent NEVER touches Windows Defender, Firewall or security services: no risk of making your PC insecure.",
        "The backup file is at %APPDATA%\\FrameForge\\backup.json — copy it before reinstalling Windows if you want future restore.",
      ],
    },
  },
];

function CopyBtn({ text, lang }) {
  const c = COPY[lang];
  const [ok, setOk] = useState(false);
  const doCopy = async (e) => {
    e.preventDefault();
    try { await navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1400); } catch {}
  };
  return (
    <button onClick={doCopy} data-testid="guide-copy-btn"
      className={`ml-2 inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest px-2 py-1 border transition-colors ${ok ? "border-[#00FF66] text-[#00FF66]" : "border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00] hover:text-[#E5FF00]"}`}>
      {ok ? <Check size={12} /> : <Copy size={12} />} {ok ? c.copied : c.copy}
    </button>
  );
}

function GuideCard({ g, lang, idx }) {
  const c = COPY[lang];
  const g_t = g[lang];
  const Icon = g.icon;
  return (
    <section id={g.id} className="scroll-mt-24 mb-14" data-testid={`guide-${g.id}`}>
      <div className="flex items-center gap-4 mb-4">
        <div className="w-11 h-11 flex items-center justify-center shrink-0" style={{ backgroundColor: g.tint, color: "#000" }}>
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-0.5">GUIDA {String(idx + 1).padStart(2, "0")}</div>
          <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tight text-white">{g_t.title}</h2>
        </div>
        <div className="hidden sm:inline-flex items-center gap-1.5 border border-[#2A2A35] px-2.5 py-1 text-[11px] font-mono text-zinc-400">
          <Clock size={11} /> {g.minutes} {c.time}
        </div>
      </div>
      <p className="text-zinc-400 leading-relaxed mb-6 max-w-2xl">{g_t.lead}</p>

      <ol className="space-y-4 mb-6">
        {g_t.steps.map((s, i) => (
          <li key={i} className="flex gap-4">
            <div className="shrink-0 w-8 h-8 border border-[#2A2A35] flex items-center justify-center font-mono text-sm text-[#E5FF00]">{i + 1}</div>
            <div className="flex-1 min-w-0 pt-1">
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`inline-flex items-center gap-1 text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 ${s.where === "web" ? "text-[#00E0FF] border border-[#00E0FF]/40" : "text-[#E5FF00] border border-[#E5FF00]/40"}`}>
                  {s.where === "web" ? <Globe size={9} /> : <Monitor size={9} />} {s.where === "web" ? c.web : c.desktop}
                </span>
              </div>
              <div className="text-sm text-zinc-200 leading-relaxed">{s.text}</div>
              {s.cmd && (
                <div className="mt-2 bg-black border border-[#1A1A24] p-3 font-mono text-xs text-[#00FF66] flex items-start gap-2">
                  <code className="flex-1 whitespace-pre-wrap break-all">{s.cmd}</code>
                  <CopyBtn text={s.cmd} lang={lang} />
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>

      {g_t.tips && g_t.tips.length > 0 && (
        <div className="border-l-2 border-[#E5FF00] pl-4 py-2 bg-[#0F0F12]">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#E5FF00] mb-1.5">Tips</div>
          <ul className="space-y-1.5 text-sm text-zinc-300">
            {g_t.tips.map((tip, i) => (
              <li key={i} className="flex gap-2 leading-relaxed"><span className="text-zinc-600">—</span>{tip}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default function Guide() {
  const lang = useLang();
  const c = COPY[lang];
  usePageMeta(c.meta_t, c.meta_d);
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <MarketingNav />
      <main className="max-w-3xl mx-auto px-6 pt-28 pb-20">
        <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-3">{c.eyebrow}</div>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter mb-4">{c.title}</h1>
        <p className="text-zinc-400 text-base sm:text-lg max-w-xl leading-relaxed mb-10">{c.sub}</p>

        {/* TOC */}
        <nav className="mb-14 border-t border-[#1A1A24]" aria-label="Table of contents">
          {GUIDES.map((g, i) => {
            const Icon = g.icon;
            return (
              <a key={g.id} href={`#${g.id}`} data-testid={`toc-${g.id}`}
                className="group flex items-center gap-4 border-b border-[#1A1A24] py-4 hover:bg-[#0A0A0C] transition-colors">
                <div className="w-8 h-8 flex items-center justify-center shrink-0" style={{ backgroundColor: g.tint, color: "#000" }}>
                  <Icon size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">GUIDA {String(i + 1).padStart(2, "0")} · {g.minutes} {c.time}</div>
                  <div className="text-base font-bold text-zinc-100 group-hover:text-[#E5FF00] transition-colors">{g[lang].title}</div>
                </div>
                <ChevronRight size={18} className="text-zinc-600 group-hover:text-[#E5FF00] shrink-0 transition-colors" />
              </a>
            );
          })}
        </nav>

        {GUIDES.map((g, i) => (
          <GuideCard key={g.id} g={g} lang={lang} idx={i} />
        ))}

        {/* CTA */}
        <div className="mt-16 border border-[#2A2A35] p-8 bg-gradient-to-br from-[#0F0F12] to-[#050505]" data-testid="guide-cta">
          <div className="flex items-start gap-4">
            <PlayCircle size={28} className="text-[#E5FF00] shrink-0 mt-1" />
            <div className="flex-1">
              <h3 className="font-display font-black text-2xl tracking-tight mb-2">{c.cta_h}</h3>
              <p className="text-zinc-400 mb-5 max-w-xl">{c.cta_sub}</p>
              <div className="flex flex-wrap gap-3">
                <Link to="/login" data-testid="guide-cta-app"
                  className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 text-sm hover:bg-[#D4EC00] transition-colors btn-volt">
                  <BookOpen size={15} /> {c.cta_btn}
                </Link>
                <Link to="/#download" data-testid="guide-cta-agent"
                  className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 text-sm hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors">
                  <Monitor size={15} /> {c.cta_agent}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
