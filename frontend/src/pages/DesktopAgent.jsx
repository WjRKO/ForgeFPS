import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu, Activity, Copy, Check, Zap, RotateCcw, Gamepad2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const ACTIONS = [
  { icon: Gauge, title: "Benchmark prima/dopo", desc: "Misura CPU, RAM, disco e latenza di rete prima e dopo l'ottimizzazione per vedere il guadagno reale." },
  { icon: Wind, title: "Pannello grafico a categorie", desc: "Il comando 'Ottimizza' apre una finestra con tab (Gaming/Latenza/Rete/Sistema), preset Competitivo/Streaming/Completo e 26 tweak con stato attuale." },
  { icon: Terminal, title: "Tweak pro NVIDIA/AMD/OBS", desc: "MSI mode GPU (latenza DPC), MPO off (fix schermo nero OBS), timer resolution, OBS ad alta priorità, disabilita telemetria NVIDIA / ULPS AMD." },
  { icon: HardDrive, title: "Debloat & pulizia", desc: "Rimuove app superflue, telemetria, ads di Windows e pulisce temp + cache Windows Update." },
  { icon: Cpu, title: "Rileva hardware/salute", desc: "Rileva CPU/GPU/RAM/temperature e le invia per analisi e consigli AI su misura." },
  { icon: ShieldCheck, title: "Backup / Ripristino tweak", desc: "Ogni modifica è salvata: ripristini tutto con un comando quando vuoi. Sicuro e reversibile." },
];

const GPU_GUIDE = {
  nvidia: {
    label: "NVIDIA Control Panel",
    path: "Pannello di controllo NVIDIA → Gestisci impostazioni 3D → Impostazioni globali",
    rows: [
      { s: "Modalità gestione energia", v: "Prestazioni massime preferite", w: "Tiene la GPU ai clock massimi, niente cali di frequenza." },
      { s: "Modalità bassa latenza", v: "Ultra", w: "Riduce il ritardo di rendering: input più reattivo (competitive)." },
      { s: "Sync verticale (V-Sync)", v: "Off (On solo con G-Sync)", w: "Meno input lag. Con G-Sync: V-Sync On + cap FPS." },
      { s: "Max Frame Rate", v: "3 FPS sotto il refresh (es. 141 per 144Hz)", w: "Con G-Sync evita tearing e mantiene la latenza minima." },
      { s: "Filtro texture - Qualità", v: "Prestazioni elevate", w: "Più FPS con impatto visivo minimo." },
      { s: "Threaded Optimization", v: "On", w: "Distribuisce il carico driver su più core CPU." },
      { s: "Dimensione cache shader", v: "10 GB / Illimitata", w: "Meno stutter da compilazione shader." },
      { s: "Frequenza aggiornamento preferita", v: "Massima disponibile", w: "Forza il refresh rate più alto del monitor." },
      { s: "Monitor Technology", v: "G-SYNC (se supportato)", w: "Sincronizzazione adattiva senza tearing." },
    ],
  },
  amd: {
    label: "AMD Adrenalin",
    path: "AMD Software: Adrenalin Edition → Gaming → Grafica",
    rows: [
      { s: "Radeon Anti-Lag", v: "Abilitato (Anti-Lag+ se disponibile)", w: "Riduce la latenza di input nei giochi." },
      { s: "Radeon Chill", v: "Disattivato", w: "Per competitive: nessun cap dinamico di FPS." },
      { s: "Wait for Vertical Refresh", v: "Off, salvo diversa indicazione", w: "Meno input lag (usa FreeSync per il tearing)." },
      { s: "Texture Filtering Quality", v: "Performance", w: "Più FPS con impatto visivo minimo." },
      { s: "Surface Format Optimization", v: "On", w: "Ottimizza l'uso della VRAM." },
      { s: "Tessellation Mode", v: "Override → AMD optimized / 8x", w: "Meno carico GPU da tessellazione eccessiva." },
      { s: "Enhanced Sync", v: "On (se non usi FreeSync)", w: "Riduce tearing senza il lag del V-Sync classico." },
      { s: "FreeSync", v: "On (nel monitor) + cap FPS", w: "Sincronizzazione adattiva: fluidità senza tearing." },
      { s: "GPU Workload", v: "Graphics", w: "Massime prestazioni per il gaming (non compute)." },
    ],
  },
};

function GpuGuide({ vendor }) {
  const [tab, setTab] = useState(vendor === "AMD" ? "amd" : "nvidia");
  useEffect(() => { if (vendor === "AMD") setTab("amd"); else if (vendor === "NVIDIA") setTab("nvidia"); }, [vendor]);
  const g = GPU_GUIDE[tab];
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="gpu-guide-card">
      <div className="flex items-start gap-4 mb-4">
        <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center shrink-0"><Gamepad2 size={22} className="text-[#E5FF00]" /></div>
        <div>
          <h3 className="font-display font-bold text-lg">Impostazioni consigliate pannello GPU</h3>
          <p className="text-zinc-500 text-sm mt-1 max-w-2xl">Queste vanno impostate a mano nel pannello del driver (non modificabili via script). Valori ottimizzati per gaming/streaming competitivo.</p>
        </div>
      </div>
      <div className="flex gap-2 mb-4">
        {["nvidia", "amd"].map((k) => (
          <button key={k} data-testid={`gpu-tab-${k}`} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-bold transition-colors ${tab === k ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
            {GPU_GUIDE[k].label}{vendor === (k === "nvidia" ? "NVIDIA" : "AMD") ? " ·  la tua GPU" : ""}
          </button>
        ))}
      </div>
      <div className="text-xs text-zinc-500 mb-3 flex items-center gap-2"><Sparkles size={13} className="text-[#00E0FF]" /> {g.path}</div>
      <div className="border border-[#1A1A24]">
        {g.rows.map((r, i) => (
          <div key={i} data-testid={`gpu-setting-${tab}-${i}`} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr] gap-1 sm:gap-4 p-3 border-b border-[#1A1A24] last:border-0">
            <div>
              <div className="text-sm text-zinc-200">{r.s}</div>
              <div className="text-xs text-zinc-600 mt-0.5">{r.w}</div>
            </div>
            <div className="text-sm font-bold text-[#00FF66] flex items-center">{r.v}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs text-zinc-500 border-t border-[#1A1A24] pt-3">
        💡 Setup latenza ottimale: G-Sync/FreeSync <span className="text-zinc-300">On</span> + V-Sync <span className="text-zinc-300">On (pannello)</span> + cap FPS 3 sotto il refresh + Low Latency <span className="text-zinc-300">Ultra</span>. Aggiorna sempre i driver (usa DDU per una pulizia completa).
      </div>
    </div>
  );
}

function CmdRow({ label, cmd, testid, accent }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); } catch { const t = document.createElement("textarea"); t.value = cmd; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success("Comando copiato!"); setTimeout(() => setCopied(false), 2000);
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

export default function DesktopAgent() {
  const [token, setToken] = useState("");
  const [gpuVendor, setGpuVendor] = useState(null);
  useEffect(() => { api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {}); }, []);
  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => {
      const gpu = (data?.data?.gpu || "").toUpperCase();
      if (/NVIDIA|GEFORCE|RTX|GTX/.test(gpu)) setGpuVendor("NVIDIA");
      else if (/AMD|RADEON|\bRX\b/.test(gpu)) setGpuVendor("AMD");
    }).catch(() => {});
  }, []);

  const cmd = (mode) => `irm "${BACKEND}/api/agent/script?t=${token || "IL_TUO_TOKEN"}&mode=${mode}" | iex`;

  return (
    <div className="max-w-5xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Desktop Agent</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Azioni reali sul PC</h1>
      </div>

      {/* Quick method: PowerShell */}
      <div className="bg-[#0F0F12] border border-[#E5FF00]/40 p-6 mb-4">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-11 h-11 bg-[#E5FF00] flex items-center justify-center shrink-0"><Zap size={22} className="text-black" /></div>
          <div>
            <h2 className="font-display font-bold text-lg">Metodo rapido — PowerShell (consigliato)</h2>
            <p className="text-zinc-400 text-sm mt-1 max-w-2xl">Nessun download, niente Python. Apri <span className="text-white">PowerShell</span>, incolla un comando e premi Invio. Il tuo account è già collegato.</p>
          </div>
        </div>

        <CmdRow label="1 · Sincronizza (sicuro, rileva e invia hardware/salute)" cmd={cmd("sync")} testid="ps-sync" accent="text-[#00FF66]" />
        <CmdRow label="2 · Benchmark (misura CPU/RAM/disco/rete — nessun cambiamento)" cmd={cmd("benchmark")} testid="ps-benchmark" accent="text-[#00E0FF]" />
        <CmdRow label="3 · Ottimizza — apre una finestra grafica per scegliere i tweak (esegui come Amministratore)" cmd={cmd("optimize")} testid="ps-optimize" accent="text-[#E5FF00]" />
        <CmdRow label="4 · Monitoraggio live — invia CPU/GPU/temp in tempo reale (vedi pagina Monitoraggio Live)" cmd={cmd("monitor")} testid="ps-monitor" accent="text-[#FF6B00]" />

        <div className="flex items-center gap-2 text-xs text-zinc-500 mt-2">
          <RotateCcw size={13} /> Ripristino tweak:
          <code className="text-zinc-400 truncate" data-testid="ps-restore-cmd">{cmd("restore")}</code>
        </div>
        <p className="text-xs text-zinc-600 mt-3">Nota: Windows può chiedere conferma per l'esecuzione (ExecutionPolicy). Le ottimizzazioni di sistema richiedono privilegi di Amministratore.</p>
      </div>

      {/* Fallback: download .py */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6">
        <div className="flex flex-col sm:flex-row items-start gap-4">
          <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center shrink-0"><MonitorDown size={22} className="text-zinc-400" /></div>
          <div className="flex-1">
            <h3 className="font-display font-semibold">In alternativa: agent Python (.py)</h3>
            <p className="text-zinc-500 text-sm mt-1 mb-3">Menu interattivo completo. Richiede Python 3.9+.</p>
            <div className="flex flex-wrap gap-3">
              <a data-testid="download-agent-btn" href={`${API}/desktop-agent/download`}
                className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 text-sm hover:border-[#E5FF00] transition-colors">
                <Download size={16} /> Scarica l'agent (.py)
              </a>
              <Link to="/app/pc" data-testid="to-mypc-btn"
                className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 text-sm hover:border-[#E5FF00] transition-colors">
                <Activity size={16} /> Vedi "Il mio PC"
              </Link>
            </div>
          </div>
        </div>
      </div>

      <GpuGuide vendor={gpuVendor} />

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[#2A2A35] border border-[#2A2A35]">
        {ACTIONS.map((a, i) => (
          <div key={i} className="bg-[#0F0F12] p-6">
            <a.icon size={20} className="text-[#E5FF00] mb-3" />
            <h3 className="font-display font-semibold text-base mb-1">{a.title}</h3>
            <p className="text-zinc-500 text-xs leading-relaxed">{a.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
