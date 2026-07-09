import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { Cpu, RotateCcw, CheckCircle2, AlertTriangle, ShieldCheck, Copy, Check, KeyRound, Info, Star, MemoryStick, MonitorPlay, MessageSquareCode } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageHeader } from "@/components/hud";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const isEn = () => i18n.language?.startsWith("en");

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

const BIOS_KEYS_EN = {
  ASUS: "Del or F2",
  MSI: "Del",
  Gigabyte: "Del or F2",
  ASRock: "F2 or Del",
  HP: "Esc then F10 (or F10 at boot)",
  Lenovo: "F1 or F2 (or Novo button)",
  Dell: "F2",
  Acer: "F2 or Del",
  Biostar: "Del",
};

// tag: cpu ("amd"|"intel"), gpu ("nvidia"|"amd"), impact (mostrato tra i consigliati),
// ramProfile / rebar => titolo e descrizione adattati all'hardware.
const BIOS_SAFE = [
  { id: "ram", ramProfile: true, impact: true, s: "XMP / EXPO / DOCP", s_en: "XMP / EXPO / DOCP", w: "Attiva il profilo RAM: senza, la memoria gira a frequenza base e perdi FPS reali. È il tweak BIOS con più impatto.", w_en: "Enables the RAM profile: without it, memory runs at base frequency and you lose real FPS. It's the highest-impact BIOS tweak." },
  { id: "rebar", rebar: true, impact: true, s: "Resizable BAR (ReBAR / SAM)", s_en: "Resizable BAR (ReBAR / SAM)", w: "ON. Guadagno prestazioni GPU gratuito. Richiede anche Above 4G Decoding: ON.", w_en: "ON. Free GPU performance gain. Also requires Above 4G Decoding: ON." },
  { id: "ftpm", s: "fTPM / PTT + Secure Boot", s_en: "fTPM / PTT + Secure Boot", w: "ON. Obbligatori per Windows 11 e anti-cheat come Valorant/Vanguard, Faceit.", w_en: "ON. Required for Windows 11 and anti-cheats like Valorant/Vanguard, Faceit." },
  { id: "fan", s: "Fan curve personalizzata", s_en: "Custom fan curve", w: "Imposta una curva più aggressiva per CPU/case: temperature più basse durante il gaming.", w_en: "Set a more aggressive curve for CPU/case: lower temperatures while gaming." },
  { id: "uefi", s: "Modalità UEFI (CSM off) + Fast Boot", s_en: "UEFI mode (CSM off) + Fast Boot", w: "Boot più veloce e moderno. Necessario per Secure Boot.", w_en: "Faster, modern boot. Required for Secure Boot." },
  { id: "pcie", s: "PCIe Gen4 per GPU/SSD NVMe", s_en: "PCIe Gen4 for GPU/NVMe SSD", w: "Assicura la massima banda per scheda video e SSD.", w_en: "Ensures maximum bandwidth for the graphics card and SSD." },
  { id: "ahci", s: "SATA mode: AHCI", s_en: "SATA mode: AHCI", w: "Corretto per gli SSD. NON cambiarlo se Windows è già installato (rischio boot).", w_en: "Correct for SSDs. Do NOT change it if Windows is already installed (boot risk)." },
  { id: "psi", cpu: "amd", s: "Power Supply Idle Control: Typical", s_en: "Power Supply Idle Control: Typical", w: "Su Ryzen previene i riavvii improvvisi in idle. Impostazione sicura.", w_en: "On Ryzen it prevents sudden idle reboots. Safe setting." },
];

const BIOS_CAUTION = [
  { id: "co", cpu: "amd", impact: true, s: "Curve Optimizer / PBO (Ryzen)", s_en: "Curve Optimizer / PBO (Ryzen)", w: "Undervolt/boost: ottimo per temp e prestazioni, ma può causare instabilità/crash. Testa con offset piccoli (es. -15) e prova la stabilità.", w_en: "Undervolt/boost: great for temps and performance, but can cause instability/crashes. Test with small offsets (e.g. -15) and check stability." },
  { id: "oc", s: "Overclock CPU / RAM manuale", s_en: "Manual CPU / RAM overclock", w: "Frequenze/timing manuali possono impedire il boot. Solo se sai cosa fai; annota i valori di default.", w_en: "Manual frequencies/timings can prevent boot. Only if you know what you're doing; note the default values." },
  { id: "bupd", s: "Aggiornamento BIOS", s_en: "BIOS update", w: "Utile per stabilità/compatibilità, ma se interrotto (blackout) può brickare la scheda madre. Usa la funzione integrata (BIOS Flashback) e non spegnere durante l'update.", w_en: "Useful for stability/compatibility, but if interrupted (power loss) it can brick the motherboard. Use the built-in feature (BIOS Flashback) and don't power off during the update." },
  { id: "volt", s: "Voltaggi (vCore, SoC, DRAM)", s_en: "Voltages (vCore, SoC, DRAM)", w: "Voltaggi errati possono danneggiare o degradare i componenti. Zona a rischio: non toccare senza esperienza.", w_en: "Wrong voltages can damage or degrade components. Danger zone: don't touch without experience." },
  { id: "cstate", cpu: "amd", s: "Disattivare Global C-States", s_en: "Disable Global C-States", w: "Riduce micro-latenze ma aumenta temperature e consumi in idle. Solo per competitive estremo.", w_en: "Reduces micro-latency but increases idle temperatures and power draw. For extreme competitive only." },
  { id: "llc", s: "Load Line Calibration (LLC)", s_en: "Load Line Calibration (LLC)", w: "Stabilizza il voltaggio sotto carico ma può alzare temperature/voltaggi reali. Impostazione avanzata.", w_en: "Stabilizes voltage under load but can raise actual temperatures/voltages. Advanced setting." },
  { id: "disable", s: "Disabilitare dispositivi integrati", s_en: "Disable integrated devices", w: "Audio/LAN/USB off può far risparmiare risorse ma rischi di perdere funzionalità o periferiche.", w_en: "Turning off Audio/LAN/USB can save resources but you risk losing features or peripherals." },
];

const RESTORE_SAFE = [
  { id: "sysrestore", s: "Crea un punto di ripristino", s_en: "Create a restore point", w: "Prima di ogni modifica importante: Cerca 'Crea un punto di ripristino' → Configura → Crea. Ti permette di tornare indietro senza perdere file.", w_en: "Before any major change: search 'Create a restore point' → Configure → Create. Lets you roll back without losing files." },
  { id: "boostrestore", s: "Ripristina i tweak FrameForge", s_en: "Restore FrameForge tweaks", w: "Annulla tutte le ottimizzazioni applicate (registro, servizi, DNS, power). Reversibile al 100% col comando qui sotto.", w_en: "Reverts all applied optimizations (registry, services, DNS, power). 100% reversible with the command below." },
  { id: "ddu", gpuDriver: true, s: "DDU (Display Driver Uninstaller)", s_en: "DDU (Display Driver Uninstaller)", w: "Rimuove completamente i driver GPU prima di reinstallarli puliti: risolve stutter/artefatti da driver corrotti.", w_en: "Completely removes GPU drivers before reinstalling them clean: fixes stutter/artifacts from corrupted drivers." },
  { id: "sfc", s: "SFC /scannow", s_en: "SFC /scannow", w: "Ripara i file di sistema danneggiati. In PowerShell admin: sfc /scannow.", w_en: "Repairs corrupted system files. In PowerShell admin: sfc /scannow." },
  { id: "dism", s: "DISM RestoreHealth", s_en: "DISM RestoreHealth", w: "Ripara l'immagine di Windows: DISM /Online /Cleanup-Image /RestoreHealth.", w_en: "Repairs the Windows image: DISM /Online /Cleanup-Image /RestoreHealth." },
];

const RESTORE_CAUTION = [
  { id: "resetkeep", s: "Reimposta il PC (mantieni i file)", s_en: "Reset the PC (keep files)", w: "Reinstalla Windows conservando i file personali ma RIMUOVE i programmi installati. Impostazioni → Sistema → Ripristino → Reimposta il PC.", w_en: "Reinstalls Windows keeping personal files but REMOVES installed programs. Settings → System → Recovery → Reset this PC." },
  { id: "resetall", s: "Reimposta il PC (rimuovi tutto)", s_en: "Reset the PC (remove everything)", w: "Cancella TUTTO (file + programmi). Usa solo dopo un backup completo. Ideale prima di vendere il PC.", w_en: "Erases EVERYTHING (files + programs). Use only after a full backup. Ideal before selling the PC." },
  { id: "restorepoint", s: "Ripristino a un punto precedente", s_en: "Restore to an earlier point", w: "Torna a uno stato passato: perdi programmi/driver installati dopo quel punto (i file personali restano).", w_en: "Reverts to a past state: you lose programs/drivers installed after that point (personal files stay)." },
  { id: "cmos", cmos: true, s: "Clear CMOS (reset BIOS)", s_en: "Clear CMOS (reset BIOS)", w: "Riporta il BIOS ai default (utile se il PC non parte dopo un tweak). Fatto via jumper/pulsante o togliendo la batteria: annulla anche XMP/ReBAR.", w_en: "Resets the BIOS to defaults (useful if the PC won't boot after a tweak). Done via jumper/button or removing the battery: also undoes XMP/ReBAR." },
  { id: "cleaninstall", s: "Reinstallazione pulita di Windows", s_en: "Clean Windows reinstall", w: "Formattazione completa da USB. La soluzione più radicale: backup obbligatorio, richiede reinstallare tutto.", w_en: "Full format from USB. The most radical solution: backup required, requires reinstalling everything." },
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
  const en = isEn();
  let s = en ? t.s_en : t.s;
  let w = en ? t.w_en : t.w;
  if (t.ramProfile) {
    if (hw.cpu === "amd") {
      s = hw.ramType === "DDR5" ? (en ? "EXPO — AMD RAM profile (DDR5)" : "EXPO — profilo RAM AMD (DDR5)") : (en ? "DOCP / EXPO — AMD RAM profile" : "DOCP / EXPO — profilo RAM AMD");
      w = en ? "Enable EXPO/DOCP in the BIOS: without it, RAM runs slow and you lose FPS. On your Ryzen it's the highest real-impact tweak." : "Attiva EXPO/DOCP nel BIOS: senza, la RAM gira lenta e perdi FPS. Sul tuo Ryzen è il tweak con più impatto reale.";
    } else if (hw.cpu === "intel") {
      s = hw.ramType === "DDR5" ? (en ? "XMP — Intel RAM profile (DDR5)" : "XMP — profilo RAM Intel (DDR5)") : (en ? "XMP — Intel RAM profile" : "XMP — profilo RAM Intel");
      w = en ? "Enable XMP in the BIOS: without it, RAM stays at base frequency and limits your Intel CPU. It's the highest-impact BIOS tweak." : "Attiva XMP nel BIOS: senza, la RAM resta alla frequenza base e limiti la CPU Intel. È il tweak BIOS con più impatto.";
    }
  }
  if (t.rebar) {
    if (hw.gpu === "nvidia") {
      s = "Resizable BAR (ReBAR)";
      w = en ? "ON for your GeForce: free performance in many games. Also requires Above 4G Decoding: ON." : "ON per la tua GeForce: prestazioni gratis in molti giochi. Richiede anche Above 4G Decoding: ON.";
    } else if (hw.gpu === "amd") {
      s = "Smart Access Memory (SAM / ReBAR)";
      w = en ? "ON for your Radeon: SAM leverages the extra CPU↔GPU bandwidth. Requires Above 4G Decoding: ON." : "ON per la tua Radeon: SAM sfrutta la banda extra CPU↔GPU. Richiede Above 4G Decoding: ON.";
    } else if (hw.gpu === "intel") {
      s = "Resizable BAR (ReBAR)";
      w = en ? "ON for your Intel Arc: strongly recommended, big performance impact. Requires Above 4G Decoding: ON." : "ON per la tua Intel Arc: fortemente consigliato, impatta molto le prestazioni. Richiede Above 4G Decoding: ON.";
    }
  }
  return { ...t, s, w };
}

function adaptRestore(t, hw, mbName) {
  const en = isEn();
  let s = en ? t.s_en : t.s;
  let w = en ? t.w_en : t.w;
  if (t.gpuDriver) {
    if (hw.gpu === "nvidia") w = en ? "Completely removes the drivers, then reinstalls the GeForce Game Ready from NVIDIA's site: fixes stutter/artifacts from corrupted drivers." : "Rimuove del tutto i driver, poi reinstalla i GeForce Game Ready dal sito NVIDIA: risolve stutter/artefatti da driver corrotti.";
    else if (hw.gpu === "amd") w = en ? "Completely removes the drivers, then reinstalls the AMD Adrenalin from AMD's site: fixes stutter/artifacts from corrupted drivers." : "Rimuove del tutto i driver, poi reinstalla gli AMD Adrenalin dal sito AMD: risolve stutter/artefatti da driver corrotti.";
    else if (hw.gpu === "intel") w = en ? "Completely removes the drivers, then reinstalls the Intel Arc from Intel's site: fixes stutter/artifacts from corrupted drivers." : "Rimuove del tutto i driver, poi reinstalla gli Intel Arc dal sito Intel: risolve stutter/artefatti da driver corrotti.";
  }
  if (t.cmos) {
    const ram = hw.cpu === "amd" ? (hw.ramType === "DDR5" ? "EXPO" : "DOCP/EXPO") : hw.cpu === "intel" ? "XMP" : "XMP/EXPO";
    const bar = hw.gpu === "amd" ? "SAM" : "ReBAR";
    const mb = mbName ? (en ? ` on your ${mbName}` : ` sulla tua ${mbName}`) : "";
    w = en ? `Resets the BIOS to defaults${mb} (useful if the PC won't boot after a tweak). Note: it also undoes ${ram} and ${bar}, to re-enable afterward.` : `Riporta il BIOS ai default${mb} (utile se il PC non parte dopo un tweak). Attenzione: annulla anche ${ram} e ${bar}, da riattivare dopo.`;
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
  const { t } = useTranslation();
  const Icon = tone === "safe" ? CheckCircle2 : AlertTriangle;
  const color = tone === "safe" ? "text-[#00FF66]" : "text-[#E5FF00]";
  return (
    <div className="flex gap-3 p-3 border-b border-[#1A1A24] last:border-0 items-start row-hover" data-testid={`${section}-${tone}-${item.id || i}`}>
      <Icon size={16} className={`${color} shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-zinc-100 font-semibold">{item.s}</div>
        <div className="text-xs text-zinc-500 mt-0.5 leading-relaxed">{item.w}</div>
      </div>
      {onAsk && (
        <button onClick={() => onAsk(item, tone)} data-testid={`ask-ai-${section}-${item.id || i}`}
          className="shrink-0 self-center inline-flex items-center gap-1 border border-[#2A2A35] px-2 py-1.5 text-[11px] text-zinc-400 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors whitespace-nowrap">
          <MessageSquareCode size={12} /> {t("bios.ask_ai")}
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
  const { t, i18n: i18nInst } = useTranslation();
  const lang = i18nInst.language;
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

  const safe = useMemo(() => filterForHardware(BIOS_SAFE, hw), [hw, lang]);
  const caution = useMemo(() => filterForHardware(BIOS_CAUTION, hw), [hw, lang]);
  const topPicks = useMemo(
    () => [...safe, ...caution].filter((t) => t.impact).slice(0, 3),
    [safe, caution]
  );

  const mb = ((data.motherboard || "") + " " + (data.system_model || "")).toUpperCase();
  let vendor = null;
  for (const v of Object.keys(BIOS_KEYS)) { if (mb.includes(v.toUpperCase())) { vendor = v; break; } }
  const keys = isEn() ? BIOS_KEYS_EN : BIOS_KEYS;
  const key = vendor ? keys[vendor] : t("bios.key_default");

  const askAI = (item, tone) => {
    const en = isEn();
    const hwStr = [data.cpu?.trim(), data.gpu, hw.ramType && `RAM ${hw.ramType}`].filter(Boolean).join(", ");
    const mbStr = data.motherboard ? (en ? ` on my ${data.motherboard} motherboard` : ` sulla mia scheda madre ${data.motherboard}`) : "";
    let q;
    if (en) {
      q = tone === "caution"
        ? `Explain in detail the BIOS setting "${item.s}"${mbStr}: how to enable it step by step, what risks it involves and which safe values to use.${hwStr ? ` My hardware: ${hwStr}.` : ""}`
        : `Explain step by step how to enable "${item.s}" in the BIOS${mbStr}: which menu it's in and which values to set.${hwStr ? ` My hardware: ${hwStr}.` : ""}`;
    } else {
      q = tone === "caution"
        ? `Spiegami in dettaglio l'impostazione BIOS "${item.s}"${mbStr}: come si attiva passo-passo, quali rischi comporta e quali valori sicuri usare.${hwStr ? ` Il mio hardware: ${hwStr}.` : ""}`
        : `Spiegami passo-passo come attivare "${item.s}" nel BIOS${mbStr}: in quale menu si trova e quali valori impostare.${hwStr ? ` Il mio hardware: ${hwStr}.` : ""}`;
    }
    navigate("/app/advisor", { state: { ask: q } });
  };

  const restoreSafe = useMemo(() => RESTORE_SAFE.map((t) => adaptRestore(t, hw, data.motherboard)), [hw, data.motherboard, lang]);
  const restoreCaution = useMemo(() => RESTORE_CAUTION.map((t) => adaptRestore(t, hw, data.motherboard)), [hw, data.motherboard, lang]);

  const askAIRestore = (item) => {
    const en = isEn();
    const hwStr = [data.cpu?.trim(), data.gpu, data.os].filter(Boolean).join(", ");
    const q = en
      ? `Guide me step by step through the restore operation "${item.s}" on Windows: when it's worth using, what the risks are and how to do it safely.${hwStr ? ` My system: ${hwStr}.` : ""}`
      : `Guidami passo-passo nell'operazione di ripristino "${item.s}" su Windows: quando conviene usarla, quali sono i rischi e come farla in sicurezza.${hwStr ? ` Il mio sistema: ${hwStr}.` : ""}`;
    navigate("/app/advisor", { state: { ask: q } });
  };

  const restoreCmd = `irm "${BACKEND}/api/agent/script?t=${token || "IL_TUO_TOKEN"}&mode=restore" | iex`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(restoreCmd); } catch { const ta = document.createElement("textarea"); ta.value = restoreCmd; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
    setCopied(true); toast.success(t("bios.copied")); setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto fade-up" data-testid="bios-restore-page">
      <PageHeader eyebrow={t("bios.eyebrow")} title={t("bios.title")} subtitle={t("bios.subtitle")} />

      <div className="flex gap-2 mb-6">
        <button data-testid="tab-bios" onClick={() => setTab("bios")}
          className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === "bios" ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
          <Cpu size={16} /> {t("bios.tab_bios")}
        </button>
        <button data-testid="tab-restore" onClick={() => setTab("restore")}
          className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === "restore" ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
          <RotateCcw size={16} /> {t("bios.tab_restore")}
        </button>
      </div>

      {tab === "bios" ? (
        <div className="space-y-4">
          {/* Hardware rilevato */}
          <div className="bg-[#0F0F12] border border-[#00E0FF]/30 p-4" data-testid="bios-hw">
            <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-[#00E0FF] mb-2">
              <Cpu size={14} /> {t("bios.hw_detected")}
            </div>
            {hasHw ? (
              <div className="flex flex-wrap gap-2">
                {hw.cpu && <span className="inline-flex items-center gap-1.5 text-xs bg-black border border-[#2A2A35] px-2.5 py-1 text-zinc-200" data-testid="hw-cpu"><Cpu size={12} className="text-[#E5FF00]" /> {data.cpu || HW_LABEL.cpu[hw.cpu]}</span>}
                {hw.gpu && <span className="inline-flex items-center gap-1.5 text-xs bg-black border border-[#2A2A35] px-2.5 py-1 text-zinc-200" data-testid="hw-gpu"><MonitorPlay size={12} className="text-[#00FF66]" /> {data.gpu || HW_LABEL.gpu[hw.gpu]}</span>}
                {hw.ramType && <span className="inline-flex items-center gap-1.5 text-xs bg-black border border-[#2A2A35] px-2.5 py-1 text-zinc-200" data-testid="hw-ram"><MemoryStick size={12} className="text-[#00E0FF]" /> RAM {hw.ramType}</span>}
              </div>
            ) : (
              <p className="text-xs text-zinc-500">{t("bios.no_hw")}</p>
            )}
          </div>

          {/* Consigliati per il tuo PC */}
          {hasHw && topPicks.length > 0 && (
            <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-5" data-testid="bios-top-picks">
              <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#E5FF00]"><Star size={16} /> {t("bios.top_picks")}</div>
              <div className="grid sm:grid-cols-3 gap-3 stagger">
                {topPicks.map((tp, i) => (
                  <div key={tp.id} className="bg-black/60 border border-[#2A2A35] p-3 flex flex-col card-hover" data-testid={`top-pick-${tp.id}`}>
                    <div className="text-xs font-bold text-zinc-100">{tp.s}</div>
                    <div className="text-[11px] text-zinc-500 mt-1 leading-relaxed line-clamp-3 flex-1">{tp.w}</div>
                    <button onClick={() => askAI(tp, tp.impact && caution.some((c) => c.id === tp.id) ? "caution" : "safe")} data-testid={`ask-ai-top-${tp.id}`}
                      className="mt-2 inline-flex items-center justify-center gap-1 border border-[#E5FF00]/40 text-[#E5FF00] px-2 py-1.5 text-[11px] font-bold hover:bg-[#E5FF00] hover:text-black transition-colors">
                      <MessageSquareCode size={12} /> {t("bios.ask_ai")}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-[#0F0F12] border border-[#2A2A35] p-5" data-testid="bios-access">
            <div className="flex items-center gap-2 text-sm font-bold mb-2"><KeyRound size={16} className="text-[#00E0FF]" /> {t("bios.how_enter")}</div>
            <p className="text-sm text-zinc-300">{t("bios.enter_pre")} <span className="text-[#E5FF00] font-bold">{key}</span>{vendor && <span className="text-zinc-500"> {t("bios.detected_board", { vendor })}</span>}.</p>
            <p className="text-xs text-zinc-500 mt-2">{t("bios.enter_alt")}</p>
          </div>

          <div className="bg-[#0F0F12] border border-[#00FF66]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#00FF66]"><ShieldCheck size={16} /> {t("bios.safe_title")}</div>
            <div className="border border-[#1A1A24]">{safe.map((it, i) => <Row key={it.id} item={it} tone="safe" i={i} section="bios" onAsk={askAI} />)}</div>
          </div>

          <div className="bg-[#0F0F12] border border-[#E5FF00]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#E5FF00]"><AlertTriangle size={16} /> {t("bios.caution_title")}</div>
            <div className="border border-[#1A1A24]">{caution.map((it, i) => <Row key={it.id} item={it} tone="caution" i={i} section="bios" onAsk={askAI} />)}</div>
          </div>

          <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start">
            <Info size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-400 leading-relaxed">{t("bios.golden_rule")}</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {hasHw && (
            <div className="bg-[#0F0F12] border border-[#00E0FF]/30 p-4" data-testid="restore-hw">
              <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-[#00E0FF] mb-2"><Cpu size={14} /> {t("bios.adapted_to")}</div>
              <p className="text-xs text-zinc-500">{t("bios.adapted_desc", { hw: [hw.gpu && (HW_LABEL.gpu[hw.gpu]), hw.cpu && (HW_LABEL.cpu[hw.cpu])].filter(Boolean).join(" · ") })}</p>
            </div>
          )}
          <div className="bg-[#0F0F12] border border-[#00FF66]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#00FF66]"><ShieldCheck size={16} /> {t("bios.restore_safe")}</div>
            <div className="border border-[#1A1A24]">{restoreSafe.map((it, i) => <Row key={it.id} item={it} tone="safe" i={i} section="restore" onAsk={askAIRestore} />)}</div>
            <div className="mt-4">
              <div className="text-xs text-zinc-500 mb-1">{t("bios.restore_cmd_hint")}</div>
              <div className="flex items-stretch gap-2">
                <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="restore-cmd">{restoreCmd}</code>
                <button data-testid="restore-copy" onClick={copy} className="shrink-0 flex items-center gap-1 border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors text-xs">
                  {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
                </button>
              </div>
            </div>
          </div>

          <div className="bg-[#0F0F12] border border-[#E5FF00]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#E5FF00]"><AlertTriangle size={16} /> {t("bios.caution_title")}</div>
            <div className="border border-[#1A1A24]">{restoreCaution.map((it, i) => <Row key={it.id} item={it} tone="caution" i={i} section="restore" onAsk={askAIRestore} />)}</div>
          </div>

          <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start">
            <Info size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-400 leading-relaxed">{t("bios.restore_info")}</p>
          </div>
        </div>
      )}
    </div>
  );
}
