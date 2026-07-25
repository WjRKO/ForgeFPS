/**
 * ScanPendingBanner — guida 4-step al primo scan, mostrata mentre il polling
 * aspetta i dati dall'agent locale.
 */
import { Download, FolderOpen, MousePointerClick, Sparkles, ArrowRight, Loader2 } from "lucide-react";

const scrollToDownload = () => {
  const el = document.querySelector('[data-testid="exe-download-block"]') || document.querySelector('[data-testid="quick-actions"]');
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
};

const STEPS = {
  en: [
    { id: "download", icon: Download, title: "1. Download the ZIP", desc: "Personalized with your token — no manual paste needed.", cta: "Download now", action: scrollToDownload },
    { id: "extract", icon: FolderOpen, title: "2. Extract the folder", desc: "Right click -> Extract all. Keep it wherever you want." },
    { id: "run", icon: MousePointerClick, title: "3. Double-click Avvia-FrameForge.bat", desc: "(Or forgefps-agent.exe.) The secure GUI opens instantly." },
    { id: "scan", icon: Sparkles, title: "4. Scan runs automatically", desc: "Hardware + health + startup + games detected in ~5s. This page will update the moment your data arrives." },
  ],
  it: [
    { id: "download", icon: Download, title: "1. Scarica lo ZIP", desc: "Personalizzato col tuo token — nessun copia-incolla manuale.", cta: "Scarica ora", action: scrollToDownload },
    { id: "extract", icon: FolderOpen, title: "2. Estrai la cartella", desc: "Tasto destro -> Estrai tutto. Puoi tenerla ovunque." },
    { id: "run", icon: MousePointerClick, title: "3. Doppio click su Avvia-FrameForge.bat", desc: "(Oppure forgefps-agent.exe.) La GUI sicura si apre in un istante." },
    { id: "scan", icon: Sparkles, title: "4. Lo scan parte da solo", desc: "Hardware + salute + avvio + giochi rilevati in ~5s. Questa pagina si aggiorna nel momento in cui i dati arrivano." },
  ],
};

function StepCard({ step, idx }) {
  const Icon = step.icon;
  return (
    <div
      className="bg-black/40 border border-[#2A2A35] hover:border-[#E5FF00]/40 p-4 transition-colors"
      data-testid={`first-scan-step-${idx + 1}`}
    >
      <Icon size={18} className="text-[#E5FF00] mb-2" />
      <div className="text-sm font-bold text-zinc-100 mb-1">{step.title}</div>
      <div className="text-xs text-zinc-500 leading-relaxed">{step.desc}</div>
      {step.cta && (
        <button
          onClick={step.action}
          data-testid={`first-scan-step-${idx + 1}-cta`}
          className="mt-3 text-xs font-bold text-[#E5FF00] hover:text-[#F5FF66] inline-flex items-center gap-1"
        >
          {step.cta} <ArrowRight size={12} />
        </button>
      )}
    </div>
  );
}

export default function ScanPendingBanner({ en }) {
  const steps = en ? STEPS.en : STEPS.it;

  return (
    <div className="border border-[#E5FF00]/40 bg-gradient-to-br from-[#E5FF00]/10 via-[#00E0FF]/5 to-transparent p-6 mb-6" data-testid="first-scan-pending">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 border border-[#E5FF00]/50 bg-black flex items-center justify-center shrink-0">
          <Loader2 size={18} className="text-[#E5FF00] animate-spin" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#E5FF00] mb-1">
            {en ? "// first scan · waiting..." : "// primo scan · in attesa..."}
          </div>
          <h2 className="font-display font-black text-2xl tracking-tighter text-zinc-100 mb-1">
            {en ? "4 steps to your first scan" : "4 step per il tuo primo scan"}
          </h2>
          <p className="text-xs text-zinc-400 leading-relaxed max-w-xl">
            {en
              ? "This page listens in real time. As soon as the FrameForge Agent starts on your PC, the scan arrives here automatically."
              : "Questa pagina ascolta in tempo reale. Non appena FrameForge Agent parte sul tuo PC, lo scan arriva qui da solo."}
          </p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {steps.map((step, i) => <StepCard key={step.id} step={step} idx={i} />)}
      </div>

      <div className="mt-4 flex items-center gap-2 text-[11px] text-zinc-500">
        <span className="w-1.5 h-1.5 bg-[#E5FF00] rounded-full animate-pulse" />
        {en
          ? "Polling every 3s. Leave this tab open — no refresh needed."
          : "Aggiorno ogni 3s. Tieni questa scheda aperta — nessun refresh necessario."}
      </div>
    </div>
  );
}
