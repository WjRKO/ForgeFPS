/**
 * useDiagnose — hook che incapsula stato, side-effects e handler della
 * DiagnosePanel (chiamate a /advisor/diagnose*, applied-tweaks, outcome,
 * feedback, planned-actions).
 *
 * Ritorna { state, handlers } cosi' che il componente-vista resti sottile
 * e le viste (idle/loading/error/done) siano puri componenti presentativi.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import api from "@/lib/api";

const toSlug = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80);

export function useDiagnose({ hasSpecs }) {
  const { t, i18n } = useTranslation();
  const isEn = (i18n.resolvedLanguage || i18n.language || "it").toLowerCase().startsWith("en");
  const [state, setState] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [savedIds, setSavedIds] = useState(new Set());
  const [createdAt, setCreatedAt] = useState(null);
  const [appliedSlugs, setAppliedSlugs] = useState(new Set());
  const [feedback, setFeedback] = useState({});
  const [expandedVerify, setExpandedVerify] = useState({});
  const [outcome, setOutcome] = useState(null);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof localStorage === "undefined") return false;
    return localStorage.getItem("diagnose_collapsed") === "1";
  });

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

  const toggleCollapsed = () => {
    setCollapsed((v) => {
      const next = !v;
      try { localStorage.setItem("diagnose_collapsed", next ? "1" : "0"); } catch {}
      return next;
    });
  };

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

  const toggleVerify = (i) => setExpandedVerify((p) => ({ ...p, [i]: !p[i] }));

  return {
    // i18n
    t, isEn,
    // state
    state, result, error, savedIds, createdAt, appliedSlugs, feedback,
    expandedVerify, outcome, collapsed,
    // handlers
    run, toggleCollapsed, toggleApplied, submitFeedback, savePlanned,
    dismiss, toggleVerify, toSlug,
  };
}
