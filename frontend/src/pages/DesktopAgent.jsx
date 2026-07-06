import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { MonitorDown, Download, Terminal, ShieldCheck, HardDrive, Wind, Gauge, Cpu, Activity, Copy, Check, Zap, RotateCcw, Gamepad2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const isEn = () => i18n.language?.startsWith("en");

const ACTIONS = [
  { icon: Gauge, title: "Benchmark prima/dopo", title_en: "Before/after benchmark", desc: "Misura CPU, RAM, disco e latenza di rete prima e dopo l'ottimizzazione per vedere il guadagno reale.", desc_en: "Measures CPU, RAM, disk and network latency before and after optimization to see the real gain." },
  { icon: Wind, title: "Pannello grafico a categorie", title_en: "Graphical panel by category", desc: "Il comando 'Ottimizza' apre una finestra con tab (Gaming/Latenza/Rete/Sistema), preset Competitivo/Streaming/Completo e 26 tweak con stato attuale.", desc_en: "The 'Optimize' command opens a window with tabs (Gaming/Latency/Network/System), Competitive/Streaming/Full presets and 26 tweaks with their current state." },
  { icon: Terminal, title: "Tweak pro NVIDIA/AMD/OBS", title_en: "Pro NVIDIA/AMD/OBS tweaks", desc: "MSI mode GPU (latenza DPC), MPO off (fix schermo nero OBS), timer resolution, OBS ad alta priorità, disabilita telemetria NVIDIA / ULPS AMD.", desc_en: "GPU MSI mode (DPC latency), MPO off (fixes OBS black screen), timer resolution, high-priority OBS, disable NVIDIA telemetry / AMD ULPS." },
  { icon: HardDrive, title: "Debloat & pulizia", title_en: "Debloat & cleanup", desc: "Rimuove app superflue, telemetria, ads di Windows e pulisce temp + cache Windows Update.", desc_en: "Removes bloatware, telemetry, Windows ads and cleans temp + Windows Update cache." },
  { icon: Cpu, title: "Rileva hardware/salute", title_en: "Detect hardware/health", desc: "Rileva CPU/GPU/RAM/temperature e le invia per analisi e consigli AI su misura.", desc_en: "Detects CPU/GPU/RAM/temperatures and sends them for tailored AI analysis and advice." },
  { icon: ShieldCheck, title: "Backup / Ripristino tweak", title_en: "Backup / Restore tweaks", desc: "Ogni modifica è salvata: ripristini tutto con un comando quando vuoi. Sicuro e reversibile.", desc_en: "Every change is saved: restore everything with one command whenever you want. Safe and reversible." },
];

const GPU_GUIDE = {
  nvidia: {
    label: "NVIDIA Control Panel",
    path: "Pannello di controllo NVIDIA → Gestisci impostazioni 3D → Impostazioni globali",
    path_en: "NVIDIA Control Panel → Manage 3D settings → Global settings",
    rows: [
      { s: "Modalità gestione energia", s_en: "Power management mode", v: "Prestazioni massime preferite", v_en: "Prefer maximum performance", w: "Tiene la GPU ai clock massimi, niente cali di frequenza.", w_en: "Keeps the GPU at maximum clocks, no frequency drops." },
      { s: "Modalità bassa latenza", s_en: "Low latency mode", v: "Ultra", v_en: "Ultra", w: "Riduce il ritardo di rendering: input più reattivo (competitive).", w_en: "Reduces render lag: more responsive input (competitive)." },
      { s: "Sync verticale (V-Sync)", s_en: "Vertical sync (V-Sync)", v: "Off (On solo con G-Sync)", v_en: "Off (On only with G-Sync)", w: "Meno input lag. Con G-Sync: V-Sync On + cap FPS.", w_en: "Less input lag. With G-Sync: V-Sync On + FPS cap." },
      { s: "Max Frame Rate", s_en: "Max Frame Rate", v: "3 FPS sotto il refresh (es. 141 per 144Hz)", v_en: "3 FPS below refresh (e.g. 141 for 144Hz)", w: "Con G-Sync evita tearing e mantiene la latenza minima.", w_en: "With G-Sync avoids tearing and keeps latency minimal." },
      { s: "Filtro texture - Qualità", s_en: "Texture filtering - Quality", v: "Prestazioni elevate", v_en: "High performance", w: "Più FPS con impatto visivo minimo.", w_en: "More FPS with minimal visual impact." },
      { s: "Threaded Optimization", s_en: "Threaded Optimization", v: "On", v_en: "On", w: "Distribuisce il carico driver su più core CPU.", w_en: "Spreads the driver load across multiple CPU cores." },
      { s: "Dimensione cache shader", s_en: "Shader cache size", v: "10 GB / Illimitata", v_en: "10 GB / Unlimited", w: "Meno stutter da compilazione shader.", w_en: "Less stutter from shader compilation." },
      { s: "Frequenza aggiornamento preferita", s_en: "Preferred refresh rate", v: "Massima disponibile", v_en: "Highest available", w: "Forza il refresh rate più alto del monitor.", w_en: "Forces the monitor's highest refresh rate." },
      { s: "Monitor Technology", s_en: "Monitor Technology", v: "G-SYNC (se supportato)", v_en: "G-SYNC (if supported)", w: "Sincronizzazione adattiva senza tearing.", w_en: "Adaptive sync without tearing." },
    ],
  },
  amd: {
    label: "AMD Adrenalin",
    path: "AMD Software: Adrenalin Edition → Gaming → Grafica",
    path_en: "AMD Software: Adrenalin Edition → Gaming → Graphics",
    rows: [
      { s: "Radeon Anti-Lag", s_en: "Radeon Anti-Lag", v: "Abilitato (Anti-Lag+ se disponibile)", v_en: "Enabled (Anti-Lag+ if available)", w: "Riduce la latenza di input nei giochi.", w_en: "Reduces input latency in games." },
      { s: "Radeon Chill", s_en: "Radeon Chill", v: "Disattivato", v_en: "Disabled", w: "Per competitive: nessun cap dinamico di FPS.", w_en: "For competitive: no dynamic FPS cap." },
      { s: "Wait for Vertical Refresh", s_en: "Wait for Vertical Refresh", v: "Off, salvo diversa indicazione", v_en: "Off, unless otherwise stated", w: "Meno input lag (usa FreeSync per il tearing).", w_en: "Less input lag (use FreeSync for tearing)." },
      { s: "Texture Filtering Quality", s_en: "Texture Filtering Quality", v: "Performance", v_en: "Performance", w: "Più FPS con impatto visivo minimo.", w_en: "More FPS with minimal visual impact." },
      { s: "Surface Format Optimization", s_en: "Surface Format Optimization", v: "On", v_en: "On", w: "Ottimizza l'uso della VRAM.", w_en: "Optimizes VRAM usage." },
      { s: "Tessellation Mode", s_en: "Tessellation Mode", v: "Override → AMD optimized / 8x", v_en: "Override → AMD optimized / 8x", w: "Meno carico GPU da tessellazione eccessiva.", w_en: "Less GPU load from excessive tessellation." },
      { s: "Enhanced Sync", s_en: "Enhanced Sync", v: "On (se non usi FreeSync)", v_en: "On (if not using FreeSync)", w: "Riduce tearing senza il lag del V-Sync classico.", w_en: "Reduces tearing without classic V-Sync lag." },
      { s: "FreeSync", s_en: "FreeSync", v: "On (nel monitor) + cap FPS", v_en: "On (in the monitor) + FPS cap", w: "Sincronizzazione adattiva: fluidità senza tearing.", w_en: "Adaptive sync: smoothness without tearing." },
      { s: "GPU Workload", s_en: "GPU Workload", v: "Graphics", v_en: "Graphics", w: "Massime prestazioni per il gaming (non compute).", w_en: "Maximum performance for gaming (not compute)." },
    ],
  },
};

function GpuGuide({ vendor }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState(vendor === "AMD" ? "amd" : "nvidia");
  useEffect(() => { if (vendor === "AMD") setTab("amd"); else if (vendor === "NVIDIA") setTab("nvidia"); }, [vendor]);
  const g = GPU_GUIDE[tab];
  const en = isEn();
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6" data-testid="gpu-guide-card">
      <div className="flex items-start gap-4 mb-4">
        <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center shrink-0"><Gamepad2 size={22} className="text-[#E5FF00]" /></div>
        <div>
          <h3 className="font-display font-bold text-lg">{t("desktop.gpu_title")}</h3>
          <p className="text-zinc-500 text-sm mt-1 max-w-2xl">{t("desktop.gpu_desc")}</p>
        </div>
      </div>
      <div className="flex gap-2 mb-4">
        {["nvidia", "amd"].map((k) => (
          <button key={k} data-testid={`gpu-tab-${k}`} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-bold transition-colors ${tab === k ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
            {GPU_GUIDE[k].label}{vendor === (k === "nvidia" ? "NVIDIA" : "AMD") ? ` ·  ${t("desktop.your_gpu")}` : ""}
          </button>
        ))}
      </div>
      <div className="text-xs text-zinc-500 mb-3 flex items-center gap-2"><Sparkles size={13} className="text-[#00E0FF]" /> {en ? g.path_en : g.path}</div>
      <div className="border border-[#1A1A24]">
        {g.rows.map((r, i) => (
          <div key={i} data-testid={`gpu-setting-${tab}-${i}`} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr] gap-1 sm:gap-4 p-3 border-b border-[#1A1A24] last:border-0">
            <div>
              <div className="text-sm text-zinc-200">{en ? r.s_en : r.s}</div>
              <div className="text-xs text-zinc-600 mt-0.5">{en ? r.w_en : r.w}</div>
            </div>
            <div className="text-sm font-bold text-[#00FF66] flex items-center">{en ? r.v_en : r.v}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs text-zinc-500 border-t border-[#1A1A24] pt-3">
        💡 {t("desktop.gpu_footer")}
      </div>
    </div>
  );
}

function CmdRow({ label, cmd, testid, accent }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); } catch { const t = document.createElement("textarea"); t.value = cmd; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success(i18n.t("desktop.copied")); setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="mb-3">
      <div className={`text-xs uppercase tracking-widest mb-1 ${accent || "text-zinc-500"}`}>{label}</div>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid={`${testid}-cmd`}>{cmd}</code>
        <button data-testid={`${testid}-copy`} onClick={copy}
          className="shrink-0 flex items-center gap-1 border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors text-xs">
          {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
        </button>
      </div>
    </div>
  );
}

export default function DesktopAgent() {
  const { t } = useTranslation();
  const [token, setToken] = useState("");
  const [gpuVendor, setGpuVendor] = useState(null);
  useEffect(() => { api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {}); }, []);
  useEffect(() => {
    api.get("/pc-specs").then(({ data }) => {
      const gpu = (data?.data?.gpu || "").toUpperCase();
      if (/NVIDIA|GEFORCE|RTX|GTX/.test(gpu)) setGpuVendor("NVIDIA");
      else if (/AMD|RADEON|\bRX\b/.test(gpu)) setGpuVendor("AMD");
    }).catch(() => {});
  }, []);

  const cmd = (mode) => `irm "${BACKEND}/api/agent/script?t=${token || "IL_TUO_TOKEN"}&mode=${mode}" | iex`;

  return (
    <div className="max-w-5xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("desktop.eyebrow")}</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">{t("desktop.title")}</h1>
      </div>

      {/* Quick method: PowerShell */}
      <div className="bg-[#0F0F12] border border-[#E5FF00]/40 p-6 mb-4">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-11 h-11 bg-[#E5FF00] flex items-center justify-center shrink-0"><Zap size={22} className="text-black" /></div>
          <div>
            <h2 className="font-display font-bold text-lg">{t("desktop.quick_title")}</h2>
            <p className="text-zinc-400 text-sm mt-1 max-w-2xl">{t("desktop.quick_desc")}</p>
          </div>
        </div>

        <CmdRow label={t("desktop.step_sync")} cmd={cmd("sync")} testid="ps-sync" accent="text-[#00FF66]" />
        <CmdRow label={t("desktop.step_bench")} cmd={cmd("benchmark")} testid="ps-benchmark" accent="text-[#00E0FF]" />
        <CmdRow label={t("desktop.step_optimize")} cmd={cmd("optimize")} testid="ps-optimize" accent="text-[#E5FF00]" />
        <CmdRow label={t("desktop.step_monitor")} cmd={cmd("monitor")} testid="ps-monitor" accent="text-[#FF6B00]" />
        <CmdRow label={t("desktop.step_prematch")} cmd={cmd("prematch")} testid="ps-prematch" accent="text-[#E5FF00]" />

        <div className="flex items-center gap-2 text-xs text-zinc-500 mt-2">
          <RotateCcw size={13} /> {t("desktop.restore_label")}
          <code className="text-zinc-400 truncate" data-testid="ps-restore-cmd">{cmd("restore")}</code>
        </div>
        <p className="text-xs text-zinc-600 mt-3">{t("desktop.exec_note")}</p>
      </div>

      {/* Fallback: download .py */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6">
        <div className="flex flex-col sm:flex-row items-start gap-4">
          <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center shrink-0"><MonitorDown size={22} className="text-zinc-400" /></div>
          <div className="flex-1">
            <h3 className="font-display font-semibold">{t("desktop.python_title")}</h3>
            <p className="text-zinc-500 text-sm mt-1 mb-3">{t("desktop.python_desc")}</p>
            <div className="flex flex-wrap gap-3">
              <a data-testid="download-agent-btn" href={`${API}/desktop-agent/download`}
                className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 text-sm hover:border-[#E5FF00] transition-colors">
                <Download size={16} /> {t("desktop.download_py")}
              </a>
              <Link to="/app/pc" data-testid="to-mypc-btn"
                className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 text-sm hover:border-[#E5FF00] transition-colors">
                <Activity size={16} /> {t("desktop.see_mypc")}
              </Link>
            </div>
          </div>
        </div>
      </div>

      <GpuGuide vendor={gpuVendor} />

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[#2A2A35] border border-[#2A2A35] stagger">
        {ACTIONS.map((a, i) => (
          <div key={i} className="bg-[#0F0F12] p-6 tile-hover">
            <a.icon size={20} className="text-[#E5FF00] mb-3 icon-pop" />
            <h3 className="font-display font-semibold text-base mb-1">{isEn() ? a.title_en : a.title}</h3>
            <p className="text-zinc-500 text-xs leading-relaxed">{isEn() ? a.desc_en : a.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
