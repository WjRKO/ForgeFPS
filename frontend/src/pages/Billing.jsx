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
import { CreditCard, ExternalLink, Sparkles, ArrowRight, Loader2, Wallet, Zap, Crown } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageHeader } from "@/components/hud";

const TIER_META = {
  pro: { name: "Pro", color: "#E5FF00", icon: Zap },
  streamer: { name: "Streamer", color: "#00E0FF", icon: Crown },
  pro_trial: { name: "Pro (trial)", color: "#E5FF00", icon: Zap, isTrial: true },
  streamer_trial: { name: "Streamer (trial)", color: "#00E0FF", icon: Crown, isTrial: true },
  pro_expired: { name: "Pro scaduto", color: "#FF3B30", icon: Zap, isExpired: true },
  streamer_expired: { name: "Streamer scaduto", color: "#FF3B30", icon: Crown, isExpired: true },
  starter: { name: "Starter", color: "#A1A1AA", icon: Wallet },
};

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("it-IT", { day: "2-digit", month: "long", year: "numeric" }); }
  catch { return "—"; }
}

export default function Billing() {
  const { t } = useTranslation();
  const [info, setInfo] = useState(null);
  const [loadingPortal, setLoadingPortal] = useState(false);

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
        toast.info("Non hai ancora un piano attivo. Scegli un piano dai piani disponibili.");
      } else {
        toast.error(typeof detail === "string" ? detail : detail?.message || "Errore apertura portal");
      }
    } finally { setLoadingPortal(false); }
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
        eyebrow={<span className="inline-flex items-center gap-2"><CreditCard size={13} className="text-[#E5FF00]" /> // fatturazione</span>}
        title="Fatturazione e piano"
      />

      {/* Piano corrente */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="current-plan-card">
        <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-3">// piano corrente</div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="w-14 h-14 border-2 flex items-center justify-center" style={{ borderColor: meta.color, color: meta.color }}>
            <Icon size={26} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-display font-black text-3xl tracking-tighter" style={{ color: meta.color }}>{meta.name}</div>
            {isTrial && (
              <div className="text-sm text-zinc-400 mt-1">Trial attivo — <strong className="text-zinc-100">{info.trial_days_left} giorn{info.trial_days_left === 1 ? "o" : "i"} rimasti</strong> · scade il {fmtDate(info.trial_expires_at)}</div>
            )}
            {meta.isExpired && (
              <div className="text-sm text-[#FF3B30] mt-1">Riattiva entro <strong>{info.grace_days_left} giorni</strong> per non perdere i dati.</div>
            )}
            {isPaid && info.trial_expires_at && (
              <div className="text-sm text-zinc-400 mt-1">Rinnovo automatico via Stripe · gestito nel portal.</div>
            )}
            {isStarter && (
              <div className="text-sm text-zinc-400 mt-1">Piano gratuito. Passa a Pro per sbloccare AI Advisor, Live Monitor, Full Benchmark e altro.</div>
            )}
          </div>
        </div>
      </div>

      {/* Metodo di pagamento */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="payment-method-card">
        <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-3">// metodo di pagamento</div>
        {isPaid ? (
          <>
            <p className="text-sm text-zinc-300 mb-4 leading-relaxed">
              Aggiungi o cambia carta, vedi le fatture passate, gestisci il rinnovo tramite il portal sicuro di Stripe.
            </p>
            <button
              onClick={openPortal}
              disabled={loadingPortal}
              data-testid="open-portal-btn"
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 text-sm hover:bg-[#D4EC00] transition-colors disabled:opacity-50"
            >
              {loadingPortal ? <Loader2 size={15} className="animate-spin" /> : <ExternalLink size={15} />}
              {loadingPortal ? "Apro..." : "Gestisci pagamento su Stripe"}
            </button>
            <p className="text-[11px] text-zinc-600 mt-3 font-mono">
              🔒 Portal Stripe · dati carta mai sui nostri server · PCI-DSS
            </p>
          </>
        ) : (
          <div className="text-sm text-zinc-500 leading-relaxed">
            Nessun metodo di pagamento associato al tuo account. Aggiungerai la carta quando sottoscriverai un piano.
          </div>
        )}
      </div>

      {/* CTA upgrade */}
      {(isStarter || isTrial || meta.isExpired) && (
        <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-6" data-testid="upgrade-cta">
          <div className="flex items-start gap-4">
            <Sparkles size={22} className="text-[#E5FF00] shrink-0 mt-1" />
            <div className="flex-1">
              <h3 className="font-display font-black text-xl tracking-tighter mb-2">
                {isTrial ? "Continua con Pro dopo il trial" : meta.isExpired ? "Riattiva il tuo piano" : "Migliora il tuo piano"}
              </h3>
              <p className="text-sm text-zinc-300 leading-relaxed mb-4">
                Confronta Pro (€7/mese) e Streamer (€16/mese) — o scegli l'annuale e risparmi 2 mesi.
              </p>
              <Link
                to="/pricing"
                data-testid="see-plans-btn"
                className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 text-sm hover:bg-[#D4EC00] transition-colors"
              >
                Vedi i piani <ArrowRight size={15} />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
