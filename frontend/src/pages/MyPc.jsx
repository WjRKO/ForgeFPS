import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cpu, Activity, RefreshCw, CheckCircle2, AlertTriangle, XCircle, HelpCircle, Thermometer, MonitorDown, Sparkles, Loader2, Rocket, Pencil } from "lucide-react";
import api, { formatApiErrorDetail } from "@/lib/api";
import SpecsForm from "@/components/SpecsForm";

const SPEC_LABELS = { os: "Sistema operativo", cpu: "CPU", gpu: "GPU", ram: "RAM", disk: "Storage", motherboard: "Scheda madre", resolution: "Risoluzione" };

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
    if (d.ram_modules) x.push(`${d.ram_modules} moduli`);
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
  const color = score >= 85 ? "#00FF66" : score >= 70 ? "#E5FF00" : score >= 50 ? "#FFA500" : "#FF3B30";
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
  const [specs, setSpecs] = useState(null);
  const [health, setHealth] = useState(null);
  const [startup, setStartup] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);

  const load = async () => {
    try { const { data } = await api.get("/pc-specs"); setSpecs(data); } catch {}
    try { const { data } = await api.get("/pc-health"); setHealth(data.available ? data : null); } catch {}
  };
  useEffect(() => { load(); }, []);

  const analyzeStartup = async () => {
    setAnalyzing(true); setErr("");
    try { const { data } = await api.post("/startup/analyze"); setStartup(data); }
    catch (e) { setErr(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setAnalyzing(false); }
  };

  const hasSpecs = specs?.data?.cpu || specs?.data?.gpu;

  if (!hasSpecs || editing) {
    return (
      <div className="max-w-3xl mx-auto fade-up">
        <div className="mb-6"><div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Il mio PC</div>
          <h1 className="font-display font-black text-3xl tracking-tighter">Analisi del PC</h1></div>
        <div className="mb-4 bg-[#0F0F12] border border-[#2A2A35] p-5 text-sm text-zinc-400">
          Inserisci le tue specifiche per usare subito Advisor, Upgrade e stima FPS — <span className="text-[#E5FF00]">senza scaricare nulla</span>.
          Usa "Rileva dal browser" per compilare in automatico, oppure inserisci a mano.
        </div>
        <SpecsForm initial={specs?.data || {}}
          onSaved={(d) => { setSpecs(d); setEditing(false); load(); }}
          onCancel={hasSpecs ? () => setEditing(false) : undefined} />
        <div className="mt-4 text-center">
          <Link to="/app/desktop" data-testid="go-desktop-btn" className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-[#E5FF00] transition-colors">
            <MonitorDown size={16} /> Vuoi Health Score, temperature e ottimizzazioni reali? Usa il Desktop Agent
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <div className="mb-6 flex items-end justify-between">
        <div><div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Il mio PC</div>
          <h1 className="font-display font-black text-3xl tracking-tighter">Analisi del PC</h1></div>
        <div className="flex gap-2">
          <button data-testid="edit-specs-btn" onClick={() => setEditing(true)} className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] transition-colors"><Pencil size={15} /> Modifica</button>
          <Link to="/app/upgrade" data-testid="to-upgrade-btn" className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] transition-colors"><Rocket size={15} /> Upgrade</Link>
          <button data-testid="refresh-pc-btn" onClick={load} className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] transition-colors"><RefreshCw size={15} /> Aggiorna</button>
        </div>
      </div>

      {health && (
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-4">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4 flex items-center gap-2"><Activity size={14} className="text-[#E5FF00]" /> Health Score</div>
          <div className="flex flex-col md:flex-row gap-8 items-center">
            <ScoreRing score={health.score} grade={health.grade} />
            <div className="flex-1 w-full grid sm:grid-cols-2 gap-2">
              {health.checks.map((c, i) => (
                <div key={i} data-testid={`check-${i}`} className="flex items-start gap-2 bg-black border border-[#1A1A24] p-3">
                  {STATUS_ICON[c.status]}
                  <div className="min-w-0">
                    <div className="text-sm text-zinc-200">{c.label}</div>
                    <div className="text-xs text-zinc-500">{c.message}</div>
                    {c.fix && <div className="text-xs text-[#E5FF00] mt-1">→ {c.fix}</div>}
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
              Driver GPU: <span className="text-zinc-300">{health.driver_version}</span>
              <a href="https://www.nvidia.com/Download/index.aspx" target="_blank" rel="noreferrer" className="text-[#E5FF00] hover:underline ml-2">Controlla aggiornamenti →</a>
            </div>
          )}
        </div>
      )}

      <div className="bg-[#0F0F12] border border-[#2A2A35] mb-4">
        <div className="p-5 border-b border-[#2A2A35] text-xs uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2"><Cpu size={14} className="text-[#E5FF00]" /> Hardware</div>
        <div className="grid sm:grid-cols-2 gap-px bg-[#1A1A24]">
          {Object.entries(SPEC_LABELS).filter(([k]) => specs.data[k]).map(([k, label]) => (
            <div key={k} className="bg-[#0F0F12] p-4" data-testid={`spec-${k}`}>
              <div className="text-xs uppercase tracking-widest text-zinc-500">{label}</div>
              <div className="text-sm text-zinc-100 mt-1">{composeSpec(k, specs.data)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35]" style={{ display: (specs.startup || []).length ? "block" : "none" }}>
        <div className="p-5 border-b border-[#2A2A35] flex items-center justify-between">
          <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">Programmi all'avvio</span>
          <button data-testid="analyze-startup-btn" onClick={analyzeStartup} disabled={analyzing}
            className="flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-3 py-1.5 text-xs hover:bg-[#D4EC00] transition-colors disabled:opacity-60">
            {analyzing ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} Analizza con AI
          </button>
        </div>
        {err && <div className="p-3 text-xs text-[#FF3B30]">{err}</div>}
        {!startup && !err && <div className="p-6 text-sm text-zinc-500">{(specs.startup || []).length} programmi rilevati. Clicca "Analizza con AI" per sapere cosa disabilitare.</div>}
        {startup && (
          <div>
            <div className="p-4 text-sm text-zinc-300 border-b border-[#1A1A24] bg-black">{startup.summary}</div>
            {startup.items.map((it, i) => (
              <div key={i} className="flex items-center gap-3 p-3 border-b border-[#1A1A24]" data-testid={`startup-item-${i}`}>
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
