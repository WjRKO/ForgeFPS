/**
 * PlanUpgradeBanner — banner unificato per tutte le feature gated Pro/Streamer.
 *
 * Design: coerente con FullBenchmarkReport locked-state (border gradient, glow,
 * feature preview grid, CTA a /pricing?plan=xxx, "current plan" pill).
 *
 * i18n: eyebrow, cta e "current plan" via `plan_banner.*`. Title/description/
 * features vengono passati dai caller (traducendoli dai propri namespace,
 * es. `plan_banner.advisor.*`).
 *
 * Props:
 *   tier          "pro" | "streamer"       — piano richiesto
 *   title         string                    — heading grande
 *   description   string (may contain <b>)  — paragrafo descrittivo
 *   features      [{ icon, title, desc }]   — 2-4 feature preview (icon = lucide)
 *   currentPlan   string                    — piano attuale utente (default: "starter")
 *   compact       bool                      — variante ridotta (per sezioni inline)
 *   testid        string                    — data-testid root
 */
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Lock, Sparkles } from "lucide-react";

const TIER_CFG = {
  pro: {
    accent: "#E5FF00",
    accentGlow: "#E5FF00",
    accentSoft: "#B388FF",
    query: "?plan=pro",
    eyebrowKey: "plan_banner.eyebrow_pro",
    ctaKey: "plan_banner.cta_pro",
  },
  streamer: {
    accent: "#00E0FF",
    accentGlow: "#00E0FF",
    accentSoft: "#B388FF",
    query: "?plan=streamer",
    eyebrowKey: "plan_banner.eyebrow_streamer",
    ctaKey: "plan_banner.cta_streamer",
  },
};

// Render minimal HTML (only <b>...</b>) safely from a translated string.
function renderRich(text) {
  if (!text) return null;
  const parts = text.split(/(<b>[^<]*<\/b>)/g);
  return parts.map((p, i) => {
    const m = p.match(/^<b>([^<]*)<\/b>$/);
    if (m) return <strong key={i} className="text-white">{m[1]}</strong>;
    return <span key={i}>{p}</span>;
  });
}

export default function PlanUpgradeBanner({
  tier = "pro",
  title,
  description,
  features = [],
  currentPlan = "starter",
  compact = false,
  testid = "plan-upgrade-banner",
}) {
  const { t } = useTranslation();
  const cfg = TIER_CFG[tier] || TIER_CFG.pro;
  const padding = compact ? "p-6" : "p-8";
  const titleSize = compact ? "text-2xl" : "text-3xl";

  return (
    <div
      className={`relative overflow-hidden bg-gradient-to-br from-[#0F0F12] to-[#0A0A0F] border-2 ${padding}`}
      style={{ borderColor: `${cfg.accent}66` }}
      data-testid={testid}
    >
      <div
        className="absolute -top-24 -right-24 w-72 h-72 rounded-full blur-3xl pointer-events-none"
        style={{ backgroundColor: `${cfg.accentGlow}1A` }}
      />
      <div
        className="absolute -bottom-24 -left-24 w-72 h-72 rounded-full blur-3xl pointer-events-none"
        style={{ backgroundColor: `${cfg.accentSoft}14` }}
      />

      <div className="relative">
        <div
          className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-mono mb-3"
          style={{ color: cfg.accent }}
          data-testid={`${testid}-eyebrow`}
        >
          <Lock size={11} /> {t(cfg.eyebrowKey)}
        </div>
        <h3 className={`font-display font-black ${titleSize} mb-2 text-white`} data-testid={`${testid}-title`}>
          {title}
        </h3>
        {description && (
          <p className="text-sm text-zinc-400 max-w-2xl mb-6 leading-relaxed" data-testid={`${testid}-desc`}>
            {renderRich(description)}
          </p>
        )}

        {features.length > 0 && (
          <div className="grid sm:grid-cols-2 gap-3 mb-6 max-w-3xl">
            {features.map((f, i) => {
              const Icon = f.icon;
              return (
                <div
                  key={f.title}
                  className="flex items-start gap-3 bg-black/30 border border-[#2A2A35] p-3"
                  data-testid={`${testid}-feature-${i}`}
                >
                  {Icon && <Icon size={16} className="shrink-0 mt-0.5" style={{ color: cfg.accent }} />}
                  <div>
                    <div className="text-xs font-semibold text-white mb-0.5">{f.title}</div>
                    <div className="text-[11px] text-zinc-500 leading-relaxed">{f.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Link
            to={`/pricing${cfg.query}`}
            data-testid={`${testid}-cta`}
            className="inline-flex items-center gap-2 font-bold uppercase tracking-widest text-xs px-6 py-3 transition-opacity hover:opacity-90"
            style={{ backgroundColor: cfg.accent, color: "#000" }}
          >
            <Sparkles size={13} /> {t(cfg.ctaKey)}
          </Link>
          <span className="text-[11px] text-zinc-500">
            {t("plan_banner.current_plan")} <strong className="text-zinc-300">{currentPlan}</strong>
          </span>
        </div>
      </div>
    </div>
  );
}
