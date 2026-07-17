import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Zap, Loader2, Check } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/context/AuthContext";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePageMeta } from "@/hooks/usePageMeta";
import { trackConversion } from "@/lib/gtag";

export default function Auth({ mode }) {
  const { t } = useTranslation();
  const isLogin = mode === "login";
  usePageMeta(
    isLogin ? t("auth.meta_login_title") : t("auth.meta_register_title"),
    isLogin ? t("auth.meta_login_desc") : t("auth.meta_register_desc"),
  );
  const { login, register, formatApiErrorDetail } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [code, setCode] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      if (isLogin) {
        const res = await login(email, password, code || undefined);
        if (res && res.mfa_required) { setMfaRequired(true); setLoading(false); return; }
      } else { await register(name, email, password); trackConversion("signup"); }
      navigate("/app");
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
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
          <h1 className="font-display font-bold text-2xl tracking-tight mb-1">{isLogin ? t("auth.login_title") : t("auth.register_title")}</h1>
          <p className="text-zinc-500 text-sm mb-6">{isLogin ? t("auth.login_sub") : t("auth.register_sub")}</p>

          {error && <div data-testid="auth-error" className="mb-4 text-sm text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-3 py-2">{error}</div>}

          <form onSubmit={submit} className="space-y-4">
            {!isLogin && (
              <div>
                <label className="text-xs uppercase tracking-widest text-zinc-500">{t("auth.name")}</label>
                <input data-testid="name-input" value={name} onChange={(e) => setName(e.target.value)} required
                  className="w-full bg-black border-b border-[#2A2A35] focus:border-[#E5FF00] outline-none py-2 mt-1 text-sm transition-colors" />
              </div>
            )}
            <div>
              <label className="text-xs uppercase tracking-widest text-zinc-500">{t("auth.email")}</label>
              <input data-testid="email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                className="w-full bg-black border-b border-[#2A2A35] focus:border-[#E5FF00] outline-none py-2 mt-1 text-sm transition-colors" />
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-zinc-500">{t("auth.password")}</label>
              <input data-testid="password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                className="w-full bg-black border-b border-[#2A2A35] focus:border-[#E5FF00] outline-none py-2 mt-1 text-sm transition-colors" />
            </div>
            {isLogin && mfaRequired && (
              <div data-testid="mfa-code-field">
                <label className="text-xs uppercase tracking-widest text-[#E5FF00]">{t("auth.mfa_code")}</label>
                <input data-testid="mfa-code-input" value={code} onChange={(e) => setCode(e.target.value)} autoFocus inputMode="numeric" placeholder="123456"
                  className="w-full bg-black border-b border-[#E5FF00]/50 focus:border-[#E5FF00] outline-none py-2 mt-1 text-sm tracking-widest transition-colors" />
                <p className="text-[11px] text-zinc-500 mt-1">{t("auth.mfa_hint")}</p>
              </div>
            )}
            <button type="submit" data-testid="auth-submit-btn" disabled={loading}
              className="w-full bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors flex items-center justify-center gap-2 disabled:opacity-60 btn-volt">
              {loading && <Loader2 size={16} className="animate-spin" />}
              {isLogin ? t("auth.login_btn") : t("auth.register_btn")}
            </button>
          </form>

          <div className="mt-6 text-sm text-zinc-500 text-center">
            {isLogin ? (
              <>{t("auth.no_account")} <Link to="/register" data-testid="go-register" className="text-[#E5FF00] hover:underline">{t("auth.go_register")}</Link></>
            ) : (
              <>{t("auth.have_account")} <Link to="/login" data-testid="go-login" className="text-[#E5FF00] hover:underline">{t("auth.go_login")}</Link></>
            )}
          </div>
        </div>

        <div className="mt-6 border border-[#1A1A24] bg-[#0F0F12]/60 p-5">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3">{t("auth.feat_title")}</div>
          <ul className="space-y-2.5">
            {[t("auth.feat1"), t("auth.feat2"), t("auth.feat3")].map((f, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm text-zinc-300 leading-relaxed">
                <span className="w-4 h-4 mt-0.5 border border-[#E5FF00] flex items-center justify-center shrink-0">
                  <Check size={10} className="text-[#E5FF00]" />
                </span>
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
