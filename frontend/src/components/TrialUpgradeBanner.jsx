/**
 * TrialUpgradeBanner — banner dinamico dentro ProfileMenu che spinge upgrade
 * trial → paid con deep-link a Stripe Checkout preselezionato sul piano
 * consigliato dall'engagement dell'utente.
 *
 * Mostrato solo quando `info.suggested_upgrade` != null.
 * - Trial attivo: countdown giorni + CTA "Passa a Pro/Streamer" (monthly o yearly)
 * - Trial scaduto: countdown grace + CTA "Riattiva"
 * - Secondaria: switch al ciclo alternativo (annuale se recommend monthly, viceversa)
 */
import { useState } from "react";
import { Sparkles, ArrowRight, Loader2, Clock, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import i18n from "@/i18n";

const isEn = () => i18n.language?.startsWith("en");

const TIER_COLOR = { pro: "#E5FF00", streamer: "#00E0FF" };

export default function TrialUpgradeBanner({ info }) {
  const sug = info?.suggested_upgrade;
  const [loading, setLoading] = useState(null); // null | 'monthly' | 'yearly'

  if (!sug) return null;

  const eff = info.plan_effective;
  const isExpired = eff.endsWith("_expired");
  const days = isExpired ? info.grace_days_left : info.trial_days_left;
  const color = TIER_COLOR[sug.tier] || "#E5FF00";

  const startCheckout = async (cycle) => {
    setLoading(cycle);
    try {
      const lookup = cycle === "yearly" ? sug.lookup_yearly : sug.lookup_monthly;
      const { data } = await api.post("/payments/checkout", {
        lookup_key: lookup,
        origin_url: window.location.origin,
      });
      if (data?.checkout_url) window.location.href = data.checkout_url;
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message || (isEn() ? "Checkout error" : "Errore checkout"));
      setLoading(null);
    }
  };

  const en = isEn();
  const recCycle = sug.recommended_cycle;
  const altCycle = recCycle === "yearly" ? "monthly" : "yearly";
  const recPrice = recCycle === "yearly" ? sug.yearly_price : sug.monthly_price;
  const altPrice = recCycle === "yearly" ? sug.monthly_price : sug.yearly_price;
  const recLabel = recCycle === "yearly" ? `€${recPrice}/${en ? "year" : "anno"}` : `€${recPrice}/${en ? "month" : "mese"}`;
  const altLabel = recCycle === "yearly"
    ? (en ? `or monthly · €${altPrice}/mo` : `o mensile · €${altPrice}/mo`)
    : (en ? `or yearly · €${altPrice}/year (save €${sug.save_amount})` : `o annuale · €${altPrice}/anno (risparmi €${sug.save_amount})`);

  const HeaderIcon = isExpired ? AlertTriangle : Clock;
  const headerColor = isExpired ? "#FF3B30" : color;
  const headerText = isExpired
    ? (en ? `Expires in ${days} day${days === 1 ? "" : "s"} — reactivate now` : `Scade fra ${days} giorn${days === 1 ? "o" : "i"} — riattiva ora`)
    : days <= 3
    ? (en ? `Trial expires in ${days} day${days === 1 ? "" : "s"}` : `Trial scade fra ${days} giorn${days === 1 ? "o" : "i"}`)
    : (en ? `Trial: ${days} days left` : `Trial: ${days} giorni rimasti`);

  return (
    <div
      className="mx-3 mt-3 mb-1 border p-3 relative overflow-hidden"
      style={{ borderColor: `${headerColor}55`, backgroundColor: `${headerColor}0D` }}
      data-testid="trial-upgrade-banner"
    >
      {/* Header con countdown */}
      <div className="flex items-center gap-2 mb-2">
        <HeaderIcon size={13} style={{ color: headerColor }} className="shrink-0" />
        <div
          className="text-[10px] uppercase tracking-widest font-bold flex-1"
          style={{ color: headerColor }}
          data-testid="banner-countdown"
        >
          {headerText}
        </div>
      </div>

      {/* Reason line */}
      <div className="text-xs text-zinc-300 leading-relaxed mb-3" data-testid="banner-reason">
        {sug.reason}
      </div>

      {/* CTA principale (raccomandato) */}
      <button
        onClick={() => startCheckout(recCycle)}
        disabled={loading !== null}
        data-testid="banner-cta-primary"
        className="w-full flex items-center justify-center gap-2 font-bold text-xs uppercase tracking-widest px-3 py-2 transition-opacity hover:opacity-90 disabled:opacity-50"
        style={{ backgroundColor: color, color: "#000" }}
      >
        {loading === recCycle ? (
          <Loader2 size={13} className="animate-spin" />
        ) : (
          <Sparkles size={13} />
        )}
        <span>
          {isExpired ? (en ? "Reactivate" : "Riattiva") : (en ? "Upgrade to" : "Passa a")} {sug.tier_label} · {recLabel}
        </span>
      </button>

      {/* CTA secondaria (ciclo alternativo) */}
      <button
        onClick={() => startCheckout(altCycle)}
        disabled={loading !== null}
        data-testid="banner-cta-secondary"
        className="w-full flex items-center justify-center gap-1 mt-2 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors disabled:opacity-50"
      >
        {loading === altCycle && <Loader2 size={11} className="animate-spin" />}
        <span>{altLabel}</span>
        <ArrowRight size={11} />
      </button>
    </div>
  );
}
