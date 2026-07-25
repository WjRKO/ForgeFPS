/**
 * useFirstScanPolling — polling hook for the "first PC scan" flow.
 *
 * Returns one of:
 *   { status: "checking" }                   fase iniziale (< qualche ms)
 *   { status: "idle" }                       utente veterano, dati preesistevano
 *   { status: "pending" }                    utente nuovo, in attesa dell'agent
 *   { status: "done-fresh", specs }          scan appena arrivato durante la sessione
 *
 * Logic:
 * - checkOnce(isFirstCall=true) al mount: se esiste gia' un doc pc_specs con
 *   dati significativi -> preExisted, status="idle" (banner nascosto).
 * - Altrimenti pending + polling loop ogni POLL_INTERVAL_MS. Dopo
 *   POLL_SLOW_AFTER_MS l'intervallo passa a POLL_SLOW_INTERVAL_MS per
 *   non consumare cicli se la tab e' lasciata aperta.
 * - Quando arriva un doc valido -> status="done-fresh" + specs.
 */
import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";

const POLL_INTERVAL_MS = 3000;
const POLL_SLOW_AFTER_MS = 60_000;
const POLL_SLOW_INTERVAL_MS = 10_000;

const hasSignificantData = (data) => !!(data && (
  data.updated_at ||
  (data.data && Object.keys(data.data).length > 0) ||
  data.benchmark ||
  data.health ||
  (Array.isArray(data.startup) && data.startup.length > 0) ||
  (Array.isArray(data.games) && data.games.length > 0) ||
  (Array.isArray(data.running_apps) && data.running_apps.length > 0)
));

export function useFirstScanPolling() {
  const [status, setStatus] = useState("checking");
  const [specs, setSpecs] = useState(null);
  const pollRef = useRef(null);
  const startedAtRef = useRef(0);

  useEffect(() => {
    let stopped = false;
    startedAtRef.current = Date.now();

    const checkOnce = async (isFirstCall) => {
      try {
        const { data } = await api.get("/pc-specs");
        if (!hasSignificantData(data)) return false;
        if (isFirstCall) {
          setStatus("idle");
        } else {
          setSpecs(data.data || {});
          setStatus("done-fresh");
        }
        return true;
      } catch {
        return false;
      }
    };

    (async () => {
      const found = await checkOnce(true);
      if (stopped || found) return;
      setStatus("pending");
      const tick = async () => {
        if (stopped) return;
        const found2 = await checkOnce(false);
        if (stopped || found2) return;
        const elapsed = Date.now() - startedAtRef.current;
        const nextMs = elapsed > POLL_SLOW_AFTER_MS ? POLL_SLOW_INTERVAL_MS : POLL_INTERVAL_MS;
        pollRef.current = setTimeout(tick, nextMs);
      };
      pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    })();

    return () => {
      stopped = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  return { status, specs };
}
