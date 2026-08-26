/**
 * Viste stateless per gli stati del DiagnosePanel: Idle CTA, Loading, Error, Empty.
 * Tutti i handler e la copy vengono passati come props dal componente principale.
 */
import { Link } from "react-router-dom";
import {
  Stethoscope, ChevronRight, Loader2, AlertTriangle, X, MonitorDown,
} from "lucide-react";
import { useTranslation } from "react-i18next";

export function DiagnoseIdleCTA({ onRun, isEn, t }) {
  return (
    <button
      onClick={onRun}
      data-testid="diagnose-btn"
      className="w-full group border border-volt/40 hover:border-volt bg-gradient-to-r from-volt/10 via-info/5 to-transparent hover:from-volt/20 hover:via-info/10 p-5 transition-all text-left"
    >
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-volt text-black flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
          <Stethoscope size={24} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-volt mb-1">
            // AI COACH · KILLER FEATURE
          </div>
          <h3 className="font-display font-black text-xl tracking-tighter text-white mb-0.5">
            {t("diagnose.title")}
          </h3>
          <p className="text-zinc-400 text-sm">
            {isEn
              ? "One click. 3-5 prioritized actions just for your hardware: estimated impact, difficulty, apply in a tap."
              : "Un click. 3-5 azioni prioritizzate solo per il tuo hardware: impatto stimato, difficoltà, applica in un tap."}
          </p>
        </div>
        <ChevronRight size={20} className="text-volt group-hover:translate-x-1 transition-transform" />
      </div>
    </button>
  );
}

export function DiagnoseLoading({ isEn }) {
  return (
    <div
      className="border border-volt/40 bg-panel p-8 flex flex-col items-center gap-3"
      data-testid="diagnose-loading"
    >
      <Loader2 size={32} className="text-volt animate-spin" />
      <div className="text-sm text-zinc-300 font-mono uppercase tracking-widest">
        {isEn ? "AI is analyzing your PC..." : "L'AI sta analizzando il tuo PC..."}
      </div>
      <div className="text-xs text-zinc-500">
        {isEn ? "Health checks, benchmark trend, hardware, tweaks" : "Health checks, benchmark trend, hardware, tweak"}
      </div>
    </div>
  );
}

export function DiagnoseErrorView({ error, isEn, onRetry, onDismiss }) {
  return (
    <div
      className="border border-bad/50 bg-bad/5 p-4 flex items-start gap-3"
      data-testid="diagnose-error"
    >
      <AlertTriangle size={20} className="text-bad shrink-0 mt-0.5" />
      <div className="flex-1">
        <div className="font-semibold text-bad mb-1">
          {isEn ? "Diagnosis failed" : "Diagnosi fallita"}
        </div>
        <div className="text-sm text-zinc-400 mb-3">{error}</div>
        <button
          onClick={onRetry}
          className="text-xs font-mono uppercase tracking-widest text-volt hover:underline"
          data-testid="diagnose-retry"
        >
          {isEn ? "Retry →" : "Riprova →"}
        </button>
      </div>
      <button onClick={onDismiss} aria-label={isEn ? "Close" : "Chiudi"} className="text-zinc-500 hover:text-white">
        <X size={16} />
      </button>
    </div>
  );
}

export function DiagnoseEmpty() {
  const { t } = useTranslation();
  return (
    <div
      className="mb-6 border border-volt/30 bg-gradient-to-br from-volt/10 to-transparent p-5"
      data-testid="diagnose-empty"
    >
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-volt/20 border border-volt/40 flex items-center justify-center shrink-0">
          <Stethoscope size={24} className="text-volt" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-display font-black text-lg tracking-tight text-white mb-1">
            {t("diagnose.title")}
          </h3>
          <p className="text-zinc-400 text-sm mb-3">
            {t("diagnose.empty_desc")}
          </p>
          <Link
            to="/app/desktop"
            className="inline-flex items-center gap-1.5 border border-volt/50 text-volt hover:bg-volt/10 px-4 py-2 text-xs font-mono uppercase tracking-widest transition-colors"
            data-testid="diagnose-connect-cta"
          >
            <MonitorDown size={13} /> {t("diagnose.connect_cta")} →
          </Link>
        </div>
      </div>
    </div>
  );
}
