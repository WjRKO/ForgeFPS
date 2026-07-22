/**
 * ResetPassword — Pagina raggiunta dal link email `?token=<jwt-like>`.
 *
 * Chiama POST /api/auth/reset-password { token, password }. Il backend valida
 * il token (must exist, not used, not expired) e aggiorna la password hash.
 *
 * Se il token e' assente/scaduto/gia-usato mostra un CTA per richiederne uno nuovo.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Zap, Loader2, Lock, CheckCircle2, AlertTriangle, ArrowLeft } from "lucide-react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePageMeta } from "@/hooks/usePageMeta";
import api from "@/lib/api";

const MIN_PASSWORD_LEN = 8;

export default function ResetPassword() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  usePageMeta(
    t("auth.reset_meta_title", { defaultValue: "Reimposta password · FrameForge" }),
    t("auth.reset_meta_desc", { defaultValue: "Imposta una nuova password per il tuo account FrameForge." }),
  );

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (done) {
      const tm = setTimeout(() => navigate("/login"), 3000);
      return () => clearTimeout(tm);
    }
  }, [done, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < MIN_PASSWORD_LEN) {
      setError(t("auth.reset_pw_short", { defaultValue: `La password deve avere almeno ${MIN_PASSWORD_LEN} caratteri.`, count: MIN_PASSWORD_LEN }));
      return;
    }
    if (password !== confirm) {
      setError(t("auth.reset_pw_mismatch", { defaultValue: "Le due password non coincidono." }));
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      setDone(true);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "";
      setError(detail.includes("expired")
        ? t("auth.reset_token_expired", { defaultValue: "Il link e' scaduto. Richiedi un nuovo reset." })
        : detail.includes("used") || detail.includes("Invalid")
          ? t("auth.reset_token_invalid", { defaultValue: "Il link non e' piu' valido. Richiedi un nuovo reset." })
          : t("auth.reset_generic_error", { defaultValue: "Errore. Riprova o richiedi un nuovo link." })
      );
    } finally { setLoading(false); }
  };

  const noToken = !token;

  return (
    <div className="min-h-screen bg-[#050505] grid-bg flex items-center justify-center px-6 text-zinc-100">
      <div className="absolute top-4 right-4"><LanguageSwitcher /></div>
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-9 h-9 bg-[#E5FF00] flex items-center justify-center"><Zap size={20} className="text-black" /></div>
          <span className="font-display font-black tracking-tighter text-xl">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
        </Link>

        <div className="bg-[#0F0F12] border border-[#2A2A35] p-8">
          {done ? (
            <div data-testid="reset-done">
              <div className="w-12 h-12 border border-[#00FF66]/40 bg-[#00FF66]/10 flex items-center justify-center mb-4">
                <CheckCircle2 size={22} className="text-[#00FF66]" />
              </div>
              <h1 className="font-display font-bold text-2xl tracking-tight mb-2">
                {t("auth.reset_done_title", { defaultValue: "Password aggiornata" })}
              </h1>
              <p className="text-sm text-zinc-400 leading-relaxed mb-6">
                {t("auth.reset_done_body", { defaultValue: "Ti stiamo portando al login. La tua nuova password e' attiva." })}
              </p>
              <Link to="/login" data-testid="reset-goto-login"
                className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold text-sm px-4 py-2 hover:bg-[#D4EC00]">
                {t("auth.reset_go_login", { defaultValue: "Accedi ora" })}
              </Link>
            </div>
          ) : noToken ? (
            <div data-testid="reset-no-token">
              <div className="w-12 h-12 border border-[#FF3B30]/40 bg-[#FF3B30]/10 flex items-center justify-center mb-4">
                <AlertTriangle size={22} className="text-[#FF3B30]" />
              </div>
              <h1 className="font-display font-bold text-2xl tracking-tight mb-2">
                {t("auth.reset_no_token_title", { defaultValue: "Link non valido" })}
              </h1>
              <p className="text-sm text-zinc-400 leading-relaxed mb-6">
                {t("auth.reset_no_token_body", { defaultValue: "Questa pagina va aperta dal link che ti abbiamo inviato via email. Se il link non funziona, richiedine uno nuovo." })}
              </p>
              <Link to="/forgot-password" data-testid="reset-request-new"
                className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold text-sm px-4 py-2 hover:bg-[#D4EC00]">
                {t("auth.forgot_title", { defaultValue: "Password dimenticata?" })}
              </Link>
            </div>
          ) : (
            <>
              <h1 className="font-display font-bold text-2xl tracking-tight mb-1">
                {t("auth.reset_title", { defaultValue: "Imposta una nuova password" })}
              </h1>
              <p className="text-zinc-500 text-sm mb-6">
                {t("auth.reset_sub", { defaultValue: "Scegli qualcosa di forte. Minimo 8 caratteri." })}
              </p>

              {error && (
                <div data-testid="reset-error" className="mb-4 text-sm text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-3 py-2">
                  {error}
                </div>
              )}

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <label className="text-xs uppercase tracking-widest text-zinc-500">
                    {t("auth.reset_new_pw", { defaultValue: "Nuova password" })}
                  </label>
                  <div className="flex items-center gap-2 border-b border-[#2A2A35] focus-within:border-[#E5FF00] mt-1 transition-colors">
                    <Lock size={14} className="text-zinc-500" />
                    <input data-testid="reset-password-input" type="password" required autoFocus
                      value={password} onChange={(e) => setPassword(e.target.value)}
                      className="w-full bg-transparent outline-none py-2 text-sm" minLength={MIN_PASSWORD_LEN} />
                  </div>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-zinc-500">
                    {t("auth.reset_confirm_pw", { defaultValue: "Conferma password" })}
                  </label>
                  <div className="flex items-center gap-2 border-b border-[#2A2A35] focus-within:border-[#E5FF00] mt-1 transition-colors">
                    <Lock size={14} className="text-zinc-500" />
                    <input data-testid="reset-confirm-input" type="password" required
                      value={confirm} onChange={(e) => setConfirm(e.target.value)}
                      className="w-full bg-transparent outline-none py-2 text-sm" minLength={MIN_PASSWORD_LEN} />
                  </div>
                </div>
                <button type="submit" data-testid="reset-submit-btn" disabled={loading}
                  className="w-full bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors flex items-center justify-center gap-2 disabled:opacity-60">
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {t("auth.reset_submit", { defaultValue: "Aggiorna password" })}
                </button>
              </form>

              <div className="mt-6 text-sm text-zinc-500 text-center">
                <Link to="/login" data-testid="reset-cancel"
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
