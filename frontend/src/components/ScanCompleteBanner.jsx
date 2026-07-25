/**
 * ScanCompleteBanner — mostrato dopo che il primo scan arriva durante la sessione.
 * Green success card con CPU/GPU/RAM rilevati + CTA verso "My PC" e Dashboard.
 */
import { Link } from "react-router-dom";
import { CheckCircle2, ArrowRight } from "lucide-react";

export default function ScanCompleteBanner({ specs, en }) {
  return (
    <div className="border border-[#00FF66]/40 bg-[#00FF66]/5 p-5 mb-6" data-testid="first-scan-done">
      <div className="flex items-start gap-3">
        <CheckCircle2 size={20} className="shrink-0 text-[#00FF66] mt-0.5" />
        <div className="min-w-0 flex-1">
          <div className="text-xs uppercase tracking-[0.2em] text-[#00FF66] mb-1">
            {en ? "// scan complete" : "// scan completato"}
          </div>
          <h3 className="font-display font-black text-lg text-zinc-100 mb-1">
            {en ? "Your first scan is in!" : "Il tuo primo scan e' arrivato!"}
          </h3>
          <p className="text-xs text-zinc-400 leading-relaxed">
            {en ? "Detected: " : "Rilevato: "}
            <span className="text-[#00E0FF] font-semibold">{specs?.cpu || "CPU"}</span>
            {" · "}
            <span className="text-[#00E0FF] font-semibold">{specs?.gpu || "GPU"}</span>
            {specs?.ram && <> {" · "} <span className="text-[#00E0FF] font-semibold">{specs.ram}</span></>}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              to="/app/mypc"
              data-testid="first-scan-goto-mypc"
              className="inline-flex items-center gap-1.5 bg-[#00FF66] text-black font-bold text-xs px-3 py-1.5 hover:bg-[#33FF99] transition-colors"
            >
              {en ? "See my PC" : "Vedi il mio PC"} <ArrowRight size={12} />
            </Link>
            <Link
              to="/app"
              data-testid="first-scan-goto-dashboard"
              className="inline-flex items-center gap-1.5 border border-[#00FF66]/40 text-[#00FF66] font-bold text-xs px-3 py-1.5 hover:bg-[#00FF66]/10 transition-colors"
            >
              {en ? "Back to dashboard" : "Torna al dashboard"}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
