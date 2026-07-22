import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu, Activity, Copy, Check, Gamepad2, Sparkles, ChevronDown, FileCheck2, Lock, History, AlertTriangle, ExternalLink, Target } from "lucide-react";
import { AGENT_EXE_URL, AGENT_EXE_SHA256, AGENT_EXE_VERSION, AGENT_EXE_DATE, AGENT_RELEASES_URL, AGENT_DEFAULT_BACKEND } from "@/config/agent";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { trackConversion } from "@/lib/gtag";
import AgentPreview from "@/components/AgentPreview";
import FirstScanBanner from "@/components/FirstScanBanner";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const isEn = () => i18n.language?.startsWith("en");

const ACTIONS = [
  { icon: Gauge, title: "Benchmark prima/dopo", title_en: "Before/after benchmark", desc: "Misura CPU, RAM, disco e latenza di rete prima e dopo l'ottimizzazione per vedere il guadagno reale.", desc_en: "Measures CPU, RAM, disk and network latency before and after optimization to see the real gain." },
  { icon: Wind, title: "Pannello grafico adattivo", title_en: "Adaptive graphical panel", desc: "Il comando 'Ottimizza' apre una finestra con tab (Gaming/Latenza/Rete/Sistema), preset Competitivo/Streaming/Completo e 35 tweak che si adattano al TUO hardware: laptop vs desktop, SSD vs HDD, RAM, marca GPU.", desc_en: "The 'Optimize' command opens a window with tabs (Gaming/Latency/Network/System), Competitive/Streaming/Full presets and 35 tweaks that adapt to YOUR hardware: laptop vs desktop, SSD vs HDD, RAM, GPU brand." },
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
    exe_badge: "Nuovo", exe_title: "App desktop con un click", exe_desc: "Scarica lo ZIP dell'app Windows, estrailo e avvia forgefps-agent.exe. Da v0.6.7 usiamo il pacchetto onedir: niente falso positivo su Windows Defender.",
    exe_btn: "Scarica FrameForge (ZIP)", exe_run: "Estrai lo ZIP, entra nella cartella e doppio click su Avvia-FrameForge.bat — oppure da terminale:", exe_sha: "SHA256 del ZIP", exe_vt: "Verifica questo file su VirusTotal",
    exe_personalized_hint: "Il ZIP contiene il tuo token già dentro: estrai, apri la cartella e doppio click su Avvia-FrameForge.bat — la GUI parte senza incollare nulla.",
    bat_btn: "Scarica solo launcher (.bat)", bat_hint: "Se hai già il ZIP generico dal repo pubblico: mettilo accanto e doppio click.",
    warn_title: "Importante: a quale server si collega l'app?",
    warn_desc_a: "Per impostazione predefinita l'.exe si collega a",
    warn_desc_b: "(produzione). Il token deve provenire dallo stesso sito a cui punta l'app: se lo copi da un ambiente diverso vedrai «Token non valido».",
    warn_prod: "Stai usando il sito di produzione: scarica il token qui sotto e avvia l'.exe normalmente.",
    warn_test: "Stai usando un ambiente di test/anteprima. Per far funzionare l'.exe con QUESTO ambiente (e questo token), aggiungi il parametro --backend:",
    av_note: "Da v0.6.7 usiamo il pacchetto onedir (cartella + DLL): niente più falsi positivi euristici come nelle build --onefile precedenti. Se un vendor secondario dovesse ancora flaggarci, usa il «Metodo sicuro» qui sotto (script .ps1, ispezionabile).",
    secure_title: "Metodo sicuro (consigliato)", secure_desc: "Niente comandi remoti. Scarichi lo script, ne verifichi l'integrità (SHA256) ed esegui il file locale. Puoi aprirlo e leggerlo prima di eseguirlo.",
    token_label: "Il tuo token (privato)",
    s1: "1) Scarica lo script (non lo esegue)", s2: "2) Verifica l'integrità: l'hash deve coincidere con quello qui sotto", s3: "3) Esegui il file locale (cambia -Mode per l'azione)",
    expected: "SHA256 atteso", modes_label: "Azioni disponibili (parametro -Mode)",
    why_title: "Perché non usiamo «irm | iex»", why_desc: "Scaricare ed eseguire codice remoto in memoria non è verificabile: se la connessione o il server fossero compromessi, verrebbe eseguito codice arbitrario. Con il metodo sopra il file resta su disco, ispezionabile e con hash verificabile.",
    why_link: "Scopri di più sulla sicurezza",
    adv: "Avanzato / per utenti esperti", exec_note: "Suggerimento: apri PowerShell come Amministratore per applicare tutti i tweak.",
  },
  en: {
    exe_badge: "New", exe_title: "One-click desktop app", exe_desc: "Download the Windows app ZIP, extract it and run forgefps-agent.exe. Since v0.6.7 we ship an onedir bundle: no more Windows Defender false positive.",
    exe_btn: "Download FrameForge (ZIP)", exe_run: "Extract the ZIP, open the folder and double-click Avvia-FrameForge.bat — or from a terminal:", exe_sha: "ZIP SHA256", exe_vt: "Check this file on VirusTotal",
    exe_personalized_hint: "The ZIP has your token baked in: extract, open the folder and double-click Avvia-FrameForge.bat — GUI opens with zero prompts.",
    bat_btn: "Download launcher only (.bat)", bat_hint: "If you already have the public generic ZIP: drop this next to it and double-click.",
    warn_title: "Important: which server does the app connect to?",
    warn_desc_a: "By default the .exe connects to",
    warn_desc_b: "(production). The token must come from the same site the app points to: if you copy it from a different environment you'll see \u201cInvalid token\u201d.",
    warn_prod: "You're on the production site: copy the token below and launch the .exe normally.",
    warn_test: "You're on a test/preview environment. To make the .exe work with THIS environment (and this token), add the --backend parameter:",
    av_note: "Since v0.6.7 we ship an onedir bundle (folder + DLLs): the heuristic false positives from previous --onefile builds are gone. If a secondary vendor still flags us, use the \u201cSecure method\u201d below (.ps1 script, inspectable).",
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
  { m: "booster", it: "Game Booster (sorveglia e boosta i giochi)", en: "Game Booster (watch & boost games)" },
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

  const handleDownloadZip = async () => {
    trackConversion("agent_download");
    toast(en ? "Preparing your personalized ZIP..." : "Preparo il tuo ZIP personalizzato...");
    try {
      const resp = await api.get("/agent/download-zip", { responseType: "blob", timeout: 60000 });
      const url = window.URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url; a.download = "forgefps-agent.zip";
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(en ? "Download failed. Retry in a moment." : "Download fallito. Riprova tra un momento.");
    }
  };

  // v0.7.0+: chiama /api/agent/launch-uri per un URI firmato HMAC e apre la
  const tk = token || "IL_TUO_TOKEN";
  const isProd = (BACKEND || "").includes("forgefps.dev");
  const exeCmd = isProd
    ? `forgefps-agent.exe --token ${tk} --mode optimize`
    : `forgefps-agent.exe --backend "${BACKEND}" --token ${tk} --mode optimize`;
  const dl = `irm "${BACKEND}/api/agent/script?t=${tk}" -OutFile "$HOME\\Downloads\\forgefps.ps1"`;
  const verify = `Get-FileHash "$HOME\\Downloads\\forgefps.ps1" -Algorithm SHA256`;
  const run = (mode) => `powershell -ExecutionPolicy Bypass -File "$HOME\\Downloads\\forgefps.ps1" -Token ${tk} -Mode ${mode}`;

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("desktop.eyebrow")}</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">{t("desktop.title")}</h1>
        <p className="text-zinc-500 text-sm mt-2 max-w-2xl">{s.exe_desc}</p>
      </div>

      {/* First-scan banner: mostrato solo se l'utente non ha ancora fatto il primo sync */}
      <FirstScanBanner />

      <div className="grid lg:grid-cols-[1fr_360px] gap-6 items-start">
        {/* LEFT: content (scrolls) */}
        <div className="min-w-0 space-y-6">

          {/* Backend notice — mostrato solo se NON in prod */}
          {!isProd && (
            <div className="border border-[#FFAA00]/40 bg-[#FFAA00]/5 p-4" data-testid="exe-backend-notice">
              <div className="flex items-start gap-2.5">
                <AlertTriangle size={16} className="shrink-0 mt-0.5 text-[#FFAA00]" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-zinc-200">{s.warn_title}</div>
                  <p className="text-xs text-zinc-400 leading-relaxed mt-1">
                    {s.warn_desc_a} <code className="text-[#00E0FF]">{AGENT_DEFAULT_BACKEND}</code> {s.warn_desc_b}
                  </p>
                  <p className="text-xs text-[#FFAA00] leading-relaxed mt-2">{s.warn_test}</p>
                </div>
              </div>
            </div>
          )}

          {/* Feature grid: cosa fa l'app */}
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">{en ? "// what it does" : "// cosa fa"}</div>
            <div className="grid sm:grid-cols-2 gap-px bg-[#2A2A35] border border-[#2A2A35] stagger">
              {ACTIONS.map((a, i) => (
                <div key={i} className="bg-[#0F0F12] p-5 tile-hover">
                  <a.icon size={20} className="text-[#E5FF00] mb-3 icon-pop" />
                  <h3 className="font-display font-semibold text-base mb-1">{en ? a.title_en : a.title}</h3>
                  <p className="text-zinc-500 text-xs leading-relaxed">{en ? a.desc_en : a.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Antivirus note */}
          <div className="border border-[#00FF66]/25 bg-[#00FF66]/5 p-4 flex items-start gap-2.5" data-testid="exe-av-note">
            <ShieldCheck size={16} className="text-[#00FF66] shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-400 leading-relaxed">{s.av_note}</p>
          </div>

          {/* GPU Guide */}
          <GpuGuide vendor={gpuVendor} />

          {/* Secure PowerShell method — accordion collapsed */}
          <div className="bg-[#0F0F12] border border-[#E5FF00]/30" id="powershell-method">
            <button onClick={() => setAdvOpen((v) => !v)} data-testid="secure-toggle"
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[#141420] transition-colors">
              <span className="flex items-center gap-2.5">
                <ShieldCheck size={16} className="text-[#E5FF00]" />
                <span className="text-sm font-semibold text-zinc-200">{s.secure_title}</span>
                <span className="text-[10px] font-mono uppercase tracking-widest text-[#E5FF00] border border-[#E5FF00]/40 px-1.5 py-0.5">.ps1</span>
              </span>
              <ChevronDown size={18} className={`text-zinc-500 transition-transform ${advOpen ? "rotate-180" : ""}`} />
            </button>
            {advOpen && (
              <div className="px-5 pb-5 border-t border-[#1A1A24]" data-testid="secure-method">
                <p className="text-zinc-400 text-sm my-4 max-w-2xl">{s.secure_desc}</p>
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

                <div className="mt-5 border-t border-[#1A1A24] pt-4">
                  <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{s.modes_label}</div>
                  {RUN_MODES.map((rm) => (
                    <CmdRow key={rm.m} label={en ? rm.en : rm.it} cmd={run(rm.m)} testid={`run-${rm.m}`} accent="text-zinc-500" />
                  ))}
                </div>

                <div className="mt-4 border-t border-[#1A1A24] pt-4 flex items-start gap-3">
                  <Lock size={16} className="text-zinc-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-sm text-zinc-200 font-semibold">{s.why_title}</div>
                    <p className="text-xs text-zinc-500 max-w-2xl leading-relaxed mt-0.5">{s.why_desc}</p>
                    <Link to="/security" data-testid="why-security-link" className="text-xs text-[#E5FF00] hover:underline mt-1 inline-block">{s.why_link} →</Link>
                  </div>
                </div>

                <div className="flex flex-wrap gap-3 mt-4 border-t border-[#1A1A24] pt-4">
                  <a data-testid="download-agent-btn" href={`${API}/desktop-agent/download`} onClick={() => trackConversion("agent_download")}
                    className="inline-flex items-center gap-2 border border-[#2A2A35] px-4 py-2 text-sm hover:border-[#E5FF00] transition-colors">
                    <Download size={16} /> {t("desktop.download_py")}
                  </a>
                  <Link to="/app/pc" data-testid="to-mypc-btn"
                    className="inline-flex items-center gap-2 border border-[#2A2A35] px-4 py-2 text-sm hover:border-[#E5FF00] transition-colors">
                    <Activity size={16} /> {t("desktop.see_mypc")}
                  </Link>
                </div>
                <p className="text-xs text-zinc-600 mt-3">{s.exec_note}</p>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: sticky action panel */}
        <aside className="lg:sticky lg:top-6 lg:self-start" data-testid="exe-teaser">
          <div className="bg-gradient-to-br from-[#00E0FF]/15 to-[#0F0F12] border border-[#00E0FF]/40 p-5" data-testid="exe-download-block">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-10 h-10 border border-[#00E0FF]/40 flex items-center justify-center shrink-0"><MonitorDown size={20} className="text-[#00E0FF]" /></div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] font-mono uppercase tracking-widest text-[#00E0FF]">FrameForge Agent</div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">{AGENT_EXE_VERSION}</span>
                  <span className="text-[10px] text-zinc-500">·</span>
                  <span className="text-[10px] text-zinc-500 font-mono">{AGENT_EXE_DATE}</span>
                </div>
              </div>
            </div>

            {/* Preview GUI Edge (video/gif reale se presente, altrimenti mock animato) */}
            <AgentPreview label={en ? "Live GUI preview" : "Anteprima GUI live"} />

            <button type="button" data-testid="exe-download-btn"
              onClick={handleDownloadZip}
              className="flex items-center justify-center gap-2 bg-[#00E0FF] text-black font-bold py-3 text-sm uppercase tracking-wide hover:bg-[#33e8ff] transition-colors w-full">
              <Download size={16} /> {s.exe_btn}
            </button>
            <p className="mt-1.5 text-[10px] text-zinc-500 leading-relaxed px-1" data-testid="exe-personalized-hint">{s.exe_personalized_hint}</p>

            <a href={AGENT_RELEASES_URL} target="_blank" rel="noreferrer" data-testid="exe-releases-link"
              className="mt-2 flex items-center justify-center gap-1 text-[11px] font-mono text-zinc-400 hover:text-[#00E0FF] transition-colors">
              <History size={11} /> {en ? "All versions" : "Tutte le versioni"} <ExternalLink size={9} />
            </a>

            <div className="mt-4 pt-3 border-t border-[#2A2A35]">
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1.5 flex items-center gap-1.5">
                <FileCheck2 size={11} className="text-[#00FF66]" /> {s.exe_sha}
              </div>
              <code className="block text-[10px] text-zinc-400 font-mono break-all leading-relaxed" data-testid="exe-sha256">{AGENT_EXE_SHA256}</code>
              <a href={`https://www.virustotal.com/gui/file/${AGENT_EXE_SHA256}`} target="_blank" rel="noreferrer" data-testid="exe-virustotal"
                className="inline-flex items-center gap-1 mt-1.5 text-[11px] text-[#00FF66] hover:underline">
                <ShieldCheck size={12} /> {s.exe_vt} <ExternalLink size={9} />
              </a>
            </div>

            <div className="mt-4 pt-3 border-t border-[#2A2A35]">
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1.5">{s.exe_run}</div>
              <CmdRow label="" cmd={exeCmd} testid="exe-run" accent="text-[#E5FF00]" />
            </div>

            <a href="#powershell-method" onClick={() => setAdvOpen(true)}
              data-testid="jump-to-secure"
              className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-zinc-500 hover:text-[#E5FF00] transition-colors border-t border-[#2A2A35] pt-3">
              <ShieldCheck size={12} /> {en ? "Or use the secure PowerShell method" : "Oppure usa il metodo sicuro PowerShell"} ↓
            </a>
          </div>
        </aside>
      </div>
    </div>
  );
}
