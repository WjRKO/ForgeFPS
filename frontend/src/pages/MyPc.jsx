import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Cpu, Activity, RefreshCw, CheckCircle2, AlertTriangle, XCircle, HelpCircle, Thermometer, MonitorDown, Sparkles, Loader2, Rocket, Pencil, Users } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import api, { formatApiErrorDetail } from "@/lib/api";
import SpecsForm from "@/components/SpecsForm";
import HealthHistoryCard from "@/components/HealthHistoryCard";
import { HwInsightsPanel } from "@/components/HwInsightsPanel";
import SyncTimeline from "@/components/SyncTimeline";
import { PageHeader } from "@/components/hud";
import { useSilentLaunch } from "@/hooks/useSilentLaunch";
import BrowserPopupHint from "@/components/BrowserPopupHint";

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
    const base = x.length ? `${v} · ${x.join(" · ")}` : v;
    return d.gpu_secondary ? `${base} + ${d.gpu_secondary}` : base;
  }
  if (key === "ram") {
    const x = [];
    if (d.ram_type) x.push(d.ram_type);
    if (d.ram_speed_mhz) x.push(`${d.ram_speed_mhz}MHz`);
    if (d.ram_modules) x.push(`${d.ram_modules}×`);
    if (d.ram_manufacturer) x.push(d.ram_manufacturer);
    return x.length ? `${v} · ${x.join(" · ")}` : v;
  }
  if (key === "disk") {
    const x = [];
    if (d.storage_type) x.push(d.storage_type);
    if (d.storage_health && d.storage_health !== "Healthy") x.push(`health: ${d.storage_health}`);
    if (d.storage_wear_pct != null) x.push(`wear ${d.storage_wear_pct}%`);
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


// v0.7.4d: guida actionable quando la temp CPU non e' leggibile.
// Il PowerShell agent invia in health.checks[cpu_temp].reason uno di:
//   not_admin | vbs_on | blocklist_on | no_sensors | unknown
// Mostriamo un banner giallo/rosso sotto il grid con istruzioni specifiche.
const CPU_TEMP_REASONS = {
  not_admin: {
    title: "Temperatura CPU non leggibile — l'agent non gira come Amministratore",
    body: "Il driver dei sensori CPU richiede privilegi elevati (UAC). Riapri FrameForge Agent e conferma il prompt UAC quando appare.",
    fix_label: "Come risolvere",
    steps: [
      "Chiudi la finestra dell'agent",
      "Doppio click su Avvia-FrameForge.bat (o forgefps-agent.exe)",
      "Quando appare il prompt UAC di Windows, clicca Sì",
    ],
  },
  vbs_on: {
    title: "Temperatura CPU bloccata da Windows — Integrità della memoria attiva",
    body: "Sicurezza di Windows sta bloccando il driver di basso livello che legge la temperatura CPU. È una protezione (VBS). Puoi disattivarla se ti serve la temp.",
    fix_label: "Come disattivare (opzionale)",
    steps: [
      "Impostazioni → Privacy e sicurezza → Sicurezza di Windows",
      "Sicurezza del dispositivo → Isolamento core → Integrità della memoria → OFF",
      "Riavvia il PC",
    ],
  },
  blocklist_on: {
    title: "Temperatura CPU bloccata da Windows — Blocklist driver vulnerabili",
    body: "Windows 11 blocca WinRing0 (il driver usato per leggere i sensori CPU) tramite la Blocklist. È attiva di default per sicurezza — la temp GPU continua a funzionare comunque.",
    fix_label: "Alternativa",
    steps: [
      "La blocklist protegge da driver malevoli — sconsigliamo di disattivarla",
      "Come workaround, tieni aperto HWMonitor/HWiNFO in parallelo per vedere la temp CPU",
      "La GPU (che è quella che conta di più per il gaming) viene rilevata normalmente",
    ],
  },
  no_sensors: {
    title: "Sensori CPU non riconosciuti — probabile Ryzen Zen4 o BIOS datato",
    body: "LibreHardwareMonitor gira correttamente ma non ha trovato un sensore CPU tra i nomi standard (Tctl, Tdie, CPU Package). Su Ryzen 7000+ i sensori possono avere nomi non standard, oppure il BIOS non li espone.",
    fix_label: "Come sistemare",
    steps: [
      "Aggiorna il BIOS all'ultima versione stabile dal sito della tua motherboard",
      "In alternativa scarica LibreHardwareMonitor standalone (github.com/LibreHardwareMonitor) e verifica quali sensori CPU vede: se ne trova, mandami uno screenshot dei nomi e li aggiungo alla whitelist",
      "Riavvia FrameForge Agent dopo l'update BIOS",
    ],
  },
  no_lhm: {
    title: "Driver sensori CPU non caricato — WinRing0 bloccato",
    body: "LibreHardwareMonitor non è riuscito a caricare il driver WinRing0 che serve per leggere i sensori CPU. Anche senza VBS/Blocklist attive, Windows può bloccare driver non firmati al primo avvio.",
    fix_label: "Fix in 60 secondi (funziona su Ryzen)",
    steps: [
      "Scarica LibreHardwareMonitor standalone da github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases",
      "Estrai lo ZIP e apri LibreHardwareMonitor.exe come Amministratore (tasto destro → Esegui come Amministratore)",
      "Se vede la temperatura CPU, chiudilo — il driver WinRing0 è ora firmato per il tuo PC",
      "Riapri FrameForge Agent: la temp CPU verrà rilevata automaticamente",
    ],
  },
  unknown: {
    title: "Temperatura CPU non leggibile",
    body: "L'agent non è riuscito a determinare il motivo. Se il problema persiste, contatta il supporto con lo screenshot della console dell'agent.",
    fix_label: "Debug",
    steps: [
      "Avvia l'agent come Amministratore",
      "Controlla la console per messaggi [WARN] o [INFO][diag]",
    ],
  },
};

const CPU_TEMP_REASONS_EN = {
  not_admin: {
    title: "CPU temperature unreadable — the agent isn't running as Administrator",
    body: "The CPU sensor driver requires elevated privileges (UAC). Reopen FrameForge Agent and confirm the UAC prompt when it appears.",
    fix_label: "How to fix",
    steps: [
      "Close the agent window",
      "Double-click Avvia-FrameForge.bat (or forgefps-agent.exe)",
      "When the Windows UAC prompt appears, click Yes",
    ],
  },
  vbs_on: {
    title: "CPU temperature blocked by Windows — Memory Integrity is on",
    body: "Windows Security is blocking the low-level driver that reads the CPU temperature. It's a protection (VBS). You can turn it off if you need the temp.",
    fix_label: "How to disable (optional)",
    steps: [
      "Settings → Privacy & security → Windows Security",
      "Device security → Core isolation → Memory integrity → OFF",
      "Restart your PC",
    ],
  },
  blocklist_on: {
    title: "CPU temperature blocked by Windows — Vulnerable driver blocklist",
    body: "Windows 11 blocks WinRing0 (the driver used to read CPU sensors) via the Blocklist. It's on by default for security — GPU temp keeps working anyway.",
    fix_label: "Alternative",
    steps: [
      "The blocklist protects against malicious drivers — we recommend keeping it on",
      "As a workaround, keep HWMonitor/HWiNFO open in parallel to see the CPU temp",
      "The GPU (which matters most for gaming) is detected normally",
    ],
  },
  no_sensors: {
    title: "CPU sensors not recognized — likely Ryzen Zen4 or outdated BIOS",
    body: "LibreHardwareMonitor runs correctly but didn't find a CPU sensor among the standard names (Tctl, Tdie, CPU Package). On Ryzen 7000+ sensors can have non-standard names, or the BIOS doesn't expose them.",
    fix_label: "How to fix",
    steps: [
      "Update the BIOS to the latest stable version from your motherboard vendor's site",
      "Alternatively download standalone LibreHardwareMonitor (github.com/LibreHardwareMonitor) and check which CPU sensors it sees: if it finds any, send me a screenshot of the names and I'll add them to the whitelist",
      "Restart FrameForge Agent after the BIOS update",
    ],
  },
  no_lhm: {
    title: "CPU sensor driver not loaded — WinRing0 blocked",
    body: "LibreHardwareMonitor couldn't load the WinRing0 driver needed to read CPU sensors. Even without VBS/Blocklist enabled, Windows can block unsigned drivers on first launch.",
    fix_label: "60-second fix (works on Ryzen)",
    steps: [
      "Download standalone LibreHardwareMonitor from github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases",
      "Extract the ZIP and open LibreHardwareMonitor.exe as Administrator (right click → Run as Administrator)",
      "If it shows the CPU temperature, close it — the WinRing0 driver is now trusted on your PC",
      "Reopen FrameForge Agent: the CPU temp will be detected automatically",
    ],
  },
  unknown: {
    title: "CPU temperature unreadable",
    body: "The agent couldn't determine the reason. If the problem persists, contact support with a screenshot of the agent console.",
    fix_label: "Debug",
    steps: [
      "Run the agent as Administrator",
      "Check the console for [WARN] or [INFO][diag] messages",
    ],
  },
};

function CpuTempReasonHint({ checks }) {
  if (!Array.isArray(checks)) return null;
  const cpuCheck = checks.find((c) => c.id === "cpu_temp");
  if (!cpuCheck || cpuCheck.status !== "unknown" || !cpuCheck.reason) return null;
  const dict = i18n.language?.startsWith("en") ? CPU_TEMP_REASONS_EN : CPU_TEMP_REASONS;
  const info = dict[cpuCheck.reason] || dict.unknown;
  const isSecurity = cpuCheck.reason === "vbs_on" || cpuCheck.reason === "blocklist_on";
  const color = isSecurity ? "#E5FF00" : "#00E0FF"; // giallo = protezione security, azzurro = altro

  return (
    <div className="mt-4 border-t border-[#1A1A24] pt-3" data-testid="cpu-temp-reason-hint">
      <div className="border p-4" style={{ borderColor: `${color}66`, backgroundColor: `${color}0D` }}>
        <div className="flex items-start gap-3">
          <AlertTriangle size={16} className="shrink-0 mt-0.5" style={{ color }} />
          <div className="min-w-0 flex-1">
            <div className="text-xs uppercase tracking-widest mb-1 font-mono" style={{ color }}>// {cpuCheck.reason}</div>
            <div className="text-sm font-semibold text-zinc-100 mb-1" data-testid="cpu-temp-reason-title">{info.title}</div>
            <p className="text-xs text-zinc-400 leading-relaxed mb-3">{info.body}</p>
            <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1.5">{info.fix_label}</div>
            <ol className="text-xs text-zinc-300 space-y-1 list-decimal pl-4">
              {info.steps.map((s, i) => (<li key={i}>{s}</li>))}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}





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
  // Il polling detecta l'aggiornamento comparando 'updated_at' prima e dopo.
  const baselineRef = useRef({ updatedAt: null });
  useEffect(() => { baselineRef.current = { updatedAt: specs?.updated_at || null }; }, [specs?.updated_at]);

  const syncLaunch = useSilentLaunch({
    mode: "sync",
    timeoutMs: 60000,
    labels: {
      starting: t("mypcpage.silent_sync_start", { defaultValue: "Sincronizzazione in avvio..." }),
      running: t("mypcpage.silent_sync_running", { defaultValue: "Sincronizzazione hardware in corso..." }),
      done: t("mypcpage.silent_sync_done", { defaultValue: "Sync completato. Dati aggiornati." }),
      failed: t("mypcpage.silent_sync_failed", { defaultValue: "Sync non completato. Se hai gia' usato FrameForge con un altro account, il token locale e' disallineato: vai su 'FrameForge Agent' → 'L'agent potrebbe essere collegato ad un altro account' e scarica il launcher .bat." }),
      notInstalled: t("mypcpage.silent_not_installed", { defaultValue: "Non hai ancora installato FrameForge? Vai su 'FrameForge Agent'." }),
    },
    detectDone: async () => {
      const { data } = await api.get("/pc-specs");
      if (data.updated_at && data.updated_at !== baselineRef.current.updatedAt) {
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

      {specs?.updated_at && (() => {
        let diffSec = 0;
        try { diffSec = Math.floor((Date.now() - new Date(specs.updated_at).getTime()) / 1000); } catch { diffSec = 999999; }
        const justNow = diffSec >= 0 && diffSec < 5;
        return (
          <div className={`mb-4 flex items-center gap-2 text-xs transition-colors ${justNow ? "text-[#00FF66]" : "text-zinc-500"}`} data-testid="last-sync-info">
            <span className={`w-1.5 h-1.5 rounded-full bg-[#00FF66] ${justNow ? "animate-ping" : ""}`} />
            <span>{t("mypcpage.last_sync", { defaultValue: "Ultimo sync:" })}</span>
            <span className={`font-mono ${justNow ? "text-[#00FF66] font-bold" : "text-zinc-300"}`} data-testid="last-sync-timestamp">
              {(() => {
                try {
                  const d = new Date(specs.updated_at);
                  const diffMs = Date.now() - d.getTime();
                  const s = Math.floor(diffMs / 1000);
                  if (s < 10) return t("mypcpage.just_now", { defaultValue: "or ora" });
                  if (s < 60) return t("mypcpage.sec_ago", { count: s, defaultValue: `${s}s fa` });
                  const m = Math.floor(s / 60);
                  if (m < 60) return t("mypcpage.min_ago", { count: m, defaultValue: `${m} min fa` });
                  const h = Math.floor(m / 60);
                  if (h < 24) return t("mypcpage.hour_ago", { count: h, defaultValue: `${h}h fa` });
                  return d.toLocaleString((i18n.resolvedLanguage || i18n.language || "en").slice(0, 2), { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
                } catch { return specs.updated_at; }
              })()}
            </span>
            {justNow && <span className="text-[#00FF66] font-bold">· {t("mypcpage.sync_ok", { defaultValue: "aggiornato!" })}</span>}
          </div>
        );
      })()}

      <BrowserPopupHint testid="mypc-popup-hint" />

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
          <CpuTempReasonHint checks={health.checks} />
          {(health.fleet || health.throttling?.checked) && (
            <div className="mt-4 flex flex-wrap gap-3 border-t border-[#1A1A24] pt-3">
              {health.fleet && (
                <div className="flex items-center gap-2 text-xs" data-testid="health-fleet-percentile">
                  <Users size={13} className="text-[#00E0FF]" />
                  <span className="text-zinc-400">{t("mypcpage.health.fleetpct", { pct: health.fleet.percentile, n: health.fleet.n })}</span>
                </div>
              )}
              {health.throttling?.checked && (
                <div className="flex items-center gap-2 text-xs" data-testid="health-throttling">
                  <Thermometer size={13} className={health.throttling.detected ? "text-[#FF3B30]" : "text-[#00FF66]"} />
                  <span className={health.throttling.detected ? "text-red-400" : "text-zinc-400"}>
                    {health.throttling.detected
                      ? t("mypcpage.health.throttle_yes", { n: health.throttling.events, temp: health.throttling.max_temp })
                      : t("mypcpage.health.throttle_no")}
                  </span>
                </div>
              )}
            </div>
          )}
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

      <HwInsightsPanel />

      <HealthHistoryCard />

      <SyncTimeline days={7} />

      <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick mb-4">
        <div className="p-5 border-b border-[#2A2A35] text-xs uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2"><Cpu size={14} className="text-[#E5FF00]" /> {t("mypcpage.hardware")}</div>
        <div className="grid sm:grid-cols-2 gap-px bg-[#1A1A24]">
          {shownSpecKeys.map((k) => {
            const conf = specs.data?.hw_confidence || {};
            const cKey = k === "disk" ? "storage" : k;
            const cVal = conf[cKey];
            const badgeCls = cVal >= 2 ? "text-[#00FF66] border-[#00FF66]/30" : cVal === 1 ? "text-[#E5FF00] border-[#E5FF00]/30" : "text-zinc-600 border-zinc-800";
            return (
              <div key={k} className="bg-[#0F0F12] p-4" data-testid={`spec-${k}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs uppercase tracking-widest text-zinc-500">{specLabel(t, k)}</div>
                  {cVal != null && (
                    <span
                      className={`text-[9px] font-mono font-bold px-1.5 py-0.5 border ${badgeCls}`}
                      title={t("mypcpage.hw_sources_tooltip", "Numero di fonti indipendenti (WMI + Registry + nvidia-smi) che hanno confermato questo componente")}
                      data-testid={`hw-conf-${k}`}
                    >
                      {cVal}/2
                    </span>
                  )}
                </div>
                <div className="text-sm text-zinc-100 mt-1">{composeSpec(k, specs.data)}</div>
              </div>
            );
          })}
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
        {!startup && !err && (
          <div>
            <div className="p-3 text-xs text-zinc-500 border-b border-[#1A1A24]">
              {t("mypcpage.startup_count", { count: (specs.startup || []).length })} · {t("mypcpage.startup_hint")}
            </div>
            {(specs.startup || []).slice(0, 30).map((s, i) => (
              <div key={`${s.name}-${i}`} className="flex items-center gap-3 px-3 py-2 border-b border-[#1A1A24]" data-testid={`startup-detected-${i}`}>
                <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 shrink-0 ${s.enabled === false ? "bg-zinc-700/40 text-zinc-400" : "bg-[#00FF66]/15 text-[#00FF66]"}`}>
                  {s.enabled === false ? t("mypcpage.startup_off") : t("mypcpage.startup_on")}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{s.name}</div>
                  <div className="text-[11px] text-zinc-500 truncate">
                    {s.publisher || t("mypcpage.startup_unsigned")}
                    {s.source && <span className="text-zinc-600"> · {t(`mypcpage.startup_src.${s.source}`, s.source)}</span>}
                  </div>
                </div>
                {s.ram_mb ? <span className="text-[11px] text-zinc-400 tabular-nums shrink-0">{s.ram_mb} MB</span> : null}
              </div>
            ))}
          </div>
        )}
        {startup && (
          <div>
            <div className="p-4 text-sm text-zinc-300 border-b border-[#1A1A24] bg-black">{startup.summary}</div>
            {startup.items.map((it, i) => {
              const det = (specs.startup || []).find((s) => s.name && it.name && (s.name.toLowerCase().includes(it.name.toLowerCase()) || it.name.toLowerCase().includes(s.name.toLowerCase())));
              const how = det?.source === "service" ? t("mypcpage.startup_how_service") : det?.source === "task" ? t("mypcpage.startup_how_task") : t("mypcpage.startup_how_taskmgr");
              return (
                <div key={it.name || i} className="flex items-center gap-3 p-3 border-b border-[#1A1A24]" data-testid={`startup-item-${i}`}>
                  <span className={`text-xs font-bold uppercase px-2 py-0.5 shrink-0 ${it.recommendation === "disabilita" ? "bg-[#FF3B30]/20 text-[#FF3B30]" : it.recommendation === "mantieni" ? "bg-[#00FF66]/20 text-[#00FF66]" : "bg-[#E5FF00]/20 text-[#E5FF00]"}`}>{it.recommendation}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{it.name}{det?.ram_mb ? <span className="text-[11px] text-zinc-500"> · {det.ram_mb} MB RAM</span> : null}</div>
                    <div className="text-xs text-zinc-500">{it.reason}</div>
                    {it.recommendation === "disabilita" && <div className="text-[11px] text-[#00E0FF] mt-0.5">→ {how}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
