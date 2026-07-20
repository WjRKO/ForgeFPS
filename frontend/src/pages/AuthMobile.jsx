import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, ShieldAlert } from "lucide-react";
import api from "@/lib/api";

/**
 * /auth/mobile?t=<token>
 * Consumes a magic link token, sets auth cookies, redirects to /app.
 * Rendered on the mobile device that scanned the QR shown on desktop.
 */
export default function AuthMobile() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState("loading"); // loading | error
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const token = params.get("t");
    if (!token) { setState("error"); setErrorMsg("Link non valido: token mancante"); return; }
    (async () => {
      try {
        await api.post("/auth/consume-magic", { token });
        // Success: user is now authenticated, jump straight to the app dashboard
        navigate("/app", { replace: true });
      } catch (e) {
        setState("error");
        setErrorMsg(e?.response?.data?.detail || "Link scaduto o già usato");
      }
    })();
  }, [params, navigate]);

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center p-6" data-testid="auth-mobile-page">
      <div className="max-w-md w-full border border-[#2A2A35] bg-[#0F0F12] p-8 text-center">
        {state === "loading" && (
          <>
            <Loader2 size={40} className="text-[#E5FF00] animate-spin mx-auto mb-4" />
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#E5FF00] mb-2">// AUTENTICAZIONE MOBILE</div>
            <h1 className="font-display font-black text-2xl tracking-tight mb-2">Ti sto collegando...</h1>
            <p className="text-zinc-400 text-sm">Verifica del magic link in corso. Tra un istante sarai sulla Dashboard.</p>
          </>
        )}
        {state === "error" && (
          <>
            <ShieldAlert size={40} className="text-[#FF3B30] mx-auto mb-4" />
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#FF3B30] mb-2">// LINK NON VALIDO</div>
            <h1 className="font-display font-black text-2xl tracking-tight mb-2">Impossibile accedere</h1>
            <p className="text-zinc-400 text-sm mb-6" data-testid="auth-mobile-error">{errorMsg}</p>
            <p className="text-zinc-500 text-xs">
              I magic link durano 5 minuti e sono a uso singolo. Torna sul PC e rigenera il QR code.
            </p>
            <button
              onClick={() => navigate("/login")}
              className="mt-6 inline-flex items-center gap-1.5 border border-[#E5FF00]/50 text-[#E5FF00] hover:bg-[#E5FF00]/10 px-5 py-2 text-xs font-mono uppercase tracking-widest transition-colors"
              data-testid="auth-mobile-login-cta"
            >
              Vai al login →
            </button>
          </>
        )}
      </div>
    </div>
  );
}
