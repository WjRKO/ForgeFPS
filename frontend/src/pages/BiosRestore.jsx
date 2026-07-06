import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Cpu, RotateCcw, CheckCircle2, AlertTriangle, ShieldCheck, Copy, Check, KeyRound, Info, Star, MemoryStick, MonitorPlay, MessageSquareCode } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const BIOS_KEYS = {
  ASUS: "Canc (Del) o F2",
  MSI: "Canc (Del)",
  Gigabyte: "Canc (Del) o F2",
  ASRock: "F2 o Canc (Del)",
  HP: "Esc poi F10 (o F10 all'avvio)",
  Lenovo: "F1 o F2 (o pulsante Novo)",
  Dell: "F2",
  Acer: "F2 o Canc (Del)",
  Biostar: "Canc (Del)",
};

// tag: cpu ("amd"|"intel"), gpu ("nvidia"|"amd"), impact (mostrato tra i consigliati),
// ramProfile / rebar => titolo e descrizione adattati all'hardware.
const BIOS_SAFE = [
  { id: "ram", ramProfile: true, impact: true, s: "XMP / EXPO / DOCP", w: "Attiva il profilo RAM: senza, la memoria gira a frequenza base e perdi FPS reali. È il tweak BIOS con più impatto." },
  { id: "rebar", rebar: true, impact: true, s: "Resizable BAR (ReBAR / SAM)", w: "ON. Guadagno prestazioni GPU gratuito. Richiede anche Above 4G Decoding: ON." },
  { id: "ftpm", s: "fTPM / PTT + Secure Boot", w: "ON. Obbligatori per Windows 11 e anti-cheat come Valorant/Vanguard, Faceit." },
  { id: "fan", s: "Fan curve personalizzata", w: "Imposta una curva più aggressiva per CPU/case: temperature più basse durante il gaming." },
  { id: "uefi", s: "Modalità UEFI (CSM off) + Fast Boot", w: "Boot più veloce e moderno. Necessario per Secure Boot." },
  { id: "pcie", s: "PCIe Gen4 per GPU/SSD NVMe", w: "Assicura la massima banda per scheda video e SSD." },
  { id: "ahci", s: "SATA mode: AHCI", w: "Corretto per gli SSD. NON cambiarlo se Windows è già installato (rischio boot)." },
  { id: "psi", cpu: "amd", s: "Power Supply Idle Control: Typical", w: "Su Ryzen previene i riavvii improvvisi in idle. Impostazione sicura." },
];

const BIOS_CAUTION = [
  { id: "co", cpu: "amd", impact: true, s: "Curve Optimizer / PBO (Ryzen)", w: "Undervolt/boost: ottimo per temp e prestazioni, ma può causare instabilità/crash. Testa con offset piccoli (es. -15) e prova la stabilità." },
  { id: "oc", s: "Overclock CPU / RAM manuale", w: "Frequenze/timing manuali possono impedire il boot. Solo se sai cosa fai; annota i valori di default." },
  { id: "bupd", s: "Aggiornamento BIOS", w: "Utile per stabilità/compatibilità, ma se interrotto (blackout) può brickare la scheda madre. Usa la funzione integrata (BIOS Flashback) e non spegnere durante l'update." },
  { id: "volt", s: "Voltaggi (vCore, SoC, DRAM)", w: "Voltaggi errati possono danneggiare o degradare i componenti. Zona a rischio: non toccare senza esperienza." },
  { id: "cstate", cpu: "amd", s: "Disattivare Global C-States", w: "Riduce micro-latenze ma aumenta temperature e consumi in idle. Solo per competitive estremo." },
  { id: "llc", s: "Load Line Calibration (LLC)", w: "Stabilizza il voltaggio sotto carico ma può alzare temperature/voltaggi reali. Impostazione avanzata." },
  { id: "disable", s: "Disabilitare dispositivi integrati", w: "Audio/LAN/USB off può far risparmiare risorse ma rischi di perdere funzionalità o periferiche." },
];

const RESTORE_SAFE = [
  { id: "sysrestore", s: "Crea un punto di ripristino", w: "Prima di ogni modifica importante: Cerca 'Crea un punto di ripristino' → Configura → Crea. Ti permette di tornare indietro senza perdere file." },
  { id: "boostrestore", s: "Ripristina i tweak BoostPC", w: "Annulla tutte le ottimizzazioni applicate (registro, servizi, DNS, power). Reversibile al 100% col comando qui sotto." },
  { id: "ddu", gpuDriver: true, s: "DDU (Display Driver Uninstaller)", w: "Rimuove completamente i driver GPU prima di reinstallarli puliti: risolve stutter/artefatti da driver corrotti." },
  { id: "sfc", s: "SFC /scannow", w: "Ripara i file di sistema danneggiati. In PowerShell admin: sfc /scannow." },
  { id: "dism", s: "DISM RestoreHealth", w: "Ripara l'immagine di Windows: DISM /Online /Cleanup-Image /RestoreHealth." },
];

const RESTORE_CAUTION = [
  { id: "resetkeep", s: "Reimposta il PC (mantieni i file)", w: "Reinstalla Windows conservando i file personali ma RIMUOVE i programmi installati. Impostazioni → Sistema → Ripristino → Reimposta il PC." },
  { id: "resetall", s: "Reimposta il PC (rimuovi tutto)", w: "Cancella TUTTO (file + programmi). Usa solo dopo un backup completo. Ideale prima di vendere il PC." },
  { id: "restorepoint", s: "Ripristino a un punto precedente", w: "Torna a uno stato passato: perdi programmi/driver installati dopo quel punto (i file personali restano)." },
  { id: "cmos", cmos: true, s: "Clear CMOS (reset BIOS)", w: "Riporta il BIOS ai default (utile se il PC non parte dopo un tweak). Fatto via jumper/pulsante o togliendo la batteria: annulla anche XMP/ReBAR." },
  { id: "cleaninstall", s: "Reinstallazione pulita di Windows", w: "Formattazione completa da USB. La soluzione più radicale: backup obbligatorio, richiede reinstallare tutto." },
];

function detectHardware(data) {
  const cpuStr = (data?.cpu || "").toLowerCase();
  const gpuStr = (data?.gpu || "").toLowerCase();
  let cpu = null;
  if (/ryzen|threadripper|athlon|\bamd\b/.test(cpuStr)) cpu = "amd";
  else if (/intel|core i|core ultra|pentium|celeron|xeon/.test(cpuStr)) cpu = "intel";
  let gpu = null;
  if (/nvidia|geforce|rtx|gtx|quadro/.test(gpuStr)) gpu = "nvidia";
  else if (/radeon|\brx ?\d|vega/.test(gpuStr)) gpu = "amd";
  else if (/\barc\b|intel/.test(gpuStr)) gpu = "intel";
  const ramType = (data?.ram_type || "").toUpperCase().includes("DDR5") ? "DDR5"
    : (data?.ram_type || "").toUpperCase().includes("DDR4") ? "DDR4" : null;
  return { cpu, gpu, ramType };
}

function adaptTweak(t, hw) {
  let { s, w } = t;
  if (t.ramProfile) {
    if (hw.cpu === "amd") {
      s = hw.ramType === "DDR5" ? "EXPO — profilo RAM AMD (DDR5)" : "DOCP / EXPO — profilo RAM AMD";
      w = "Attiva EXPO/DOCP nel BIOS: senza, la RAM gira lenta e perdi FPS. Sul tuo Ryzen è il tweak con più impatto reale.";
    } else if (hw.cpu === "intel") {
      s = hw.ramType === "DDR5" ? "XMP — profilo RAM Intel (DDR5)" : "XMP — profilo RAM Intel";
      w = "Attiva XMP nel BIOS: senza, la RAM resta alla frequenza base e limiti la CPU Intel. È il tweak BIOS con più impatto.";
    }
  }
  if (t.rebar) {
    if (hw.gpu === "nvidia") {
      s = "Resizable BAR (ReBAR)";
      w = "ON per la tua GeForce: prestazioni gratis in molti giochi. Richiede anche Above 4G Decoding: ON.";
    } else if (hw.gpu === "amd") {
      s = "Smart Access Memory (SAM / ReBAR)";
      w = "ON per la tua Radeon: SAM sfrutta la banda extra CPU↔GPU. Richiede Above 4G Decoding: ON.";
    } else if (hw.gpu === "intel") {
      s = "Resizable BAR (ReBAR)";
      w = "ON per la tua Intel Arc: fortemente consigliato, impatta molto le prestazioni. Richiede Above 4G Decoding: ON.";
    }
  }
  return { ...t, s, w };
}

function adaptRestore(t, hw, mbName) {
  let { s, w } = t;
  if (t.gpuDriver) {
    if (hw.gpu === "nvidia") w = "Rimuove del tutto i driver, poi reinstalla i GeForce Game Ready dal sito NVIDIA: risolve stutter/artefatti da driver corrotti.";
    else if (hw.gpu === "amd") w = "Rimuove del tutto i driver, poi reinstalla gli AMD Adrenalin dal sito AMD: risolve stutter/artefatti da driver corrotti.";
    else if (hw.gpu === "intel") w = "Rimuove del tutto i driver, poi reinstalla gli Intel Arc dal sito Intel: risolve stutter/artefatti da driver corrotti.";
  }
  if (t.cmos) {
    const ram = hw.cpu === "amd" ? (hw.ramType === "DDR5" ? "EXPO" : "DOCP/EXPO") : hw.cpu === "intel" ? "XMP" : "XMP/EXPO";
    const bar = hw.gpu === "amd" ? "SAM" : "ReBAR";
    const mb = mbName ? ` sulla tua ${mbName}` : "";
    w = `Riporta il BIOS ai default${mb} (utile se il PC non parte dopo un tweak). Attenzione: annulla anche ${ram} e ${bar}, da riattivare dopo.`;
  }
  return { ...t, s, w };
}

function filterForHardware(list, hw) {
  return list
    .filter((t) => {
      if (t.cpu && hw.cpu && t.cpu !== hw.cpu) return false;
      return true;
    })
    .map((t) => adaptTweak(t, hw));
}

function Row({ item, tone, i, section, onAsk }) {
  const Icon = tone === "safe" ? CheckCircle2 : AlertTriangle;
  const color = tone === "safe" ? "text-[#00FF66]" : "text-[#E5FF00]";
  return (
    <div className="flex gap-3 p-3 border-b border-[#1A1A24] last:border-0 items-start" data-testid={`${section}-${tone}-${item.id || i}`}>
      <Icon size={16} className={`${color} shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-zinc-100 font-semibold">{item.s}</div>
        <div className="text-xs text-zinc-500 mt-0.5 leading-relaxed">{item.w}</div>
      </div>
      {onAsk && (
        <button onClick={() => onAsk(item, tone)} data-testid={`ask-ai-${section}-${item.id || i}`}
          className="shrink-0 self-center inline-flex items-center gap-1 border border-[#2A2A35] px-2 py-1.5 text-[11px] text-zinc-400 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors whitespace-nowrap">
          <MessageSquareCode size={12} /> Chiedi all'AI
        </button>
      )}
    </div>
  );
}

const HW_LABEL = {
  cpu: { amd: "CPU AMD Ryzen", intel: "CPU Intel" },
  gpu: { nvidia: "GPU NVIDIA", amd: "GPU AMD Radeon", intel: "GPU Intel Arc" },
};

export default function BiosRestore() {
  const [tab, setTab] = useState("bios");
  const [specs, setSpecs] = useState(null);
  const [token, setToken] = useState("");
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
  }, []);

  const data = specs?.data || {};
  const hw = useMemo(() => detectHardware(data), [specs]);
  const hasHw = hw.cpu || hw.gpu;

  const safe = useMemo(() => filterForHardware(BIOS_SAFE, hw), [hw]);
  const caution = useMemo(() => filterForHardware(BIOS_CAUTION, hw), [hw]);
  const topPicks = useMemo(
    () => [...safe, ...caution].filter((t) => t.impact).slice(0, 3),
    [safe, caution]
  );

  const mb = ((data.motherboard || "") + " " + (data.system_model || "")).toUpperCase();
  let vendor = null;
  for (const v of Object.keys(BIOS_KEYS)) { if (mb.includes(v.toUpperCase())) { vendor = v; break; } }
  const key = vendor ? BIOS_KEYS[vendor] : "Canc (Del) o F2 (varia per marca)";

  const askAI = (item, tone) => {
    const hwStr = [data.cpu?.trim(), data.gpu, hw.ramType && `RAM ${hw.ramType}`].filter(Boolean).join(", ");
    const mbStr = data.motherboard ? ` sulla mia scheda madre ${data.motherboard}` : "";
    const q = tone === "caution"
      ? `Spiegami in dettaglio l'impostazione BIOS "${item.s}"${mbStr}: come si attiva passo-passo, quali rischi comporta e quali valori sicuri usare.${hwStr ? ` Il mio hardware: ${hwStr}.` : ""}`
      : `Spiegami passo-passo come attivare "${item.s}" nel BIOS${mbStr}: in quale menu si trova e quali valori impostare.${hwStr ? ` Il mio hardware: ${hwStr}.` : ""}`;
    navigate("/app/advisor", { state: { ask: q } });
  };

  const restoreSafe = useMemo(() => RESTORE_SAFE.map((t) => adaptRestore(t, hw, data.motherboard)), [hw, data.motherboard]);
  const restoreCaution = useMemo(() => RESTORE_CAUTION.map((t) => adaptRestore(t, hw, data.motherboard)), [hw, data.motherboard]);

  const askAIRestore = (item) => {
    const hwStr = [data.cpu?.trim(), data.gpu, data.os].filter(Boolean).join(", ");
    const q = `Guidami passo-passo nell'operazione di ripristino "${item.s}" su Windows: quando conviene usarla, quali sono i rischi e come farla in sicurezza.${hwStr ? ` Il mio sistema: ${hwStr}.` : ""}`;
    navigate("/app/advisor", { state: { ask: q } });
  };

  const restoreCmd = `irm "${BACKEND}/api/agent/script?t=${token || "IL_TUO_TOKEN"}&mode=restore" | iex`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(restoreCmd); } catch { const t = document.createElement("textarea"); t.value = restoreCmd; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success("Comando copiato!"); setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto fade-up" data-testid="bios-restore-page">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Guida avanzata</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">BIOS & Ripristino</h1>
        <p className="text-zinc-500 text-sm mt-1">Impostazioni BIOS consigliate e opzioni di ripristino, adattate al tuo hardware.</p>
      </div>

      <div className="flex gap-2 mb-6">
        <button data-testid="tab-bios" onClick={() => setTab("bios")}
          className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === "bios" ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
          <Cpu size={16} /> BIOS
        </button>
        <button data-testid="tab-restore" onClick={() => setTab("restore")}
          className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === "restore" ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
          <RotateCcw size={16} /> Ripristino PC
        </button>
      </div>

      {tab === "bios" ? (
        <div className="space-y-4">
          {/* Hardware rilevato */}
          <div className="bg-[#0F0F12] border border-[#00E0FF]/30 p-4" data-testid="bios-hw">
            <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-[#00E0FF] mb-2">
              <Cpu size={14} /> Hardware rilevato
            </div>
            {hasHw ? (
              <div className="flex flex-wrap gap-2">
                {hw.cpu && <span className="inline-flex items-center gap-1.5 text-xs bg-black border border-[#2A2A35] px-2.5 py-1 text-zinc-200" data-testid="hw-cpu"><Cpu size={12} className="text-[#E5FF00]" /> {data.cpu || HW_LABEL.cpu[hw.cpu]}</span>}
                {hw.gpu && <span className="inline-flex items-center gap-1.5 text-xs bg-black border border-[#2A2A35] px-2.5 py-1 text-zinc-200" data-testid="hw-gpu"><MonitorPlay size={12} className="text-[#00FF66]" /> {data.gpu || HW_LABEL.gpu[hw.gpu]}</span>}
                {hw.ramType && <span className="inline-flex items-center gap-1.5 text-xs bg-black border border-[#2A2A35] px-2.5 py-1 text-zinc-200" data-testid="hw-ram"><MemoryStick size={12} className="text-[#00E0FF]" /> RAM {hw.ramType}</span>}
              </div>
            ) : (
              <p className="text-xs text-zinc-500">Nessun hardware rilevato. Vai su <span className="text-zinc-300">Il mio PC</span> e avvia il Desktop Agent per una guida su misura. Sotto trovi la guida generica.</p>
            )}
          </div>

          {/* Consigliati per il tuo PC */}
          {hasHw && topPicks.length > 0 && (
            <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-5" data-testid="bios-top-picks">
              <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#E5FF00]"><Star size={16} /> Consigliati per il tuo PC</div>
              <div className="grid sm:grid-cols-3 gap-3">
                {topPicks.map((t, i) => (
                  <div key={t.id} className="bg-black/60 border border-[#2A2A35] p-3 flex flex-col" data-testid={`top-pick-${t.id}`}>
                    <div className="text-xs font-bold text-zinc-100">{t.s}</div>
                    <div className="text-[11px] text-zinc-500 mt-1 leading-relaxed line-clamp-3 flex-1">{t.w}</div>
                    <button onClick={() => askAI(t, t.impact && caution.some((c) => c.id === t.id) ? "caution" : "safe")} data-testid={`ask-ai-top-${t.id}`}
                      className="mt-2 inline-flex items-center justify-center gap-1 border border-[#E5FF00]/40 text-[#E5FF00] px-2 py-1.5 text-[11px] font-bold hover:bg-[#E5FF00] hover:text-black transition-colors">
                      <MessageSquareCode size={12} /> Chiedi all'AI
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-[#0F0F12] border border-[#2A2A35] p-5" data-testid="bios-access">
            <div className="flex items-center gap-2 text-sm font-bold mb-2"><KeyRound size={16} className="text-[#00E0FF]" /> Come entrare nel BIOS</div>
            <p className="text-sm text-zinc-300">Riavvia e premi ripetutamente: <span className="text-[#E5FF00] font-bold">{key}</span>{vendor && <span className="text-zinc-500"> (rilevata scheda {vendor})</span>}.</p>
            <p className="text-xs text-zinc-500 mt-2">In alternativa da Windows: Impostazioni → Sistema → Ripristino → Avvio avanzato → Riavvia ora → Risoluzione problemi → Opzioni avanzate → Impostazioni firmware UEFI.</p>
          </div>

          <div className="bg-[#0F0F12] border border-[#00FF66]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#00FF66]"><ShieldCheck size={16} /> Impostazioni SICURE (consigliate)</div>
            <div className="border border-[#1A1A24]">{safe.map((it, i) => <Row key={it.id} item={it} tone="safe" i={i} section="bios" onAsk={askAI} />)}</div>
          </div>

          <div className="bg-[#0F0F12] border border-[#E5FF00]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#E5FF00]"><AlertTriangle size={16} /> Da usare CON CAUTELA</div>
            <div className="border border-[#1A1A24]">{caution.map((it, i) => <Row key={it.id} item={it} tone="caution" i={i} section="bios" onAsk={askAI} />)}</div>
          </div>

          <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start">
            <Info size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-400 leading-relaxed">Regola d'oro: <span className="text-zinc-200">cambia una sola impostazione alla volta</span> e testa la stabilità. Annota i valori di default. Se il PC non parte, esegui un <span className="text-zinc-200">Clear CMOS</span> o carica i "Load Optimized Defaults".</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {hasHw && (
            <div className="bg-[#0F0F12] border border-[#00E0FF]/30 p-4" data-testid="restore-hw">
              <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-[#00E0FF] mb-2"><Cpu size={14} /> Adattato al tuo hardware</div>
              <p className="text-xs text-zinc-500">DDU e Clear CMOS qui sotto sono personalizzati per {[hw.gpu && (HW_LABEL.gpu[hw.gpu]), hw.cpu && (HW_LABEL.cpu[hw.cpu])].filter(Boolean).join(" · ")}.</p>
            </div>
          )}
          <div className="bg-[#0F0F12] border border-[#00FF66]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#00FF66]"><ShieldCheck size={16} /> Ripristini SICURI (reversibili)</div>
            <div className="border border-[#1A1A24]">{restoreSafe.map((it, i) => <Row key={it.id} item={it} tone="safe" i={i} section="restore" onAsk={askAIRestore} />)}</div>
            <div className="mt-4">
              <div className="text-xs text-zinc-500 mb-1">Comando per ripristinare i tweak applicati da BoostPC (esegui in PowerShell):</div>
              <div className="flex items-stretch gap-2">
                <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="restore-cmd">{restoreCmd}</code>
                <button data-testid="restore-copy" onClick={copy} className="shrink-0 flex items-center gap-1 border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors text-xs">
                  {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
                </button>
              </div>
            </div>
          </div>

          <div className="bg-[#0F0F12] border border-[#E5FF00]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#E5FF00]"><AlertTriangle size={16} /> Da usare CON CAUTELA</div>
            <div className="border border-[#1A1A24]">{restoreCaution.map((it, i) => <Row key={it.id} item={it} tone="caution" i={i} section="restore" onAsk={askAIRestore} />)}</div>
          </div>

          <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start">
            <Info size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-400 leading-relaxed">Prima di un ripristino importante fai sempre un <span className="text-zinc-200">backup dei file</span>. Per i problemi causati dai tweak BoostPC basta il comando <span className="text-zinc-200">restore</span> qui sopra, senza reinstallare nulla.</p>
          </div>
        </div>
      )}
    </div>
  );
}
