import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu, Activity, Copy, Check, Gamepad2, Sparkles, ChevronDown, FileCheck2, Lock, History, AlertTriangle } from "lucide-react";
import { AGENT_EXE_URL, AGENT_EXE_SHA256, AGENT_EXE_VERSION, AGENT_EXE_DATE, AGENT_RELEASES_URL, AGENT_DEFAULT_BACKEND } from "@/config/agent";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const isEn = () => i18n.language?.startsWith("en");

const ACTIONS = [
  { icon: Gauge, title: "Benchmark prima/dopo", title_en: "Before/after benchmark", desc: "Misura CPU, RAM, disco e latenza di rete prima e dopo l'ottimizzazione per vedere il guadagno reale.", desc_en: "Measures CPU, RAM, disk and network latency before and after optimization to see the real gain." },
  { icon: Wind, title: "Pannello grafico a categorie", title_en: "Graphical panel by category", desc: "Il comando 'Ottimizza' apre una finestra con tab (Gaming/Latenza/Rete/Sistema), preset Competitivo/Streaming/Completo e 26 tweak con stato attuale.", desc_en: "The 'Optimize' command opens a window with tabs (Gaming/Latency/Network/System), Competitive/Streaming/Full presets and 26 tweaks with their current state." },
  { icon: Terminal, title: "Tweak pro NVIDIA/AMD/OBS", title_en: "Pro NVIDIA/AMD/OBS tweaks", desc: "MSI mode GPU (latenza DPC), MPO off (fix schermo nero OBS), timer resolution, OBS ad alta priorità, disabilita telemetria NVIDIA / ULPS AMD.", desc_en: "GPU MSI mode (DPC latency), MPO off (fixes OBS black screen), timer resolution, high-priority OBS, disable NVIDIA telemetry / AMD ULPS." },
  { icon: HardDrive, title: "Debloat & pulizia", title_en: "Debloat & cleanup", desc: "Rimuove app superflue, telemetria, ads di Windows e pulisce temp + cache Windows Update.", desc_en: "Removes bloatware, telemetry, Windows ads and cleans temp + Windows Update cache." },
  { icon: Cpu, title: "Rileva hardware/salute", title_en: "Detect hardware/health", desc: "Rileva CPU/GPU/RAM/temperature e le invia per analisi e consigli AI su misura.", desc_en: "Detects CPU/GPU/RAM/temperatures and sends them for tailored AI analysis and advice." },
  { icon: ShieldCheck, title: "Backup / Ripristino tweak", title_en: "Backup / Restore tweaks", desc: "Ogni modifica è salvata: ripristini tutto con un comando quando vuoi. Sicuro e reversibile.", desc_en: "Every change is saved: restore everything with one command whenever you want. Safe and reversible." },
];

const GPU_GUIDE = {
  nvidia: {
    label: "NVIDIA Control Panel",
    path: "Pannello di controllo NVIDIA → Gestisci impostazioni 3D → Impostazioni globali",
    path_en: "NVIDIA Control Panel → Manage 3D settings → Global settings",
    rows: [
      { s: "Modalità gestione energia", s_en: "Power management mode", v: "Prestazioni massime preferite", v_en: "Prefer maximum performance", w: "Tiene la GPU ai clock massimi, niente cali di frequenza.", w_en: "Keeps the GPU at maximum clocks, no frequency drops." },
      { s: "Modalità bassa latenza", s_en: "Low latency mode", v: "Ultra", v_en: "Ultra", w: "Riduce il ritardo di rendering: input più reattivo (competitive).", w_en: "Reduces render lag: more responsive input (competitive)." },
      { s: "Sync verticale (V-Sync)", s_en: "Vertical sync (V-Sync)", v: "Off (On solo con G-Sync)", v_en: "Off (On only with G-Sync)", w: "Meno input lag. Con G-Sync: V-Sync On + cap FPS.", w_en: "Less input lag. With G-Sync: V-Sync On + FPS cap." },
      { s: "Max Frame Rate", s_en: "Max Frame Rate", v: "3 FPS sotto il refresh (es. 141 per 144Hz)", v_en: "3 FPS below refresh (e.g. 141 for 144Hz)", w: "Con G-Sync evita tearing e mantiene la latenza minima.", w_en: "With G-Sync avoids tearing and keeps latency minimal." },
      { s: "Filtro texture - Qualità", s_en: "Texture filtering - Quality", v: "Prestazioni elevate", v_en: "High performance", w: "Più FPS con impatto visivo minimo.", w_en: "More FPS with minimal visual impact." },
      { s: "Threaded Optimization", s_en: "Threaded Optimization", v: "On", v_en: "On", w: "Distribuisce il carico driver su più core CPU.", w_en: "Spreads the driver load across multiple CPU cores." },
      { s: "Dimensione cache shader", s_en: "Shader cache size", v: "10 GB / Illimitata", v_en: "10 GB / Unlimited", w: "Meno stutter da compilazione shader.", w_en: "Less stutter from shader compilation." },
      { s: "Frequenza aggiornamento preferita", s_en: "Preferred refresh rate", v: "Massima disponibile", v_en: "Highest available", w: "Forza il refresh rate più alto del monitor.", w_en: "Forces the monitor's highest refresh rate." },
      { s: "Monitor Technology", s_en: "Monitor Technology", v: "G-SYNC (se supportato)", v_en: "G-SYNC (if supported)", w: "Sincronizzazione adattiva senza tearing.", w_en: "Adaptive sync without tearing." },
    ],
  },
  amd: {
    label: "AMD Adrenalin",
    path: "AMD Software: Adrenalin Edition → Gaming → Grafica",
    path_en: "AMD Software: Adrenalin Edition → Gaming → Graphics",
    rows: [
      { s: "Radeon Anti-Lag", s_en: "Radeon Anti-Lag", v: "Abilitato (Anti-Lag+ se disponibile)", v_en: "Enabled (Anti-Lag+ if available)", w: "Riduce la latenza di input nei giochi.", w_en: "Reduces input latency in games." },
      { s: "Radeon Chill", s_en: "Radeon Chill", v: "Disattivato", v_en: "Disabled", w: "Per competitive: nessun cap dinamico di FPS.", w_en: "For competitive: no dynamic FPS cap." },
      { s: "Wait for Vertical Refresh", s_en: "Wait for Vertical Refresh", v: "Off, salvo diversa indicazione", v_en: "Off, unless otherwise stated", w: "Meno input lag (usa FreeSync per il tearing).", w_en: "Less input lag (use FreeSync for tearing)." },
      { s: "Texture Filtering Quality", s_en: "Texture Filtering Quality", v: "Performance", v_en: "Performance", w: "Più FPS con impatto visivo minimo.", w_en: "More FPS with minimal visual impact." },
      { s: "Surface Format Optimization", s_en: "Surface Format Optimization", v: "On", v_en: "On", w: "Ottimizza l'uso della VRAM.", w_en: "Optimizes VRAM usage." },
      { s: "Tessellation Mode", s_en: "Tessellation Mode", v: "Override → AMD optimized / 8x", v_en: "Override → AMD optimized / 8x", w: "Meno carico GPU da tessellazione eccessiva.", w_en: "Less GPU load from excessive tessellation." },
      { s: "Enhanced Sync", s_en: "Enhanced Sync", v: "On (se non usi FreeSync)", v_en: "On (if not using FreeSync)", w: "Riduce tearing senza il lag del V-Sync classico.", w_en: "Reduces tearing without classic V-Sync lag." },
      { s: "FreeSync", s_en: "FreeSync", v: "On (nel monitor) + cap FPS", v_en: "On (in the monitor) + FPS cap", w: "Sincronizzazione adattiva: fluidità senza tearing.", w_en: "Adaptive sync: smoothness without tearing." },
      { s: "GPU Workload", s_en: "GPU Workload", v: "Graphics", v_en: "Graphics", w: "Massime prestazioni per il gaming (non compute).", w_en: "Maximum performance for gaming (not compute)." },
    ],
  },
};

function GpuGuide({ vendor }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState(vendor === "AMD" ? "amd" : "nvidia");
  useEffect(() => { if (vendor === "AMD") setTab("amd"); else if (vendor === "NVIDIA") setTab("nvidia"); }, [vendor]);
  const g = GPU_GUIDE[tab];
  const en = isEn();
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="gpu-guide-card">
      <div className="flex items-start gap-4 mb-4">
        <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center shrink-0"><Gamepad2 size={22} className="text-[#E5FF00]" /></div>
        <div>
          <h3 className="font-display font-bold text-lg">{t("desktop.gpu_title")}</h3>
          <p className="text-zinc-500 text-sm mt-1 max-w-2xl">{t("desktop.gpu_desc")}</p>
        </div>
      </div>
      <div className="flex gap-2 mb-4">
        {["nvidia", "amd"].map((k) => (
          <button key={k} data-testid={`gpu-tab-${k}`} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-bold transition-colors ${tab === k ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
            {GPU_GUIDE[k].label}{vendor === (k === "nvidia" ? "NVIDIA" : "AMD") ? ` ·  ${t("desktop.your_gpu")}` : ""}
          </button>
        ))}
      </div>
      <div className="text-xs text-zinc-500 mb-3 flex items-center gap-2"><Sparkles size={13} className="text-[#00E0FF]" /> {en ? g.path_en : g.path}</div>
      <div className="border border-[#1A1A24]">
        {g.rows.map((r, i) => (
          <div key={i} data-testid={`gpu-setting-${tab}-${i}`} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr] gap-1 sm:gap-4 p-3 border-b border-[#1A1A24] last:border-0">
            <div>
              <div className="text-sm text-zinc-200">{en ? r.s_en : r.s}</div>
              <div className="text-xs text-zinc-600 mt-0.5">{en ? r.w_en : r.w}</div>
            </div>
            <div className="text-sm font-bold text-[#00FF66] flex items-center">{en ? r.v_en : r.v}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs text-zinc-500 border-t border-[#1A1A24] pt-3">
        💡 {t("desktop.gpu_footer")}
      </div>
    </div>
  );
}

function CmdRow({ label, cmd, testid, accent }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); } catch { const t = document.createElement("textarea"); t.value = cmd; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success(i18n.t("desktop.copied")); setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="mb-3">
      <div className={`text-xs uppercase tracking-widest mb-1 ${accent || "text-zinc-500"}`}>{label}</div>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid={`${testid}-cmd`}>{cmd}</code>
        <button data-testid={`${testid}-copy`} onClick={copy}
          className="shrink-0 flex items-center gap-1 border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors text-xs">
          {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
        </button>
      </div>
    </div>
  );
}

const SECURE = {
  it: {
    exe_badge: "In arrivo", exe_title: "App desktop con un click", exe_desc: "Scarica l'app Windows (.exe) e avviala. Firma digitale in preparazione: al primo avvio Windows può mostrare «App non riconosciuta» → Ulteriori informazioni → Esegui comunque.",
    exe_btn: "Scarica FrameForge (.exe)", exe_run: "Fai doppio click e incolla il token quando richiesto — oppure da terminale:", exe_sha: "SHA256 dell'.exe",
    warn_title: "Importante: a quale server si collega l'app?",
    warn_desc_a: "Per impostazione predefinita l'.exe si collega a",
    warn_desc_b: "(produzione). Il token deve provenire dallo stesso sito a cui punta l'app: se lo copi da un ambiente diverso vedrai «Token non valido».",
    warn_prod: "Stai usando il sito di produzione: scarica il token qui sotto e avvia l'.exe normalmente.",
    warn_test: "Stai usando un ambiente di test/anteprima. Per far funzionare l'.exe con QUESTO ambiente (e questo token), aggiungi il parametro --backend:",
    av_note: "Alcuni antivirus (spesso Windows Defender) possono segnalare un falso positivo: è tipico degli .exe creati con PyInstaller, non è un vero virus. In quel caso usa il «Metodo sicuro» qui sotto (script .ps1, ispezionabile e non flaggato), oppure vedi la guida per firmare/segnalare l'app.",
    secure_title: "Metodo sicuro (consigliato)", secure_desc: "Niente comandi remoti. Scarichi lo script, ne verifichi l'integrità (SHA256) ed esegui il file locale. Puoi aprirlo e leggerlo prima di eseguirlo.",
    token_label: "Il tuo token (privato)",
    s1: "1) Scarica lo script (non lo esegue)", s2: "2) Verifica l'integrità: l'hash deve coincidere con quello qui sotto", s3: "3) Esegui il file locale (cambia -Mode per l'azione)",
    expected: "SHA256 atteso", modes_label: "Azioni disponibili (parametro -Mode)",
    why_title: "Perché non usiamo «irm | iex»", why_desc: "Scaricare ed eseguire codice remoto in memoria non è verificabile: se la connessione o il server fossero compromessi, verrebbe eseguito codice arbitrario. Con il metodo sopra il file resta su disco, ispezionabile e con hash verificabile.",
    why_link: "Scopri di più sulla sicurezza",
    adv: "Avanzato / per utenti esperti", exec_note: "Suggerimento: apri PowerShell come Amministratore per applicare tutti i tweak.",
  },
  en: {
    exe_badge: "Coming soon", exe_title: "One-click desktop app", exe_desc: "Download the Windows app (.exe) and launch it. Digital signature in progress: on first run Windows may show \u201cUnrecognized app\u201d \u2192 More info \u2192 Run anyway.",
    exe_btn: "Download FrameForge (.exe)", exe_run: "Double-click and paste the token when asked — or from a terminal:", exe_sha: ".exe SHA256",
    warn_title: "Important: which server does the app connect to?",
    warn_desc_a: "By default the .exe connects to",
    warn_desc_b: "(production). The token must come from the same site the app points to: if you copy it from a different environment you'll see \u201cInvalid token\u201d.",
    warn_prod: "You're on the production site: copy the token below and launch the .exe normally.",
    warn_test: "You're on a test/preview environment. To make the .exe work with THIS environment (and this token), add the --backend parameter:",
    av_note: "Some antivirus (often Windows Defender) may show a false positive: it's typical of PyInstaller .exe files, not a real virus. If it happens, use the \u201cSecure method\u201d below (.ps1 script, inspectable and not flagged), or see the guide to sign/report the app.",
    secure_title: "Secure method (recommended)", secure_desc: "No remote commands. Download the script, verify its integrity (SHA256) and run the local file. You can open and read it before running.",
    token_label: "Your token (private)",
    s1: "1) Download the script (does not run it)", s2: "2) Verify integrity: the hash must match the one below", s3: "3) Run the local file (change -Mode for the action)",
    expected: "Expected SHA256", modes_label: "Available actions (-Mode parameter)",
    why_title: "Why we don't use \u00abirm | iex\u00bb", why_desc: "Downloading and running remote code in memory isn't verifiable: if the connection or server were compromised, arbitrary code would run. With the method above the file stays on disk, inspectable and with a verifiable hash.",
    why_link: "Learn more about security",
    adv: "Advanced / for power users", exec_note: "Tip: open PowerShell as Administrator to apply all tweaks.",
  },
};

const RUN_MODES = [
  { m: "optimize", it: "Ottimizza (finestra grafica)", en: "Optimize (graphical window)" },
  { m: "sync", it: "Rileva hardware/salute", en: "Detect hardware/health" },
  { m: "benchmark", it: "Benchmark prima/dopo", en: "Before/after benchmark" },
  { m: "monitor", it: "Monitor live", en: "Live monitor" },
  { m: "prematch", it: "Prima del match", en: "Pre-match" },
  { m: "restore", it: "Ripristina i tweak", en: "Restore tweaks" },
];

export default function DesktopAgent() {
  const { t } = useTranslation();
  const [token, setToken] = useState("");
  const [sha, setSha] = useState("");
  const [gpuVendor, setGpuVendor] = useState(null);
  const [advOpen, setAdvOpen] = useState(false);
  const en = isEn();
  const s = en ? SECURE.en : SECURE.it;

  useEffect(() => { api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {}); }, []);
  useEffect(() => {
    if (!token) return;
    api.get(`/agent/script-info?t=${token}`).then(({ data }) => setSha(data.sha256)).catch(() => {});
  }, [token]);
  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => {
      const gpu = (data?.data?.gpu || "").toUpperCase();
      if (/NVIDIA|GEFORCE|RTX|GTX/.test(gpu)) setGpuVendor("NVIDIA");
      else if (/AMD|RADEON|\bRX\b/.test(gpu)) setGpuVendor("AMD");
    }).catch(() => {});
  }, []);

  const tk = token || "IL_TUO_TOKEN";
  const isProd = (BACKEND || "").includes("forgefps.dev");
  const exeCmd = isProd
    ? `forgefps-agent.exe --token ${tk} --mode optimize`
    : `forgefps-agent.exe --backend "${BACKEND}" --token ${tk} --mode optimize`;
  const dl = `irm "${BACKEND}/api/agent/script?t=${tk}" -OutFile "$HOME\\Downloads\\forgefps.ps1"`;
  const verify = `Get-FileHash "$HOME\\Downloads\\forgefps.ps1" -Algorithm SHA256`;
  const run = (mode) => `powershell -ExecutionPolicy Bypass -File "$HOME\\Downloads\\forgefps.ps1" -Token ${tk} -Mode ${mode}`;

  return (
    <div className="max-w-5xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("desktop.eyebrow")}</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">{t("desktop.title")}</h1>
      </div>

      {/* One-click .exe */}
      <div className="bg-[#0F0F12] border border-[#00E0FF]/40 p-6 mb-4" data-testid="exe-teaser">
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 border border-[#00E0FF]/40 flex items-center justify-center shrink-0"><MonitorDown size={22} className="text-[#00E0FF]" /></div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-display font-bold text-lg">{s.exe_title}</h2>
              <span className="text-[10px] font-mono uppercase tracking-widest bg-[#00E0FF]/15 text-[#00E0FF] border border-[#00E0FF]/30 px-2 py-0.5">{AGENT_EXE_VERSION}</span>
            </div>
            <div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-zinc-500">
              <span className="inline-flex items-center gap-1"><History size={11} /> {en ? "Updated" : "Aggiornato"} {AGENT_EXE_DATE}</span>
              <a href={AGENT_RELEASES_URL} target="_blank" rel="noreferrer" data-testid="exe-releases-link" className="text-[#00E0FF] hover:underline">{en ? "All versions" : "Tutte le versioni"} →</a>
            </div>
            <p className="text-zinc-400 text-sm mt-1 max-w-2xl">{s.exe_desc}</p>
            <a href={AGENT_EXE_URL} target="_blank" rel="noreferrer" data-testid="exe-download-btn"
              className="mt-3 inline-flex items-center gap-2 bg-[#00E0FF] text-black font-bold px-5 py-2.5 text-sm uppercase tracking-wide hover:bg-[#33e8ff] transition-colors">
              <Download size={16} /> {s.exe_btn}
            </a>
            <div className="flex items-center gap-2 mt-3 text-xs">
              <FileCheck2 size={13} className="text-[#00FF66] shrink-0" />
              <span className="text-zinc-500">{s.exe_sha}:</span>
              <code className="text-zinc-300 break-all" data-testid="exe-sha256">{AGENT_EXE_SHA256}</code>
            </div>
            <div className="mt-3">
              <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{s.exe_run}</div>
              <CmdRow label="" cmd={exeCmd} testid="exe-run" accent="text-[#E5FF00]" />
            </div>

            {/* Backend / token mismatch notice */}
            <div className={`mt-3 border p-3.5 ${isProd ? "border-[#00FF66]/30 bg-[#00FF66]/5" : "border-[#FFAA00]/40 bg-[#FFAA00]/5"}`} data-testid="exe-backend-notice">
              <div className="flex items-start gap-2.5">
                <AlertTriangle size={16} className={`shrink-0 mt-0.5 ${isProd ? "text-[#00FF66]" : "text-[#FFAA00]"}`} />
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-zinc-200">{s.warn_title}</div>
                  <p className="text-xs text-zinc-400 leading-relaxed mt-1">
                    {s.warn_desc_a} <code className="text-[#00E0FF]">{AGENT_DEFAULT_BACKEND}</code> {s.warn_desc_b}
                  </p>
                  <p className={`text-xs leading-relaxed mt-2 ${isProd ? "text-[#00FF66]" : "text-[#FFAA00]"}`}>
                    {isProd ? s.warn_prod : s.warn_test}
                  </p>
                  {!isProd && (
                    <div className="mt-2">
                      <CmdRow label="" cmd={exeCmd} testid="exe-backend-cmd" accent="text-[#FFAA00]" />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Antivirus false-positive note */}
            <p className="mt-3 text-xs text-zinc-500 leading-relaxed flex items-start gap-2" data-testid="exe-av-note">
              <ShieldCheck size={13} className="text-[#00FF66] shrink-0 mt-0.5" />
              <span>{s.av_note}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Secure method */}
      <div className="bg-[#0F0F12] border border-[#E5FF00]/40 p-6 mb-4" data-testid="secure-method">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-11 h-11 bg-[#E5FF00] flex items-center justify-center shrink-0"><ShieldCheck size={22} className="text-black" /></div>
          <div>
            <h2 className="font-display font-bold text-lg">{s.secure_title}</h2>
            <p className="text-zinc-400 text-sm mt-1 max-w-2xl">{s.secure_desc}</p>
          </div>
        </div>

        <CmdRow label={s.token_label} cmd={token || "…"} testid="agent-token" accent="text-[#00E0FF]" />
        <CmdRow label={s.s1} cmd={dl} testid="secure-download" accent="text-[#00FF66]" />
        <div className="mb-3">
          <div className="text-xs uppercase tracking-widest mb-1 text-[#00E0FF]">{s.s2}</div>
          <div className="flex items-stretch gap-2">
            <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="secure-verify-cmd">{verify}</code>
          </div>
          <div className="flex items-center gap-2 mt-2 text-xs">
            <FileCheck2 size={13} className="text-[#00FF66] shrink-0" />
            <span className="text-zinc-500">{s.expected}:</span>
            <code className="text-zinc-300 break-all" data-testid="expected-sha256">{sha || "…"}</code>
          </div>
        </div>
        <CmdRow label={s.s3} cmd={run("optimize")} testid="secure-run" accent="text-[#E5FF00]" />

        <div className="mt-4 border-t border-[#1A1A24] pt-4 flex items-start gap-3">
          <Lock size={16} className="text-zinc-400 shrink-0 mt-0.5" />
          <div>
            <div className="text-sm text-zinc-200 font-semibold">{s.why_title}</div>
            <p className="text-xs text-zinc-500 max-w-2xl leading-relaxed mt-0.5">{s.why_desc}</p>
            <Link to="/security" data-testid="why-security-link" className="text-xs text-[#E5FF00] hover:underline mt-1 inline-block">{s.why_link} →</Link>
          </div>
        </div>
      </div>

      {/* Advanced (collapsed) */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] mb-6">
        <button onClick={() => setAdvOpen((v) => !v)} data-testid="advanced-toggle"
          className="w-full flex items-center justify-between px-6 py-4 text-left">
          <span className="flex items-center gap-2 text-sm font-semibold text-zinc-300"><Terminal size={16} className="text-zinc-500" /> {s.adv}</span>
          <ChevronDown size={18} className={`text-zinc-500 transition-transform ${advOpen ? "rotate-180" : ""}`} />
        </button>
        {advOpen && (
          <div className="px-6 pb-6" data-testid="advanced-content">
            <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{s.modes_label}</div>
            {RUN_MODES.map((rm) => (
              <CmdRow key={rm.m} label={en ? rm.en : rm.it} cmd={run(rm.m)} testid={`run-${rm.m}`} accent="text-zinc-500" />
            ))}
            <div className="flex flex-wrap gap-3 mt-4 border-t border-[#1A1A24] pt-4">
              <a data-testid="download-agent-btn" href={`${API}/desktop-agent/download`}
                className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 text-sm hover:border-[#E5FF00] transition-colors">
                <Download size={16} /> {t("desktop.download_py")}
              </a>
              <Link to="/app/pc" data-testid="to-mypc-btn"
                className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 text-sm hover:border-[#E5FF00] transition-colors">
                <Activity size={16} /> {t("desktop.see_mypc")}
              </Link>
            </div>
            <p className="text-xs text-zinc-600 mt-3">{s.exec_note}</p>
          </div>
        )}
      </div>

      <GpuGuide vendor={gpuVendor} />

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[#2A2A35] border border-[#2A2A35] stagger">
        {ACTIONS.map((a, i) => (
          <div key={i} className="bg-[#0F0F12] p-6 tile-hover">
            <a.icon size={20} className="text-[#E5FF00] mb-3 icon-pop" />
            <h3 className="font-display font-semibold text-base mb-1">{isEn() ? a.title_en : a.title}</h3>
            <p className="text-zinc-500 text-xs leading-relaxed">{isEn() ? a.desc_en : a.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
