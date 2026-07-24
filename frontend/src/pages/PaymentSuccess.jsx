/**
 * Payment Success page — poll Stripe session status finche' payment_status="paid",
 * poi redirect al dashboard con toast. In caso di timeout (30s), mostra un messaggio
 * con contatto supporto.
 */
import { useEffect, useState } from "react";
import { useSearchParams, Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import api from "@/lib/api";

const COPY = {
  it: {
    checking: "Confermo il pagamento con Stripe...",
    success: "Pagamento completato! Il tuo piano è attivo.",
    success_hint: "Ti stiamo portando al dashboard...",
    failed: "Il pagamento non è andato a buon fine.",
    failed_hint: "Nessun addebito è stato fatto. Riprova o contatta il supporto.",
    to_dashboard: "Vai al dashboard",
    to_pricing: "Torna ai piani",
    timeout: "Sto verificando ancora... Se non vedi il tuo piano attivo tra un minuto, contatta il supporto.",
  },
  en: {
    checking: "Confirming payment with Stripe...",
    success: "Payment complete! Your plan is active.",
    success_hint: "Redirecting you to the dashboard...",
    failed: "Payment was not successful.",
    failed_hint: "No charge was made. Try again or contact support.",
    to_dashboard: "Go to dashboard",
    to_pricing: "Back to plans",
    timeout: "Still verifying... If you don't see your plan active in a minute, contact support.",
  },
};

export default function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const navigate = useNavigate();
  const lang = useLang();
  const c = COPY[lang];
  const [state, setState] = useState("checking"); // checking | success | failed | timeout
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    if (!sessionId) { setState("failed"); return; }
    let cancelled = false;
    const poll = async () => {
      try {
        const { data } = await api.get(`/payments/status/${sessionId}`);
        if (data.payment_status === "paid") {
          if (!cancelled) {
            setState("success");
            toast.success(c.success);
            setTimeout(() => navigate("/app"), 2000);
          }
          return;
        }
        if (data.status === "failed" || data.payment_status === "failed") {
          if (!cancelled) setState("failed");
          return;
        }
      } catch (e) { /* transient network error */ }
      // Retry with backoff (max 15 attempts = 30s)
      setAttempts((a) => a + 1);
    };
    poll();
    const interval = setInterval(() => {
      if (attempts >= 15) { setState((s) => (s === "checking" ? "timeout" : s)); return; }
      poll();
    }, 2000);
    return () => { cancelled = true; clearInterval(interval); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <MarketingNav />
      <main className="max-w-2xl mx-auto px-6 pt-32 pb-24 text-center" data-testid="payment-success">
        {state === "checking" && (
          <>
            <Loader2 size={48} className="text-[#E5FF00] mx-auto mb-6 animate-spin" />
            <h1 className="font-display font-black text-3xl tracking-tighter mb-3">{c.checking}</h1>
            <p className="text-zinc-500 text-sm">Session: <span className="font-mono">{sessionId?.slice(0, 20)}...</span></p>
          </>
        )}
        {state === "success" && (
          <>
            <CheckCircle2 size={56} className="text-[#00FF66] mx-auto mb-6" />
            <h1 className="font-display font-black text-4xl tracking-tighter mb-3" data-testid="success-title">{c.success}</h1>
            <p className="text-zinc-400 mb-8">{c.success_hint}</p>
            <Link to="/app" data-testid="go-dashboard-btn"
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3 uppercase tracking-wide text-sm hover:bg-[#D4EC00] transition-colors">
              {c.to_dashboard} <ArrowRight size={15} />
            </Link>
          </>
        )}
        {state === "failed" && (
          <>
            <XCircle size={56} className="text-[#FF3B30] mx-auto mb-6" />
            <h1 className="font-display font-black text-3xl tracking-tighter mb-3">{c.failed}</h1>
            <p className="text-zinc-400 mb-8">{c.failed_hint}</p>
            <Link to="/pricing" className="inline-flex items-center gap-2 border border-[#2A2A35] px-6 py-3 uppercase tracking-wide text-sm hover:border-[#E5FF00] transition-colors">
              {c.to_pricing} <ArrowRight size={15} />
            </Link>
          </>
        )}
        {state === "timeout" && (
          <>
            <Loader2 size={48} className="text-[#FFA500] mx-auto mb-6" />
            <h1 className="font-display font-black text-2xl tracking-tighter mb-3">{c.timeout}</h1>
            <Link to="/app" className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3 uppercase tracking-wide text-sm hover:bg-[#D4EC00] transition-colors">
              {c.to_dashboard} <ArrowRight size={15} />
            </Link>
          </>
        )}
      </main>
      <MarketingFooter />
    </div>
  );
}
