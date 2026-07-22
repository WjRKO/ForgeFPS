import { useEffect, useRef, useCallback, useState } from "react";
import api from "@/lib/api";
import { useSilentLaunch } from "./useSilentLaunch";

/**
 * Sync ambientale (Fase 2):
 * - Legge /api/pc-specs, calcola l'eta' dell'ultimo sync (updated_at).
 * - Trigger automatico silent sync se:
 *   1. Ultimo sync > STALE_HOURS (default 24h) → all'apertura pagina
 *   2. Tab torna in focus dopo IDLE_HOURS di inattivita' (default 1h)
 * - Debounce: max 1 auto-sync ogni COOLDOWN_MIN (default 30 min) per non
 *   sovraccaricare il PC dell'utente.
 * - Espone { ageSec, tier, forceSync, refresh } per FreshnessBadge / AI hover.
 *
 * tier: 'fresh' (< 10min) | 'warm' (< STALE_HOURS h) | 'stale' (>= STALE_HOURS h) | 'unknown'
 */
const STALE_HOURS = 24;
const IDLE_HOURS = 1;
const COOLDOWN_MIN = 30;
const FRESH_MIN = 10;
const LS_LAST_AUTO = "ff_autosync_last_ts";
const LS_LAST_HIDDEN = "ff_last_hidden_ts";

export function useAutoSync({ enabled = true, onSynced } = {}) {
  const [updatedAt, setUpdatedAt] = useState(null);
  const [now, setNow] = useState(Date.now());
  const triggeredRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/pc-specs");
      setUpdatedAt(data?.updated_at || null);
      return data?.updated_at || null;
    } catch (e) {
      console.error("useAutoSync refresh failed", e);
      return null;
    }
  }, []);

  // Silent sync
  const sync = useSilentLaunch({
    mode: "sync",
    timeoutMs: 60000,
    labels: {
      starting: "",
      running: "",
      done: "",
      failed: "",
    },
    detectDone: async () => {
      const u = await refresh();
      if (u && u !== updatedAt) {
        try { window.localStorage.setItem(LS_LAST_AUTO, String(Date.now())); } catch (e) { console.error("LS write failed", e); }
        onSynced?.(u);
        return true;
      }
      return false;
    },
  });

  const canAutoSync = () => {
    try {
      const last = parseInt(window.localStorage.getItem(LS_LAST_AUTO) || "0", 10);
      if (!last) return true;
      return Date.now() - last > COOLDOWN_MIN * 60 * 1000;
    } catch { return true; }
  };

  const forceSync = useCallback(() => {
    if (sync.running) return;
    sync.launch();
  }, [sync]);

  // Trigger 1 (disabilitato v0.7.4): auto-launch al carico pagina.
  // Prima causava un URI navigation ad ogni login/reload che apriva un popup
  // "Aprire FrameForge?" nel browser e (con exe non allineato) una finestra
  // PowerShell visibile. Ora il badge mostra solo lo status; l'utente clicca
  // manualmente per sincronizzare quando vuole.
  useEffect(() => {
    if (!enabled || triggeredRef.current) return;
    (async () => {
      const u = await refresh();
      if (!u) return;
      // Solo un log info per debug — nessun sync automatico.
      const age = (Date.now() - new Date(u).getTime()) / (1000 * 60 * 60);
      if (age >= STALE_HOURS) {
        console.log(`[autosync] Stale by ${age.toFixed(1)}h — user can click the badge to sync.`);
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  // Trigger 2 (disabilitato v0.7.4): auto-launch al ritorno di focus dopo idle.
  // Stessa motivazione del Trigger 1. Manteniamo solo il tracking dell'idle
  // per potenziali future analytics; nessuna azione automatica.
  useEffect(() => {
    if (!enabled) return;
    const onVis = () => {
      if (document.visibilityState === "hidden") {
        try { window.localStorage.setItem(LS_LAST_HIDDEN, String(Date.now())); } catch (e) { console.error("LS write failed", e); }
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [enabled]);

  // Ticker to keep 'now' updated per age display (every 30s)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  // Compute age + tier
  let ageSec = null, tier = "unknown";
  if (updatedAt) {
    try {
      ageSec = Math.floor((now - new Date(updatedAt).getTime()) / 1000);
      if (ageSec < FRESH_MIN * 60) tier = "fresh";
      else if (ageSec < STALE_HOURS * 3600) tier = "warm";
      else tier = "stale";
    } catch { tier = "unknown"; }
  }

  return { updatedAt, ageSec, tier, forceSync, refresh, running: sync.running };
}
