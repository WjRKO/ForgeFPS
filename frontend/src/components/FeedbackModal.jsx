/**
 * FeedbackModal — modale rapido per inviare feedback: bug / idea / altro.
 * - Selettore tipo (3 pillole)
 * - Textarea + contatore caratteri
 * - Screenshot opzionale (drag&drop o file picker) convertito in dataURL
 * - Invio a POST /api/feedback (che opzionalmente inoltra su Discord webhook)
 */
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { X, Bug, Lightbulb, MessageSquare, Image as ImageIcon, Send, Loader2, Check } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

const KINDS = [
  { id: "bug", icon: Bug, color: "#FF3B30", it: "Bug", en: "Bug" },
  { id: "idea", icon: Lightbulb, color: "#E5FF00", it: "Idea", en: "Idea" },
  { id: "other", icon: MessageSquare, color: "#00E0FF", it: "Altro", en: "Other" },
];

const MAX_MSG = 4000;
const MAX_SCREENSHOT_BYTES = 1_500_000; // ~1.5MB data URL

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

export default function FeedbackModal({ open, onClose }) {
  const { i18n } = useTranslation();
  const en = (i18n.resolvedLanguage || i18n.language || "it").startsWith("en");
  const location = useLocation();
  const [kind, setKind] = useState("bug");
  const [message, setMessage] = useState("");
  const [screenshot, setScreenshot] = useState(null); // data URL
  const [screenshotName, setScreenshotName] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (open) {
      setDone(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleFile = async (file) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error(en ? "Only image files" : "Solo file immagine");
      return;
    }
    if (file.size > MAX_SCREENSHOT_BYTES) {
      toast.error(en ? "Image too large (max 1.5MB)" : "Immagine troppo grande (max 1.5MB)");
      return;
    }
    const url = await fileToDataUrl(file);
    setScreenshot(url);
    setScreenshotName(file.name);
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    if (message.trim().length < 5) {
      toast.error(en ? "Message too short" : "Messaggio troppo corto");
      return;
    }
    setBusy(true);
    try {
      await api.post("/feedback", {
        kind,
        message: message.trim(),
        page: location.pathname,
        screenshot: screenshot || undefined,
      });
      setDone(true);
      toast.success(en ? "Thanks — feedback sent!" : "Grazie — feedback inviato!");
      setTimeout(() => {
        onClose?.();
        setMessage("");
        setScreenshot(null);
        setScreenshotName("");
        setKind("bug");
      }, 900);
    } catch {
      toast.error(en ? "Send failed. Try again." : "Invio fallito. Riprova.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={onClose}
      data-testid="feedback-modal-overlay"
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg bg-[#0F0F12] border-2 border-[#E5FF00]/40 relative"
        data-testid="feedback-modal"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={i18n.t("a11y.close")}
          className="absolute top-3 right-3 p-1.5 text-zinc-500 hover:text-white hover:bg-white/5 transition-colors"
          data-testid="feedback-close"
        >
          <X size={16} />
        </button>

        <div className="p-6 border-b border-[#1A1A24]">
          <div className="text-[11px] font-mono uppercase tracking-widest text-[#E5FF00] mb-1">// {en ? "we listen" : "ti ascoltiamo"}</div>
          <h2 className="font-display font-black text-2xl tracking-tighter text-white">
            {en ? "Send feedback" : "Invia feedback"}
          </h2>
          <p className="text-xs text-zinc-500 mt-1">
            {en
              ? "Bugs, ideas, small annoyances — anything. Screenshots really help."
              : "Bug, idee, piccoli fastidi — tutto vale. Gli screenshot ci aiutano tanto."}
          </p>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-500 mb-2">
              {en ? "type" : "tipo"}
            </div>
            <div className="grid grid-cols-3 gap-2">
              {KINDS.map((k) => {
                const Icon = k.icon;
                const active = kind === k.id;
                return (
                  <button
                    key={k.id}
                    type="button"
                    onClick={() => setKind(k.id)}
                    data-testid={`feedback-kind-${k.id}`}
                    className={`flex items-center justify-center gap-2 py-2.5 border text-xs font-bold uppercase tracking-widest transition-all ${
                      active
                        ? "text-black"
                        : "border-[#2A2A35] text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
                    }`}
                    style={active ? { backgroundColor: k.color, borderColor: k.color } : {}}
                  >
                    <Icon size={13} /> {en ? k.en : k.it}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-500">
                {en ? "your message" : "il tuo messaggio"}
              </div>
              <div className={`text-[11px] font-mono ${message.length > MAX_MSG * 0.9 ? "text-[#FF3B30]" : "text-zinc-600"}`}>
                {message.length}/{MAX_MSG}
              </div>
            </div>
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value.slice(0, MAX_MSG))}
              placeholder={en
                ? "Describe what happened, what you expected, or your idea..."
                : "Descrivi cosa e' successo, cosa ti aspettavi, o la tua idea..."}
              rows={5}
              data-testid="feedback-message"
              className="w-full bg-black/60 border border-[#2A2A35] focus:border-[#E5FF00] px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none resize-none transition-colors"
            />
          </div>

          <div>
            <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-500 mb-2">
              {en ? "screenshot (optional)" : "screenshot (opzionale)"}
            </div>
            {screenshot ? (
              <div className="flex items-center gap-3 border border-[#2A2A35] bg-black/40 p-3">
                <img src={screenshot} alt="preview" className="w-14 h-14 object-cover border border-[#2A2A35]" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-zinc-300 truncate">{screenshotName}</div>
                  <div className="text-[11px] text-zinc-600 font-mono">{Math.round(screenshot.length / 1024)} KB</div>
                </div>
                <button
                  type="button"
                  onClick={() => { setScreenshot(null); setScreenshotName(""); }}
                  className="text-zinc-500 hover:text-[#FF3B30] p-1"
                  data-testid="feedback-remove-screenshot"
                >
                  <X size={14} />
                </button>
              </div>
            ) : (
              <label
                className="flex flex-col items-center justify-center gap-2 border border-dashed border-[#2A2A35] hover:border-[#E5FF00]/60 bg-black/20 py-6 cursor-pointer transition-colors"
                data-testid="feedback-attach-label"
              >
                <ImageIcon size={20} className="text-zinc-500" />
                <span className="text-xs text-zinc-400">
                  {en ? "Click to attach a screenshot" : "Clicca per allegare uno screenshot"}
                </span>
                <span className="text-[11px] text-zinc-600 font-mono">PNG · JPG · max 1.5 MB</span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => handleFile(e.target.files?.[0])}
                  data-testid="feedback-file-input"
                />
              </label>
            )}
          </div>
        </div>

        <div className="p-6 border-t border-[#1A1A24] flex items-center justify-between gap-3">
          <div className="text-[11px] text-zinc-600 font-mono">
            {en ? `page: ${location.pathname}` : `pagina: ${location.pathname}`}
          </div>
          <button
            type="submit"
            disabled={busy || done || message.trim().length < 5}
            data-testid="feedback-submit"
            className={`inline-flex items-center gap-2 font-bold uppercase tracking-widest text-xs px-5 py-2.5 transition-all ${
              done
                ? "bg-[#00FF66] text-black"
                : "bg-[#E5FF00] text-black hover:bg-[#F5FF66] disabled:opacity-50 disabled:cursor-not-allowed"
            }`}
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : done ? <Check size={13} /> : <Send size={13} />}
            {done ? (en ? "Sent!" : "Inviato!") : (en ? "Send" : "Invia")}
          </button>
        </div>
      </form>
    </div>
  );
}
