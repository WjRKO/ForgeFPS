import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Radio, Square, Copy, Gamepad2, Loader2 } from "lucide-react";
import api from "@/lib/api";

/**
 * Live monitor control panel — replaces the "Avvia monitor" launcher when the
 * agent is actively streaming telemetry. Shows a REC-style badge, live duration,
 * sample count, current game, and a Stop button that flips the server-side
 * `monitor_control.stop_requested` flag. The agent's telemetry POST reads the
 * flag and the loop exits cleanly on its next tick (~1s).
 */
export default function MonitorLiveControl({ startedAt, sampleCount, game }) {
  const { t } = useTranslation();
  const [now, setNow] = useState(Date.now());
  const [stopping, setStopping] = useState(false);
  const [stopRequestedAt, setStopRequestedAt] = useState(null);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const durationSec = useMemo(() => {
    if (!startedAt) return 0;
    return Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 1000));
  }, [now, startedAt]);

  const fmt = (s) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  const requestStop = async () => {
    if (stopping) return;
    setStopping(true);
    try {
      await api.post("/monitor/stop");
      setStopRequestedAt(Date.now());
      toast.success(t("live.stop_requested", { defaultValue: "Stop richiesto — il monitor si chiuderà entro pochi secondi." }));
    } catch (e) {
      console.error("monitor/stop failed", e);
      toast.error(t("live.stop_failed", { defaultValue: "Impossibile richiedere lo stop. Chiudi la finestra sul PC." }));
      setStopping(false);
    }
  };

  const copyUri = async () => {
    try {
      const { data } = await api.get("/agent/launch-uri?mode=monitor");
      await navigator.clipboard.writeText(data.uri);
      toast.success(t("live.uri_copied", { defaultValue: "Link monitor copiato negli appunti." }));
    } catch (e) {
      toast.error(t("live.uri_copy_failed", { defaultValue: "Impossibile copiare il link." }));
    }
  };

  const stopPending = stopRequestedAt && Date.now() - stopRequestedAt < 15000;

  return (
    <div className="bg-[#0F0F12] border border-[#FF3B30]/40 hud-tick p-5 mb-6" data-testid="monitor-live-control">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2 shrink-0">
          <span className="relative flex h-3 w-3">
            <span className={`absolute inline-flex h-full w-full rounded-full bg-[#FF3B30] opacity-75 ${stopPending ? "" : "animate-ping"}`} />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-[#FF3B30]" />
          </span>
          <span className="font-display font-black text-lg text-[#FF3B30]">REC</span>
        </div>

        <div className="flex items-baseline gap-2">
          <span className="font-mono text-2xl tabular-nums text-zinc-100" data-testid="live-duration">{fmt(durationSec)}</span>
          <span className="text-xs text-zinc-500 uppercase tracking-widest">{t("live.duration", { defaultValue: "durata" })}</span>
        </div>

        <div className="flex items-baseline gap-2 border-l border-[#1A1A24] pl-4">
          <span className="font-mono text-xl tabular-nums text-zinc-300" data-testid="live-samples">{sampleCount}</span>
          <span className="text-xs text-zinc-500 uppercase tracking-widest">{t("live.samples", { defaultValue: "sample" })}</span>
        </div>

        {game && (
          <div className="flex items-center gap-1.5 bg-black border border-[#00FF66]/40 text-[#00FF66] px-2.5 py-1 text-xs font-bold uppercase" data-testid="live-game">
            <Gamepad2 size={12} /> {game}
          </div>
        )}

        <div className="flex items-center gap-2 ml-auto">
          <button onClick={copyUri} data-testid="live-copy-uri"
            className="inline-flex items-center gap-1.5 border border-[#2A2A35] px-3 py-2 text-xs hover:border-[#E5FF00] btn-ghost"
            title={t("live.copy_uri_hint", { defaultValue: "Copia il link monitor (per riavviare)" })}>
            <Copy size={13} /> {t("live.copy_uri", { defaultValue: "Copia link" })}
          </button>
          <button onClick={requestStop} disabled={stopping || stopPending} data-testid="live-stop-btn"
            className="inline-flex items-center gap-1.5 bg-[#FF3B30]/10 border border-[#FF3B30]/60 text-[#FF3B30] px-3 py-2 text-xs font-bold hover:bg-[#FF3B30]/20 disabled:opacity-60 transition-colors">
            {stopping || stopPending ? <Loader2 size={13} className="animate-spin" /> : <Square size={13} />}
            {stopPending ? t("live.stopping", { defaultValue: "In arresto…" }) : t("live.stop", { defaultValue: "Ferma" })}
          </button>
        </div>
      </div>
      {stopPending && (
        <div className="text-xs text-zinc-500 mt-3 border-t border-[#1A1A24] pt-3" data-testid="stop-pending-hint">
          {t("live.stop_pending_hint", { defaultValue: "Il monitor si chiuderà al prossimo tick (max ~2s). Se resta aperto, chiudi la finestra sul PC manualmente." })}
        </div>
      )}
    </div>
  );
}
