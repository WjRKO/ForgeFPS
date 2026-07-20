import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Sparkles, Stethoscope, ChevronRight, Loader2, AlertTriangle, RefreshCw,
} from "lucide-react";
import api from "@/lib/api";
import DiagnoseHeader, { relTime } from "./DiagnoseHeader";
import DiagnoseAction from "./DiagnoseAction";

/**
 * Big diagnostic panel for the AI Advisor page.
 * One-click: fetches personalized action plan from /api/advisor/diagnose,
 * renders each action with impact + difficulty + concrete CTAs.
 */
export default function DiagnosePanel({ hasSpecs }) {
  const { t, i18n } = useTranslation();
  const isEn = (i18n.resolvedLanguage || i18n.language || "it").toLowerCase().startsWith("en");
  const [state, setState] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [savedIds, setSavedIds] = useState(new Set());
  const [createdAt, setCreatedAt] = useState(null);
  const [appliedSlugs, setAppliedSlugs] = useState(new Set());
  const [feedback, setFeedback] = useState({}); // {actionTitle: "up"|"down"}
  const [expandedVerify, setExpandedVerify] = useState({});
  const [outcome, setOutcome] = useState(null);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof localStorage === "undefined") return false;
    return localStorage.getItem("diagnose_collapsed") === "1";
  });

  const toggleCollapsed = () => {
    setCollapsed((v) => {
      const next = !v;
      try { localStorage.setItem("diagnose_collapsed", next ? "1" : "0"); } catch {}
      return next;
    });
  };

  const toSlug = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80);

  useEffect(() => {
    if (!hasSpecs) return;
    let cancelled = false;
    Promise.all([
      api.get("/advisor/diagnose/latest").catch(() => ({ data: {} })),
      api.get("/advisor/applied-tweaks").catch(() => ({ data: [] })),
      api.get("/advisor/outcome").catch(() => ({ data: {} })),
    ]).then(([latest, applied, out]) => {
      if (cancelled) return;
      if (latest.data?.available) {
        setResult({ summary: latest.data.summary, actions: latest.data.actions, id: latest.data.id });
        setCreatedAt(latest.data.created_at);
        setState("done");
      }
      setAppliedSlugs(new Set((applied.data || []).map((a) => a.slug)));
      if (out.data?.available) setOutcome(out.data);
    });
    return () => { cancelled = true; };
  }, [hasSpecs]);

  const run = async () => {
    setState("loading");
    setError("");
    try {
      const lang = (i18n.resolvedLanguage || i18n.language || "it").slice(0, 2);
      const { data } = await api.post("/advisor/diagnose", { lang });
      setResult(data);
      setCreatedAt(new Date().toISOString());
      setSavedIds(new Set());
      setFeedback({});
      setState("done");
    } catch (e) {
      setError(e?.response?.data?.detail || t("diagnose.error_default"));
      setState("error");
    }
  };

  const toggleApplied = async (action) => {
    const slug = toSlug(action.title);
    const isActive = appliedSlugs.has(slug);
    try {
      await api.post("/advisor/applied-tweaks", { title: action.title, active: !isActive });
      setAppliedSlugs((prev) => {
        const next = new Set(prev);
        if (isActive) next.delete(slug); else next.add(slug);
        return next;
      });
      toast.success(isActive ? t("diagnose.toast_marked_inactive") : t("diagnose.toast_marked_active"), {
        description: isActive ? "" : (isEn ? "AI will consider this in future diagnoses" : "L'AI ne terrà conto nelle prossime diagnosi"),
      });
    } catch {
      toast.error(t("diagnose.toast_mark_fail"));
    }
  };

  const submitFeedback = async (action, rating) => {
    const key = action.title;
    if (feedback[key] === rating) return;
    try {
      await api.post("/advisor/feedback", {
        target_type: "diagnose_action",
        target_id: result?.id || "unknown",
        action_title: action.title,
        rating,
      });
      setFeedback((prev) => ({ ...prev, [key]: rating }));
      toast.success(rating === "up" ? t("diagnose.toast_feedback_up") : t("diagnose.toast_feedback_down"));
    } catch {
      toast.error(t("diagnose.toast_feedback_fail"));
    }
  };

  const savePlanned = async (action) => {
    try {
      const { data } = await api.post("/advisor/planned-actions", {
        title: action.title,
        description: action.description || "",
        impact: action.impact || "",
        difficulty: (action.difficulty || "facile").toLowerCase(),
        kind: action.kind || "tweak",
        source: "advisor_diagnose",
      });
      setSavedIds((s) => new Set([...s, action.title]));
      toast.success(t("diagnose.toast_saved"), { description: t("diagnose.toast_saved_desc") });
      return data;
    } catch {
      toast.error(t("diagnose.toast_save_fail"));
    }
  };

  const dismiss = () => {
    setResult(null);
    setState("idle");
  };

  if (!hasSpecs) {
    return <DiagnoseEmpty />;
  }

  return (
    <div className="mb-6" data-testid="diagnose-panel">
      {state === "idle" && (
        <button
          onClick={run}
          data-testid="diagnose-btn"
          className="w-full group border border-[#E5FF00]/40 hover:border-[#E5FF00] bg-gradient-to-r from-[#E5FF00]/10 via-[#00E0FF]/5 to-transparent hover:from-[#E5FF00]/20 hover:via-[#00E0FF]/10 p-5 transition-all text-left"
        >
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-[#E5FF00] text-black flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
              <Stethoscope size={24} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#E5FF00] mb-1">
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
            <ChevronRight size={20} className="text-[#E5FF00] group-hover:translate-x-1 transition-transform" />
          </div>
        </button>
      )}

      {state === "loading" && (
        <div
          className="border border-[#E5FF00]/40 bg-[#0F0F12] p-8 flex flex-col items-center gap-3"
          data-testid="diagnose-loading"
        >
          <Loader2 size={32} className="text-[#E5FF00] animate-spin" />
          <div className="text-sm text-zinc-300 font-mono uppercase tracking-widest">
            {isEn ? "AI is analyzing your PC..." : "L'AI sta analizzando il tuo PC..."}
          </div>
          <div className="text-xs text-zinc-500">{isEn ? "Health checks, benchmark trend, hardware, tweaks" : "Health checks, benchmark trend, hardware, tweak"}</div>
        </div>
      )}

      {state === "error" && (
        <div
          className="border border-[#FF3B30]/50 bg-[#FF3B30]/5 p-4 flex items-start gap-3"
          data-testid="diagnose-error"
        >
          <AlertTriangle size={20} className="text-[#FF3B30] shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-semibold text-[#FF3B30] mb-1">{isEn ? "Diagnosis failed" : "Diagnosi fallita"}</div>
            <div className="text-sm text-zinc-400 mb-3">{error}</div>
            <button
              onClick={run}
              className="text-xs font-mono uppercase tracking-widest text-[#E5FF00] hover:underline"
              data-testid="diagnose-retry"
            >
              {isEn ? "Retry →" : "Riprova →"}
            </button>
          </div>
          <button onClick={dismiss} className="text-zinc-500 hover:text-white">
            <X size={16} />
          </button>
        </div>
      )}

      {state === "done" && result && (
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

          {/* Actions list — hidden when collapsed */}
          {!collapsed && (
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
                onToggleVerify={() => setExpandedVerify((p) => ({ ...p, [i]: !p[i] }))}
                onApply={savePlanned}
                onToggleApplied={toggleApplied}
                onSubmitFeedback={submitFeedback}
              />
            ))}
          </div>
          )}

          {/* Footer — hidden when collapsed */}
          {!collapsed && (
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
          )}
        </div>
      )}
    </div>
  );
}


// -------------------- Sub-components (kept in-file to preserve one-import contract) --------------------

function DiagnoseEmpty() {
  const { t } = useTranslation();
  return (
    <div
      className="mb-6 border border-[#E5FF00]/30 bg-gradient-to-br from-[#E5FF00]/10 to-transparent p-5"
      data-testid="diagnose-empty"
    >
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-[#E5FF00]/20 border border-[#E5FF00]/40 flex items-center justify-center shrink-0">
          <Stethoscope size={24} className="text-[#E5FF00]" />
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
            className="inline-flex items-center gap-1.5 border border-[#E5FF00]/50 text-[#E5FF00] hover:bg-[#E5FF00]/10 px-4 py-2 text-xs font-mono uppercase tracking-widest transition-colors"
            data-testid="diagnose-connect-cta"
          >
            <MonitorDown size={13} /> {t("diagnose.connect_cta")} →
          </Link>
        </div>
      </div>
    </div>
  );
}

