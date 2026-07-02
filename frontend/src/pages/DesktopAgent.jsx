import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu, Activity, Copy, Check, Zap, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const ACTIONS = [
  { icon: HardDrive, title: "Pulizia file temporanei", desc: "Rimuove cache e file temporanei di Windows liberando spazio su disco." },
  { icon: Gauge, title: "Piano energetico prestazioni", desc: "Attiva il profilo High Performance per massimizzare CPU e GPU." },
  { icon: Cpu, title: "Rileva hardware/salute", desc: "Rileva CPU/GPU/RAM/temperature e le invia per analisi e consigli AI." },
  { icon: Wind, title: "Tweak gaming", desc: "Abilita Game Mode e Hardware-Accelerated GPU Scheduling." },
  { icon: Terminal, title: "Flush DNS", desc: "Svuota la cache DNS per ridurre problemi di rete e latenza." },
  { icon: ShieldCheck, title: "Backup / Ripristino tweak", desc: "Salva lo stato prima delle modifiche e ripristina quando vuoi." },
];

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
  useEffect(() => { api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {}); }, []);

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
        <CmdRow label="2 · Ottimizza (applica tweak — apri PowerShell come Amministratore)" cmd={cmd("optimize")} testid="ps-optimize" accent="text-[#E5FF00]" />

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
