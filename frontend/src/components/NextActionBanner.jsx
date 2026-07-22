import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ArrowRight, X, Sparkles, Gauge, MessageSquareCode, Download, TrendingUp } from "lucide-react";

/**
 * "Next best action" banner: contextual nudge shown after key user actions.
 * Uses localStorage to remember dismissal per action type. Auto-hides if
 * dismissed within the last 24h to avoid banner spam.
 *
 * Props:
 *  - kind: "no-hw" | "post-sync" | "post-apply" | "post-benchmark" (contextual copy preset)
 *  - custom: override { icon, text, ctaLabel, to } — bypasses `kind`
 *  - dismissKey: string for localStorage (default derived from kind)
 */
export default function NextActionBanner({ kind, custom, dismissKey, testid }) {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(true);
  const storageKey = `ff_nba_${dismissKey || kind || "custom"}`;

  useEffect(() => {
    const v = localStorage.getItem(storageKey);
    if (!v) { setDismissed(false); return; }
    const age = Date.now() - Number(v);
    setDismissed(age < 24 * 3600 * 1000);
  }, [storageKey]);

  if (dismissed) return null;

  const PRESETS = {
    "no-hw": {
      icon: Download,
      text: t("nba.no_hw", { defaultValue: "Non hai ancora collegato il PC. Installa FrameForge Agent per sbloccare Health Score, benchmark e tweak reali." }),
      ctaLabel: t("nba.no_hw_cta", { defaultValue: "Installa Agent" }),
      to: "/app/desktop",
      accent: "#E5FF00",
    },
    "post-sync": {
      icon: MessageSquareCode,
      text: t("nba.post_sync", { defaultValue: "Sync completata. Ora chiedi all'AI Advisor cosa migliorare sul tuo hardware." }),
      ctaLabel: t("nba.post_sync_cta", { defaultValue: "Apri Advisor" }),
      to: "/app/advisor",
      accent: "#00E0FF",
    },
    "post-apply": {
      icon: Gauge,
      text: t("nba.post_apply", { defaultValue: "Tweak applicati. Fai un benchmark per misurare il guadagno reale." }),
      ctaLabel: t("nba.post_apply_cta", { defaultValue: "Esegui benchmark" }),
      to: "/app/benchmark",
      accent: "#00FF66",
    },
    "post-benchmark": {
      icon: TrendingUp,
      text: t("nba.post_bench", { defaultValue: "Benchmark completato. Salva il report PDF o confronta con la media della community." }),
      ctaLabel: t("nba.post_bench_cta", { defaultValue: "Vedi confronto" }),
      to: "/app/benchmark",
      accent: "#B388FF",
    },
  };
  const cfg = custom || PRESETS[kind];
  if (!cfg) return null;
  const Icon = cfg.icon || Sparkles;
  const dismiss = () => { localStorage.setItem(storageKey, String(Date.now())); setDismissed(true); };

  return (
    <div className="border p-4 mb-4 flex items-center gap-4 fade-up"
      style={{ borderColor: `${cfg.accent}50`, backgroundColor: `${cfg.accent}0d` }}
      data-testid={testid || `nba-${kind || "custom"}`}>
      <div className="shrink-0"><Icon size={20} style={{ color: cfg.accent }} /></div>
      <div className="flex-1 text-sm text-zinc-300 leading-relaxed">
        <span className="text-[10px] uppercase tracking-[0.2em] font-mono mr-2" style={{ color: cfg.accent }}>
          {t("nba.next", { defaultValue: "prossima mossa" })}
        </span>
        {cfg.text}
      </div>
      <Link to={cfg.to} onClick={dismiss}
        className="shrink-0 inline-flex items-center gap-1.5 border px-3 py-1.5 text-xs font-bold uppercase tracking-widest hover:opacity-80 transition-opacity"
        style={{ borderColor: cfg.accent, color: cfg.accent }}
        data-testid={`${testid || `nba-${kind || "custom"}`}-cta`}>
        {cfg.ctaLabel} <ArrowRight size={12} />
      </Link>
      <button onClick={dismiss}
        className="shrink-0 text-zinc-500 hover:text-zinc-200 transition-colors p-1"
        data-testid={`${testid || `nba-${kind || "custom"}`}-dismiss`}
        title={t("nba.dismiss", { defaultValue: "Nascondi per 24h" })}>
        <X size={14} />
      </button>
    </div>
  );
}
