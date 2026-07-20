import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Cpu, Gauge, Thermometer, MemoryStick, Zap, Radio, Gamepad2, Bell, Timer, Sparkles } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { toast } from "sonner";
import api from "@/lib/api";
import { SessionSummary } from "./SessionSummary";
import { SecureRunBlock } from "@/components/SecureRunBlock";

const freshAcc = () => ({ startTs: null, lastTs: null, fps: [], cpuTempMax: 0, gpuTempMax: 0, cpuSum: 0, cpuN: 0, gpuSum: 0, gpuN: 0, latSum: 0, latN: 0, latMax: 0, games: {}, samples: 0 });

const buildSummary = (a) => {
  if (a.samples === 0) return null;
  const dur = a.startTs && a.lastTs ? (new Date(a.lastTs) - new Date(a.startTs)) / 1000 : 0;
  let game = null, best = 0;
  for (const [g, n] of Object.entries(a.games)) { if (n > best) { best = n; game = g; } }
  const fps = [...a.fps].sort((x, y) => x - y);
  const pct = (p) => (fps.length ? fps[Math.min(fps.length - 1, Math.floor(p * fps.length))] : null);
  const avg = fps.length ? Math.round(fps.reduce((s, v) => s + v, 0) / fps.length) : null;
  return {
    durationSec: dur, game, samples: a.samples,
    fpsAvg: avg, fpsMin: fps.length ? fps[0] : null, fpsMax: fps.length ? fps[fps.length - 1] : null,
    fps1low: pct(0.01),
    cpuTempMax: a.cpuTempMax, gpuTempMax: a.gpuTempMax,
    cpuUtilAvg: a.cpuN ? Math.round(a.cpuSum / a.cpuN) : null,
    gpuUtilAvg: a.gpuN ? Math.round(a.gpuSum / a.gpuN) : null,
    latAvg: a.latN ? Math.round(a.latSum / a.latN) : null,
    latMax: a.latMax || null,
  };
};

function Stat({ icon: Icon, label, value, unit, accent, testid }) {
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-4" data-testid={testid}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-zinc-500 mb-2"><Icon size={14} className={accent} /> {label}</div>
      <div className="font-display font-black text-3xl tabular-nums">{value ?? "--"}<span className="text-base text-zinc-500 ml-1">{value != null ? unit : ""}</span></div>
    </div>
  );
}

function MetricGroup({ title, children }) {
  return (
    <div className="mb-6">
      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-600 font-bold mb-2">{title}</div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{children}</div>
    </div>
  );
}

export default function Live() {
  const { t } = useTranslation();
  const [data, setData] = useState({ samples: [], live: false });
  const [token, setToken] = useState("");
  const [alerts, setAlerts] = useState({ enabled: true, cpu_max: 90, gpu_max: 85 });
  const [summary, setSummary] = useState(null);
  const acc = useRef(freshAcc());
  const seenRef = useRef(new Set());
  const timer = useRef(null);

  useEffect(() => {
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch((e) => console.error("load agent token failed", e));
    api.get("/alerts").then(({ data }) => setAlerts(data)).catch((e) => console.error("load alerts failed", e));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount; setters are stable
  }, []);
  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await api.get("/pc-telemetry");
        setData(data);
        for (const s of (data.samples || [])) {
          if (!s.ts || seenRef.current.has(s.ts)) continue;
          seenRef.current.add(s.ts);
          // New session if a gap > 30s between samples (agent restarted / older data).
          if (acc.current.lastTs && (new Date(s.ts) - new Date(acc.current.lastTs)) > 30000) acc.current = freshAcc();
          const b = acc.current;
          if (!b.startTs) b.startTs = s.ts;
          b.lastTs = s.ts;
          b.samples++;
          if (s.cpu_util != null) { b.cpuSum += s.cpu_util; b.cpuN++; }
          if (s.gpu_util != null) { b.gpuSum += s.gpu_util; b.gpuN++; }
          if (s.cpu_temp != null && s.cpu_temp > b.cpuTempMax) b.cpuTempMax = s.cpu_temp;
          if (s.gpu_temp != null && s.gpu_temp > b.gpuTempMax) b.gpuTempMax = s.gpu_temp;
          if (s.fps != null && s.fps > 0) { b.fps.push(s.fps); if (s.game) b.games[s.game] = (b.games[s.game] || 0) + 1; }
          if (s.latency_ms != null && s.latency_ms > 0) { b.latSum += s.latency_ms; b.latN++; if (s.latency_ms > b.latMax) b.latMax = s.latency_ms; }
        }
        setSummary(buildSummary(acc.current));
      } catch (e) { console.error("telemetry poll failed", e); }
    };
    load();
    timer.current = setInterval(load, 1000);
    return () => clearInterval(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- polling loop uses refs (stable) and module-level api; deps intentionally empty
  }, []);

  const resetSession = () => { acc.current = freshAcc(); setSummary(null); toast.success(t("live.session_reset_done")); };

  const saveAlerts = async () => {
    try { await api.put("/alerts", alerts); toast.success(t("live.alerts_saved")); } catch { toast.error(t("live.save_err")); }
  };

  const last = data.samples[data.samples.length - 1] || {};
  const chart = data.samples.map((s, i) => ({
    i, cpu: s.cpu_util ?? null, gpu: s.gpu_util ?? null, cpuT: s.cpu_temp ?? null, gpuT: s.gpu_temp ?? null, fps: s.fps ?? null,
  }));

  return (
    <div className="max-w-5xl mx-auto fade-up" data-testid="live-page">
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("live.eyebrow")}</div>
          <h1 className="font-display font-black text-3xl tracking-tighter">{t("live.title")}</h1>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 border text-xs font-bold ${data.live ? "border-[#00FF66]/50 text-[#00FF66]" : "border-[#2A2A35] text-zinc-500"}`} data-testid="live-status">
          <Radio size={14} className={data.live ? "animate-pulse" : ""} /> {data.live ? t("live.live") : t("live.agent_off")}
        </div>
      </div>

      {!data.live && (
        <div className="bg-[#0F0F12] border border-[#E5FF00]/40 p-5 mb-6">
          <p className="text-sm text-zinc-300 mb-1 font-semibold">{t("live.start_title")}</p>
          <p className="text-xs text-zinc-500 mb-3">{t("live.start_desc")}</p>
          <SecureRunBlock token={token} mode="monitor" testid="monitor-run-cmd" />
        </div>
      )}

      <MetricGroup title={t("live.grp_perf")}>
        <Stat icon={Gamepad2} label={last.game ? `FPS · ${last.game}` : "FPS"} value={last.fps} unit="" accent="text-[#00FF66]" testid="stat-fps" />
        <Stat icon={Cpu} label="CPU" value={last.cpu_util} unit="%" accent="text-[#E5FF00]" testid="stat-cpu" />
        <Stat icon={Gauge} label="GPU" value={last.gpu_util} unit="%" accent="text-[#00E0FF]" testid="stat-gpu" />
        <Stat icon={Zap} label={t("live.st_gpu_power")} value={last.gpu_power} unit="W" accent="text-[#E5FF00]" testid="stat-gpu-power" />
      </MetricGroup>

      <MetricGroup title={t("live.grp_temp")}>
        <Stat icon={Thermometer} label={t("live.st_cpu_temp")} value={last.cpu_temp} unit="°C" accent="text-[#FF6B00]" testid="stat-cpu-temp" />
        <Stat icon={Thermometer} label={t("live.st_gpu_temp")} value={last.gpu_temp} unit="°C" accent="text-[#FF3B30]" testid="stat-gpu-temp" />
      </MetricGroup>

      <MetricGroup title={t("live.grp_mem")}>
        <Stat icon={MemoryStick} label={t("live.st_ram")} value={last.ram_used_pct} unit="%" accent="text-[#00FF66]" testid="stat-ram" />
        <Stat icon={MemoryStick} label={t("live.st_vram")} value={last.vram_used_pct} unit="%" accent="text-[#B388FF]" testid="stat-vram" />
        <Stat icon={Timer} label={t("live.st_latency")} value={last.latency_ms} unit="ms" accent="text-[#00E0FF]" testid="stat-latency" />
      </MetricGroup>

      {summary && <SessionSummary summary={summary} onReset={resetSession} />}

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 mb-6" data-testid="reflex-card">
        <div className="flex items-center gap-2 text-sm font-bold mb-1"><Sparkles size={16} className="text-[#00E0FF]" /> {t("live.reflex_title")}</div>
        <p className="text-xs text-zinc-400 mb-3">{t("live.reflex_desc")}</p>
        <ul className="space-y-1.5 text-sm text-zinc-300">
          {["reflex_t1", "reflex_t2", "reflex_t3", "reflex_t4"].map((k) => (
            <li key={k} className="flex items-start gap-2" data-testid={`reflex-${k}`}><span className="text-[#00E0FF] mt-0.5">→</span> {t(`live.${k}`)}</li>
          ))}
        </ul>
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 mb-6" data-testid="alert-settings">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4"><Bell size={14} className="text-[#FF3B30]" /> {t("live.alert_title")}</div>
        <div className="flex flex-wrap items-end gap-5">
          <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer" data-testid="alert-enabled">
            <input type="checkbox" checked={alerts.enabled} onChange={(e) => setAlerts({ ...alerts, enabled: e.target.checked })} className="accent-[#E5FF00] w-4 h-4" />
            {t("live.push_active")}
          </label>
          <div>
            <div className="text-xs text-zinc-500 mb-1">{t("live.cpu_threshold")}</div>
            <input type="number" data-testid="alert-cpu-max" value={alerts.cpu_max} onChange={(e) => setAlerts({ ...alerts, cpu_max: parseInt(e.target.value) || 0 })}
              className="w-24 bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none" />
          </div>
          <div>
            <div className="text-xs text-zinc-500 mb-1">{t("live.gpu_threshold")}</div>
            <input type="number" data-testid="alert-gpu-max" value={alerts.gpu_max} onChange={(e) => setAlerts({ ...alerts, gpu_max: parseInt(e.target.value) || 0 })}
              className="w-24 bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none" />
          </div>
          <button data-testid="save-alerts-btn" onClick={saveAlerts} className="bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#c9e000] transition-colors">{t("common.save")}</button>
        </div>
        <p className="text-xs text-zinc-600 mt-3">{t("live.alert_hint")}</p>
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4">{t("live.chart_title")}</div>
        {chart.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-zinc-600 text-sm">{t("live.waiting")}</div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chart}>
              <CartesianGrid stroke="#1A1A24" strokeDasharray="3 3" />
              <XAxis dataKey="i" tick={{ fill: "#52525b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#52525b", fontSize: 10 }} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: "#0A0A0C", border: "1px solid #2A2A35", fontSize: 12 }} />
              <Line type="monotone" dataKey="cpu" name="CPU %" stroke="#E5FF00" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="monotone" dataKey="gpu" name="GPU %" stroke="#00E0FF" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="monotone" dataKey="fps" name="FPS" stroke="#00FF66" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="monotone" dataKey="cpuT" name="CPU °C" stroke="#FF6B00" dot={false} strokeWidth={1.5} isAnimationActive={false} />
              <Line type="monotone" dataKey="gpuT" name="GPU °C" stroke="#FF3B30" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
