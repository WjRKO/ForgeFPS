/**
 * ForgotPassword — Richiedi link di reset.
 *
 * Chiama POST /api/auth/forgot-password che RITORNA SEMPRE {ok:true} anche se
 * l'email non esiste (anti-enumeration). Mostriamo lo stesso messaggio a
 * prescindere per non rivelare quali email sono registrate.
 *
 * Nota UX: il link di reset viene stampato nei log del backend in dev.
 * In produzione il backend puo' inviare l'email via Resend/SendGrid (da integrare).
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Zap, Loader2, Mail, ArrowLeft, CheckCircle2 } from "lucide-react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePageMeta } from "@/hooks/usePageMeta";
import api from "@/lib/api";

export default function ForgotPassword() {
  const { t } = useTranslation();
  usePageMeta(
    t("auth.forgot_meta_title", { defaultValue: "Password dimenticata · FrameForge" }),
    t("auth.forgot_meta_desc", { defaultValue: "Recupera l'accesso al tuo account FrameForge." }),
  );
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email: email.trim().toLowerCase() });
      setSent(true);
    } catch (err) {
      // Backend ritorna sempre 200 per anti-enumeration; qualsiasi errore qui e' rete/CORS.
      setError(t("auth.forgot_generic_error", { defaultValue: "Errore di rete. Riprova." }));
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#050505] grid-bg flex items-center justify-center px-6 text-zinc-100">
      <div className="absolute top-4 right-4"><LanguageSwitcher /></div>
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-9 h-9 bg-[#E5FF00] flex items-center justify-center"><Zap size={20} className="text-black" /></div>
          <span className="font-display font-black tracking-tighter text-xl">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
        </Link>

        <div className="bg-[#0F0F12] border border-[#2A2A35] p-8">
          {sent ? (
            <div data-testid="forgot-sent">
              <div className="w-12 h-12 border border-[#00FF66]/40 bg-[#00FF66]/10 flex items-center justify-center mb-4">
                <CheckCircle2 size={22} className="text-[#00FF66]" />
              </div>
              <h1 className="font-display font-bold text-2xl tracking-tight mb-2">
                {t("auth.forgot_sent_title", { defaultValue: "Controlla la tua casella" })}
              </h1>
              <p className="text-sm text-zinc-400 leading-relaxed mb-4">
                {t("auth.forgot_sent_body", { defaultValue: "Se l'email inserita e' associata a un account FrameForge, riceverai un link per reimpostare la password entro qualche minuto. Controlla anche la cartella spam." })}
              </p>
              <p className="text-xs text-zinc-500 mb-6">
                {t("auth.forgot_sent_hint", { defaultValue: "Il link scade dopo 1 ora. Non hai ricevuto nulla dopo 10 minuti? Contatta il supporto o riprova." })}
              </p>
              <Link to="/login" data-testid="forgot-back-login"
                className="inline-flex items-center gap-2 text-sm text-[#E5FF00] hover:underline">
                <ArrowLeft size={14} /> {t("auth.back_to_login", { defaultValue: "Torna al login" })}
              </Link>
            </div>
          ) : (
            <>
              <h1 className="font-display font-bold text-2xl tracking-tight mb-1">
                {t("auth.forgot_title", { defaultValue: "Password dimenticata?" })}
              </h1>
              <p className="text-zinc-500 text-sm mb-6">
                {t("auth.forgot_sub", { defaultValue: "Ti mandiamo un link per reimpostarla. Nessuno scherzo, arriva subito." })}
              </p>

              {error && (
                <div data-testid="forgot-error" className="mb-4 text-sm text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-3 py-2">
                  {error}
                </div>
              )}

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <label className="text-xs uppercase tracking-widest text-zinc-500">
                    {t("auth.email", { defaultValue: "Email" })}
                  </label>
                  <div className="flex items-center gap-2 border-b border-[#2A2A35] focus-within:border-[#E5FF00] mt-1 transition-colors">
                    <Mail size={14} className="text-zinc-500" />
                    <input data-testid="forgot-email-input" type="email" required autoFocus
                      value={email} onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-transparent outline-none py-2 text-sm" />
                  </div>
                </div>
                <button type="submit" data-testid="forgot-submit-btn" disabled={loading}
                  className="w-full bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors flex items-center justify-center gap-2 disabled:opacity-60">
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {t("auth.forgot_submit", { defaultValue: "Manda il link" })}
                </button>
              </form>

              <div className="mt-6 text-sm text-zinc-500 text-center">
                <Link to="/login" data-testid="forgot-cancel"
                  className="text-[#E5FF00] hover:underline inline-flex items-center gap-1">
                  <ArrowLeft size={14} /> {t("auth.back_to_login", { defaultValue: "Torna al login" })}
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
