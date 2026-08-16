/**
 * Billing page — accessibile via ProfileMenu → "Fatturazione".
 *
 * Se piano paid: mostra piano corrente + link a Stripe Customer Portal per gestire
 * metodo di pagamento, vedere fatture, cancellare.
 * Se trial/starter: propone upgrade (link a /pricing).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CreditCard, ExternalLink, Sparkles, ArrowRight, Loader2, Wallet, Zap, Crown, XCircle } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import i18n from "@/i18n";
import { PageHeader } from "@/components/hud";

const TIER_META = {
  pro: { name: "Pro", color: "#E5FF00", icon: Zap },
  streamer: { name: "Streamer", color: "#00E0FF", icon: Crown },
  pro_trial: { name: "Pro (trial)", color: "#E5FF00", icon: Zap, isTrial: true },
  streamer_trial: { name: "Streamer (trial)", color: "#00E0FF", icon: Crown, isTrial: true },
  pro_expired: { name: "Pro scaduto", name_en: "Pro expired", color: "#FF3B30", icon: Zap, isExpired: true },
  streamer_expired: { name: "Streamer scaduto", name_en: "Streamer expired", color: "#FF3B30", icon: Crown, isExpired: true },
  starter: { name: "Starter", color: "#A1A1AA", icon: Wallet },
};

const isEn = () => i18n.language?.startsWith("en");

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(isEn() ? "en-US" : "it-IT", { day: "2-digit", month: "long", year: "numeric" }); }
  catch { return "—"; }
}

export default function Billing() {
  const { t } = useTranslation();
  const [info, setInfo] = useState(null);
  const [loadingPortal, setLoadingPortal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [askCancel, setAskCancel] = useState(false);

  useEffect(() => {
    api.get("/subscriptions/status").then(({ data }) => setInfo(data)).catch(() => {});
  }, []);

  const openPortal = async () => {
    setLoadingPortal(true);
    try {
      const { data } = await api.post("/payments/portal");
      if (data?.portal_url) window.location.href = data.portal_url;
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const code = typeof detail === "object" ? detail?.code : null;
      if (code === "no_customer") {
        toast.info(isEn() ? "You don't have an active plan yet. Pick one from the available plans." : "Non hai ancora un piano attivo. Scegli un piano dai piani disponibili.");
      } else {
        toast.error(typeof detail === "string" ? detail : detail?.message || (isEn() ? "Error opening portal" : "Errore apertura portal"));
      }
    } finally { setLoadingPortal(false); }
  };

  // Chi e' in trial non ha un customer Stripe, quindi il portal gli risponde 400:
  // senza questo l'unico modo per fermare il trial era aspettarne la scadenza.
  const cancelTrial = async () => {
    setCancelling(true);
    try {
      await api.post("/subscriptions/cancel-trial");
      toast.success(isEn() ? "Trial cancelled. You are back on the Starter plan." : "Trial annullato. Sei tornato al piano Starter.");
      setAskCancel(false);
      const { data } = await api.get("/subscriptions/status");
      setInfo(data);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message || (isEn() ? "Could not cancel the trial" : "Impossibile annullare il trial"));
    } finally { setCancelling(false); }
  };

  if (!info) {
    return <div className="max-w-4xl mx-auto py-10 text-center text-zinc-500"><Loader2 size={24} className="mx-auto animate-spin" /></div>;
  }

  const eff = info.plan_effective;
  const meta = TIER_META[eff] || TIER_META.starter;
  const Icon = meta.icon;
  const isPaid = eff === "pro" || eff === "streamer";
  const isTrial = eff === "pro_trial" || eff === "streamer_trial";
  const isStarter = eff === "starter";

  return (
    <div className="max-w-4xl mx-auto fade-up" data-testid="billing-page">
      <PageHeader
        eyebrow={<span className="inline-flex items-center gap-2"><CreditCard size={13} className="text-[#E5FF00]" /> {isEn() ? "// billing" : "// fatturazione"}</span>}
        title={isEn() ? "Billing & plan" : "Fatturazione e piano"}
      />

      {/* Piano corrente */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="current-plan-card">
        <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-3">{isEn() ? "// current plan" : "// piano corrente"}</div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="w-14 h-14 border-2 flex items-center justify-center" style={{ borderColor: meta.color, color: meta.color }}>
            <Icon size={26} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-display font-black text-3xl tracking-tighter" style={{ color: meta.color }}>{isEn() && meta.name_en ? meta.name_en : meta.name}</div>
            {isTrial && (
              <div className="text-sm text-zinc-400 mt-1">{isEn() ? <>Trial active — <strong className="text-zinc-100">{info.trial_days_left} day{info.trial_days_left === 1 ? "" : "s"} left</strong> · expires {fmtDate(info.trial_expires_at)}</> : <>Trial attivo — <strong className="text-zinc-100">{info.trial_days_left} giorn{info.trial_days_left === 1 ? "o" : "i"} rimasti</strong> · scade il {fmtDate(info.trial_expires_at)}</>}</div>
            )}
            {meta.isExpired && (
              <div className="text-sm text-[#FF3B30] mt-1">{isEn() ? <>Reactivate within <strong>{info.grace_days_left} days</strong> to keep your data.</> : <>Riattiva entro <strong>{info.grace_days_left} giorni</strong> per non perdere i dati.</>}</div>
            )}
            {isPaid && info.trial_expires_at && (
              <div className="text-sm text-zinc-400 mt-1">{isEn() ? "Automatic renewal via Stripe · managed in the portal." : "Rinnovo automatico via Stripe · gestito nel portal."}</div>
            )}
            {isStarter && (
              <div className="text-sm text-zinc-400 mt-1">{isEn() ? "Free plan. Upgrade to Pro to unlock AI Advisor, Live Monitor, Full Benchmark and more." : "Piano gratuito. Passa a Pro per sbloccare AI Advisor, Live Monitor, Full Benchmark e altro."}</div>
            )}
          </div>
        </div>
      </div>

      {/* Metodo di pagamento */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="payment-method-card">
        <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-3">{isEn() ? "// payment method" : "// metodo di pagamento"}</div>
        {isPaid ? (
          <>
            <p className="text-sm text-zinc-300 mb-4 leading-relaxed">
              {isEn() ? "Add or change your card, view past invoices, manage renewal through Stripe's secure portal." : "Aggiungi o cambia carta, vedi le fatture passate, gestisci il rinnovo tramite il portal sicuro di Stripe."}
            </p>
            <button
              onClick={openPortal}
              disabled={loadingPortal}
              data-testid="open-portal-btn"
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 text-sm hover:bg-[#D4EC00] transition-colors disabled:opacity-50"
            >
              {loadingPortal ? <Loader2 size={15} className="animate-spin" /> : <ExternalLink size={15} />}
              {loadingPortal ? (isEn() ? "Opening..." : "Apro...") : (isEn() ? "Manage payment on Stripe" : "Gestisci pagamento su Stripe")}
            </button>
            <p className="text-[11px] text-zinc-600 mt-3 font-mono">
              {isEn() ? "🔒 Stripe Portal · card data never on our servers · PCI-DSS" : "🔒 Portal Stripe · dati carta mai sui nostri server · PCI-DSS"}
            </p>
          </>
        ) : (
          <div className="text-sm text-zinc-500 leading-relaxed">
            {isEn() ? "No payment method linked to your account. You'll add a card when you subscribe to a plan." : "Nessun metodo di pagamento associato al tuo account. Aggiungerai la carta quando sottoscriverai un piano."}
          </div>
        )}
      </div>

      {/* Annullamento trial */}
      {isTrial && (
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="cancel-trial-card">
          <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-3">{isEn() ? "// cancel trial" : "// annulla trial"}</div>
          {askCancel ? (
            <>
              <p className="text-sm text-zinc-300 mb-4 leading-relaxed">
                {isEn()
                  ? "You will go back to the Starter plan immediately and lose access to Pro features. Your data is kept."
                  : "Tornerai subito al piano Starter e perderai l'accesso alle funzioni Pro. I tuoi dati restano salvati."}
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={cancelTrial}
                  disabled={cancelling}
                  data-testid="cancel-trial-confirm"
                  className="inline-flex items-center gap-2 border border-[#FF3B30]/50 text-[#FF3B30] px-5 py-2.5 text-sm hover:bg-[#FF3B30]/10 transition-colors disabled:opacity-50"
                >
                  {cancelling ? <Loader2 size={15} className="animate-spin" /> : <XCircle size={15} />}
                  {isEn() ? "Yes, cancel the trial" : "Sì, annulla il trial"}
                </button>
                <button
                  onClick={() => setAskCancel(false)}
                  disabled={cancelling}
                  data-testid="cancel-trial-back"
                  className="border border-[#2A2A35] text-zinc-300 px-5 py-2.5 text-sm hover:border-[#E5FF00]/50 transition-colors disabled:opacity-50"
                >
                  {isEn() ? "Keep the trial" : "Mantieni il trial"}
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
                {isEn()
                  ? "You can stop the trial at any time. No card was ever required, so there is nothing to charge."
                  : "Puoi fermare il trial quando vuoi. Non è mai stata richiesta una carta, quindi non c'è nulla da addebitare."}
              </p>
              <button
                onClick={() => setAskCancel(true)}
                data-testid="cancel-trial-btn"
                className="text-sm text-zinc-400 underline underline-offset-4 hover:text-[#FF3B30] transition-colors"
              >
                {isEn() ? "Cancel the trial" : "Annulla il trial"}
              </button>
            </>
          )}
        </div>
      )}

      {/* CTA upgrade */}
      {(isStarter || isTrial || meta.isExpired) && (
        <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-6" data-testid="upgrade-cta">
          <div className="flex items-start gap-4">
            <Sparkles size={22} className="text-[#E5FF00] shrink-0 mt-1" />
            <div className="flex-1">
              <h3 className="font-display font-black text-xl tracking-tighter mb-2">
                {isTrial ? (isEn() ? "Continue with Pro after the trial" : "Continua con Pro dopo il trial") : meta.isExpired ? (isEn() ? "Reactivate your plan" : "Riattiva il tuo piano") : (isEn() ? "Upgrade your plan" : "Migliora il tuo piano")}
              </h3>
              <p className="text-sm text-zinc-300 leading-relaxed mb-4">
                {isEn() ? "Compare Pro (€7/month) and Streamer (€16/month) — or go yearly and save 2 months." : "Confronta Pro (€7/mese) e Streamer (€16/mese) — o scegli l'annuale e risparmi 2 mesi."}
              </p>
              <Link
                to="/pricing"
                data-testid="see-plans-btn"
                className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 text-sm hover:bg-[#D4EC00] transition-colors"
              >
                {isEn() ? "See plans" : "Vedi i piani"} <ArrowRight size={15} />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
