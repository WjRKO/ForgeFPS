import { Link } from "react-router-dom";
import {
  Sparkles, ChevronRight, Zap, Wrench, MonitorDown, Bookmark, Check,
  Gauge, ThumbsUp, ThumbsDown, Eye, CheckCircle2,
} from "lucide-react";

const DIFFICULTY_STYLES = {
  facile:    { color: "text-[#00FF66]", key: "easy" },
  easy:      { color: "text-[#00FF66]", key: "easy" },
  medio:     { color: "text-[#E5FF00]", key: "medium" },
  medium:    { color: "text-[#E5FF00]", key: "medium" },
  avanzato:  { color: "text-[#FF6A00]", key: "advanced" },
  advanced:  { color: "text-[#FF6A00]", key: "advanced" },
};

const KIND_ICONS = {
  tweak: Zap,
  driver: MonitorDown,
  hardware: Gauge,
  maintenance: Wrench,
  manual: Sparkles,
};

export default function DiagnoseAction({ t, index, action, isActive, isSaved, feedback, verifyOpen, onToggleVerify, onApply, onToggleApplied, onSubmitFeedback }) {
  const Icon = KIND_ICONS[action.kind] || Zap;
  const diff = DIFFICULTY_STYLES[(action.difficulty || "").toLowerCase()] || DIFFICULTY_STYLES.facile;
  const diffLabel = t(`diagnose.difficulty_${diff.key}`);
  return (
    <div
      className={`p-5 transition-colors ${isActive ? "bg-[#00FF66]/5" : "hover:bg-[#0F0F12]"}`}
      data-testid={`diagnose-action-${index}`}
    >
      <div className="flex items-start gap-4">
        <div className="flex flex-col items-center shrink-0">
          <div className={`w-8 h-8 border font-black flex items-center justify-center ${isActive ? "border-[#00FF66]/60 bg-[#00FF66]/15 text-[#00FF66]" : "border-[#E5FF00]/50 bg-[#E5FF00]/10 text-[#E5FF00]"}`}>
            {isActive ? <CheckCircle2 size={14} /> : (action.priority || index + 1)}
          </div>
          <Icon size={14} className="text-zinc-500 mt-2" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h4 className={`font-display font-black text-base tracking-tight ${isActive ? "text-zinc-400 line-through" : "text-white"}`}>{action.title}</h4>
            {isActive ? (
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#00FF66] border border-[#00FF66]/40 bg-[#00FF66]/10 px-1.5">{t("diagnose.already_active")}</span>
            ) : (
              <span className={`text-[10px] font-mono uppercase tracking-widest ${diff.color}`}>{diffLabel}</span>
            )}
          </div>
          {!isActive && action.impact && (
            <div className="inline-flex items-center gap-1.5 text-xs text-[#00FF66] mb-2 font-mono">
              <Zap size={11} /> {action.impact}
            </div>
          )}
          <p className={`text-sm leading-relaxed mb-3 whitespace-pre-wrap ${isActive ? "text-zinc-500" : "text-zinc-400"}`}>{action.description}</p>

          {action.verify && (
            <div className="mb-3">
              <button
                onClick={onToggleVerify}
                className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-widest text-zinc-500 hover:text-[#00E0FF] transition-colors"
                data-testid={`diagnose-action-${index}-verify-toggle`}
              >
                <Eye size={11} /> {t("diagnose.verify_toggle")}
                <ChevronRight size={11} className={`transition-transform ${verifyOpen ? "rotate-90" : ""}`} />
              </button>
              {verifyOpen && (
                <div className="mt-2 p-3 border border-[#00E0FF]/30 bg-[#00E0FF]/5 text-xs text-zinc-300 leading-relaxed font-mono whitespace-pre-wrap" data-testid={`diagnose-action-${index}-verify`}>
                  {action.verify}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2 items-center">
            {!isActive && (
              <>
                <Link
                  to={action.kind === "driver" ? "/app/pc" : "/app/desktop"}
                  data-testid={`diagnose-action-${index}-apply`}
                  className="inline-flex items-center gap-1.5 bg-[#E5FF00] text-black font-bold px-3 py-1.5 text-[11px] font-mono uppercase tracking-widest hover:bg-white transition-colors"
                >
                  <MonitorDown size={12} /> {action.cta || t("diagnose.cta_apply_default")}
                </Link>
                <button
                  onClick={() => onApply(action)}
                  disabled={isSaved}
                  data-testid={`diagnose-action-${index}-save`}
                  className="inline-flex items-center gap-1.5 border border-[#2A2A35] hover:border-[#00E0FF] text-zinc-300 hover:text-[#00E0FF] px-3 py-1.5 text-[11px] font-mono uppercase tracking-widest transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSaved ? <><Check size={12} /> {t("diagnose.saved")}</> : <><Bookmark size={12} /> {t("diagnose.save")}</>}
                </button>
              </>
            )}
            <button
              onClick={() => onToggleApplied(action)}
              data-testid={`diagnose-action-${index}-mark-active`}
              className={`inline-flex items-center gap-1.5 border px-3 py-1.5 text-[11px] font-mono uppercase tracking-widest transition-colors ${
                isActive
                  ? "border-[#00FF66]/50 bg-[#00FF66]/10 text-[#00FF66] hover:bg-[#00FF66]/20"
                  : "border-[#2A2A35] hover:border-[#00FF66] text-zinc-400 hover:text-[#00FF66]"
              }`}
            >
              <CheckCircle2 size={12} /> {isActive ? t("diagnose.mark_inactive") : t("diagnose.mark_active")}
            </button>

            <div className="flex items-center gap-0.5 ml-auto">
              <button
                onClick={() => onSubmitFeedback(action, "up")}
                data-testid={`diagnose-action-${index}-thumb-up`}
                aria-label="Utile"
                className={`p-1.5 border transition-colors ${feedback === "up" ? "border-[#00FF66] bg-[#00FF66]/10 text-[#00FF66]" : "border-transparent text-zinc-600 hover:text-[#00FF66] hover:border-[#2A2A35]"}`}
              >
                <ThumbsUp size={12} />
              </button>
              <button
                onClick={() => onSubmitFeedback(action, "down")}
                data-testid={`diagnose-action-${index}-thumb-down`}
                aria-label={t("diagnose.thumb_not_useful")}
                className={`p-1.5 border transition-colors ${feedback === "down" ? "border-[#FF3B30] bg-[#FF3B30]/10 text-[#FF3B30]" : "border-transparent text-zinc-600 hover:text-[#FF3B30] hover:border-[#2A2A35]"}`}
              >
                <ThumbsDown size={12} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
