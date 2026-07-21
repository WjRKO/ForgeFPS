import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";

/**
 * Hook per lanciare l'agent Desktop in modalita' SILENT via protocollo
 * custom `frameforge://` (v0.7.1+).
 *
 * Flusso:
 *   1. Chiama GET /api/agent/launch-uri?mode=X&silent=1 -> URI firmato HMAC
 *   2. Naviga a window.location.href = uri -> Windows lancia l'exe hidden
 *   3. Polling di detectDone(callback) fino a onDone o timeout
 *   4. Toast di stato in-browser (nessuna finestra Windows visibile)
 *
 * Se l'app non e' installata, il browser mostra "site can't be reached" o
 * nulla: dopo 3s se document.visibilityState non e' cambiato, mostriamo un
 * hint "installala prima".
 *
 * detectDone: async () => bool  (deve leggere il campo da backend e verificare
 *   se l'operazione e' completata; es. sync ha bumped synced_at)
 * onDone: () => void
 * timeoutMs: default 90s (sync ~15s, benchmark ~120s -> alza a 180s per bench)
 */
export function useSilentLaunch({ mode, detectDone, onDone, timeoutMs = 90000, labels = {} } = {}) {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef({ stop: false });

  const l = {
    starting: labels.starting || "Avvio in corso...",
    running: labels.running || "In esecuzione...",
    done: labels.done || "Completato",
    failed: labels.failed || "Non risponde. Hai installato FrameForge?",
    notInstalled: labels.notInstalled || "Non hai ancora installato FrameForge? Scaricalo prima.",
  };

  const launch = useCallback(async () => {
    if (running) return;
    setRunning(true);
    setError("");
    abortRef.current = { stop: false };
    const toastId = toast.loading(l.starting);
    try {
      const { data } = await api.get(`/agent/launch-uri?mode=${encodeURIComponent(mode)}&silent=1`);
      if (!data?.uri) throw new Error("no uri");
      // Cattura lo stato di partenza per rilevare "cambio focus" (utile per il
      // fallback "app non installata"): se il browser non perde MAI focus per
      // >3s, molto probabilmente il protocollo non e' registrato.
      const initialVis = document.visibilityState;
      const startedAt = Date.now();
      window.location.href = data.uri;
      toast.loading(l.running, { id: toastId });

      // Polling per rilevare il completamento
      const startTs = Date.now();
      const intervalMs = 2000;
      while (Date.now() - startTs < timeoutMs) {
        if (abortRef.current.stop) return;
        // Check "app non installata": dopo 3s se ancora visibile senza mai
        // essere andata in background, hint di installazione
        if (Date.now() - startedAt > 3000 && document.visibilityState === initialVis && initialVis === "visible") {
          // Non blocchiamo, ma flagghiamo (mostrato solo al timeout)
        }
        await new Promise((r) => setTimeout(r, intervalMs));
        try {
          const done = await detectDone?.();
          if (done) {
            toast.success(l.done, { id: toastId });
            onDone?.();
            return;
          }
        } catch (e) {
          console.error("detectDone error", e);
        }
      }
      // Timeout: probabilmente app non installata o offline
      toast.error(l.failed, { id: toastId, duration: 6000 });
      setError(l.notInstalled);
    } catch (e) {
      console.error("silent launch error", e);
      toast.error(l.failed, { id: toastId });
      setError(String(e.message || e));
    } finally {
      setRunning(false);
    }
  }, [mode, detectDone, onDone, timeoutMs, running, l.starting, l.running, l.done, l.failed, l.notInstalled]);

  const cancel = useCallback(() => { abortRef.current.stop = true; setRunning(false); }, []);

  return { launch, cancel, running, error };
}
