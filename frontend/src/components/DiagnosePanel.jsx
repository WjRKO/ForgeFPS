import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Sparkles, Stethoscope, ChevronRight, ChevronDown, Zap, Wrench, MonitorDown,
  Bookmark, Check, X, Loader2, Gauge, AlertTriangle, RefreshCw,
  ThumbsUp, ThumbsDown, Eye, CheckCircle2,
} from "lucide-react";
import api from "@/lib/api";

const DIFFICULTY_STYLES = {
  facile:    { color: "text-[#00FF66]", label: "Facile" },
  easy:      { color: "text-[#00FF66]", label: "Easy" },
  medio:     { color: "text-[#E5FF00]", label: "Medio" },
  medium:    { color: "text-[#E5FF00]", label: "Medium" },
  avanzato:  { color: "text-[#FF6A00]", label: "Avanzato" },
  advanced:  { color: "text-[#FF6A00]", label: "Advanced" },
};

const KIND_ICONS = {
  tweak: Zap,
  driver: MonitorDown,
  hardware: Gauge,
  maintenance: Wrench,
  manual: Sparkles,
};

function relTimeIt(iso) {
  if (!iso) return "";
  const d = new Date(iso).getTime();
  const diff = (Date.now() - d) / 1000;
  if (diff < 60) return "adesso";
  if (diff < 3600) return `${Math.floor(diff / 60)} min fa`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h fa`;
  const days = Math.floor(diff / 86400);
  return `${days} ${days === 1 ? "giorno" : "giorni"} fa`;
}

/**
 * Big diagnostic panel for the AI Advisor page.
 * One-click: fetches personalized action plan from /api/advisor/diagnose,
 * renders each action with impact + difficulty + concrete CTAs.
 */
export default function DiagnosePanel({ hasSpecs }) {
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
      const { data } = await api.post("/advisor/diagnose");
      setResult(data);
      setCreatedAt(new Date().toISOString());
      setSavedIds(new Set());
      setFeedback({});
      setState("done");
    } catch (e) {
      setError(e?.response?.data?.detail || "Errore durante la diagnosi");
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
      toast.success(isActive ? "Segnato come non attivo" : "Segnato come già attivo", {
        description: isActive ? "" : "L'AI ne terrà conto nelle prossime diagnosi",
      });
    } catch {
      toast.error("Impossibile aggiornare lo stato");
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
      toast.success(rating === "up" ? "Feedback registrato 👍" : "Feedback registrato 👎");
    } catch {
      toast.error("Feedback fallito");
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
      toast.success("Azione salvata", { description: "La trovi nella tua Dashboard" });
      return data;
    } catch {
      toast.error("Salvataggio fallito");
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
                Diagnosi PC AI
              </h3>
              <p className="text-zinc-400 text-sm">
                Un click. 3-5 azioni prioritizzate solo per il tuo hardware: impatto stimato, difficoltà, applica in un tap.
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
            L'AI sta analizzando il tuo PC...
          </div>
          <div className="text-xs text-zinc-500">Health checks, benchmark trend, hardware, tweak</div>
        </div>
      )}

      {state === "error" && (
        <div
          className="border border-[#FF3B30]/50 bg-[#FF3B30]/5 p-4 flex items-start gap-3"
          data-testid="diagnose-error"
        >
          <AlertTriangle size={20} className="text-[#FF3B30] shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-semibold text-[#FF3B30] mb-1">Diagnosi fallita</div>
            <div className="text-sm text-zinc-400 mb-3">{error}</div>
            <button
              onClick={run}
              className="text-xs font-mono uppercase tracking-widest text-[#E5FF00] hover:underline"
              data-testid="diagnose-retry"
            >
              Riprova →
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
              <RefreshCw size={11} /> Rigenera
            </button>
            <span className="text-zinc-600 font-mono">Generato da FrameForge AI</span>
          </div>
          )}
        </div>
      )}
    </div>
  );
}


// -------------------- Sub-components (kept in-file to preserve one-import contract) --------------------

function DiagnoseEmpty() {
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
            Diagnosi PC AI
          </h3>
          <p className="text-zinc-400 text-sm mb-3">
            Collega prima il tuo PC per ottenere una diagnosi personalizzata: 3-5 azioni prioritizzate
            con impatto stimato su FPS, latenza e temperature.
          </p>
          <Link
            to="/app/desktop"
            className="inline-flex items-center gap-1.5 border border-[#E5FF00]/50 text-[#E5FF00] hover:bg-[#E5FF00]/10 px-4 py-2 text-xs font-mono uppercase tracking-widest transition-colors"
            data-testid="diagnose-connect-cta"
          >
            <MonitorDown size={13} /> Connetti il PC →
          </Link>
        </div>
      </div>
    </div>
  );
}

function DiagnoseHeader({ result, createdAt, collapsed, outcome, onToggleCollapsed, onDismiss }) {
  return (
    <div className="p-5 border-b border-[#1A1A24] flex items-start gap-3">
      <button
        onClick={onToggleCollapsed}
        className="w-10 h-10 bg-[#00E0FF]/15 border border-[#00E0FF]/40 flex items-center justify-center shrink-0 hover:bg-[#00E0FF]/25 transition-colors group"
        data-testid="diagnose-collapse-toggle"
        aria-label={collapsed ? "Espandi diagnosi" : "Comprimi diagnosi"}
        aria-expanded={!collapsed}
        title={collapsed ? "Espandi diagnosi" : "Comprimi diagnosi"}
      >
        {collapsed
          ? <ChevronRight size={18} className="text-[#00E0FF] group-hover:translate-x-0.5 transition-transform" />
          : <ChevronDown size={18} className="text-[#00E0FF]" />}
      </button>
      <button
        onClick={onToggleCollapsed}
        className="flex-1 min-w-0 text-left"
        data-testid="diagnose-header-clickable"
        aria-label={collapsed ? "Espandi diagnosi" : "Comprimi diagnosi"}
      >
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#00E0FF]">
            // DIAGNOSI · {(result.actions || []).length} AZIONI
          </div>
          {createdAt && (
            <span
              className="text-[10px] font-mono text-zinc-500"
              data-testid="diagnose-timestamp"
              title={new Date(createdAt).toLocaleString()}
            >
              · generata {relTimeIt(createdAt)}
            </span>
          )}
          {collapsed && (
            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 border border-[#2A2A35] px-1.5 py-0.5">
              Compressa
            </span>
          )}
        </div>
        <p className="text-sm text-zinc-200 leading-relaxed">
          {result.summary || "Ecco le azioni consigliate dall'AI per il tuo PC."}
        </p>
        {outcome?.available && outcome.delta !== 0 && (
          <div
            className={`mt-2 inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest border px-2 py-0.5 ${
              outcome.delta > 0
                ? "border-[#00FF66]/40 bg-[#00FF66]/10 text-[#00FF66]"
                : "border-[#FF3B30]/40 bg-[#FF3B30]/10 text-[#FF3B30]"
            }`}
            data-testid="outcome-badge"
            title="Delta benchmark tra prima e dopo l'ultima diagnosi"
          >
            {outcome.delta > 0 ? <ThumbsUp size={10} /> : <ThumbsDown size={10} />}
            Dopo l'ultima diagnosi: {outcome.delta > 0 ? "+" : ""}{outcome.delta} punti benchmark
          </div>
        )}
      </button>
      <button
        onClick={onDismiss}
        className="text-zinc-500 hover:text-white shrink-0"
        data-testid="diagnose-close"
        aria-label="Chiudi"
      >
        <X size={16} />
      </button>
    </div>
  );
}

function DiagnoseAction({ index, action, isActive, isSaved, feedback, verifyOpen, onToggleVerify, onApply, onToggleApplied, onSubmitFeedback }) {
  const Icon = KIND_ICONS[action.kind] || Zap;
  const diff = DIFFICULTY_STYLES[(action.difficulty || "").toLowerCase()] || DIFFICULTY_STYLES.facile;
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
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#00FF66] border border-[#00FF66]/40 bg-[#00FF66]/10 px-1.5">GIÀ ATTIVO</span>
            ) : (
              <span className={`text-[10px] font-mono uppercase tracking-widest ${diff.color}`}>{diff.label}</span>
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
                <Eye size={11} /> Come verificare se è già attivo
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
                  <MonitorDown size={12} /> {action.cta || "Apri agent"}
                </Link>
                <button
                  onClick={() => onApply(action)}
                  disabled={isSaved}
                  data-testid={`diagnose-action-${index}-save`}
                  className="inline-flex items-center gap-1.5 border border-[#2A2A35] hover:border-[#00E0FF] text-zinc-300 hover:text-[#00E0FF] px-3 py-1.5 text-[11px] font-mono uppercase tracking-widest transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSaved ? <><Check size={12} /> Salvata</> : <><Bookmark size={12} /> Salva</>}
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
              <CheckCircle2 size={12} /> {isActive ? "Attivo" : "Segna già attivo"}
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
                aria-label="Non utile"
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
