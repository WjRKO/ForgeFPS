import { RefreshCw, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAutoSync } from "@/hooks/useAutoSync";

/**
 * Freshness badge globale (Fase 2 · Sync ambientale):
 * verde <10min, giallo <24h, rosso >=24h, grigio unknown.
 * Click → force sync silent. Piazzato nell'header dell'app.
 */
export default function FreshnessBadge() {
  const { t } = useTranslation();
  const { ageSec, tier, forceSync, running } = useAutoSync({ enabled: true });

  if (tier === "unknown") return null;

  const config = {
    fresh: { color: "#00FF66", bg: "rgba(0,255,102,0.08)", border: "rgba(0,255,102,0.4)" },
    warm:  { color: "#E5FF00", bg: "rgba(229,255,0,0.08)", border: "rgba(229,255,0,0.4)" },
    stale: { color: "#FF3B30", bg: "rgba(255,59,48,0.08)", border: "rgba(255,59,48,0.4)" },
  }[tier];

  const fmtAge = () => {
    if (ageSec == null) return "";
    if (ageSec < 60) return t("freshness.just_now", { defaultValue: "or ora" });
    if (ageSec < 3600) return t("freshness.min_ago", { count: Math.floor(ageSec / 60), defaultValue: `${Math.floor(ageSec / 60)} min fa` });
    const h = Math.floor(ageSec / 3600);
    if (h < 24) return t("freshness.hour_ago", { count: h, defaultValue: `${h}h fa` });
    return t("freshness.days_ago", { count: Math.floor(h / 24), defaultValue: `${Math.floor(h / 24)}gg fa` });
  };

  const label = {
    fresh: t("freshness.fresh_label", { defaultValue: "Dati aggiornati" }),
    warm: t("freshness.warm_label", { defaultValue: "Aggiornati" }),
    stale: t("freshness.stale_label", { defaultValue: "Sync suggerito" }),
  }[tier];

  return (
    <button
      type="button"
      onClick={forceSync}
      disabled={running}
      data-testid="freshness-badge"
      title={t("freshness.click_hint", { defaultValue: "Clicca per sincronizzare ora" })}
      style={{ backgroundColor: config.bg, borderColor: config.border, color: config.color }}
      className="flex items-center gap-2 px-2.5 py-1 border text-[11px] font-mono uppercase tracking-widest transition-all hover:brightness-125 disabled:opacity-60"
    >
      {running ? (
        <Loader2 size={11} className="animate-spin" />
      ) : (
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: config.color }} />
      )}
      <span className="hidden sm:inline">{label}</span>
      <span className="font-bold">{fmtAge()}</span>
      {!running && tier === "stale" && <RefreshCw size={11} />}
    </button>
  );
}
