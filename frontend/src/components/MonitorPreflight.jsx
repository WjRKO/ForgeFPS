import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { PlayCircle, CheckCircle2, AlertTriangle, XCircle, Gamepad2, Bell, Loader2, Battery } from "lucide-react";
import api from "@/lib/api";

/**
 * Pre-flight checklist popover shown before launching the monitor.
 * Reads the last known snapshot from the backend (running_apps + alert settings)
 * and shows a set of go/no-go checks. The user can proceed anyway.
 */
export default function MonitorPreflight({ open, onClose, onConfirm, launching }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [checks, setChecks] = useState(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    (async () => {
      try {
        const [pre, al, guard] = await Promise.all([
          api.get("/prematch").catch(() => ({ data: {} })),
          api.get("/alerts").catch(() => ({ data: {} })),
          api.get("/benchmarks/guardrails").catch(() => ({ data: {} })),
        ]);
        const running = (pre.data?.running_apps || []).map((a) => String(a).toLowerCase());
        const gameKeys = ["fortnite", "valorant", "cs2", "csgo", "leagueoflegends", "riotclient", "apex", "warzone", "modernwarfare", "battlefield", "rocketleague", "overwatch", "genshin", "starfield", "cyberpunk", "eldenring", "minecraft", "roblox"];
        const heavyKeys = ["chrome", "msedge", "firefox", "brave", "discord", "slack", "teams", "telegram", "spotify"];
        const gameProc = running.find((a) => gameKeys.some((k) => a.includes(k)));
        const heavyProcs = running.filter((a) => heavyKeys.some((k) => a.includes(k)));
        const stale = pre.data?.running_at ? (Date.now() - new Date(pre.data.running_at).getTime()) / 1000 > 600 : true;

        setChecks([
          {
            key: "agent",
            status: "ok",
            label: t("live.pf_agent", { defaultValue: "Agent connesso" }),
            hint: t("live.pf_agent_ok", { defaultValue: "Token attivo, backend raggiungibile" }),
          },
          {
            key: "game",
            status: stale ? "unknown" : gameProc ? "ok" : "warn",
            label: t("live.pf_game", { defaultValue: "Gioco in esecuzione" }),
            hint: stale
              ? t("live.pf_game_stale", { defaultValue: "Nessun sync recente — lancia una sync per aggiornare la lista processi" })
              : gameProc
                ? `${t("live.pf_game_ok", { defaultValue: "Rilevato" })}: ${gameProc}`
                : t("live.pf_game_none", { defaultValue: "Nessun gioco rilevato. Avvialo prima del monitor per catturare gli FPS" }),
          },
          {
            key: "heavy",
            status: heavyProcs.length === 0 ? "ok" : heavyProcs.length <= 2 ? "warn" : "bad",
            label: t("live.pf_heavy", { defaultValue: "App in background" }),
            hint: heavyProcs.length === 0
              ? t("live.pf_heavy_ok", { defaultValue: "Ambiente pulito" })
              : t("live.pf_heavy_warn", { defaultValue: "Rilevate app che possono influenzare i risultati" }) + `: ${heavyProcs.slice(0, 4).join(", ")}${heavyProcs.length > 4 ? "…" : ""}`,
          },
          {
            key: "alerts",
            status: al.data?.enabled ? "ok" : "warn",
            label: t("live.pf_alerts", { defaultValue: "Alert push attivi" }),
            hint: al.data?.enabled
              ? `CPU ≥${al.data.cpu_max}°C · GPU ≥${al.data.gpu_max}°C`
              : t("live.pf_alerts_off", { defaultValue: "Push disattivate — non riceverai notifiche per temperature critiche" }),
          },
        ]);
      } catch (e) {
        console.error("preflight failed", e);
        setChecks([{ key: "err", status: "warn", label: "Preflight check", hint: String(e.message || e) }]);
      } finally {
        setLoading(false);
      }
    })();
  }, [open, t]);

  const canProceed = useMemo(() => !checks || checks.every((c) => c.status !== "bad"), [checks]);
  const hasWarning = useMemo(() => (checks || []).some((c) => c.status === "warn" || c.status === "bad"), [checks]);

  if (!open) return null;

  const STATUS_ICON = {
    ok: <CheckCircle2 size={16} className="text-[#00FF66] shrink-0" />,
    warn: <AlertTriangle size={16} className="text-[#E5FF00] shrink-0" />,
    bad: <XCircle size={16} className="text-[#FF3B30] shrink-0" />,
    unknown: <AlertTriangle size={16} className="text-zinc-500 shrink-0" />,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80" onClick={onClose} data-testid="monitor-preflight">
      <div className="bg-[#0F0F12] border border-[#2A2A35] max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">{t("live.pf_eyebrow", { defaultValue: "// pre-flight" })}</div>
            <h3 className="font-display font-black text-xl">{t("live.pf_title", { defaultValue: "Tutto pronto per il monitor?" })}</h3>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 text-xl leading-none px-2" data-testid="preflight-close">×</button>
        </div>

        {loading ? (
          <div className="py-10 flex items-center justify-center text-zinc-500 text-sm gap-2">
            <Loader2 size={16} className="animate-spin" /> {t("live.pf_loading", { defaultValue: "Controllo lo stato del sistema…" })}
          </div>
        ) : (
          <div className="space-y-2 mb-5" data-testid="preflight-checks">
            {(checks || []).map((c) => (
              <div key={c.key} className="flex items-start gap-3 bg-black border border-[#1A1A24] p-3" data-testid={`pf-check-${c.key}`}>
                {STATUS_ICON[c.status]}
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-zinc-200 font-semibold">{c.label}</div>
                  <div className="text-xs text-zinc-500 mt-0.5">{c.hint}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {hasWarning && !loading && (
          <div className="text-xs text-zinc-500 mb-4 border-l-2 border-[#E5FF00]/40 pl-3">
            {t("live.pf_warn_hint", { defaultValue: "Puoi comunque avviare il monitor — le note sopra sono solo un promemoria." })}
          </div>
        )}

        <div className="flex items-center gap-3 justify-end">
          <button onClick={onClose} disabled={launching}
            data-testid="preflight-cancel"
            className="text-xs text-zinc-500 hover:text-zinc-300 px-3 py-2">
            {t("common.cancel", { defaultValue: "Annulla" })}
          </button>
          <button onClick={onConfirm} disabled={loading || !canProceed || launching}
            data-testid="preflight-confirm"
            className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EE00] disabled:opacity-50 transition-colors">
            {launching ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
            {launching ? t("live.pf_launching", { defaultValue: "Apertura…" }) : t("live.pf_go", { defaultValue: "Ora avvia" })}
          </button>
        </div>
      </div>
    </div>
  );
}
