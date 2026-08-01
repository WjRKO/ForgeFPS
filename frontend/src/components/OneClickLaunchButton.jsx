/**
 * OneClickLaunchButton — bottone che avvia il FrameForge Agent locale
 * via protocollo custom `frameforge://` senza copia-incolla di PowerShell.
 *
 * UX flow:
 *   1. Utente click "Avvia test"
 *   2. Backend firma un URI `frameforge://launch?mode=X&sig=...`
 *   3. Browser reindirizza a quell'URI -> Windows apre l'agent locale
 *   4. Polling `detectDone` (ottimista: 30-60s tipicamente)
 *   5. Se timeout -> fallback UI: "sembra che l'agent non risponda"
 *
 * Se l'utente non ha installato l'agent, il browser mostrera' un dialog
 * "sito non raggiungibile" o silenziosamente nulla. Dopo il timeout mostriamo
 * un link fallback verso /app/desktop per il download.
 *
 * Props:
 *   mode           — modalita' passata all'agent (es. "bufferbloat", "benchmark")
 *   label          — testo bottone (es. "Avvia test bufferbloat")
 *   detectDone     — async fn () => boolean per rilevare completamento
 *   timeoutMs      — default 60s
 *   onDone         — callback dopo completamento
 *   testid         — data-testid del bottone
 */
import { useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { Play, Loader2, ExternalLink, Download } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import i18n from "@/i18n";

const isEn = () => i18n.language?.startsWith("en");

export default function OneClickLaunchButton({
  mode,
  label,
  detectDone,
  timeoutMs = 60000,
  onLaunch,
  onDone,
  testid = "oneclick-launch",
}) {
  const [state, setState] = useState("idle"); // idle | launching | running | failed
  const abortRef = useRef({ stop: false });

  const launch = useCallback(async () => {
    if (state === "launching" || state === "running") return;
    setState("launching");
    abortRef.current = { stop: false };
    const en = isEn();
    const toastId = toast.loading(en ? "Preparing launch..." : "Preparo il lancio...");
    try {
      const { data } = await api.get(`/agent/launch-uri?mode=${encodeURIComponent(mode)}&silent=0`);
      if (!data?.uri) throw new Error("no_uri");
      const initialVis = document.visibilityState;
      const startedAt = Date.now();
      onLaunch?.(startedAt);
      window.location.href = data.uri;
      toast.loading(en ? "Test running... check the FrameForge Agent window" : "Test in corso... controlla la finestra FrameForge Agent", { id: toastId });
      setState("running");

      // Polling per rilevare completamento
      const startTs = Date.now();
      const intervalMs = 3000;
      let notInstalledFlagged = false;
      while (Date.now() - startTs < timeoutMs) {
        if (abortRef.current.stop) return;
        await new Promise((r) => setTimeout(r, intervalMs));
        // Hint: se dopo 4s la tab non ha mai perso focus, forse l'agent non e' installato
        if (!notInstalledFlagged && Date.now() - startedAt > 4000 && document.visibilityState === initialVis && initialVis === "visible") {
          notInstalledFlagged = true;
        }
        try {
          const done = await detectDone?.();
          if (done) {
            toast.success(en ? "Done!" : "Test completato!", { id: toastId });
            setState("idle");
            onDone?.();
            return;
          }
        } catch (_) { /* ignore polling errors */ }
      }
      // Timeout
      toast.error(en ? "The agent didn't respond. Have you installed FrameForge Agent?" : "L'agent non ha risposto. Hai installato FrameForge Agent?", { id: toastId, duration: 6000 });
      setState("failed");
    } catch (e) {
      toast.error(en ? "Launch failed. Make sure FrameForge Agent is installed." : "Lancio fallito. Verifica di aver installato FrameForge Agent.", { id: toastId });
      setState("failed");
    }
  }, [mode, state, detectDone, timeoutMs, onDone, onLaunch]);

  const isBusy = state === "launching" || state === "running";
  const failed = state === "failed";

  return (
    <div className="space-y-2" data-testid={testid}>
      <button
        onClick={launch}
        disabled={isBusy}
        data-testid={`${testid}-btn`}
        className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#D4EC00] transition-colors disabled:opacity-60 disabled:cursor-wait"
      >
        {isBusy ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
        <span>{isBusy ? (state === "launching" ? (isEn() ? "Launching..." : "Avvio...") : (isEn() ? "Running..." : "In corso...")) : (label || (isEn() ? "Launch with 1 click" : "Avvia con 1 click"))}</span>
      </button>
      {failed && (
        <div className="flex items-center gap-2 text-[11px] text-[#FF9500]" data-testid={`${testid}-fallback`}>
          <span>{isEn() ? "If you don't have the agent, download it first:" : "Se non hai l'agent, scaricalo prima:"}</span>
          <Link to="/app/desktop" className="inline-flex items-center gap-1 text-[#00E0FF] hover:underline">
            <Download size={11} /> {isEn() ? "Install FrameForge Agent" : "Installa FrameForge Agent"}
            <ExternalLink size={10} />
          </Link>
        </div>
      )}
    </div>
  );
}
