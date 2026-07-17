import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Cookie } from "lucide-react";
import { useTranslation } from "react-i18next";
import { setConsent, getStoredConsent } from "@/lib/gtag";

const COPY = {
  it: {
    title: "Cookie & privacy",
    body: "Usiamo cookie tecnici e, con il tuo consenso, cookie di misurazione (Google Ads) per capire cosa funziona e migliorare il servizio. Puoi cambiare idea quando vuoi.",
    more: "Dettagli",
    accept: "Accetta",
    reject: "Rifiuta",
  },
  en: {
    title: "Cookies & privacy",
    body: "We use technical cookies and, with your consent, measurement cookies (Google Ads) to understand what works and improve the service. You can change your mind anytime.",
    more: "Details",
    accept: "Accept",
    reject: "Reject",
  },
};

export const ConsentBanner = () => {
  const { i18n } = useTranslation();
  const lang = (i18n.language || "it").startsWith("en") ? "en" : "it";
  const c = COPY[lang];
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!getStoredConsent()) setShow(true);
  }, []);

  const choose = (granted) => { setConsent(granted); setShow(false); };

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 40 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="fixed bottom-0 left-0 right-0 z-[60] p-3 sm:p-4" data-testid="consent-banner">
          <div className="max-w-4xl mx-auto bg-[#0A0A0C] border border-[#2A2A35] shadow-2xl p-4 sm:p-5 flex flex-col md:flex-row md:items-center gap-4">
            <div className="flex items-start gap-3 flex-1">
              <div className="shrink-0 w-9 h-9 bg-[#E5FF00]/10 border border-[#E5FF00]/30 flex items-center justify-center">
                <Cookie size={17} className="text-[#E5FF00]" />
              </div>
              <div>
                <div className="font-display font-bold text-sm text-zinc-100">{c.title}</div>
                <p className="text-xs text-zinc-400 leading-relaxed mt-1">
                  {c.body}{" "}
                  <Link to="/privacy-telemetry" data-testid="consent-more" className="text-[#E5FF00] hover:underline">{c.more}</Link>
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button data-testid="consent-reject" onClick={() => choose(false)}
                className="px-4 py-2 text-sm font-semibold border border-[#2A2A35] text-zinc-300 hover:border-[#FF3B30]/50 hover:text-white transition-colors">
                {c.reject}
              </button>
              <button data-testid="consent-accept" onClick={() => choose(true)}
                className="px-5 py-2 text-sm font-bold bg-[#E5FF00] text-black hover:bg-[#D4EC00] transition-colors btn-volt">
                {c.accept}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
