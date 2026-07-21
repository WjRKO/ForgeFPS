import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Cpu, Activity, RefreshCw, CheckCircle2, AlertTriangle, XCircle, HelpCircle, Thermometer, MonitorDown, Sparkles, Loader2, Rocket, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import api, { formatApiErrorDetail } from "@/lib/api";
import SpecsForm from "@/components/SpecsForm";
import HealthHistoryCard from "@/components/HealthHistoryCard";
import { PageHeader } from "@/components/hud";
import { useSilentLaunch } from "@/hooks/useSilentLaunch";

const SPEC_KEYS = ["os", "cpu", "gpu", "ram", "disk", "motherboard", "resolution"];
const specLabel = (t, k) => ({ os: t("mypcpage.sl_os"), cpu: "CPU", gpu: "GPU", ram: "RAM", disk: t("mypcpage.sl_disk"), motherboard: t("mypcpage.sl_mb"), resolution: t("mypcpage.sl_res") }[k]);

function composeSpec(key, d) {
  const v = d[key];
  if (!v) return null;
  if (key === "cpu") {
    const x = [];
    if (d.cpu_cores) x.push(`${d.cpu_cores}C`);
    if (d.cpu_threads) x.push(`${d.cpu_threads}T`);
    if (d.cpu_clock_ghz) x.push(`${d.cpu_clock_ghz}GHz`);
    return x.length ? `${v} · ${x.join(" / ")}` : v;
  }
  if (key === "gpu") {
    const x = [];
    if (d.gpu_vram_gb) x.push(`${d.gpu_vram_gb}GB VRAM`);
    if (d.gpu_driver_version) x.push(`driver ${d.gpu_driver_version}`);
    return x.length ? `${v} · ${x.join(" · ")}` : v;
  }
  if (key === "ram") {
    const x = [];
    if (d.ram_type) x.push(d.ram_type);
    if (d.ram_speed_mhz) x.push(`${d.ram_speed_mhz}MHz`);
    if (d.ram_modules) x.push(`${d.ram_modules}×`);
    return x.length ? `${v} · ${x.join(" · ")}` : v;
  }
  if (key === "os") return d.form_factor ? `${v} · ${d.form_factor}` : v;
  if (key === "resolution") return d.refresh_hz ? `${v} @ ${d.refresh_hz}Hz` : v;
  if (key === "motherboard") {
    const x = [];
    if (d.cpu_socket) x.push(`socket ${d.cpu_socket}`);
    if (d.chipset) x.push(`chipset ${d.chipset}`);
    return x.length ? `${v} · ${x.join(" · ")}` : v;
  }
  return v;
}

const STATUS_ICON = { ok: <CheckCircle2 size={16} className="text-[#00FF66]" />, warn: <AlertTriangle size={16} className="text-[#E5FF00]" />, bad: <XCircle size={16} className="text-[#FF3B30]" />, unknown: <HelpCircle size={16} className="text-zinc-600" /> };





function ScoreRing({ score, grade }) {
  const scoreColor = (s) => {
    if (s >= 85) return "#00FF66";
    if (s >= 70) return "#E5FF00";
    if (s >= 50) return "#FFA500";
    return "#FF3B30";
  };
  const color = scoreColor(score);
  const circumference = 2 * Math.PI * 52;
  const offset = circumference - (score / 100) * circumference;
  return (
    <div className="relative w-40 h-40 shrink-0">
      <svg className="w-40 h-40 -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="52" fill="none" stroke="#2A2A35" strokeWidth="8" />
        <circle cx="60" cy="60" r="52" fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset} style={{ transition: "stroke-dashoffset 0.8s ease" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-display font-black text-4xl" style={{ color }} data-testid="health-score">{score}</div>
        <div className="text-xs uppercase tracking-widest text-zinc-500">{grade}</div>
      </div>
    </div>
  );
}

export default function MyPc() {
  const { t } = useTranslation();
  const [specs, setSpecs] = useState(null);
  const [health, setHealth] = useState(null);
  const [startup, setStartup] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);

  const load = async () => {
    try { const { data } = await api.get("/pc-specs"); setSpecs(data); } catch (e) { console.error("load pc-specs failed", e); }
    try { const { data } = await api.get("/pc-health"); setHealth(data.available ? data : null); } catch (e) { console.error("load pc-health failed", e); }
  };
  useEffect(() => { load(); }, []);

  // Silent launch: sync ambientale (nessuna finestra visibile).
  // Il polling detecta l'aggiornamento comparando 'synced_at' prima e dopo.
  const baselineRef = useRef({ syncedAt: null });
  useEffect(() => { baselineRef.current = { syncedAt: specs?.synced_at || null }; }, [specs?.synced_at]);

  const syncLaunch = useSilentLaunch({
    mode: "sync",
    timeoutMs: 60000,
    labels: {
      starting: t("mypcpage.silent_sync_start", { defaultValue: "Sincronizzazione in avvio..." }),
      running: t("mypcpage.silent_sync_running", { defaultValue: "Sincronizzazione hardware in corso..." }),
      done: t("mypcpage.silent_sync_done", { defaultValue: "Sync completato. Dati aggiornati." }),
      failed: t("mypcpage.silent_sync_failed", { defaultValue: "L'app non risponde. Hai installato FrameForge?" }),
      notInstalled: t("mypcpage.silent_not_installed", { defaultValue: "Non hai ancora installato FrameForge? Vai su 'Collega il PC'." }),
    },
    detectDone: async () => {
      const { data } = await api.get("/pc-specs");
      if (data.synced_at && data.synced_at !== baselineRef.current.syncedAt) {
        setSpecs(data);
        try { const { data: h } = await api.get("/pc-health"); setHealth(h.available ? h : null); } catch (e) { console.error("post-sync health reload", e); }
        return true;
      }
      return false;
    },
  });

  const analyzeStartup = async () => {
    setAnalyzing(true); setErr("");
    try { const { data } = await api.post("/startup/analyze"); setStartup(data); }
    catch (e) { setErr(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setAnalyzing(false); }
  };

  const hasSpecs = specs?.data?.cpu || specs?.data?.gpu;
  const shownSpecKeys = useMemo(
    () => SPEC_KEYS.filter((k) => specs?.data?.[k]),
    [specs]
  );

  if (!hasSpecs || editing) {
    return (
      <div className="max-w-3xl mx-auto fade-up">
        <div className="mb-6"><div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("mypcpage.eyebrow")}</div>
          <h1 className="font-display font-black text-3xl tracking-tighter">{t("mypcpage.title")}</h1></div>
        <div className="mb-4 bg-[#0F0F12] border border-[#2A2A35] p-5 text-sm text-zinc-400">
          {t("mypcpage.intro")} <span className="text-[#E5FF00]">{t("mypcpage.intro_hl")}</span>.
          {" "}{t("mypcpage.intro2")}
        </div>
        <SpecsForm initial={specs?.data || {}}
          onSaved={(d) => { setSpecs(d); setEditing(false); load(); }}
          onCancel={hasSpecs ? () => setEditing(false) : undefined} />
        <div className="mt-4 text-center">
          <Link to="/app/desktop" data-testid="go-desktop-btn" className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-[#E5FF00] transition-colors">
            <MonitorDown size={16} /> {t("mypcpage.want_more")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <PageHeader eyebrow={t("mypcpage.eyebrow")} title={t("mypcpage.title")}
        actions={<>
          <button data-testid="silent-sync-btn" onClick={syncLaunch.launch} disabled={syncLaunch.running}
            className="flex items-center gap-2 border border-[#00E0FF]/50 text-[#00E0FF] px-3 py-2 text-sm hover:bg-[#00E0FF]/10 disabled:opacity-60 transition-colors">
            {syncLaunch.running ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            {t("mypcpage.silent_sync_btn", { defaultValue: "Sincronizza ora" })}
          </button>
          <button data-testid="edit-specs-btn" onClick={() => setEditing(true)} className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] btn-ghost"><Pencil size={15} /> {t("mypcpage.edit")}</button>
          <Link to="/app/upgrade" data-testid="to-upgrade-btn" className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] btn-ghost"><Rocket size={15} /> {t("mypcpage.upgrade")}</Link>
          <button data-testid="refresh-pc-btn" onClick={load} className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] btn-ghost"><RefreshCw size={15} /> {t("mypcpage.refresh")}</button>
        </>} />

      {health && (
        <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick p-6 mb-4">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4 flex items-center gap-2"><Activity size={14} className="text-[#E5FF00]" /> Health Score</div>
          <div className="flex flex-col md:flex-row gap-8 items-center">
            <ScoreRing score={health.score} grade={t(`mypcpage.health.grade.${health.grade_key}`, health.grade)} />
            <div className="flex-1 w-full grid sm:grid-cols-2 gap-2">
              {health.checks.map((c, i) => (
                <div key={c.id || i} data-testid={`check-${i}`} className="flex items-start gap-2 bg-black border border-[#1A1A24] p-3">
                  {STATUS_ICON[c.status]}
                  <div className="min-w-0">
                    <div className="text-sm text-zinc-200">{t(`mypcpage.health.label.${c.id}`, c.label)}</div>
                    <div className="text-xs text-zinc-500">{t(`mypcpage.health.msg.${c.mkey}`, { v: c.mval, defaultValue: c.message })}</div>
                    {c.fix && <div className="text-xs text-[#E5FF00] mt-1">→ {t(`mypcpage.health.fix.${c.id}`, c.fix)}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
          {(health.gpu_temp != null || health.cpu_temp != null) && (
            <div className="mt-4 flex flex-wrap gap-3 border-t border-[#1A1A24] pt-3">
              {health.cpu_temp != null && (
                <div className="flex items-center gap-2 text-sm" data-testid="cpu-temp">
                  <Thermometer size={15} className={health.cpu_temp >= 90 ? "text-[#FF3B30]" : health.cpu_temp >= 80 ? "text-[#E5FF00]" : "text-[#00FF66]"} />
                  <span className="text-zinc-500">CPU</span> <span className="font-bold">{health.cpu_temp}°C</span>
                </div>
              )}
              {health.gpu_temp != null && (
                <div className="flex items-center gap-2 text-sm" data-testid="gpu-temp">
                  <Thermometer size={15} className={health.gpu_temp >= 85 ? "text-[#FF3B30]" : health.gpu_temp >= 75 ? "text-[#E5FF00]" : "text-[#00FF66]"} />
                  <span className="text-zinc-500">GPU</span> <span className="font-bold">{health.gpu_temp}°C</span>
                </div>
              )}
            </div>
          )}
          {health.driver_version && (
            <div className="mt-4 text-xs text-zinc-500 flex items-center gap-2 border-t border-[#1A1A24] pt-3">
              {t("mypcpage.driver_gpu")} <span className="text-zinc-300">{health.driver_version}</span>
              <a href="https://www.nvidia.com/Download/index.aspx" target="_blank" rel="noreferrer" className="text-[#E5FF00] hover:underline ml-2">{t("mypcpage.check_updates")}</a>
            </div>
          )}
        </div>
      )}

      <HealthHistoryCard />

      <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick mb-4">
        <div className="p-5 border-b border-[#2A2A35] text-xs uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2"><Cpu size={14} className="text-[#E5FF00]" /> {t("mypcpage.hardware")}</div>
        <div className="grid sm:grid-cols-2 gap-px bg-[#1A1A24]">
          {shownSpecKeys.map((k) => (
            <div key={k} className="bg-[#0F0F12] p-4" data-testid={`spec-${k}`}>
              <div className="text-xs uppercase tracking-widest text-zinc-500">{specLabel(t, k)}</div>
              <div className="text-sm text-zinc-100 mt-1">{composeSpec(k, specs.data)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35]" style={{ display: (specs.startup || []).length ? "block" : "none" }}>
        <div className="p-5 border-b border-[#2A2A35] flex items-center justify-between">
          <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">{t("mypcpage.startup")}</span>
          <button data-testid="analyze-startup-btn" onClick={analyzeStartup} disabled={analyzing}
            className="flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-3 py-1.5 text-xs hover:bg-[#D4EC00] transition-colors disabled:opacity-60 btn-volt">
            {analyzing ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} {t("mypcpage.analyze_ai")}
          </button>
        </div>
        {err && <div className="p-3 text-xs text-[#FF3B30]">{err}</div>}
        {!startup && !err && <div className="p-6 text-sm text-zinc-500">{t("mypcpage.startup_count", { count: (specs.startup || []).length })}</div>}
        {startup && (
          <div>
            <div className="p-4 text-sm text-zinc-300 border-b border-[#1A1A24] bg-black">{startup.summary}</div>
            {startup.items.map((it, i) => (
              <div key={it.name || i} className="flex items-center gap-3 p-3 border-b border-[#1A1A24]" data-testid={`startup-item-${i}`}>
                <span className={`text-xs font-bold uppercase px-2 py-0.5 shrink-0 ${it.recommendation === "disabilita" ? "bg-[#FF3B30]/20 text-[#FF3B30]" : it.recommendation === "mantieni" ? "bg-[#00FF66]/20 text-[#00FF66]" : "bg-[#E5FF00]/20 text-[#E5FF00]"}`}>{it.recommendation}</span>
                <div className="flex-1 min-w-0"><div className="text-sm truncate">{it.name}</div><div className="text-xs text-zinc-500">{it.reason}</div></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
