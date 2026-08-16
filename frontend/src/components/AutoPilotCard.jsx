import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Rocket, Loader2, Lock, ArrowRight, ChevronDown, ChevronUp, RotateCcw, Undo2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useSilentLaunch } from "@/hooks/useSilentLaunch";


export const AutoPilotCard = () => {
  const { t, i18n } = useTranslation();
  const c = t("autopilot", { returnObjects: true });
  const [status, setStatus] = useState(null);
  const [showReport, setShowReport] = useState(false);
  const startedAtRef = useRef(null);

  const load = () => api.get("/autopilot/status").then(({ data }) => setStatus(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const launcher = useSilentLaunch({
    mode: "autopilot",
    timeoutMs: 300000,
    labels: { starting: c.starting, running: c.running, done: c.done, failed: c.failed },
    detectDone: async () => {
      const { data } = await api.get("/autopilot/status");
      const l = data?.latest;
      return !!(l && l.status === "done" && l.completed_at && startedAtRef.current && l.completed_at > startedAtRef.current);
    },
    onDone: () => { load(); setShowReport(true); },
  });

  const restorer = useSilentLaunch({
    mode: "restore",
    timeoutMs: 120000,
    labels: { starting: c.restore_start, running: c.restoring, done: c.restored, failed: c.restore_failed },
    detectDone: async () => {
      const { data } = await api.get("/autopilot/status");
      return data?.latest?.status === "reverted";
    },
    onDone: () => load(),
  });

  const start = async () => {
    if (launcher.running) return;
    try {
      await api.post("/autopilot/start");
      startedAtRef.current = new Date().toISOString();
      launcher.launch();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
      load();
    }
  };

  const latest = ["done", "reverted"].includes(status?.latest?.status) ? status.latest : null;
  const locked = !!(status && status.limit != null && status.remaining <= 0 && !launcher.running);

  return (
    <div className="border border-[#E5FF00]/30 bg-gradient-to-br from-[#E5FF00]/[0.06] to-transparent hud-tick p-5" data-testid="autopilot-card">
      <div className="flex flex-wrap items-center gap-4">
        <div className="w-11 h-11 flex items-center justify-center border border-[#E5FF00]/50 text-[#E5FF00] shrink-0">
          {launcher.running ? <Loader2 size={18} className="animate-spin" /> : <Rocket size={18} />}
        </div>
        <div className="flex-1 min-w-[220px]">
          <div className="flex items-center gap-2">
            <span className="text-sm font-black uppercase tracking-widest">{c.title}</span>
            <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 border border-[#2A2A35] px-1.5 py-0.5" data-testid="autopilot-quota">
              {status?.limit == null ? c.quota_pro : `${c.quota_free} · ${status.remaining}/${status.limit}`}
            </span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">{c.desc}</p>
        </div>
        {locked ? (
          <div className="flex items-center gap-2" data-testid="autopilot-locked">
            <span className="flex items-center gap-1.5 text-[11px] text-zinc-500"><Lock size={12} /> {c.locked}</span>
            <Link to="/pricing" data-testid="autopilot-upgrade-link"
              className="text-[10px] font-bold uppercase tracking-widest border border-[#E5FF00]/40 text-[#E5FF00] px-3 py-2 hover:bg-[#E5FF00]/10 transition-colors">
              {c.upgrade}
            </Link>
          </div>
        ) : (
          <button onClick={start} disabled={launcher.running} data-testid="autopilot-start-btn"
            className="flex items-center gap-2 text-xs font-black uppercase tracking-widest bg-[#E5FF00] text-black px-5 py-2.5 hover:bg-[#F0FF4D] transition-colors disabled:opacity-50">
            {launcher.running ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />} {c.btn}
          </button>
        )}
      </div>

      {latest && (
        <div className="mt-4 border-t border-[#2A2A35] pt-3">
          <button onClick={() => setShowReport((s) => !s)} data-testid="autopilot-report-toggle"
            className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-zinc-500 hover:text-zinc-300 transition-colors">
            {c.report} · {new Date(latest.completed_at).toLocaleString()} {showReport ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </button>
          {latest.status === "reverted" && (
            <span className="ml-3 inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest text-zinc-400 border border-[#2A2A35] px-1.5 py-0.5" data-testid="autopilot-reverted-badge">
              <Undo2 size={9} /> {c.reverted_badge}
            </span>
          )}
          {showReport && (
            <div className="mt-3 flex flex-wrap gap-6 text-sm" data-testid="autopilot-report">
              <div>
                <div className="text-2xl font-black text-[#E5FF00]">{(latest.applied || []).length}</div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{c.applied}</div>
              </div>
              {latest.before?.score != null && latest.after?.score != null && (
                <div>
                  <div className="text-2xl font-black flex items-center gap-2">
                    <span className="text-zinc-500">{latest.before.score}</span>
                    <ArrowRight size={14} className="text-zinc-600" />
                    <span className={latest.delta_score >= 0 ? "text-[#00FF66]" : "text-[#FF9F1C]"}>{latest.after.score}</span>
                    {latest.delta_score != null && latest.delta_score !== 0 && (
                      <span className={`text-xs font-mono ${latest.delta_score > 0 ? "text-[#00FF66]" : "text-[#FF9F1C]"}`}>
                        {latest.delta_score > 0 ? "+" : ""}{latest.delta_score}
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{c.health}</div>
                </div>
              )}
              {(latest.applied || []).length === 0 && (
                <p className="text-xs text-zinc-500 self-center">{c.none_needed}</p>
              )}
              {(latest.applied || []).length > 0 && (
                <div className="flex-1 min-w-[200px] flex flex-wrap gap-1 items-center">
                  {latest.applied.slice(0, 10).map((id) => (
                    <span key={id} className="text-[9px] font-mono border border-[#2A2A35] text-zinc-500 px-1.5 py-0.5">{id}</span>
                  ))}
                  {latest.applied.length > 10 && <span className="text-[9px] text-zinc-600">+{latest.applied.length - 10}</span>}
                </div>
              )}
              {latest.status === "done" && (latest.applied || []).length > 0 && (
                <button onClick={() => restorer.launch()} disabled={restorer.running || launcher.running}
                  data-testid="autopilot-restore-btn"
                  className="self-center flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest border border-[#2A2A35] text-zinc-400 px-3 py-2 hover:border-[#FF9F1C] hover:text-[#FF9F1C] transition-colors disabled:opacity-50">
                  {restorer.running ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />} {c.restore_btn}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
