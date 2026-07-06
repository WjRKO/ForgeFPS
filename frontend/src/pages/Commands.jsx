import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Terminal, Copy, Check, ShieldAlert, MessageSquareCode, Trash2, Wrench, Wifi, Zap, Package, Search, MonitorPlay, Rocket, Power, HeartPulse, AlertTriangle, Undo2, Download, CalendarClock, Sparkles } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

const CATS = [
  {
    id: "boost", title: "Boost prestazioni", icon: Rocket, color: "#E5FF00",
    items: [
      { cmd: "powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61", desc: "Sblocca il piano Ultimate Performance (il più aggressivo), poi selezionalo dalle opzioni di risparmio energia." },
      { cmd: "reg add \"HKCU\\System\\GameConfigStore\" /v GameDVR_Enabled /t REG_DWORD /d 0 /f", desc: "Disattiva Game DVR / registrazione in background: recupera FPS nei giochi.", undo: "reg add \"HKCU\\System\\GameConfigStore\" /v GameDVR_Enabled /t REG_DWORD /d 1 /f" },
      { cmd: "Disable-MMAgent -MemoryCompression", desc: "Disattiva la compressione RAM (consigliato con 16GB o più): meno carico CPU.", admin: true, undo: "Enable-MMAgent -MemoryCompression" },
      { cmd: "bcdedit /set useplatformclock false", desc: "Riduce micro-stutter forzando il timer HPET off. Testa la stabilità dopo il riavvio.", admin: true, warn: true, undo: "bcdedit /deletevalue useplatformclock" },
      { cmd: "bcdedit /set disabledynamictick yes", desc: "Disattiva il dynamic tick del kernel: latenza più costante ma consumi leggermente più alti.", admin: true, warn: true, undo: "bcdedit /set disabledynamictick no" },
    ],
  },
  {
    id: "clean", title: "Pulizia & Manutenzione", icon: Trash2, color: "#00FF66",
    items: [
      { cmd: "ipconfig /flushdns", desc: "Svuota la cache DNS: risolve siti o giochi che non si connettono." },
      { cmd: "cleanmgr /sagerun:1", desc: "Avvia la Pulizia disco per rimuovere i file temporanei di sistema." },
      { cmd: "Clear-RecycleBin -Force", desc: "Svuota il Cestino di tutti i dischi senza conferma." },
      { cmd: "wsreset.exe", desc: "Resetta la cache del Microsoft Store (fix download/app bloccate)." },
      { cmd: "Remove-Item \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue", desc: "Svuota la cartella dei file temporanei dell'utente." },
      { cmd: "Get-ChildItem \"$env:WINDIR\\SoftwareDistribution\\Download\" -Recurse | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue", desc: "Pulisce la cache dei download di Windows Update (recupera spazio).", admin: true },
      { cmd: "Dism.exe /online /Cleanup-Image /StartComponentCleanup", desc: "Rimuove i componenti e gli aggiornamenti vecchi: può liberare diversi GB.", admin: true },
    ],
  },
  {
    id: "startup", title: "Avvio più veloce", icon: Power, color: "#00E0FF",
    items: [
      { cmd: "bcdedit /timeout 3", desc: "Riduce a 3 secondi il timeout del menu di avvio.", admin: true, undo: "bcdedit /timeout 30" },
      { cmd: "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location | Format-Table -Auto", desc: "Elenca i programmi che partono all'avvio, per capire cosa disattivare." },
    ],
  },
  {
    id: "repair", title: "Riparazione sistema", icon: Wrench, color: "#E5FF00",
    items: [
      { cmd: "sfc /scannow", desc: "Cerca e ripara i file di sistema di Windows danneggiati.", admin: true },
      { cmd: "DISM /Online /Cleanup-Image /RestoreHealth", desc: "Ripara l'immagine di Windows. Eseguilo prima di sfc se il problema persiste.", admin: true },
      { cmd: "chkdsk C: /f /r", desc: "Controlla e ripara gli errori del disco C: al prossimo riavvio.", admin: true },
    ],
  },
  {
    id: "net", title: "Rete", icon: Wifi, color: "#00E0FF",
    items: [
      { cmd: "netsh winsock reset", desc: "Reset dello stack di rete Winsock: fix lag o assenza di internet. Riavvia dopo.", admin: true },
      { cmd: "netsh int ip reset", desc: "Reset della configurazione IP di Windows.", admin: true },
      { cmd: "netsh int tcp set global autotuninglevel=normal", desc: "Ripristina il tuning TCP corretto: migliora throughput e stabilità.", admin: true },
      { cmd: "ipconfig /release; ipconfig /renew", desc: "Rilascia e rinnova l'indirizzo IP assegnato dal router." },
      { cmd: "Get-NetAdapter | Restart-NetAdapter", desc: "Riavvia tutte le schede di rete senza riavviare il PC.", admin: true },
      { cmd: "Test-Connection 1.1.1.1 -Count 10", desc: "Esegue 10 ping a Cloudflare per verificare stabilità e latenza." },
    ],
  },
  {
    id: "perf", title: "Prestazioni & Gaming", icon: Zap, color: "#E5FF00",
    items: [
      { cmd: "powercfg /setactive scheme_min", desc: "Attiva il piano di alimentazione Prestazioni elevate." },
      { cmd: "powercfg /energy", desc: "Genera un report HTML sui problemi energetici e di consumo.", admin: true },
      { cmd: "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10", desc: "Mostra i 10 processi che stanno consumando più CPU adesso." },
    ],
  },
  {
    id: "apps", title: "Gestione app (winget)", icon: Package, color: "#00FF66",
    items: [
      { cmd: "winget upgrade --all", desc: "Aggiorna in un colpo solo tutti i programmi installati sul PC." },
      { cmd: "winget list", desc: "Elenca tutto il software installato con la versione." },
    ],
  },
  {
    id: "health", title: "Salute & Diagnostica", icon: HeartPulse, color: "#00E0FF",
    items: [
      { cmd: "powercfg /batteryreport", desc: "Genera un report sulla salute della batteria (portatili)." },
      { cmd: "Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object DeviceId, Wear, Temperature", desc: "Mostra usura e temperatura dei tuoi SSD/HDD." },
      { cmd: "winsat formal", desc: "Ri-esegue il benchmark ufficiale di Windows (Experience Index).", admin: true },
      { cmd: "pnputil /enum-devices /problem", desc: "Elenca i dispositivi e i driver che presentano un problema.", admin: true },
      { cmd: "DISM /Online /Cleanup-Image /AnalyzeComponentStore", desc: "Controlla se conviene pulire lo store dei componenti di Windows.", admin: true },
      { cmd: "dxdiag", desc: "Apre lo strumento di diagnostica DirectX (GPU, driver, audio)." },
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
  nvidia: { label: "GPU NVIDIA", cmd: 'Start-Process "https://www.nvidia.com/Download/index.aspx"', desc: "Apre la pagina di download dei driver GeForce Game Ready per la tua NVIDIA." },
  amd: { label: "GPU AMD", cmd: 'Start-Process "https://www.amd.com/en/support"', desc: "Apre la pagina di download dei driver AMD Adrenalin per la tua Radeon." },
  intel: { label: "GPU Intel", cmd: 'Start-Process "https://www.intel.com/content/www/us/en/download-center/home.html"', desc: "Apre il download center per i driver della tua Intel Arc." },
};

function CopyBtn({ text, testid }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); } catch { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success("Comando copiato!"); setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={copy} data-testid={testid}
      className="shrink-0 flex items-center justify-center border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors">
      {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
    </button>
  );
}

const MAINT = [
  { label: "Svuota la cache DNS", slabel: "Svuoto la cache DNS", cmd: "ipconfig /flushdns" },
  { label: "Pulisci i file temporanei utente", slabel: "Pulisco i file temporanei utente", cmd: "Remove-Item \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue" },
  { label: "Pulisci i temporanei di sistema", slabel: "Pulisco i temporanei di sistema", cmd: "Remove-Item \"$env:WINDIR\\Temp\\*\" -Recurse -Force -ErrorAction SilentlyContinue" },
  { label: "Svuota il Cestino", slabel: "Svuoto il Cestino", cmd: "Clear-RecycleBin -Force -ErrorAction SilentlyContinue" },
  { label: "Pulisci la cache di Windows Update", slabel: "Pulisco la cache di Windows Update", cmd: "Remove-Item \"$env:WINDIR\\SoftwareDistribution\\Download\\*\" -Recurse -Force -ErrorAction SilentlyContinue" },
  { label: "Resetta la cache del Microsoft Store", slabel: "Resetto la cache dello Store", cmd: "Start-Process wsreset.exe -WindowStyle Hidden" },
];

const DAYS = [
  { v: "Monday", l: "Lunedì" }, { v: "Tuesday", l: "Martedì" }, { v: "Wednesday", l: "Mercoledì" },
  { v: "Thursday", l: "Giovedì" }, { v: "Friday", l: "Venerdì" }, { v: "Saturday", l: "Sabato" }, { v: "Sunday", l: "Domenica" },
];
const TIMES = ["09:00", "12:00", "15:00", "18:00", "21:00", "03:00"];

function toB64Utf8(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach((b) => { bin += String.fromCharCode(b); });
  return btoa(bin);
}

function buildMaintScript(withBom) {
  const lines = ["Write-Host '== BoostPC - Manutenzione settimanale ==' -ForegroundColor Cyan"];
  MAINT.forEach((m, i) => {
    lines.push(`Write-Host '[${i + 1}/${MAINT.length}] ${m.slabel}...' -ForegroundColor Yellow`);
    lines.push(m.cmd);
  });
  lines.push("Write-Host 'Manutenzione completata!' -ForegroundColor Green");
  return (withBom ? "\uFEFF" : "") + lines.join("\r\n");
}

function MaintenanceCard() {
  const [day, setDay] = useState("Sunday");
  const [time, setTime] = useState("12:00");

  const oneLine = MAINT.map((m) => m.cmd).join("; ");
  const scheduleCmd = (() => {
    const b64 = toB64Utf8(buildMaintScript(true));
    return [
      `$b='${b64}'`,
      `$p="$env:LOCALAPPDATA\\BoostPC"`,
      `New-Item -ItemType Directory -Force -Path $p | Out-Null`,
      `[IO.File]::WriteAllBytes("$p\\Manutenzione.ps1",[Convert]::FromBase64String($b))`,
      `$arg='-WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$p+'\\Manutenzione.ps1"'`,
      `$a=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg`,
      `$t=New-ScheduledTaskTrigger -Weekly -DaysOfWeek ${day} -At '${time}'`,
      `Register-ScheduledTask -TaskName 'BoostPC-Manutenzione' -Action $a -Trigger $t -Description 'Manutenzione settimanale BoostPC' -Force`,
    ].join("; ");
  })();

  const download = () => {
    const blob = new Blob([buildMaintScript(true)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "BoostPC-Manutenzione.ps1"; document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success("Script scaricato! Tasto destro → Esegui con PowerShell (come Admin).");
  };

  return (
    <div className="bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/40 p-5 mb-5" data-testid="maintenance-card">
      <div className="flex items-center gap-2 text-sm font-bold mb-1 text-[#E5FF00]"><Sparkles size={16} /> Manutenzione 1-click</div>
      <p className="text-xs text-zinc-400 mb-3 leading-relaxed">Esegue in sequenza tutte le pulizie sicure. Scaricalo, eseguilo subito o pianificalo automaticamente ogni settimana.</p>

      <div className="grid sm:grid-cols-2 gap-2 mb-4">
        {MAINT.map((m, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-zinc-400"><Check size={12} className="text-[#00FF66] shrink-0" /> {m.label}</div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <button onClick={download} data-testid="maint-download"
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EC00] transition-colors">
          <Download size={15} /> Scarica script .ps1
        </button>
        <CopyBtn text={oneLine} testid="maint-oneline-copy" />
        <span className="inline-flex items-center text-xs text-zinc-500">Copia (esegui ora, PowerShell Admin)</span>
      </div>

      <div className="border-t border-[#2A2A35] pt-4">
        <div className="flex items-center gap-2 text-xs font-bold text-zinc-200 mb-2"><CalendarClock size={14} className="text-[#00E0FF]" /> Pianifica settimanale</div>
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-xs text-zinc-500">Ogni</span>
          <select value={day} onChange={(e) => setDay(e.target.value)} data-testid="maint-day"
            className="bg-black border border-[#2A2A35] text-xs text-zinc-200 px-2 py-1.5 focus:border-[#E5FF00] outline-none">
            {DAYS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
          </select>
          <span className="text-xs text-zinc-500">alle</span>
          <select value={time} onChange={(e) => setTime(e.target.value)} data-testid="maint-time"
            className="bg-black border border-[#2A2A35] text-xs text-zinc-200 px-2 py-1.5 focus:border-[#E5FF00] outline-none">
            {TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="text-xs text-zinc-500 mb-1">Copia e incolla in PowerShell (crea l'attività pianificata di Windows):</div>
        <div className="flex items-stretch gap-2">
          <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-[11px] text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="maint-schedule-cmd">{scheduleCmd}</code>
          <CopyBtn text={scheduleCmd} testid="maint-schedule-copy" />
        </div>
        <p className="text-[11px] text-zinc-600 mt-2">Per rimuovere la pianificazione: <span className="text-zinc-400">Unregister-ScheduledTask -TaskName 'BoostPC-Manutenzione' -Confirm:$false</span></p>
      </div>
    </div>
  );
}

function CmdRow({ item, onAsk }) {
  return (
    <div className="p-4 border-b border-[#1A1A24] last:border-0" data-testid={`cmd-${item.cmd.slice(0, 24)}`}>
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        {item.admin && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-1.5 py-0.5" data-testid="admin-badge">
            <ShieldAlert size={11} /> Richiede Admin
          </span>
        )}
        {item.warn && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#E5FF00] border border-[#E5FF00]/40 bg-[#E5FF00]/10 px-1.5 py-0.5" data-testid="warn-badge">
            <AlertTriangle size={11} /> Avanzato
          </span>
        )}
        <span className="text-xs text-zinc-500 leading-relaxed">{item.desc}</span>
      </div>

      {item.warn && (
        <div className="text-[11px] text-[#E5FF00]/80 leading-relaxed mb-2">
          Tweak spinto: applicalo solo se sai cosa fai e testa la stabilità dopo il riavvio. In caso di problemi usa il comando "Annulla" qui sotto.
        </div>
      )}

      <div className="flex items-stretch gap-2">
        <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap">{item.cmd}</code>
        <CopyBtn text={item.cmd} testid="cmd-copy" />
        <button onClick={() => onAsk(item)} data-testid="cmd-ask-ai"
          className="shrink-0 inline-flex items-center gap-1 border border-[#2A2A35] px-2.5 text-[11px] text-zinc-400 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors whitespace-nowrap">
          <MessageSquareCode size={12} /> Chiedi all'AI
        </button>
      </div>

      {item.undo && (
        <div className="flex items-stretch gap-2 mt-2">
          <div className="shrink-0 flex items-center gap-1 text-[11px] text-zinc-500 px-1"><Undo2 size={12} /> Annulla:</div>
          <code className="flex-1 bg-black/60 border border-[#2A2A35] px-3 py-2 text-[11px] text-zinc-400 overflow-x-auto whitespace-nowrap">{item.undo}</code>
          <CopyBtn text={item.undo} testid="cmd-undo-copy" />
        </div>
      )}
    </div>
  );
}

export default function Commands() {
  const [specs, setSpecs] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
  }, []);

  const data = specs?.data || {};
  const gpuBrand = useMemo(() => detectGpu(data.gpu), [specs]);

  const cats = useMemo(() => {
    const list = [...CATS];
    const g = gpuBrand && GPU_CMD[gpuBrand];
    if (g) {
      list.push({
        id: "gpu", title: `Driver GPU (${g.label})`, icon: MonitorPlay, color: "#00FF66",
        items: [g, { cmd: "dxdiag", desc: "Verifica il modello GPU e la versione driver attualmente installati." }],
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
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Toolbox</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Comandi Utili</h1>
        <p className="text-zinc-500 text-sm mt-1">Comandi quotidiani per manutenzione, pulizia e boost. Copia e incolla nel Terminale.</p>
      </div>

      <div className="bg-black border border-[#2A2A35] p-4 flex gap-3 items-start mb-5">
        <Terminal size={16} className="text-[#00E0FF] shrink-0 mt-0.5" />
        <p className="text-xs text-zinc-400 leading-relaxed">
          Per i comandi con <span className="text-[#FF3B30] font-bold">Richiede Admin</span>: apri <span className="text-zinc-200">PowerShell come amministratore</span> (tasto destro su Start → "Terminale (Admin)"). I comandi <span className="text-[#E5FF00] font-bold">Avanzato</span> modificano parametri di sistema: usali con cautela e sfrutta il comando "Annulla".
        </p>
      </div>

      <MaintenanceCard />

      <div className="space-y-4">
        {cats.map((cat) => (
          <div key={cat.id} className="bg-[#0F0F12] border border-[#2A2A35]" data-testid={`cmd-cat-${cat.id}`}>
            <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2A35]">
              <cat.icon size={16} style={{ color: cat.color }} />
              <span className="text-sm font-bold text-zinc-100">{cat.title}</span>
            </div>
            <div>{cat.items.map((it, i) => <CmdRow key={i} item={it} onAsk={askAI} />)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
