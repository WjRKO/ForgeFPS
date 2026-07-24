/**
 * PlanStatusBanner
 *
 * Banner in cima al Layout della dashboard che mostra:
 *  - Trial attivo: "Trial Pro attivo · X giorni rimasti" con CTA "Vedi piani"
 *  - Trial scaduto in grace period: "Trial scaduto. Riattiva entro X giorni" (arancione)
 *  - Piano attivo pagato: nessun banner (silenzio)
 *  - Starter: nessun banner (non intrusivo)
 *
 * Fetch: GET /api/subscriptions/status (una volta al mount + retry ogni 5 min).
 * Se la risposta 401 (loggedOut) o error, il banner non appare.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Gift, AlertTriangle, ArrowRight, X } from "lucide-react";
import api from "@/lib/api";

const LS_DISMISSED_KEY = "ff_plan_banner_dismissed_v1";

export default function PlanStatusBanner() {
  const { i18n } = useTranslation();
  const en = (i18n.language || "").startsWith("en");
  const [info, setInfo] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Se l'utente ha dismissato il banner oggi, non lo mostriamo
    try {
      const last = window.localStorage.getItem(LS_DISMISSED_KEY);
      if (last && (Date.now() - parseInt(last, 10)) < 12 * 60 * 60 * 1000) setDismissed(true);
    } catch (e) { /* localStorage disabilitato: mostriamo comunque */ }

    const load = async () => {
      try {
        const { data } = await api.get("/subscriptions/status");
        setInfo(data);
      } catch (e) { /* utente non loggato o errore: banner silenzioso */ }
    };
    load();
    // Refresh ogni 10 minuti (allineato con eventuale scadenza trial)
    const t = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(t);
  }, []);

  const dismiss = () => {
    setDismissed(true);
    try { window.localStorage.setItem(LS_DISMISSED_KEY, String(Date.now())); } catch {}
  };

  if (!info || dismissed) return null;

  const days = info.trial_days_left;
  const graceDays = info.grace_days_left;
  const isTrial = info.plan_stored === "pro_trial" || info.plan_stored === "streamer_trial";
  const isExpired = info.show_reactivate;

  // Nessun banner per: starter (senza trial precedente), piano pagato attivo
  if (!isTrial && !isExpired) return null;
  // Se piano pagato attivo (pro/streamer) senza trial info, non serve
  if (info.plan_effective === "pro" || info.plan_effective === "streamer") return null;

  // Trial attivo
  if (isTrial && days > 0) {
    const urgent = days <= 3;
    const tier = info.plan_stored === "streamer_trial" ? "Streamer" : "Pro";
    const bg = urgent ? "bg-[#FFA500]/10 border-[#FFA500]/40" : "bg-[#E5FF00]/10 border-[#E5FF00]/40";
    const iconColor = urgent ? "text-[#FFA500]" : "text-[#E5FF00]";
    return (
      <div className={`border-b ${bg}`} data-testid="plan-banner-trial">
        <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center gap-3">
          <Gift size={16} className={`shrink-0 ${iconColor}`} />
          <div className="text-sm text-zinc-200 min-w-0 flex-1 truncate">
            {en ? (
              <>Your <strong>{tier} trial</strong> is active — <strong>{days} day{days === 1 ? "" : "s"} left</strong>. {urgent && "Add a card to continue after the trial."}</>
            ) : (
              <>Il tuo <strong>trial {tier}</strong> è attivo — <strong>{days} giorn{days === 1 ? "o" : "i"} rimasti</strong>. {urgent && "Aggiungi una carta per continuare dopo il trial."}</>
            )}
          </div>
          <Link to="/pricing" data-testid="plan-banner-cta"
            className={`inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 transition-colors ${urgent ? "bg-[#FFA500] text-black hover:bg-[#FFB933]" : "bg-[#E5FF00] text-black hover:bg-[#D4EE00]"}`}>
            {en ? "See plans" : "Vedi piani"} <ArrowRight size={11} />
          </Link>
          <button onClick={dismiss} className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors" data-testid="plan-banner-dismiss" title={en ? "Dismiss" : "Chiudi"}>
            <X size={14} />
          </button>
        </div>
      </div>
    );
  }

  // Trial scaduto - Grace period 30gg (banner arancione "riattiva")
  if (isExpired) {
    const tier = info.plan_effective === "streamer_expired" ? "Streamer" : "Pro";
    return (
      <div className="border-b border-[#FF3B30]/40 bg-[#FF3B30]/10" data-testid="plan-banner-expired">
        <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center gap-3">
          <AlertTriangle size={16} className="shrink-0 text-[#FF3B30]" />
          <div className="text-sm text-zinc-200 min-w-0 flex-1 truncate">
            {en ? (
              <>Your <strong>{tier} trial expired</strong>. Reactivate within <strong>{graceDays} day{graceDays === 1 ? "" : "s"}</strong> to keep your data.</>
            ) : (
              <>Il tuo <strong>trial {tier} è scaduto</strong>. Riattiva entro <strong>{graceDays} giorn{graceDays === 1 ? "o" : "i"}</strong> per conservare i tuoi dati.</>
            )}
          </div>
          <Link to="/pricing" data-testid="plan-banner-reactivate"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 bg-[#FF3B30] text-white hover:bg-[#FF5544] transition-colors">
            {en ? "Reactivate" : "Riattiva"} <ArrowRight size={11} />
          </Link>
          <button onClick={dismiss} className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors" data-testid="plan-banner-dismiss-expired">
            <X size={14} />
          </button>
        </div>
      </div>
    );
  }

  return null;
}
