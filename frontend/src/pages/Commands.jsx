import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { Terminal, Copy, Check, ShieldAlert, MessageSquareCode, Trash2, Wrench, Wifi, Zap, Package, Search, MonitorPlay, Rocket, Power, HeartPulse, AlertTriangle, Undo2, Download, CalendarClock, Sparkles } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageHeader } from "@/components/hud";

const isEn = () => i18n.language?.startsWith("en");

const CATS = [
  {
    id: "boost", title: "Boost prestazioni", icon: Rocket, color: "#E5FF00",
    items: [
      { cmd: "powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61", desc: "Sblocca il piano Ultimate Performance (il più aggressivo), poi selezionalo dalle opzioni di risparmio energia.", de: "Unlocks the Ultimate Performance power plan (the most aggressive one), then select it from the power options." },
      { cmd: "reg add \"HKCU\\System\\GameConfigStore\" /v GameDVR_Enabled /t REG_DWORD /d 0 /f", desc: "Disattiva Game DVR / registrazione in background: recupera FPS nei giochi.", de: "Disables Game DVR / background recording: recovers FPS in games.", undo: "reg add \"HKCU\\System\\GameConfigStore\" /v GameDVR_Enabled /t REG_DWORD /d 1 /f" },
      { cmd: "Disable-MMAgent -MemoryCompression", desc: "Disattiva la compressione RAM (consigliato con 16GB o più): meno carico CPU.", de: "Disables RAM compression (recommended with 16GB or more): less CPU load.", admin: true, undo: "Enable-MMAgent -MemoryCompression" },
      { cmd: "bcdedit /set useplatformclock false", desc: "Riduce micro-stutter forzando il timer HPET off. Testa la stabilità dopo il riavvio.", de: "Reduces micro-stutter by forcing the HPET timer off. Test stability after reboot.", admin: true, warn: true, undo: "bcdedit /deletevalue useplatformclock" },
      { cmd: "bcdedit /set disabledynamictick yes", desc: "Disattiva il dynamic tick del kernel: latenza più costante ma consumi leggermente più alti.", de: "Disables the kernel dynamic tick: more consistent latency but slightly higher power draw.", admin: true, warn: true, undo: "bcdedit /set disabledynamictick no" },
    ],
  },
  {
    id: "clean", title: "Pulizia & Manutenzione", icon: Trash2, color: "#00FF66",
    items: [
      { cmd: "ipconfig /flushdns", desc: "Svuota la cache DNS: risolve siti o giochi che non si connettono.", de: "Flushes the DNS cache: fixes sites or games that won't connect." },
      { cmd: "cleanmgr /sagerun:1", desc: "Avvia la Pulizia disco per rimuovere i file temporanei di sistema.", de: "Launches Disk Cleanup to remove temporary system files." },
      { cmd: "Clear-RecycleBin -Force", desc: "Svuota il Cestino di tutti i dischi senza conferma.", de: "Empties the Recycle Bin on all drives without confirmation." },
      { cmd: "wsreset.exe", desc: "Resetta la cache del Microsoft Store (fix download/app bloccate).", de: "Resets the Microsoft Store cache (fixes stuck downloads/apps)." },
      { cmd: "Remove-Item \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue", desc: "Svuota la cartella dei file temporanei dell'utente.", de: "Empties the user temporary files folder." },
      { cmd: "Get-ChildItem \"$env:WINDIR\\SoftwareDistribution\\Download\" -Recurse | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue", desc: "Pulisce la cache dei download di Windows Update (recupera spazio).", de: "Clears the Windows Update download cache (frees up space).", admin: true },
      { cmd: "Dism.exe /online /Cleanup-Image /StartComponentCleanup", desc: "Rimuove i componenti e gli aggiornamenti vecchi: può liberare diversi GB.", de: "Removes old components and updates: can free up several GB.", admin: true },
    ],
  },
  {
    id: "startup", title: "Avvio più veloce", icon: Power, color: "#00E0FF",
    items: [
      { cmd: "bcdedit /timeout 3", desc: "Riduce a 3 secondi il timeout del menu di avvio.", de: "Reduces the boot menu timeout to 3 seconds.", admin: true, undo: "bcdedit /timeout 30" },
      { cmd: "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location | Format-Table -Auto", desc: "Elenca i programmi che partono all'avvio, per capire cosa disattivare.", de: "Lists the programs that start at boot, to see what to disable." },
    ],
  },
  {
    id: "repair", title: "Riparazione sistema", icon: Wrench, color: "#E5FF00",
    items: [
      { cmd: "sfc /scannow", desc: "Cerca e ripara i file di sistema di Windows danneggiati.", de: "Scans and repairs corrupted Windows system files.", admin: true },
      { cmd: "DISM /Online /Cleanup-Image /RestoreHealth", desc: "Ripara l'immagine di Windows. Eseguilo prima di sfc se il problema persiste.", de: "Repairs the Windows image. Run it before sfc if the problem persists.", admin: true },
      { cmd: "chkdsk C: /f /r", desc: "Controlla e ripara gli errori del disco C: al prossimo riavvio.", de: "Checks and repairs errors on drive C: at the next reboot.", admin: true },
    ],
  },
  {
    id: "net", title: "Rete", icon: Wifi, color: "#00E0FF",
    items: [
      { cmd: "netsh winsock reset", desc: "Reset dello stack di rete Winsock: fix lag o assenza di internet. Riavvia dopo.", de: "Resets the Winsock network stack: fixes lag or no internet. Reboot afterward.", admin: true },
      { cmd: "netsh int ip reset", desc: "Reset della configurazione IP di Windows.", de: "Resets the Windows IP configuration.", admin: true },
      { cmd: "netsh int tcp set global autotuninglevel=normal", desc: "Ripristina il tuning TCP corretto: migliora throughput e stabilità.", de: "Restores proper TCP tuning: improves throughput and stability.", admin: true },
      { cmd: "ipconfig /release; ipconfig /renew", desc: "Rilascia e rinnova l'indirizzo IP assegnato dal router.", de: "Releases and renews the IP address assigned by the router." },
      { cmd: "Get-NetAdapter | Restart-NetAdapter", desc: "Riavvia tutte le schede di rete senza riavviare il PC.", de: "Restarts all network adapters without rebooting the PC.", admin: true },
      { cmd: "Test-Connection 1.1.1.1 -Count 10", desc: "Esegue 10 ping a Cloudflare per verificare stabilità e latenza.", de: "Pings Cloudflare 10 times to check stability and latency." },
    ],
  },
  {
    id: "perf", title: "Prestazioni & Gaming", icon: Zap, color: "#E5FF00",
    items: [
      { cmd: "powercfg /setactive scheme_min", desc: "Attiva il piano di alimentazione Prestazioni elevate.", de: "Activates the High Performance power plan." },
      { cmd: "powercfg /energy", desc: "Genera un report HTML sui problemi energetici e di consumo.", de: "Generates an HTML report on power and consumption issues.", admin: true },
      { cmd: "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10", desc: "Mostra i 10 processi che stanno consumando più CPU adesso.", de: "Shows the top 10 processes using the most CPU right now." },
    ],
  },
  {
    id: "apps", title: "Gestione app (winget)", icon: Package, color: "#00FF66",
    items: [
      { cmd: "winget upgrade --all", desc: "Aggiorna in un colpo solo tutti i programmi installati sul PC.", de: "Updates all installed programs on the PC in one go." },
      { cmd: "winget list", desc: "Elenca tutto il software installato con la versione.", de: "Lists all installed software with its version." },
    ],
  },
  {
    id: "health", title: "Salute & Diagnostica", icon: HeartPulse, color: "#00E0FF",
    items: [
      { cmd: "powercfg /batteryreport", desc: "Genera un report sulla salute della batteria (portatili).", de: "Generates a battery health report (laptops)." },
      { cmd: "Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object DeviceId, Wear, Temperature", desc: "Mostra usura e temperatura dei tuoi SSD/HDD.", de: "Shows the wear and temperature of your SSDs/HDDs." },
      { cmd: "winsat formal", desc: "Ri-esegue il benchmark ufficiale di Windows (Experience Index).", de: "Re-runs the official Windows benchmark (Experience Index).", admin: true },
      { cmd: "pnputil /enum-devices /problem", desc: "Elenca i dispositivi e i driver che presentano un problema.", de: "Lists devices and drivers that have a problem.", admin: true },
      { cmd: "DISM /Online /Cleanup-Image /AnalyzeComponentStore", desc: "Controlla se conviene pulire lo store dei componenti di Windows.", de: "Checks whether it's worth cleaning the Windows component store.", admin: true },
      { cmd: "dxdiag", desc: "Apre lo strumento di diagnostica DirectX (GPU, driver, audio).", de: "Opens the DirectX diagnostic tool (GPU, drivers, audio)." },
    ],
  },
];

function detectGpu(gpuStr = "") {
  const g = gpuStr.toLowerCase();
  if (/nvidia|geforce|rtx|gtx|quadro/.test(g)) return "nvidia";
  if (/radeon|\brx ?\d|vega/.test(g)) return "amd";
  if (/\barc\b|intel/.test(g)) return "intel";
  return null;
}

const GPU_CMD = {
  nvidia: { label: "GPU NVIDIA", cmd: 'Start-Process "https://www.nvidia.com/Download/index.aspx"', desc: "Apre la pagina di download dei driver GeForce Game Ready per la tua NVIDIA.", de: "Opens the GeForce Game Ready driver download page for your NVIDIA." },
  amd: { label: "GPU AMD", cmd: 'Start-Process "https://www.amd.com/en/support"', desc: "Apre la pagina di download dei driver AMD Adrenalin per la tua Radeon.", de: "Opens the AMD Adrenalin driver download page for your Radeon." },
  intel: { label: "GPU Intel", cmd: 'Start-Process "https://www.intel.com/content/www/us/en/download-center/home.html"', desc: "Apre il download center per i driver della tua Intel Arc.", de: "Opens the download center for your Intel Arc drivers." },
};

function CopyBtn({ text, testid }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); } catch { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success(i18n.t("commands.copied")); setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={copy} data-testid={testid}
      className="shrink-0 flex items-center justify-center border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors">
      {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
    </button>
  );
}

const MAINT = [
  { label: "Svuota la cache DNS", label_en: "Flush the DNS cache", slabel: "Svuoto la cache DNS", cmd: "ipconfig /flushdns" },
  { label: "Pulisci i file temporanei utente", label_en: "Clean user temp files", slabel: "Pulisco i file temporanei utente", cmd: "Remove-Item \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue" },
  { label: "Pulisci i temporanei di sistema", label_en: "Clean system temp files", slabel: "Pulisco i temporanei di sistema", cmd: "Remove-Item \"$env:WINDIR\\Temp\\*\" -Recurse -Force -ErrorAction SilentlyContinue" },
  { label: "Svuota il Cestino", label_en: "Empty the Recycle Bin", slabel: "Svuoto il Cestino", cmd: "Clear-RecycleBin -Force -ErrorAction SilentlyContinue" },
  { label: "Pulisci la cache di Windows Update", label_en: "Clean the Windows Update cache", slabel: "Pulisco la cache di Windows Update", cmd: "Remove-Item \"$env:WINDIR\\SoftwareDistribution\\Download\\*\" -Recurse -Force -ErrorAction SilentlyContinue" },
  { label: "Resetta la cache del Microsoft Store", label_en: "Reset the Microsoft Store cache", slabel: "Resetto la cache dello Store", cmd: "Start-Process wsreset.exe -WindowStyle Hidden" },
];

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const TIMES = ["09:00", "12:00", "15:00", "18:00", "21:00", "03:00"];

function toB64Utf8(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach((b) => { bin += String.fromCharCode(b); });
  return btoa(bin);
}

function buildMaintScript(withBom) {
  const lines = ["Write-Host '== FrameForge - Manutenzione settimanale ==' -ForegroundColor Cyan"];
  MAINT.forEach((m, i) => {
    lines.push(`Write-Host '[${i + 1}/${MAINT.length}] ${m.slabel}...' -ForegroundColor Yellow`);
    lines.push(m.cmd);
  });
  lines.push("Write-Host 'Manutenzione completata!' -ForegroundColor Green");
  return (withBom ? "\uFEFF" : "") + lines.join("\r\n");
}

function MaintenanceCard() {
  const { t } = useTranslation();
  const [day, setDay] = useState("Sunday");
  const [time, setTime] = useState("12:00");

  const oneLine = MAINT.map((m) => m.cmd).join("; ");
  const scheduleCmd = (() => {
    const b64 = toB64Utf8(buildMaintScript(true));
    return [
      `$b='${b64}'`,
      `$p="$env:LOCALAPPDATA\\FrameForge"`,
      `New-Item -ItemType Directory -Force -Path $p | Out-Null`,
      `[IO.File]::WriteAllBytes("$p\\Manutenzione.ps1",[Convert]::FromBase64String($b))`,
      `$arg='-WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$p+'\\Manutenzione.ps1"'`,
      `$a=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg`,
      `$t=New-ScheduledTaskTrigger -Weekly -DaysOfWeek ${day} -At '${time}'`,
      `Register-ScheduledTask -TaskName 'FrameForge-Manutenzione' -Action $a -Trigger $t -Description 'Manutenzione settimanale FrameForge' -Force`,
    ].join("; ");
  })();

  const download = () => {
    const blob = new Blob([buildMaintScript(true)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "FrameForge-Manutenzione.ps1"; document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success(t("commands.toast_download"));
  };

  return (
    <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-5 mb-5" data-testid="maintenance-card">
      <div className="flex items-center gap-2 text-sm font-bold mb-1 text-[#E5FF00]"><Sparkles size={16} /> {t("commands.maint_title")}</div>
      <p className="text-xs text-zinc-400 mb-3 leading-relaxed">{t("commands.maint_desc")}</p>

      <div className="grid sm:grid-cols-2 gap-2 mb-4">
        {MAINT.map((m, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-zinc-400"><Check size={12} className="text-[#00FF66] shrink-0" /> {isEn() ? m.label_en : m.label}</div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <button onClick={download} data-testid="maint-download"
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EC00] transition-colors btn-volt">
          <Download size={15} /> {t("commands.download_script")}
        </button>
        <CopyBtn text={oneLine} testid="maint-oneline-copy" />
        <span className="inline-flex items-center text-xs text-zinc-500">{t("commands.copy_run_hint")}</span>
      </div>

      <div className="border-t border-[#2A2A35] pt-4">
        <div className="flex items-center gap-2 text-xs font-bold text-zinc-200 mb-2"><CalendarClock size={14} className="text-[#00E0FF]" /> {t("commands.schedule_title")}</div>
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-xs text-zinc-500">{t("commands.every")}</span>
          <select value={day} onChange={(e) => setDay(e.target.value)} data-testid="maint-day"
            className="bg-black border border-[#2A2A35] text-xs text-zinc-200 px-2 py-1.5 focus:border-[#E5FF00] outline-none">
            {DAYS.map((d) => <option key={d} value={d}>{t(`commands.days.${d}`)}</option>)}
          </select>
          <span className="text-xs text-zinc-500">{t("commands.at")}</span>
          <select value={time} onChange={(e) => setTime(e.target.value)} data-testid="maint-time"
            className="bg-black border border-[#2A2A35] text-xs text-zinc-200 px-2 py-1.5 focus:border-[#E5FF00] outline-none">
            {TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="text-xs text-zinc-500 mb-1">{t("commands.schedule_hint")}</div>
        <div className="flex items-stretch gap-2">
          <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-[11px] text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="maint-schedule-cmd">{scheduleCmd}</code>
          <CopyBtn text={scheduleCmd} testid="maint-schedule-copy" />
        </div>
        <p className="text-[11px] text-zinc-600 mt-2">{t("commands.remove_schedule")} <span className="text-zinc-400">Unregister-ScheduledTask -TaskName 'FrameForge-Manutenzione' -Confirm:$false</span></p>
      </div>
    </div>
  );
}

function CmdRow({ item, onAsk }) {
  const { t } = useTranslation();
  return (
    <div className="p-4 border-b border-[#1A1A24] last:border-0" data-testid={`cmd-${item.cmd.slice(0, 24)}`}>
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        {item.admin && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-1.5 py-0.5" data-testid="admin-badge">
            <ShieldAlert size={11} /> {t("commands.requires_admin")}
          </span>
        )}
        {item.warn && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#E5FF00] border border-[#E5FF00]/40 bg-[#E5FF00]/10 px-1.5 py-0.5" data-testid="warn-badge">
            <AlertTriangle size={11} /> {t("commands.advanced")}
          </span>
        )}
        <span className="text-xs text-zinc-500 leading-relaxed">{isEn() ? item.de : item.desc}</span>
      </div>

      {item.warn && (
        <div className="text-[11px] text-[#E5FF00]/80 leading-relaxed mb-2">
          {t("commands.advanced_warn")}
        </div>
      )}

      <div className="flex items-stretch gap-2">
        <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap">{item.cmd}</code>
        <CopyBtn text={item.cmd} testid="cmd-copy" />
        <button onClick={() => onAsk(item)} data-testid="cmd-ask-ai"
          className="shrink-0 inline-flex items-center gap-1 border border-[#2A2A35] px-2.5 text-[11px] text-zinc-400 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors whitespace-nowrap">
          <MessageSquareCode size={12} /> {t("commands.ask_ai")}
        </button>
      </div>

      {item.undo && (
        <div className="flex items-stretch gap-2 mt-2">
          <div className="shrink-0 flex items-center gap-1 text-[11px] text-zinc-500 px-1"><Undo2 size={12} /> {t("commands.undo")}</div>
          <code className="flex-1 bg-black/60 border border-[#2A2A35] px-3 py-2 text-[11px] text-zinc-400 overflow-x-auto whitespace-nowrap">{item.undo}</code>
          <CopyBtn text={item.undo} testid="cmd-undo-copy" />
        </div>
      )}
    </div>
  );
}

export default function Commands() {
  const { t } = useTranslation();
  const [specs, setSpecs] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
  }, []);

  const data = useMemo(() => specs?.data || {}, [specs]);
  const gpuBrand = useMemo(() => detectGpu(data.gpu), [data.gpu]);

  const cats = useMemo(() => {
    const list = [...CATS];
    const g = gpuBrand && GPU_CMD[gpuBrand];
    if (g) {
      list.push({
        id: "gpu", title: `Driver GPU (${g.label})`, icon: MonitorPlay, color: "#00FF66",
        items: [g, { cmd: "dxdiag", desc: "Verifica il modello GPU e la versione driver attualmente installati.", de: "Checks the GPU model and currently installed driver version." }],
      });
    }
    return list;
  }, [gpuBrand]);

  const askAI = (item) => {
    const sys = [data.cpu?.trim(), data.gpu, data.os].filter(Boolean).join(", ");
    const q = `Spiegami in modo semplice cosa fa il comando "${item.cmd}" su Windows, quando conviene usarlo e se comporta rischi.${sys ? ` Il mio sistema: ${sys}.` : ""}`;
    navigate("/app/advisor", { state: { ask: q } });
  };

  return (
    <div className="max-w-4xl mx-auto fade-up" data-testid="commands-page">
      <PageHeader eyebrow={t("commands.eyebrow")} title={t("commands.title")} subtitle={t("commands.subtitle")} />

      <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start mb-5">
        <Terminal size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
        <p className="text-xs text-zinc-400 leading-relaxed">{t("commands.admin_hint")}</p>
      </div>

      <MaintenanceCard />

      <div className="space-y-4">
        {cats.map((cat) => (
          <div key={cat.id} className="bg-[#0F0F12] border border-[#2A2A35] panel-hover" data-testid={`cmd-cat-${cat.id}`}>
            <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2A35]">
              <cat.icon size={16} style={{ color: cat.color }} className="icon-pop" />
              <span className="text-sm font-bold text-zinc-100">{cat.id === "gpu" ? `${t("commands.cat.gpu")} (${GPU_CMD[gpuBrand]?.label})` : t(`commands.cat.${cat.id}`)}</span>
            </div>
            <div>{cat.items.map((it, i) => <CmdRow key={i} item={it} onAsk={askAI} />)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
