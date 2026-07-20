import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { X, Loader2, RefreshCw, Smartphone } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

/**
 * MobileHandoffModal — displays a magic-link QR code that the user scans
 * with their phone to open the FrameForge dashboard without logging in again.
 * Token TTL: 5 minutes, single-use (enforced backend-side).
 */
export default function MobileHandoffModal({ open, onClose }) {
  const [state, setState] = useState("idle"); // idle | loading | ready | error
  const [magicUrl, setMagicUrl] = useState("");
  const [remaining, setRemaining] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  const generate = async () => {
    setState("loading");
    setErrorMsg("");
    try {
      const { data } = await api.post("/auth/magic-link");
      const url = `${window.location.origin}/auth/mobile?t=${encodeURIComponent(data.token)}`;
      setMagicUrl(url);
      setRemaining(data.expires_in_seconds || 300);
      setState("ready");
    } catch (e) {
      setState("error");
      setErrorMsg(e?.response?.data?.detail || "Errore nella generazione del link");
    }
  };

  // Countdown that expires the QR client-side (backend still enforces TTL).
  useEffect(() => {
    if (state !== "ready") return;
    if (remaining <= 0) { setState("idle"); return; }
    const id = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
    return () => clearInterval(id);
  }, [state, remaining]);

  useEffect(() => {
    if (open && state === "idle") generate();
    if (!open) { setState("idle"); setMagicUrl(""); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="mobile-handoff-overlay"
    >
      <div
        className="max-w-md w-full bg-[#0F0F12] border border-[#2A2A35] p-6 relative"
        onClick={(e) => e.stopPropagation()}
        data-testid="mobile-handoff-modal"
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-zinc-500 hover:text-white"
          data-testid="mobile-handoff-close"
          aria-label="Chiudi"
        >
          <X size={18} />
        </button>

        <div className="text-[10px] font-mono uppercase tracking-widest text-[#E5FF00] mb-2 flex items-center gap-2">
          <Smartphone size={12} /> // CONTINUA SUL TELEFONO
        </div>
        <h2 className="font-display font-black text-xl tracking-tight text-white mb-1">Apri la Dashboard sul mobile</h2>
        <p className="text-zinc-400 text-sm mb-5">
          Scansiona il QR con la fotocamera del telefono. Ti collegherà automaticamente al tuo account, senza login.
        </p>

        <div className="flex justify-center items-center mb-5 min-h-[240px]">
          {state === "loading" && <Loader2 size={40} className="text-[#E5FF00] animate-spin" />}
          {state === "error" && (
            <div className="text-center">
              <div className="text-[#FF3B30] text-sm mb-3" data-testid="mobile-handoff-error">{errorMsg}</div>
              <button
                onClick={generate}
                className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-widest text-[#E5FF00] hover:underline"
                data-testid="mobile-handoff-retry"
              >
                <RefreshCw size={11} /> Riprova
              </button>
            </div>
          )}
          {state === "ready" && magicUrl && (
            <div className="bg-white p-4" data-testid="mobile-handoff-qr">
              <QRCodeSVG value={magicUrl} size={200} level="M" includeMargin={false} />
            </div>
          )}
          {state === "idle" && remaining === 0 && magicUrl && (
            <div className="text-center">
              <div className="text-zinc-500 text-sm mb-3">Il QR è scaduto</div>
              <button
                onClick={generate}
                className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-widest text-[#E5FF00] hover:underline"
                data-testid="mobile-handoff-regenerate"
              >
                <RefreshCw size={11} /> Genera nuovo QR
              </button>
            </div>
          )}
        </div>

        {state === "ready" && (
          <>
            <div className="flex items-center justify-between text-xs font-mono uppercase tracking-widest mb-3">
              <span className="text-zinc-500">Scade tra</span>
              <span className={remaining < 60 ? "text-[#FF3B30]" : "text-[#00FF66]"} data-testid="mobile-handoff-countdown">
                {mm}:{ss}
              </span>
            </div>
            <button
              onClick={generate}
              className="w-full inline-flex items-center justify-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-zinc-500 hover:text-[#E5FF00] py-2 border-t border-[#1A1A24] transition-colors"
              data-testid="mobile-handoff-regenerate-active"
            >
              <RefreshCw size={11} /> Rigenera
            </button>
          </>
        )}

        <div className="mt-4 pt-4 border-t border-[#1A1A24] text-[10px] text-zinc-600 leading-relaxed">
          <strong className="text-zinc-500">Sicurezza:</strong> il link scade in 5 minuti ed è a uso singolo.
          Se qualcuno lo intercetta dopo l'uso, non funziona.
        </div>
      </div>
    </div>
  );
}
