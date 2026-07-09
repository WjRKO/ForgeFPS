import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toPng } from "html-to-image";
import { toast } from "sonner";
import { Share2, RotateCcw, Zap, Gamepad2, Thermometer, Cpu, Gauge, Clock, Loader2, Timer } from "lucide-react";

const fmtDuration = (sec) => {
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${r}s` : `${r}s`;
};

function Metric({ icon: Icon, label, value, unit, accent, big, testid }) {
  return (
    <div className="bg-black/60 border border-[#1A1A24] px-4 py-3" data-testid={testid}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-zinc-500 mb-1">
        <Icon size={12} className={accent} /> {label}
      </div>
      <div className={`font-display font-black ${big ? "text-4xl" : "text-2xl"} leading-none`}>
        {value ?? "--"}<span className="text-sm text-zinc-500 ml-1">{value != null ? unit : ""}</span>
      </div>
    </div>
  );
}

export const SessionSummary = ({ summary, onReset }) => {
  const { t } = useTranslation();
  const cardRef = useRef(null);
  const [busy, setBusy] = useState(false);

  const share = async () => {
    if (!cardRef.current) return;
    setBusy(true);
    try {
      const dataUrl = await toPng(cardRef.current, { pixelRatio: 2, backgroundColor: "#0A0A0C", cacheBust: true });
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], "boostpc-session.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "BoostPC", text: t("live.session_share_text") });
        toast.success(t("live.session_shared"));
      } else {
        const a = document.createElement("a");
        a.href = dataUrl; a.download = "boostpc-session.png"; a.click();
        toast.success(t("live.session_shared"));
      }
    } catch {
      toast.error(t("live.save_err"));
    } finally {
      setBusy(false);
    }
  };

  const game = summary.game || t("live.session_no_game");
  const now = new Date();

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 mb-6" data-testid="session-summary">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-zinc-500">
          <Zap size={14} className="text-[#E5FF00]" /> {t("live.session_title")}
        </div>
        <div className="flex items-center gap-2">
          <button data-testid="session-reset-btn" onClick={onReset}
            className="flex items-center gap-1.5 border border-[#2A2A35] px-3 py-1.5 text-xs hover:border-[#E5FF00] transition-colors">
            <RotateCcw size={13} /> {t("live.session_reset")}
          </button>
          <button data-testid="session-share-btn" onClick={share} disabled={busy}
            className="flex items-center gap-1.5 bg-[#E5FF00] text-black font-bold px-3 py-1.5 text-xs hover:bg-[#c9e000] transition-colors disabled:opacity-60">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Share2 size={13} />} {t("live.session_share")}
          </button>
        </div>
      </div>

      {/* Shareable card (exported to PNG) */}
      <div ref={cardRef} className="relative overflow-hidden bg-[#0A0A0C] border border-[#2A2A35] p-6" data-testid="session-card"
        style={{ backgroundImage: "radial-gradient(circle at 15% 0%, rgba(229,255,0,0.10), transparent 45%), radial-gradient(circle at 100% 100%, rgba(0,224,255,0.08), transparent 40%)" }}>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-[#E5FF00] flex items-center justify-center"><Zap size={16} className="text-black" fill="black" /></div>
            <span className="font-display font-black text-lg tracking-tight">BOOST<span className="text-[#E5FF00]">PC</span></span>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-[0.25em] text-[#E5FF00]">{t("live.session_recap")}</div>
            <div className="text-[10px] text-zinc-500">{now.toLocaleDateString()} · {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
          </div>
        </div>

        <div className="flex items-center gap-2 mb-4">
          <Gamepad2 size={16} className="text-[#00FF66]" />
          <span className="font-display font-black text-2xl tracking-tight truncate">{game}</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
          <Metric icon={Zap} label={t("live.session_fps_avg")} value={summary.fpsAvg} unit="FPS" accent="text-[#00FF66]" big testid="sc-fps-avg" />
          <Metric icon={Gauge} label={t("live.session_fps_low")} value={summary.fps1low} unit="FPS" accent="text-[#00E0FF]" testid="sc-fps-low" />
          <Metric icon={Gauge} label={t("live.session_fps_min")} value={summary.fpsMin} unit="FPS" accent="text-[#FF6B00]" testid="sc-fps-min" />
          <Metric icon={Gauge} label={t("live.session_fps_max")} value={summary.fpsMax} unit="FPS" accent="text-[#E5FF00]" testid="sc-fps-max" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <Metric icon={Thermometer} label={t("live.cpu_temp_max")} value={summary.cpuTempMax || null} unit="°C" accent="text-[#FF6B00]" testid="sc-cpu-temp" />
          <Metric icon={Thermometer} label={t("live.gpu_temp_max")} value={summary.gpuTempMax || null} unit="°C" accent="text-[#FF3B30]" testid="sc-gpu-temp" />
          <Metric icon={Cpu} label={t("live.cpu_avg")} value={summary.cpuUtilAvg} unit="%" accent="text-[#E5FF00]" testid="sc-cpu-avg" />
          <Metric icon={Clock} label={t("live.session_duration")} value={fmtDuration(summary.durationSec)} unit="" accent="text-[#B388FF]" testid="sc-duration" />
        </div>
        {summary.latAvg != null && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
            <Metric icon={Timer} label={t("live.session_lat_avg")} value={summary.latAvg} unit="ms" accent="text-[#00E0FF]" testid="sc-lat-avg" />
            <Metric icon={Timer} label={t("live.session_lat_max")} value={summary.latMax} unit="ms" accent="text-[#FF6B00]" testid="sc-lat-max" />
          </div>
        )}

        <div className="mt-5 pt-3 border-t border-[#1A1A24] flex items-center justify-between text-[10px] text-zinc-600">
          <span>boostpc · AI performance for gamers & streamers</span>
          <span>{summary.samples} {t("live.session_samples")}</span>
        </div>
      </div>
    </div>
  );
};
