/**
 * DiagnosePanel — big diagnostic panel for the AI Advisor page.
 * One-click: fetches personalized action plan from /api/advisor/diagnose,
 * renders each action with impact + difficulty + concrete CTAs.
 *
 * Refactor 2026-07-25: la logica di stato/effetti/handlers vive in
 * `useDiagnose` (hook). Le viste sono componenti stateless:
 *   idle     -> <DiagnoseIdleCTA/>
 *   loading  -> <DiagnoseLoading/>
 *   error    -> <DiagnoseErrorView/>
 *   done     -> <DiagnoseResultView/>
 *   no-specs -> <DiagnoseEmpty/>
 */
import { useDiagnose } from "@/hooks/useDiagnose";
import { DiagnoseIdleCTA, DiagnoseLoading, DiagnoseErrorView, DiagnoseEmpty } from "./DiagnoseStates";
import DiagnoseResultView from "./DiagnoseResultView";

export default function DiagnosePanel({ hasSpecs }) {
  const d = useDiagnose({ hasSpecs });

  if (!hasSpecs) return <DiagnoseEmpty />;

  return (
    <div className="mb-6" data-testid="diagnose-panel">
      {d.state === "idle" && <DiagnoseIdleCTA onRun={d.run} isEn={d.isEn} t={d.t} />}
      {d.state === "loading" && <DiagnoseLoading isEn={d.isEn} />}
      {d.state === "error" && (
        <DiagnoseErrorView error={d.error} isEn={d.isEn} onRetry={d.run} onDismiss={d.dismiss} />
      )}
      {d.state === "done" && d.result && <DiagnoseResultView d={d} />}
    </div>
  );
}
