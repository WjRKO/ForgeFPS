import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu } from "lucide-react";
import { API } from "@/lib/api";

const ACTIONS = [
  { icon: HardDrive, title: "Pulizia file temporanei", desc: "Rimuove cache e file temporanei di Windows liberando spazio su disco." },
  { icon: Gauge, title: "Piano energetico prestazioni", desc: "Attiva il profilo High Performance per massimizzare CPU e GPU." },
  { icon: Cpu, title: "Processi pesanti", desc: "Mostra i processi che consumano piu' RAM per chiuderli." },
  { icon: Wind, title: "Tweak gaming", desc: "Abilita Game Mode e Hardware-Accelerated GPU Scheduling." },
  { icon: Terminal, title: "Flush DNS", desc: "Svuota la cache DNS per ridurre problemi di rete e latenza." },
  { icon: ShieldCheck, title: "Pulizia disco", desc: "Avvia lo strumento di pulizia disco integrato di Windows." },
];

export default function DesktopAgent() {
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
              Per motivi di sicurezza il browser non può modificare il tuo sistema. Scarica il companion locale in Python:
              esegue azioni <span className="text-[#E5FF00]">reali</span> di ottimizzazione direttamente su Windows.
              Avvialo con <code className="text-[#00FF66]">python boostpc_agent.py</code> (consigliato come Amministratore).
            </p>
            <a data-testid="download-agent-btn" href={`${API}/desktop-agent/download`}
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3 hover:bg-[#D4EC00] transition-colors volt-glow">
              <Download size={18} /> Scarica l'agent (.py)
            </a>
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

      <div className="mt-6 bg-black border border-[#2A2A35] p-5 font-mono text-xs text-zinc-400">
        <div className="text-[#00FF66] mb-2"># Requisiti</div>
        <div>1. Windows 10/11 + Python 3.9+</div>
        <div>2. Scarica il file e avvialo: <span className="text-[#E5FF00]">python boostpc_agent.py</span></div>
        <div>3. Scegli un'azione dal menu (o "A" per eseguirle tutte)</div>
      </div>
    </div>
  );
}
