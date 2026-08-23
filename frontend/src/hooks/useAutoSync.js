import { useEffect, useCallback, useState } from "react";
import api from "@/lib/api";
import { useSilentLaunch } from "./useSilentLaunch";
import { SYNC_TIMEOUT_MS } from "@/lib/syncLabels";

/**
 * Eta' dell'ultimo sync + sync manuale per il badge di freschezza.
 *
 * Nasceva come "sync ambientale": due trigger automatici - all'apertura pagina
 * se i dati erano vecchi, e al ritorno di focus dopo un'ora di inattivita' -
 * con un debounce per non tempestare il PC. In v0.7.4 sono stati disattivati:
 * facevano navigare a un URI `frameforge://` a ogni login, quindi il browser
 * chiedeva "Aprire FrameForge?" e, con un exe disallineato, si apriva pure una
 * finestra PowerShell. Da allora il badge mostra lo stato e l'utente clicca.
 *
 * Restava pero' l'impalcatura dei trigger spenti: il debounce `canAutoSync()`
 * definito e mai chiamato, il timestamp dell'ultimo idle scritto in
 * localStorage e mai riletto "per potenziali future analytics", le costanti che
 * li taravano. Codice che non si esegue non si rompe mai in modo visibile: si
 * limita a far credere a chi legge che ci sia un comportamento che non c'e'.
 * Quel che serviva davvero e' in git; qui resta cosa il badge mostra oggi.
 *
 * tier: 'fresh' (< 10min) | 'warm' (< 24h) | 'stale' (>= 24h) | 'unknown'
 */
const STALE_HOURS = 24;
const FRESH_MIN = 10;

export function useAutoSync({ enabled = true, labels, onSynced } = {}) {
  const [updatedAt, setUpdatedAt] = useState(null);
  const [now, setNow] = useState(Date.now());

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

  const sync = useSilentLaunch({
    mode: "sync",
    timeoutMs: SYNC_TIMEOUT_MS,
    // Le etichette arrivano da chi ha `t`. Prima erano quattro stringhe vuote,
    // che l'hook trattava come "non passate" e sostituiva con i propri default
    // in italiano: il badge parlava italiano anche in inglese.
    labels,
    detectDone: async () => {
      const u = await refresh();
      if (u && u !== updatedAt) {
        onSynced?.(u);
        return true;
      }
      return false;
    },
  });

  const forceSync = useCallback(() => {
    if (sync.running) return;
    sync.launch();
  }, [sync]);

  // All'apertura: quanto sono vecchi i dati. Nessun sync automatico.
  useEffect(() => {
    if (!enabled) return;
    refresh();
  }, [enabled, refresh]);

  // Ticker per tenere aggiornata l'eta' mostrata (ogni 30s)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

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
