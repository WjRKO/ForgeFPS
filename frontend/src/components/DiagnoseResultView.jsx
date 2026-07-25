/**
 * DiagnoseResultView — vista "done" del DiagnosePanel: header (con collapse/dismiss),
 * lista delle azioni AI e footer con "rigenera".
 */
import { RefreshCw } from "lucide-react";
import DiagnoseHeader from "./DiagnoseHeader";
import DiagnoseAction from "./DiagnoseAction";

export default function DiagnoseResultView({ d }) {
  const {
    t, result, createdAt, collapsed, outcome, appliedSlugs, savedIds,
    feedback, expandedVerify, toSlug,
    toggleCollapsed, dismiss, run,
    toggleApplied, submitFeedback, savePlanned, toggleVerify,
  } = d;

  return (
    <div className="border border-[#00E0FF]/40 bg-gradient-to-br from-[#00E0FF]/5 to-transparent" data-testid="diagnose-result">
      <DiagnoseHeader
        t={t}
        result={result}
        createdAt={createdAt}
        collapsed={collapsed}
        outcome={outcome}
        onToggleCollapsed={toggleCollapsed}
        onDismiss={dismiss}
      />

      {!collapsed && (
        <>
          <div className="divide-y divide-[#1A1A24]" data-testid="diagnose-actions-list">
            {(result.actions || []).map((a, i) => (
              <DiagnoseAction
                key={a.title || i}
                t={t}
                index={i}
                action={a}
                isActive={appliedSlugs.has(toSlug(a.title))}
                isSaved={savedIds.has(a.title)}
                feedback={feedback[a.title]}
                verifyOpen={!!expandedVerify[i]}
                onToggleVerify={() => toggleVerify(i)}
                onApply={savePlanned}
                onToggleApplied={toggleApplied}
                onSubmitFeedback={submitFeedback}
              />
            ))}
          </div>

          <div className="p-4 border-t border-[#1A1A24] flex items-center justify-between text-xs">
            <button
              onClick={run}
              className="inline-flex items-center gap-1.5 text-zinc-500 hover:text-[#E5FF00] font-mono uppercase tracking-widest transition-colors"
              data-testid="diagnose-again"
            >
              <RefreshCw size={11} /> {t("diagnose.regenerate")}
            </button>
            <span className="text-zinc-600 font-mono">{t("diagnose.footer")}</span>
          </div>
        </>
      )}
    </div>
  );
}
