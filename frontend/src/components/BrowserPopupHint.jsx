import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Info, X } from "lucide-react";

const LS_KEY = "ff_popup_hint_dismissed_v1";

/**
 * Hint one-shot che appare sotto i bottoni che triggerano frameforge://
 * (Sincronizza ora, Benchmark ora, Avvia monitor). Spiega all'utente che
 * il popup del browser e' normale e come farlo sparire per sempre (spuntare
 * "Consenti sempre"). Dismissibile con X + persistente in localStorage.
 */
export default function BrowserPopupHint({ testid = "browser-popup-hint" }) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      const dismissed = window.localStorage.getItem(LS_KEY);
      if (!dismissed) setVisible(true);
    } catch { setVisible(true); }
  }, []);

  const dismiss = () => {
    try { window.localStorage.setItem(LS_KEY, String(Date.now())); } catch (e) { console.error("hint dismiss failed", e); }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="mb-4 flex items-start gap-2 bg-[#0F0F12] border border-[#00E0FF]/30 px-3 py-2 text-xs text-zinc-400 leading-relaxed" data-testid={testid}>
      <Info size={13} className="text-[#00E0FF] shrink-0 mt-0.5" />
      <div className="flex-1">
        <span className="text-[#00E0FF] font-semibold">
          {t("popup_hint.title", { defaultValue: "Prima volta?" })}
        </span>{" "}
        {t("popup_hint.body", {
          defaultValue: "Chrome ti chiederà 'Aprire FrameForge?'. Spunta 'Consenti sempre' e non lo vedrai più.",
        })}
      </div>
      <button
        type="button"
        onClick={dismiss}
        data-testid={`${testid}-dismiss`}
        className="shrink-0 text-zinc-500 hover:text-zinc-200 transition-colors"
        title={t("popup_hint.dismiss", { defaultValue: "Ho capito" })}
      >
        <X size={14} />
      </button>
    </div>
  );
}
