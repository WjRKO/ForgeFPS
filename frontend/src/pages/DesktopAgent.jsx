import { Link } from "react-router-dom";
import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu, Activity } from "lucide-react";
import { API } from "@/lib/api";

const ACTIONS = [
  { icon: HardDrive, title: "Pulizia file temporanei", desc: "Rimuove cache e file temporanei di Windows liberando spazio su disco." },
  { icon: Gauge, title: "Piano energetico prestazioni", desc: "Attiva il profilo High Performance per massimizzare CPU e GPU." },
  { icon: Cpu, title: "Processi pesanti", desc: "Mostra i processi che consumano piu' RAM per chiuderli." },
  { icon: Wind, title: "Tweak gaming", desc: "Abilita Game Mode e Hardware-Accelerated GPU Scheduling." },
  { icon: Terminal, title: "Rileva hardware/salute", desc: "Rileva CPU/GPU/RAM/temperature e le invia per analisi e consigli AI." },
  { icon: ShieldCheck, title: "Backup / Ripristino tweak", desc: "Salva lo stato prima delle modifiche e ripristina quando vuoi." },
];

const STEPS = [
  "Windows 10/11 + Python 3.9+ (esegui come Amministratore consigliato)",
  "Avvia: python boostpc_agent.py",
  "Opzione 7 → rileva e invia hardware/salute al tuo account",
  "Opzione 8 → ripristina le impostazioni dal backup",
];

export default function DesktopAgent() {
  return (
    <div className="max-w-5xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Desktop Agent</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Azioni reali sul PC</h1>
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-8 mb-6">
        <div className="flex flex-col sm:flex-row items-start gap-6">
          <div className="w-14 h-14 bg-[#E5FF00] flex items-center justify-center shrink-0"><MonitorDown size={28} className="text-black" /></div>
          <div className="flex-1">
            <h2 className="font-display font-bold text-xl mb-2">BOOST PC Desktop Agent (Windows)</h2>
            <p className="text-zinc-400 text-sm leading-relaxed mb-5 max-w-2xl">
              Il browser non può modificare il sistema. Scarica il companion locale in Python: esegue azioni
              <span className="text-[#E5FF00]"> reali</span> di ottimizzazione e rileva l'hardware del tuo PC.
              Il file è <span className="text-[#00FF66]">già collegato al tuo account</span> (token incluso).
            </p>
            <div className="flex flex-wrap gap-3">
              <a data-testid="download-agent-btn" href={`${API}/desktop-agent/download`}
                className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3 hover:bg-[#D4EC00] transition-colors volt-glow">
                <Download size={18} /> Scarica l'agent (.py)
              </a>
              <Link to="/app/pc" data-testid="to-mypc-btn"
                className="inline-flex items-center gap-2 border border-[#2A2A35] px-6 py-3 hover:border-[#E5FF00] transition-colors">
                <Activity size={18} /> Vedi analisi "Il mio PC"
              </Link>
            </div>
          </div>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[#2A2A35] border border-[#2A2A35] mb-6">
        {ACTIONS.map((a, i) => (
          <div key={i} className="bg-[#0F0F12] p-6">
            <a.icon size={20} className="text-[#E5FF00] mb-3" />
            <h3 className="font-display font-semibold text-base mb-1">{a.title}</h3>
            <p className="text-zinc-500 text-xs leading-relaxed">{a.desc}</p>
          </div>
        ))}
      </div>

      <div className="bg-black border border-[#2A2A35] p-5 font-mono text-xs text-zinc-400">
        <div className="text-[#00FF66] mb-2"># Come si usa</div>
        {STEPS.map((s, i) => <div key={i}>{i + 1}. {s}</div>)}
      </div>
    </div>
  );
}
