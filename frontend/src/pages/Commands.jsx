import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Terminal, Copy, Check, ShieldAlert, MessageSquareCode, Trash2, Wrench, Wifi, Zap, Package, Search, MonitorPlay } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

const CATS = [
  {
    id: "clean", title: "Pulizia & Manutenzione", icon: Trash2, color: "#00FF66",
    items: [
      { cmd: "ipconfig /flushdns", desc: "Svuota la cache DNS: risolve siti o giochi che non si connettono." },
      { cmd: "cleanmgr /sagerun:1", desc: "Avvia la Pulizia disco per rimuovere i file temporanei di sistema." },
      { cmd: "wsreset.exe", desc: "Resetta la cache del Microsoft Store (fix download/app bloccate)." },
      { cmd: "Get-ChildItem $env:TEMP -Recurse | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue", desc: "Svuota la cartella dei file temporanei dell'utente." },
    ],
  },
  {
    id: "repair", title: "Riparazione sistema", icon: Wrench, color: "#E5FF00",
    items: [
      { cmd: "sfc /scannow", desc: "Cerca e ripara i file di sistema di Windows danneggiati.", admin: true },
      { cmd: "DISM /Online /Cleanup-Image /RestoreHealth", desc: "Ripara l'immagine di Windows. Eseguilo prima di sfc se il problema persiste.", admin: true },
      { cmd: "chkdsk C: /f /r", desc: "Controlla e ripara gli errori del disco C: al prossimo riavvio.", admin: true },
    ],
  },
  {
    id: "net", title: "Rete", icon: Wifi, color: "#00E0FF",
    items: [
      { cmd: "netsh winsock reset", desc: "Reset dello stack di rete Winsock: fix lag o assenza di internet. Riavvia dopo.", admin: true },
      { cmd: "netsh int ip reset", desc: "Reset della configurazione IP di Windows.", admin: true },
      { cmd: "ipconfig /release; ipconfig /renew", desc: "Rilascia e rinnova l'indirizzo IP assegnato dal router." },
      { cmd: "Test-Connection 1.1.1.1 -Count 10", desc: "Esegue 10 ping a Cloudflare per verificare stabilità e latenza." },
    ],
  },
  {
    id: "perf", title: "Prestazioni & Gaming", icon: Zap, color: "#E5FF00",
    items: [
      { cmd: "powercfg /setactive scheme_min", desc: "Attiva il piano di alimentazione Prestazioni elevate." },
      { cmd: "powercfg /energy", desc: "Genera un report HTML sui problemi energetici e di consumo.", admin: true },
      { cmd: "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10", desc: "Mostra i 10 processi che stanno consumando più CPU adesso." },
    ],
  },
  {
    id: "apps", title: "Gestione app (winget)", icon: Package, color: "#00FF66",
    items: [
      { cmd: "winget upgrade --all", desc: "Aggiorna in un colpo solo tutti i programmi installati sul PC." },
      { cmd: "winget list", desc: "Elenca tutto il software installato con la versione." },
    ],
  },
  {
    id: "diag", title: "Diagnostica", icon: Search, color: "#00E0FF",
    items: [
      { cmd: "pnputil /enum-devices /problem", desc: "Elenca i dispositivi e i driver che presentano un problema.", admin: true },
      { cmd: "DISM /Online /Cleanup-Image /AnalyzeComponentStore", desc: "Controlla se conviene pulire lo store dei componenti di Windows.", admin: true },
      { cmd: "dxdiag", desc: "Apre lo strumento di diagnostica DirectX (GPU, driver, audio)." },
    ],
  },
];

function detectGpu(gpuStr = "") {
  const g = gpuStr.toLowerCase();
  if (/nvidia|geforce|rtx|gtx|quadro/.test(g)) return "nvidia";
  if (/radeon|\brx ?\d|vega/.test(g)) return "amd";
  if (/\barc\b|intel/.test(g)) return "intel";
  return null;
}

const GPU_CMD = {
  nvidia: { label: "GPU NVIDIA", cmd: 'Start-Process "https://www.nvidia.com/Download/index.aspx"', desc: "Apre la pagina di download dei driver GeForce Game Ready per la tua NVIDIA." },
  amd: { label: "GPU AMD", cmd: 'Start-Process "https://www.amd.com/en/support"', desc: "Apre la pagina di download dei driver AMD Adrenalin per la tua Radeon." },
  intel: { label: "GPU Intel", cmd: 'Start-Process "https://www.intel.com/content/www/us/en/download-center/home.html"', desc: "Apre il download center per i driver della tua Intel Arc." },
};

function CmdRow({ item, onAsk }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(item.cmd); } catch { const t = document.createElement("textarea"); t.value = item.cmd; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success("Comando copiato!"); setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="p-4 border-b border-[#1A1A24] last:border-0" data-testid={`cmd-${item.cmd.slice(0, 24)}`}>
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        {item.admin && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-1.5 py-0.5" data-testid="admin-badge">
            <ShieldAlert size={11} /> Richiede Admin
          </span>
        )}
        <span className="text-xs text-zinc-500 leading-relaxed">{item.desc}</span>
      </div>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap">{item.cmd}</code>
        <button onClick={copy} data-testid="cmd-copy"
          className="shrink-0 flex items-center justify-center border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors">
          {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
        </button>
        <button onClick={() => onAsk(item)} data-testid="cmd-ask-ai"
          className="shrink-0 inline-flex items-center gap-1 border border-[#2A2A35] px-2.5 text-[11px] text-zinc-400 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors whitespace-nowrap">
          <MessageSquareCode size={12} /> Chiedi all'AI
        </button>
      </div>
    </div>
  );
}

export default function Commands() {
  const [specs, setSpecs] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
  }, []);

  const data = specs?.data || {};
  const gpuBrand = useMemo(() => detectGpu(data.gpu), [specs]);

  const cats = useMemo(() => {
    const list = [...CATS];
    const g = gpuBrand && GPU_CMD[gpuBrand];
    if (g) {
      list.push({
        id: "gpu", title: `Driver GPU (${g.label})`, icon: MonitorPlay, color: "#00FF66",
        items: [g, { cmd: "dxdiag", desc: "Verifica il modello GPU e la versione driver attualmente installati." }],
      });
    }
    return list;
  }, [gpuBrand]);

  const askAI = (item) => {
    const sys = [data.cpu?.trim(), data.gpu, data.os].filter(Boolean).join(", ");
    const q = `Spiegami in modo semplice cosa fa il comando "${item.cmd}" su Windows, quando conviene usarlo e se comporta rischi.${sys ? ` Il mio sistema: ${sys}.` : ""}`;
    navigate("/app/advisor", { state: { ask: q } });
  };

  return (
    <div className="max-w-4xl mx-auto fade-up" data-testid="commands-page">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Toolbox</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Comandi Utili</h1>
        <p className="text-zinc-500 text-sm mt-1">Comandi quotidiani per manutenzione, rete e prestazioni. Copia e incolla nel Terminale.</p>
      </div>

      <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start mb-5">
        <Terminal size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
        <p className="text-xs text-zinc-400 leading-relaxed">
          Per i comandi con <span className="text-[#FF3B30] font-bold">Richiede Admin</span>: apri <span className="text-zinc-200">PowerShell come amministratore</span> (tasto destro su Start → "Terminale (Admin)"). Gli altri funzionano anche in una finestra normale.
        </p>
      </div>

      <div className="space-y-4">
        {cats.map((cat) => (
          <div key={cat.id} className="bg-[#0F0F12] border border-[#2A2A35]" data-testid={`cmd-cat-${cat.id}`}>
            <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2A35]">
              <cat.icon size={16} style={{ color: cat.color }} />
              <span className="text-sm font-bold text-zinc-100">{cat.title}</span>
            </div>
            <div>{cat.items.map((it, i) => <CmdRow key={i} item={it} onAsk={askAI} />)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
