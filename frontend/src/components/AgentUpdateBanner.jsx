/**
 * AgentUpdateBanner — banner globale che invita ad aggiornare il FrameForge Agent
 * a una versione piu' recente. Mostrato solo se:
 *  - l'utente ha gia' usato l'agent almeno una volta (has_ever_run)
 *  - la versione installata e' inferiore alla latest (o non riportata = pre-0.7.6)
 *
 * Dismissibile per sessione (sessionStorage) — appare di nuovo al prossimo login.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { X, ArrowUpCircle, ExternalLink, Sparkles } from "lucide-react";
import api from "@/lib/api";

const DISMISS_KEY = "agent_update_banner_dismissed_v";

export default function AgentUpdateBanner() {
  const { i18n } = useTranslation();
  const en = (i18n.resolvedLanguage || i18n.language || "it").startsWith("en");
  const [state, setState] = useState({ loading: true, show: false, installed: null, latest: null });

  useEffect(() => {
    api.get("/agent/status").then(({ data }) => {
      if (!data?.is_outdated) return setState({ loading: false, show: false });
      // Dismiss valido solo per la latest_version specifica: se esce v0.7.7 il banner riappare.
      const dismissed = sessionStorage.getItem(`${DISMISS_KEY}${data.latest_version}`);
      setState({
        loading: false,
        show: !dismissed,
        installed: data.installed_version,
        latest: data.latest_version,
      });
    }).catch(() => setState({ loading: false, show: false }));
  }, []);

  if (state.loading || !state.show) return null;

  const dismiss = () => {
    sessionStorage.setItem(`${DISMISS_KEY}${state.latest}`, "1");
    setState((s) => ({ ...s, show: false }));
  };

  return (
    <div
      className="border-b border-[#E5FF00]/40 bg-gradient-to-r from-[#E5FF00]/15 via-[#00E0FF]/8 to-transparent"
      data-testid="agent-update-banner"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-2.5 flex items-center gap-3 flex-wrap">
        <div className="relative shrink-0">
          <ArrowUpCircle size={18} className="text-[#E5FF00]" />
          <span className="absolute -top-1 -right-1 w-2 h-2 bg-[#E5FF00] rounded-full animate-pulse" />
        </div>
        <div className="flex-1 min-w-0 text-sm text-zinc-200 flex items-center gap-2 flex-wrap">
          <span className="font-bold">
            {en ? "New FrameForge Agent available" : "Nuova versione FrameForge Agent"}
          </span>
          <span className="text-zinc-400">·</span>
          <span className="text-xs text-zinc-400 flex items-center gap-1.5">
            <span className="font-mono">
              {state.installed || (en ? "unknown" : "sconosciuta")}
            </span>
            <span className="text-zinc-600">→</span>
            <span className="font-mono text-[#E5FF00] font-bold">v{state.latest}</span>
          </span>
          <span className="text-zinc-400 hidden md:inline">·</span>
          <span className="text-xs text-zinc-400 hidden md:inline">
            {en ? "silent buttons no longer flash the terminal" : "i bottoni silent non fanno piu' lampeggiare il terminale"}
          </span>
        </div>
        <Link
          to="/app/desktop"
          data-testid="agent-update-cta"
          className="inline-flex items-center gap-1.5 bg-[#E5FF00] text-black font-bold uppercase tracking-widest text-[11px] px-3 py-1.5 hover:bg-[#F5FF66] transition-colors"
        >
          <Sparkles size={12} /> {en ? "Update now" : "Aggiorna ora"}
        </Link>
        <button
          type="button"
          onClick={dismiss}
          data-testid="agent-update-dismiss"
          className="p-1 text-zinc-500 hover:text-white transition-colors"
          aria-label={en ? "Dismiss" : "Chiudi"}
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
