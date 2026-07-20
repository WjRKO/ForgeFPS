import { ChevronRight, ChevronDown, ThumbsUp, ThumbsDown, X } from "lucide-react";

export function relTime(iso, t) {
  if (!iso) return "";
  const d = new Date(iso).getTime();
  const diff = (Date.now() - d) / 1000;
  if (diff < 60) return t("diagnose.just_now");
  if (diff < 3600) return `${Math.floor(diff / 60)} ${t("diagnose.min_ago")}`;
  if (diff < 86400) {
    const h = Math.floor(diff / 3600);
    return `${h} ${t(h === 1 ? "diagnose.hour_ago" : "diagnose.hours_ago")}`;
  }
  const days = Math.floor(diff / 86400);
  return `${days} ${t("diagnose.days_ago")}`;
}

export default function DiagnoseHeader({ t, result, createdAt, collapsed, outcome, onToggleCollapsed, onDismiss }) {
  const collapseLabel = collapsed ? t("diagnose.toggle_expand") : t("diagnose.toggle_collapse");
  return (
    <div className="p-5 border-b border-[#1A1A24] flex items-start gap-3">
      <button
        onClick={onToggleCollapsed}
        className="w-10 h-10 bg-[#00E0FF]/15 border border-[#00E0FF]/40 flex items-center justify-center shrink-0 hover:bg-[#00E0FF]/25 transition-colors group"
        data-testid="diagnose-collapse-toggle"
        aria-label={collapseLabel}
        aria-expanded={!collapsed}
        title={collapseLabel}
      >
        {collapsed
          ? <ChevronRight size={18} className="text-[#00E0FF] group-hover:translate-x-0.5 transition-transform" />
          : <ChevronDown size={18} className="text-[#00E0FF]" />}
      </button>
      <button
        onClick={onToggleCollapsed}
        className="flex-1 min-w-0 text-left"
        data-testid="diagnose-header-clickable"
        aria-label={collapseLabel}
      >
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#00E0FF]">
            {t("diagnose.header_prefix")} · {(result.actions || []).length} {t("diagnose.header_actions")}
          </div>
          {createdAt && (
            <span
              className="text-[10px] font-mono text-zinc-500"
              data-testid="diagnose-timestamp"
              title={new Date(createdAt).toLocaleString()}
            >
              · {t("diagnose.header_generated")} {relTime(createdAt, t)}
            </span>
          )}
          {collapsed && (
            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 border border-[#2A2A35] px-1.5 py-0.5">
              {t("diagnose.collapsed_badge")}
            </span>
          )}
        </div>
        <p className="text-sm text-zinc-200 leading-relaxed">
          {result.summary || t("diagnose.summary_fallback")}
        </p>
        {outcome?.available && outcome.delta !== 0 && (
          <div
            className={`mt-2 inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest border px-2 py-0.5 ${
              outcome.delta > 0
                ? "border-[#00FF66]/40 bg-[#00FF66]/10 text-[#00FF66]"
                : "border-[#FF3B30]/40 bg-[#FF3B30]/10 text-[#FF3B30]"
            }`}
            data-testid="outcome-badge"
          >
            {outcome.delta > 0 ? <ThumbsUp size={10} /> : <ThumbsDown size={10} />}
            {t("diagnose.outcome_after")} {outcome.delta > 0 ? "+" : ""}{outcome.delta} {t("diagnose.outcome_points")}
          </div>
        )}
      </button>
      <button
        onClick={onDismiss}
        className="text-zinc-500 hover:text-white shrink-0"
        data-testid="diagnose-close"
        aria-label={t("diagnose.close")}
      >
        <X size={16} />
      </button>
    </div>
  );
}
