import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Sparkles, Stethoscope, ChevronRight, Zap, Wrench, MonitorDown,
  Bookmark, Check, X, Loader2, Gauge, AlertTriangle, RefreshCw,
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
  const [state, setState] = useState("idle"); // idle | loading | done | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [savedIds, setSavedIds] = useState(new Set());
  const [createdAt, setCreatedAt] = useState(null);

  // Al mount: prova a ripescare l'ultima diagnosi salvata dal DB.
  // Se esiste la mostro subito con badge \"generata Xh fa\", cos\u00ec l'utente
  // non deve rigenerarla dopo aver cliccato altrove.
  useEffect(() => {
    if (!hasSpecs) return;
    let cancelled = false;
    api.get("/advisor/diagnose/latest").then(({ data }) => {
      if (cancelled || !data?.available) return;
      setResult({ summary: data.summary, actions: data.actions, id: data.id });
      setCreatedAt(data.created_at);
      setState("done");
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [hasSpecs]);

  const run = async () => {
    setState("loading");
    setError("");
    try {
      const { data } = await api.post("/advisor/diagnose");
      setResult(data);
      setCreatedAt(new Date().toISOString());
      setSavedIds(new Set());  // reset saved status
      setState("done");
    } catch (e) {
      setError(e?.response?.data?.detail || "Errore durante la diagnosi");
      setState("error");
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
          {/* Header */}
          <div className="p-5 border-b border-[#1A1A24] flex items-start gap-3">
            <div className="w-10 h-10 bg-[#00E0FF]/15 border border-[#00E0FF]/40 flex items-center justify-center shrink-0">
              <Stethoscope size={18} className="text-[#00E0FF]" />
            </div>
            <div className="flex-1 min-w-0">
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
              </div>
              <p className="text-sm text-zinc-200 leading-relaxed">
                {result.summary || "Ecco le azioni consigliate dall'AI per il tuo PC."}
              </p>
            </div>
            <button
              onClick={dismiss}
              className="text-zinc-500 hover:text-white shrink-0"
              data-testid="diagnose-close"
              aria-label="Chiudi"
            >
              <X size={16} />
            </button>
          </div>

          {/* Actions list */}
          <div className="divide-y divide-[#1A1A24]">
            {(result.actions || []).map((a, i) => {
              const Icon = KIND_ICONS[a.kind] || Zap;
              const diff = DIFFICULTY_STYLES[(a.difficulty || "").toLowerCase()] || DIFFICULTY_STYLES.facile;
              const saved = savedIds.has(a.title);
              return (
                <div key={i} className="p-5 hover:bg-[#0F0F12] transition-colors" data-testid={`diagnose-action-${i}`}>
                  <div className="flex items-start gap-4">
                    <div className="flex flex-col items-center shrink-0">
                      <div className="w-8 h-8 border border-[#E5FF00]/50 bg-[#E5FF00]/10 text-[#E5FF00] font-black flex items-center justify-center">
                        {a.priority || i + 1}
                      </div>
                      <Icon size={14} className="text-zinc-500 mt-2" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h4 className="font-display font-black text-base tracking-tight text-white">{a.title}</h4>
                        <span className={`text-[10px] font-mono uppercase tracking-widest ${diff.color}`}>{diff.label}</span>
                      </div>
                      {a.impact && (
                        <div className="inline-flex items-center gap-1.5 text-xs text-[#00FF66] mb-2 font-mono">
                          <Zap size={11} /> {a.impact}
                        </div>
                      )}
                      <p className="text-sm text-zinc-400 leading-relaxed mb-3 whitespace-pre-wrap">{a.description}</p>
                      <div className="flex flex-wrap gap-2">
                        <Link
                          to={a.kind === "driver" ? "/app/pc" : "/app/desktop"}
                          data-testid={`diagnose-action-${i}-apply`}
                          className="inline-flex items-center gap-1.5 bg-[#E5FF00] text-black font-bold px-3 py-1.5 text-[11px] font-mono uppercase tracking-widest hover:bg-white transition-colors"
                        >
                          <MonitorDown size={12} /> {a.cta || "Apri agent"}
                        </Link>
                        <button
                          onClick={() => savePlanned(a)}
                          disabled={saved}
                          data-testid={`diagnose-action-${i}-save`}
                          className="inline-flex items-center gap-1.5 border border-[#2A2A35] hover:border-[#00E0FF] text-zinc-300 hover:text-[#00E0FF] px-3 py-1.5 text-[11px] font-mono uppercase tracking-widest transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                        >
                          {saved ? <><Check size={12} /> Salvata</> : <><Bookmark size={12} /> Salva per dopo</>}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer */}
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
        </div>
      )}
    </div>
  );
}
