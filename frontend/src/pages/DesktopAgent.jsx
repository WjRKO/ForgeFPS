import { useEffect, useState } from "react";
import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu, RefreshCw, CheckCircle2 } from "lucide-react";
import api, { API } from "@/lib/api";

const ACTIONS = [
  { icon: HardDrive, title: "Pulizia file temporanei", desc: "Rimuove cache e file temporanei di Windows liberando spazio su disco." },
  { icon: Gauge, title: "Piano energetico prestazioni", desc: "Attiva il profilo High Performance per massimizzare CPU e GPU." },
  { icon: Cpu, title: "Processi pesanti", desc: "Mostra i processi che consumano piu' RAM per chiuderli." },
  { icon: Wind, title: "Tweak gaming", desc: "Abilita Game Mode e Hardware-Accelerated GPU Scheduling." },
  { icon: Terminal, title: "Flush DNS", desc: "Svuota la cache DNS per ridurre problemi di rete e latenza." },
  { icon: ShieldCheck, title: "Rileva hardware + invia", desc: "Rileva CPU/GPU/RAM del PC e le invia per consigli AI su misura." },
];

const SPEC_LABELS = { os: "Sistema operativo", cpu: "CPU", gpu: "GPU", ram: "RAM", disk: "Storage", motherboard: "Scheda madre", resolution: "Risoluzione" };

export default function DesktopAgent() {
  const [specs, setSpecs] = useState(null);

  const load = async () => { try { const { data } = await api.get("/pc-specs"); setSpecs(data); } catch {} };
  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-5xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Desktop Agent</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Azioni reali sul PC</h1>
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-8 mb-6 relative overflow-hidden">
        <div className="relative z-10 flex flex-col sm:flex-row items-start gap-6">
          <div className="w-14 h-14 bg-[#E5FF00] flex items-center justify-center shrink-0"><MonitorDown size={28} className="text-black" /></div>
          <div className="flex-1">
            <h2 className="font-display font-bold text-xl mb-2">BOOST PC Desktop Agent (Windows)</h2>
            <p className="text-zinc-400 text-sm leading-relaxed mb-5 max-w-2xl">
              Il browser non può modificare il sistema. Scarica il companion locale in Python: esegue azioni
              <span className="text-[#E5FF00]"> reali</span> di ottimizzazione e rileva l'hardware del tuo PC.
              Il file è <span className="text-[#00FF66]">già collegato al tuo account</span> (token incluso): avvialo con
              <code className="text-[#00FF66]"> python boostpc_agent.py</code> e scegli l'opzione 7 per inviare le specifiche.
            </p>
            <a data-testid="download-agent-btn" href={`${API}/desktop-agent/download`}
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3 hover:bg-[#D4EC00] transition-colors volt-glow">
              <Download size={18} /> Scarica l'agent (.py)
            </a>
          </div>
        </div>
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35] mb-6">
        <div className="p-5 border-b border-[#2A2A35] flex items-center justify-between">
          <span className="text-xs uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2"><Cpu size={14} className="text-[#E5FF00]" /> Il mio PC</span>
          <button data-testid="refresh-specs-btn" onClick={load} className="text-zinc-500 hover:text-[#E5FF00]"><RefreshCw size={15} /></button>
        </div>
        {specs?.data ? (
          <div>
            <div className="p-4 flex items-center gap-2 text-xs text-[#00FF66] border-b border-[#1A1A24]">
              <CheckCircle2 size={14} /> Hardware rilevato · l'AI Advisor userà questi dati per consigli su misura
            </div>
            <div className="grid sm:grid-cols-2 gap-px bg-[#1A1A24]">
              {Object.entries(SPEC_LABELS).filter(([k]) => specs.data[k]).map(([k, label]) => (
                <div key={k} className="bg-[#0F0F12] p-4" data-testid={`spec-${k}`}>
                  <div className="text-xs uppercase tracking-widest text-zinc-500">{label}</div>
                  <div className="text-sm text-zinc-100 mt-1">{specs.data[k]}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="p-8 text-center text-zinc-500 text-sm">
            Nessuna specifica ricevuta. Scarica ed esegui l'agent, poi scegli l'opzione <span className="text-[#E5FF00]">7</span> per inviare l'hardware.
          </div>
        )}
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
