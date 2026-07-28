import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Cpu, Gauge, MemoryStick, Zap, Radio, Bell, Sparkles, PlayCircle, Activity, BellRing, LineChart as LineChartIcon, ChevronDown, Fan, Thermometer, Wind } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { toast } from "sonner";
import api from "@/lib/api";
import { SessionSummary } from "@/components/SessionSummary";
import { SecureRunBlock } from "@/components/SecureRunBlock";
import { PrimaryButton } from "@/components/hud";
import ObsOverlayPanel from "@/components/ObsOverlayPanel";
import CurrentGameCard from "@/components/CurrentGameCard";
import BrowserPopupHint from "@/components/BrowserPopupHint";
import MonitorPreflight from "@/components/MonitorPreflight";
import GameplayDoctor from "@/components/GameplayDoctor";
import MonitorLiveControl from "@/components/MonitorLiveControl";
import BottleneckDetector from "@/components/BottleneckDetector";
import PlanUpgradeBanner from "@/components/PlanUpgradeBanner";

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

const tempClass = (v) => (v == null ? "text-zinc-500" : v >= 85 ? "text-[#FF3B30]" : v >= 75 ? "text-[#FF6B00]" : "text-zinc-100");

const seriesStats = (arr) => {
  const v = arr.filter((x) => x != null && !Number.isNaN(x));
  if (!v.length) return null;
  return { min: Math.min(...v), max: Math.max(...v), avg: Math.round(v.reduce((s, x) => s + x, 0) / v.length) };
};

/* --- Bento metric card: big main readout + secondary rows --- */
function BentoCard({ icon: Icon, label, main, mainUnit, mainClass = "", rows = [], testid }) {
  const ghost = main == null;
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] p-4 h-full flex flex-col rounded-none" data-testid={testid}>
      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-2">
        <Icon size={13} /> {label}
      </div>
      <div className={`font-mono tabular-nums font-black text-4xl lg:text-5xl leading-none ${ghost ? "text-zinc-800" : mainClass || "text-zinc-100"}`}>
        {main ?? "--"}
        <span className={`text-sm ml-1 font-normal ${ghost ? "text-zinc-800" : "text-zinc-500"}`}>{main != null ? mainUnit : ""}</span>
      </div>
      {rows.length > 0 && (
        <div className="mt-3 pt-2 border-t border-[#1A1A24] space-y-1">
          {rows.map((r) => (
            <div key={r.label} className="flex items-baseline justify-between text-xs" data-testid={r.testid}>
              <span className="text-zinc-600 uppercase tracking-wider text-[10px]">{r.label}</span>
              <span className={`font-mono tabular-nums ${r.value == null ? "text-zinc-800" : r.cls || "text-zinc-300"}`}>
                {r.value ?? "--"}<span className="text-zinc-600 ml-0.5">{r.value != null ? r.unit : ""}</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* --- v0.7.7: compact precision sensor cell (fan / VRM / CPU power / Vcore) --- */
function PrecisionCell({ icon: Icon, label, value, unit, cls, testid }) {
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] p-3 rounded-none flex items-center gap-3" data-testid={testid}>
      <Icon size={16} className="text-zinc-600 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{label}</div>
        <div className={`font-mono tabular-nums text-base font-black leading-tight ${value == null ? "text-zinc-800" : cls || "text-zinc-100"}`}>
          {value ?? "--"}<span className="text-xs ml-1 font-normal text-zinc-500">{value != null ? unit : ""}</span>
        </div>
      </div>
    </div>
  );
}

/* --- Tabbed telemetry charts (perf / thermals / utilization) --- */
function TelemetryCharts({ chart, waitingText, t }) {
  const [tab, setTab] = useState("perf");
  const TABS = [
    { id: "perf", label: t("live.tab_perf") },
    { id: "therm", label: t("live.tab_therm") },
    { id: "util", label: t("live.tab_util") },
  ];
  const LINES = {
    perf: [
      { k: "fps", name: "FPS", color: "#00FF66", axis: "left", w: 2 },
      { k: "lat", name: "ms", color: "#00E0FF", axis: "right", w: 1.5 },
    ],
    therm: [
      { k: "cpuT", name: "CPU °C", color: "#FF6B00", axis: "left", w: 2 },
      { k: "gpuT", name: "GPU °C", color: "#FF3B30", axis: "left", w: 2 },
    ],
    util: [
      { k: "cpu", name: "CPU %", color: "#E5FF00", axis: "left", w: 2 },
      { k: "gpu", name: "GPU %", color: "#00E0FF", axis: "left", w: 2 },
    ],
  };
  const lines = LINES[tab];
  const fixedDomain = tab !== "perf";
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] rounded-none h-full flex flex-col" data-testid="telemetry-charts">
      <div className="flex border-b border-[#1A1A24]">
        {TABS.map((tb) => (
          <button key={tb.id} onClick={() => setTab(tb.id)} data-testid={`chart-tab-${tb.id}`}
            className={`px-4 py-3 text-[11px] font-bold uppercase tracking-widest transition-colors ${tab === tb.id ? "text-[#E5FF00] border-b-2 border-[#E5FF00] -mb-px bg-black/30" : "text-zinc-500 hover:text-zinc-300"}`}>
            {tb.label}
          </button>
        ))}
      </div>
      <div className="p-4 flex-1">
        {chart.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-zinc-600 text-sm font-mono">{waitingText}</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chart}>
              <CartesianGrid stroke="#1A1A24" strokeDasharray="3 3" />
              <XAxis dataKey="i" tick={{ fill: "#52525b", fontSize: 10 }} />
              <YAxis yAxisId="left" tick={{ fill: "#52525b", fontSize: 10 }} domain={fixedDomain ? [0, tab === "therm" ? 110 : 100] : ["auto", "auto"]} />
              {tab === "perf" && <YAxis yAxisId="right" orientation="right" tick={{ fill: "#52525b", fontSize: 10 }} domain={["auto", "auto"]} />}
              <Tooltip contentStyle={{ background: "#0A0A0C", border: "1px solid #2A2A35", fontSize: 12 }} />
              {lines.map((l) => (
                <Line key={l.k} yAxisId={l.axis} type="monotone" dataKey={l.k} name={l.name} stroke={l.color} dot={false} strokeWidth={l.w} isAnimationActive={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      {chart.length > 0 && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 px-4 pb-3 pt-1 border-t border-[#1A1A24] text-[11px] font-mono text-zinc-500" data-testid="chart-stats-row">
          {lines.map((l) => {
            const st = seriesStats(chart.map((c) => c[l.k]));
            if (!st) return null;
            return (
              <span key={l.k} data-testid={`chart-stat-${l.k}`}>
                <span style={{ color: l.color }} className="font-bold">{l.name}</span>
                {" "}{t("live.min")} <span className="text-zinc-200">{st.min}</span>
                {" · "}{t("live.avg")} <span className="text-zinc-200">{st.avg}</span>
                {" · "}{t("live.max")} <span className="text-zinc-200">{st.max}</span>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* --- Compact thermal alert settings (sidebar) --- */
function AlertSettings({ alerts, setAlerts, onSave, t }) {
  return (
    <div className="bg-[#0F0F12] border border-[#1A1A24] p-4 rounded-none" data-testid="alert-settings">
      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-3">
        <Bell size={13} className="text-[#FF3B30]" /> {t("live.alert_title")}
      </div>
      <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer mb-3" data-testid="alert-enabled">
        <input type="checkbox" checked={alerts.enabled} onChange={(e) => setAlerts({ ...alerts, enabled: e.target.checked })} className="accent-[#E5FF00] w-4 h-4" />
        {t("live.push_active")}
      </label>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-zinc-600 mb-1">{t("live.cpu_threshold")}</div>
          <input type="number" data-testid="alert-cpu-max" value={alerts.cpu_max} onChange={(e) => setAlerts({ ...alerts, cpu_max: parseInt(e.target.value) || 0 })}
            className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm font-mono focus:border-[#E5FF00] outline-none rounded-none" />
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-zinc-600 mb-1">{t("live.gpu_threshold")}</div>
          <input type="number" data-testid="alert-gpu-max" value={alerts.gpu_max} onChange={(e) => setAlerts({ ...alerts, gpu_max: parseInt(e.target.value) || 0 })}
            className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm font-mono focus:border-[#E5FF00] outline-none rounded-none" />
        </div>
      </div>
      <button data-testid="save-alerts-btn" onClick={onSave}
        className="w-full border border-[#E5FF00]/60 text-[#E5FF00] py-2 text-xs font-bold uppercase tracking-widest hover:bg-[#E5FF00] hover:text-black transition-colors rounded-none">
        {t("common.save")}
      </button>
      <p className="text-[11px] text-zinc-600 mt-3 leading-relaxed">{t("live.alert_hint")}</p>
    </div>
  );
}

export default function Live() {
  const { t } = useTranslation();
  const [data, setData] = useState({ samples: [], live: false });
  const [token, setToken] = useState("");
  const [alerts, setAlerts] = useState({ enabled: true, cpu_max: 90, gpu_max: 85 });
  const [summary, setSummary] = useState(null);
  const [preflightOpen, setPreflightOpen] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [planInfo, setPlanInfo] = useState(null); // null=loading
  const acc = useRef(freshAcc());
  const seenRef = useRef(new Set());
  const timer = useRef(null);

  useEffect(() => {
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch((e) => console.error("load agent token failed", e));
    api.get("/alerts").then(({ data }) => setAlerts(data)).catch((e) => console.error("load alerts failed", e));
    api.get("/subscriptions/status").then(({ data }) => setPlanInfo(data)).catch(() => setPlanInfo({ is_pro: false, plan_effective: "starter" }));
  }, []);
  useEffect(() => {
    if (planInfo && !planInfo.is_pro) return; // skip telemetry poll if gated
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
  }, [planInfo]);

  const resetSession = () => { acc.current = freshAcc(); setSummary(null); toast.success(t("live.session_reset_done")); };

  const saveAlerts = async () => {
    try { await api.put("/alerts", alerts); toast.success(t("live.alerts_saved")); } catch { toast.error(t("live.save_err")); }
  };

  const last = data.samples[data.samples.length - 1] || {};
  const chart = useMemo(() => data.samples.map((s, i) => ({
    i, cpu: s.cpu_util ?? null, gpu: s.gpu_util ?? null, cpuT: s.cpu_temp ?? null, gpuT: s.gpu_temp ?? null, fps: s.fps ?? null, lat: s.latency_ms ?? null,
  })), [data.samples]);

  const fpsClass = last.fps != null && last.fps > 144 ? "text-[#E5FF00]" : "text-zinc-100";

  return (
    <div className="max-w-7xl mx-auto fade-up" data-testid="live-page">
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("live.eyebrow")}</div>
          <h1 className="font-display font-black text-3xl tracking-tighter uppercase">{t("live.title")}</h1>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 border text-xs font-bold font-mono uppercase tracking-widest ${data.live ? "border-[#00FF66]/50 text-[#00FF66]" : "border-[#2A2A35] text-zinc-500"}`} data-testid="live-status">
          <Radio size={14} className={data.live ? "animate-pulse" : ""} /> {data.live ? t("live.link_active") : t("live.agent_off")}
        </div>
      </div>

      {planInfo && !planInfo.is_pro ? (
        <PlanUpgradeBanner
          tier="pro"
          title={t("plan_banner.live.title")}
          description={t("plan_banner.live.desc")}
          features={[
            { icon: Activity, title: t("plan_banner.live.f1_t"), desc: t("plan_banner.live.f1_d") },
            { icon: LineChartIcon, title: t("plan_banner.live.f2_t"), desc: t("plan_banner.live.f2_d") },
            { icon: BellRing, title: t("plan_banner.live.f3_t"), desc: t("plan_banner.live.f3_d") },
            { icon: Sparkles, title: t("plan_banner.live.f4_t"), desc: t("plan_banner.live.f4_d") },
          ]}
          currentPlan={planInfo.plan_effective || "starter"}
          testid="live-locked"
        />
      ) : (
        <>
      {/* ===== TOP BAR: live control OR offline launch hero ===== */}
      {data.live ? (
        <MonitorLiveControl
          startedAt={acc.current.startTs}
          sampleCount={acc.current.samples}
          game={last.game}
        />
      ) : (
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-8 mb-4 text-center rounded-none" data-testid="live-offline-hero">
          <div className="font-mono text-[11px] uppercase tracking-[0.3em] text-zinc-600 mb-3">// {t("live.agent_off")}</div>
          <div className="font-display font-black text-2xl uppercase tracking-tight mb-1">{t("live.start_title")}</div>
          <p className="text-sm text-zinc-500 mb-6 max-w-xl mx-auto">{t("live.start_desc")}</p>
          <div className="flex flex-col items-center gap-3">
            <PrimaryButton
              icon={PlayCircle}
              type="button"
              testid="monitor-launch-btn"
              onClick={() => setPreflightOpen(true)}>
              {t("live.launch_btn", { defaultValue: "Avvia monitor sul PC" })}
            </PrimaryButton>
            <BrowserPopupHint testid="live-popup-hint" />
            <details className="text-xs text-zinc-500 w-full max-w-2xl text-left">
              <summary className="cursor-pointer hover:text-zinc-300 transition-colors text-center">
                {t("live.manual_cmd", { defaultValue: "Preferisci copiare il comando manualmente?" })}
              </summary>
              <div className="mt-3">
                <SecureRunBlock token={token} mode="monitor" testid="monitor-run-cmd" />
              </div>
            </details>
          </div>
        </div>
      )}

      <MonitorPreflight
        open={preflightOpen}
        launching={launching}
        onClose={() => { if (!launching) setPreflightOpen(false); }}
        onConfirm={async () => {
          setLaunching(true);
          try {
            // Clear any stale stop flag from a previous session so the new
            // monitor doesn't exit on its first tick.
            await api.post("/monitor/reset").catch(() => {});
            const { data: u } = await api.get("/agent/launch-uri?mode=monitor");
            if (!u?.uri) throw new Error("no uri");
            window.location.href = u.uri;
            toast(t("live.launching", { defaultValue: "Apertura del monitor sul PC..." }));
            setPreflightOpen(false);
          } catch (e) {
            console.error("monitor launch failed", e);
            toast.error(t("live.launch_failed", { defaultValue: "Impossibile aprire. Hai installato FrameForge?" }));
          } finally {
            setLaunching(false);
          }
        }}
      />

      {/* ===== v0.7.7: UNIVERSAL GAME DETECTOR CARD ===== */}
      <CurrentGameCard
        appid={last.steam_appid}
        gameName={last.game_name || last.game}
        source={last.game_source}
        exe={last.game_exe}
        fullscreen={last.game_fullscreen}
      />

      {/* ===== 4 BENTO METRIC CARDS ===== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <BentoCard icon={Zap} label={last.game ? `${t("live.card_perf")} · ${last.game}` : t("live.card_perf")}
          main={last.fps} mainUnit="FPS" mainClass={fpsClass} testid="stat-fps"
          rows={[{ label: t("live.st_latency"), value: last.latency_ms, unit: "ms", cls: "text-[#00E0FF]", testid: "stat-latency" }]} />
        <BentoCard icon={Cpu} label={t("live.card_cpu")}
          main={last.cpu_util} mainUnit="%" testid="stat-cpu"
          rows={[{ label: t("live.st_cpu_temp"), value: last.cpu_temp, unit: "°C", cls: tempClass(last.cpu_temp), testid: "stat-cpu-temp" }]} />
        <BentoCard icon={Gauge} label={t("live.card_gpu")}
          main={last.gpu_util} mainUnit="%" testid="stat-gpu"
          rows={[
            { label: t("live.st_gpu_temp"), value: last.gpu_temp, unit: "°C", cls: tempClass(last.gpu_temp), testid: "stat-gpu-temp" },
            { label: t("live.st_gpu_power"), value: last.gpu_power, unit: "W", cls: "text-zinc-300", testid: "stat-gpu-power" },
          ]} />
        <BentoCard icon={MemoryStick} label={t("live.card_mem")}
          main={last.ram_used_pct} mainUnit="%" testid="stat-ram"
          rows={[{ label: t("live.st_vram"), value: last.vram_used_pct, unit: "%", cls: "text-[#B388FF]", testid: "stat-vram" }]} />
      </div>

      {/* ===== v0.7.7: PRECISION SENSORS STRIP (fan RPM / VRM temp / CPU power / Vcore) ===== */}
      {(last.fan_rpm_max != null || last.vrm_temp != null || last.cpu_power != null || last.cpu_vcore != null) && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4" data-testid="precision-sensors">
          <PrecisionCell icon={Fan} label={t("live.st_fan_rpm", "Fan RPM")} value={last.fan_rpm_max} unit="RPM" cls="text-[#00E0FF]" testid="stat-fan-rpm" />
          <PrecisionCell icon={Thermometer} label={t("live.st_vrm_temp", "VRM Temp")} value={last.vrm_temp} unit="°C" cls={tempClass(last.vrm_temp)} testid="stat-vrm-temp" />
          <PrecisionCell icon={Zap} label={t("live.st_cpu_power", "CPU Power")} value={last.cpu_power} unit="W" cls="text-[#E5FF00]" testid="stat-cpu-power" />
          <PrecisionCell icon={Wind} label={t("live.st_cpu_vcore", "Vcore")} value={last.cpu_vcore} unit="V" cls="text-[#B388FF]" testid="stat-cpu-vcore" />
        </div>
      )}

      {/* ===== MAIN: charts (2/3) + sidebar tools (1/3) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2">
          <TelemetryCharts chart={chart} waitingText={t("live.waiting")} t={t} />
        </div>
        <div className="space-y-4">
          {data.live && <BottleneckDetector />}
          <AlertSettings alerts={alerts} setAlerts={setAlerts} onSave={saveAlerts} t={t} />
          <details className="bg-[#0F0F12] border border-[#1A1A24] rounded-none group" data-testid="reflex-card">
            <summary className="flex items-center justify-between gap-2 p-4 cursor-pointer select-none text-sm font-bold hover:bg-black/30 transition-colors">
              <span className="flex items-center gap-2"><Sparkles size={15} className="text-[#00E0FF]" /> {t("live.reflex_title")}</span>
              <ChevronDown size={15} className="text-zinc-500 group-open:rotate-180 transition-transform" />
            </summary>
            <div className="px-4 pb-4">
              <p className="text-xs text-zinc-500 mb-3">{t("live.reflex_desc")}</p>
              <ul className="space-y-2 text-sm text-zinc-300">
                {["reflex_t1", "reflex_t2", "reflex_t3", "reflex_t4"].map((k) => (
                  <li key={k} className="border-l-2 border-[#00E0FF]/40 pl-3 text-[13px] leading-relaxed" data-testid={`reflex-${k}`}>{t(`live.${k}`)}</li>
                ))}
              </ul>
            </div>
          </details>
        </div>
      </div>

      {/* ===== SESSION SUMMARY (full width, shareable) ===== */}
      {summary && <SessionSummary summary={summary} onReset={resetSession} />}

      <GameplayDoctor />

      {/* ===== OBS Browser Overlay (Streamer only) ===== */}
      <div className="mb-6">
        <ObsOverlayPanel />
      </div>
      </>
      )}
    </div>
  );
}
