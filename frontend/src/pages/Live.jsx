import { useEffect, useRef, useState } from "react";
import { Activity, Cpu, Gauge, Thermometer, MemoryStick, Zap, Copy, Check, Radio } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { toast } from "sonner";
import api from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

function Stat({ icon: Icon, label, value, unit, accent, testid }) {
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-4" data-testid={testid}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-zinc-500 mb-2"><Icon size={14} className={accent} /> {label}</div>
      <div className="font-display font-black text-3xl">{value ?? "--"}<span className="text-base text-zinc-500 ml-1">{value != null ? unit : ""}</span></div>
    </div>
  );
}

export default function Live() {
  const [data, setData] = useState({ samples: [], live: false });
  const [token, setToken] = useState("");
  const [copied, setCopied] = useState(false);
  const timer = useRef(null);

  useEffect(() => { api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {}); }, []);
  useEffect(() => {
    const load = async () => { try { const { data } = await api.get("/pc-telemetry"); setData(data); } catch {} };
    load();
    timer.current = setInterval(load, 2000);
    return () => clearInterval(timer.current);
  }, []);

  const last = data.samples[data.samples.length - 1] || {};
  const chart = data.samples.map((s, i) => ({
    i, cpu: s.cpu_util ?? null, gpu: s.gpu_util ?? null, cpuT: s.cpu_temp ?? null, gpuT: s.gpu_temp ?? null,
  }));
  const cmd = `irm "${BACKEND}/api/agent/script?t=${token || "IL_TUO_TOKEN"}&mode=monitor" | iex`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); } catch { const t = document.createElement("textarea"); t.value = cmd; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); toast.success("Comando copiato!"); setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto fade-up" data-testid="live-page">
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Monitoraggio Live</div>
          <h1 className="font-display font-black text-3xl tracking-tighter">Telemetria in tempo reale</h1>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 border text-xs font-bold ${data.live ? "border-[#00FF66]/50 text-[#00FF66]" : "border-[#2A2A35] text-zinc-500"}`} data-testid="live-status">
          <Radio size={14} className={data.live ? "animate-pulse" : ""} /> {data.live ? "LIVE" : "Agent non attivo"}
        </div>
      </div>

      {!data.live && (
        <div className="bg-[#0F0F12] border border-[#E5FF00]/40 p-5 mb-6">
          <p className="text-sm text-zinc-300 mb-1 font-semibold">Avvia il monitoraggio dal tuo PC</p>
          <p className="text-xs text-zinc-500 mb-3">Apri PowerShell, incolla il comando e lascia la finestra aperta. I dati appariranno qui in tempo reale (aggiornamento ogni 2s).</p>
          <div className="flex items-stretch gap-2">
            <code className="flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs text-[#00FF66] overflow-x-auto whitespace-nowrap" data-testid="monitor-cmd">{cmd}</code>
            <button data-testid="monitor-copy" onClick={copy} className="shrink-0 flex items-center gap-1 border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors text-xs">
              {copied ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Stat icon={Cpu} label="CPU" value={last.cpu_util} unit="%" accent="text-[#E5FF00]" testid="stat-cpu" />
        <Stat icon={Gauge} label="GPU" value={last.gpu_util} unit="%" accent="text-[#00E0FF]" testid="stat-gpu" />
        <Stat icon={Thermometer} label="Temp CPU" value={last.cpu_temp} unit="°C" accent="text-[#FF6B00]" testid="stat-cpu-temp" />
        <Stat icon={Thermometer} label="Temp GPU" value={last.gpu_temp} unit="°C" accent="text-[#FF3B30]" testid="stat-gpu-temp" />
        <Stat icon={MemoryStick} label="RAM usata" value={last.ram_used_pct} unit="%" accent="text-[#00FF66]" testid="stat-ram" />
        <Stat icon={MemoryStick} label="VRAM usata" value={last.vram_used_pct} unit="%" accent="text-[#B388FF]" testid="stat-vram" />
        <Stat icon={Activity} label="Clock GPU" value={last.gpu_clock} unit="MHz" accent="text-[#00E0FF]" testid="stat-gpu-clock" />
        <Stat icon={Zap} label="Potenza GPU" value={last.gpu_power} unit="W" accent="text-[#E5FF00]" testid="stat-gpu-power" />
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4">Utilizzo & temperature (ultimi campioni)</div>
        {chart.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-zinc-600 text-sm">In attesa di dati dall'agent…</div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chart}>
              <CartesianGrid stroke="#1A1A24" strokeDasharray="3 3" />
              <XAxis dataKey="i" tick={{ fill: "#52525b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#52525b", fontSize: 10 }} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: "#0A0A0C", border: "1px solid #2A2A35", fontSize: 12 }} />
              <Line type="monotone" dataKey="cpu" name="CPU %" stroke="#E5FF00" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="monotone" dataKey="gpu" name="GPU %" stroke="#00E0FF" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="monotone" dataKey="cpuT" name="CPU °C" stroke="#FF6B00" dot={false} strokeWidth={1.5} isAnimationActive={false} />
              <Line type="monotone" dataKey="gpuT" name="GPU °C" stroke="#FF3B30" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
