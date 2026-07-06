import { useEffect, useState } from "react";
import { Cpu, RotateCcw, CheckCircle2, AlertTriangle, ShieldCheck, Copy, Check, KeyRound, Info } from "lucide-react";
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

const BIOS_SAFE = [
  { s: "XMP / EXPO / DOCP", w: "Attiva il profilo RAM: senza, la memoria gira a frequenza base e perdi FPS reali. È il tweak BIOS con più impatto." },
  { s: "Resizable BAR (ReBAR / SAM)", w: "ON. Guadagno prestazioni GPU gratuito. Richiede anche Above 4G Decoding: ON." },
  { s: "fTPM / PTT + Secure Boot", w: "ON. Obbligatori per Windows 11 e anti-cheat come Valorant/Vanguard, Faceit." },
  { s: "Fan curve personalizzata", w: "Imposta una curva più aggressiva per CPU/case: temperature più basse durante il gaming." },
  { s: "Modalità UEFI (CSM off) + Fast Boot", w: "Boot più veloce e moderno. Necessario per Secure Boot." },
  { s: "PCIe Gen4 per GPU/SSD NVMe", w: "Assicura la massima banda per scheda video e SSD." },
  { s: "SATA mode: AHCI", w: "Corretto per gli SSD. NON cambiarlo se Windows è già installato (rischio boot)." },
  { s: "Power Supply Idle Control: Typical", w: "Su Ryzen previene i riavvii improvvisi in idle. Impostazione sicura." },
];

const BIOS_CAUTION = [
  { s: "Curve Optimizer / PBO (Ryzen)", w: "Undervolt/boost: ottimo per temp e prestazioni, ma può causare instabilità/crash. Testa con offset piccoli (es. -15) e prova la stabilità." },
  { s: "Overclock CPU / RAM manuale", w: "Frequenze/timing manuali possono impedire il boot. Solo se sai cosa fai; annota i valori di default." },
  { s: "Aggiornamento BIOS", w: "Utile per stabilità/compatibilità, ma se interrotto (blackout) può brickare la scheda madre. Usa la funzione integrata (BIOS Flashback) e non spegnere durante l'update." },
  { s: "Voltaggi (vCore, SoC, DRAM)", w: "Voltaggi errati possono danneggiare o degradare i componenti. Zona a rischio: non toccare senza esperienza." },
  { s: "Disattivare Global C-States", w: "Riduce micro-latenze ma aumenta temperature e consumi in idle. Solo per competitive estremo." },
  { s: "Load Line Calibration (LLC)", w: "Stabilizza il voltaggio sotto carico ma può alzare temperature/voltaggi reali. Impostazione avanzata." },
  { s: "Disabilitare dispositivi integrati", w: "Audio/LAN/USB off può far risparmiare risorse ma rischi di perdere funzionalità o periferiche." },
];

const RESTORE_SAFE = [
  { s: "Crea un punto di ripristino", w: "Prima di ogni modifica importante: Cerca 'Crea un punto di ripristino' → Configura → Crea. Ti permette di tornare indietro senza perdere file." },
  { s: "Ripristina i tweak BoostPC", w: "Annulla tutte le ottimizzazioni applicate (registro, servizi, DNS, power). Reversibile al 100% col comando qui sotto." },
  { s: "DDU (Display Driver Uninstaller)", w: "Rimuove completamente i driver GPU prima di reinstallarli puliti: risolve stutter/artefatti da driver corrotti." },
  { s: "SFC /scannow", w: "Ripara i file di sistema danneggiati. In PowerShell admin: sfc /scannow." },
  { s: "DISM RestoreHealth", w: "Ripara l'immagine di Windows: DISM /Online /Cleanup-Image /RestoreHealth." },
];

const RESTORE_CAUTION = [
  { s: "Reimposta il PC (mantieni i file)", w: "Reinstalla Windows conservando i file personali ma RIMUOVE i programmi installati. Impostazioni → Sistema → Ripristino → Reimposta il PC." },
  { s: "Reimposta il PC (rimuovi tutto)", w: "Cancella TUTTO (file + programmi). Usa solo dopo un backup completo. Ideale prima di vendere il PC." },
  { s: "Ripristino a un punto precedente", w: "Torna a uno stato passato: perdi programmi/driver installati dopo quel punto (i file personali restano)." },
  { s: "Clear CMOS (reset BIOS)", w: "Riporta il BIOS ai default (utile se il PC non parte dopo un tweak). Fatto via jumper/pulsante o togliendo la batteria: annulla anche XMP/ReBAR." },
  { s: "Reinstallazione pulita di Windows", w: "Formattazione completa da USB. La soluzione più radicale: backup obbligatorio, richiede reinstallare tutto." },
];

function Row({ item, tone, i, section }) {
  const Icon = tone === "safe" ? CheckCircle2 : AlertTriangle;
  const color = tone === "safe" ? "text-[#00FF66]" : "text-[#E5FF00]";
  return (
    <div className="flex gap-3 p-3 border-b border-[#1A1A24] last:border-0" data-testid={`${section}-${tone}-${i}`}>
      <Icon size={16} className={`${color} shrink-0 mt-0.5`} />
      <div>
        <div className="text-sm text-zinc-100 font-semibold">{item.s}</div>
        <div className="text-xs text-zinc-500 mt-0.5 leading-relaxed">{item.w}</div>
      </div>
    </div>
  );
}

export default function BiosRestore() {
  const [tab, setTab] = useState("bios");
  const [specs, setSpecs] = useState(null);
  const [token, setToken] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
  }, []);

  const mb = ((specs?.data?.motherboard || "") + " " + (specs?.data?.system_model || "")).toUpperCase();
  let vendor = null;
  for (const v of Object.keys(BIOS_KEYS)) { if (mb.includes(v.toUpperCase())) { vendor = v; break; } }
  const key = vendor ? BIOS_KEYS[vendor] : "Canc (Del) o F2 (varia per marca)";

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
        <p className="text-zinc-500 text-sm mt-1">Impostazioni BIOS consigliate e opzioni di ripristino, divise tra sicure e da usare con cautela.</p>
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
          <div className="bg-[#0F0F12] border border-[#2A2A35] p-5" data-testid="bios-access">
            <div className="flex items-center gap-2 text-sm font-bold mb-2"><KeyRound size={16} className="text-[#00E0FF]" /> Come entrare nel BIOS</div>
            <p className="text-sm text-zinc-300">Riavvia e premi ripetutamente: <span className="text-[#E5FF00] font-bold">{key}</span>{vendor && <span className="text-zinc-500"> (rilevata scheda {vendor})</span>}.</p>
            <p className="text-xs text-zinc-500 mt-2">In alternativa da Windows: Impostazioni → Sistema → Ripristino → Avvio avanzato → Riavvia ora → Risoluzione problemi → Opzioni avanzate → Impostazioni firmware UEFI.</p>
          </div>

          <div className="bg-[#0F0F12] border border-[#00FF66]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#00FF66]"><ShieldCheck size={16} /> Impostazioni SICURE (consigliate)</div>
            <div className="border border-[#1A1A24]">{BIOS_SAFE.map((it, i) => <Row key={i} item={it} tone="safe" i={i} section="bios" />)}</div>
          </div>

          <div className="bg-[#0F0F12] border border-[#E5FF00]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#E5FF00]"><AlertTriangle size={16} /> Da usare CON CAUTELA</div>
            <div className="border border-[#1A1A24]">{BIOS_CAUTION.map((it, i) => <Row key={i} item={it} tone="caution" i={i} section="bios" />)}</div>
          </div>

          <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start">
            <Info size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-400 leading-relaxed">Regola d'oro: <span className="text-zinc-200">cambia una sola impostazione alla volta</span> e testa la stabilità. Annota i valori di default. Se il PC non parte, esegui un <span className="text-zinc-200">Clear CMOS</span> o carica i "Load Optimized Defaults".</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="bg-[#0F0F12] border border-[#00FF66]/30 p-5">
            <div className="flex items-center gap-2 text-sm font-bold mb-3 text-[#00FF66]"><ShieldCheck size={16} /> Ripristini SICURI (reversibili)</div>
            <div className="border border-[#1A1A24]">{RESTORE_SAFE.map((it, i) => <Row key={i} item={it} tone="safe" i={i} section="restore" />)}</div>
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
            <div className="border border-[#1A1A24]">{RESTORE_CAUTION.map((it, i) => <Row key={i} item={it} tone="caution" i={i} section="restore" />)}</div>
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
