/**
 * FullBenchmarkReport — visualizza il payload `full` inviato dall'agent in modalita' fullbench.
 *
 * Sezioni:
 *   - Header: durata, timestamp, delta vs precedente
 *   - CPU: burst vs sustained + thermal throttle flag
 *   - RAM: bandwidth L2/L3/DRAM
 *   - Disk: seq QD1 + rand 4K QD1/QD32
 *   - Network: 3 endpoint (avg/p95/loss)
 *   - Thermal Trace: line chart CPU/GPU temp nel tempo
 *
 * Empty state se `latest === null`: CTA per lanciare il test dall'agent.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Cpu, MemoryStick, HardDrive, Globe, Thermometer, Loader2, Zap, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip as ReTooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import api from "@/lib/api";
import OneClickLaunchButton from "@/components/OneClickLaunchButton";
import PlanUpgradeBanner from "@/components/PlanUpgradeBanner";
import i18n from "@/i18n";

const isEnFB = () => i18n.language?.startsWith("en");

const fmtMops = (n) => n == null ? "--" : `${n.toLocaleString()} Mops/s`;
const fmtMbps = (n) => n == null ? "--" : `${(n/1000).toFixed(1)} GB/s`;
const fmtIops = (n) => n == null ? "--" : `${n.toLocaleString()} IOPS`;
const fmtMs = (n) => n == null ? "--" : `${n} ms`;

function pctDelta(now, prev) {
  if (now == null || prev == null || prev === 0) return null;
  return ((now - prev) / prev * 100);
}

function DeltaBadge({ delta, positive = "up" }) {
  if (delta == null || Math.abs(delta) < 1) return null;
  const isImprovement = positive === "up" ? delta > 0 : delta < 0;
  const color = isImprovement ? "text-[#00FF66]" : "text-[#FF9500]";
  const Icon = delta > 0 ? TrendingUp : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] ${color} font-mono`}>
      <Icon size={10} /> {delta > 0 ? "+" : ""}{delta.toFixed(1)}%
    </span>
  );
}

function Card({ title, icon: Icon, accent, children, testid }) {
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-5" data-testid={testid}>
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-zinc-500 mb-3">
        {Icon && <Icon size={13} className={accent} />} {title}
      </div>
      {children}
    </div>
  );
}

function StatRow({ label, value, sub, deltaProps, testid }) {
  return (
    <div className="flex items-baseline justify-between border-b border-[#2A2A35]/40 py-2 last:border-b-0" data-testid={testid}>
      <div>
        <div className="text-xs text-zinc-400">{label}</div>
        {sub && <div className="text-[10px] text-zinc-600">{sub}</div>}
      </div>
      <div className="text-right">
        <div className="font-display font-bold text-lg text-white">{value}</div>
        {deltaProps && <DeltaBadge {...deltaProps} />}
      </div>
    </div>
  );
}

export default function FullBenchmarkReport() {
  const { t } = useTranslation();
  const [state, setState] = useState({ loading: true, latest: null, prev: null, history: [], locked: false, lockInfo: null });

  const load = async () => {
    try {
      const { data } = await api.get("/pc-benchmark/full");
      const hist = data?.history || [];
      setState({
        loading: false,
        latest: data?.latest || null,
        prev: hist.length > 1 ? hist[1] : null,
        history: hist,
        locked: false,
        lockInfo: null,
      });
    } catch (e) {
      // 402 = plan gate: piano insufficiente. Mostriamo l'upsell banner.
      if (e?.response?.status === 402) {
        const detail = e.response.data?.detail || {};
        setState({ loading: false, latest: null, prev: null, history: [], locked: true, lockInfo: detail });
        return;
      }
      setState({ loading: false, latest: null, prev: null, history: [], locked: false, lockInfo: null });
    }
  };

  useEffect(() => { load(); }, []);

  if (state.loading) {
    return (
      <div className="flex items-center gap-2 text-zinc-500 py-12 justify-center" data-testid="fullbench-loading">
        <Loader2 size={16} className="animate-spin" /> Caricamento Full Benchmark...
      </div>
    );
  }

  // Plan gate: utente non-Streamer -> banner upsell
  if (state.locked) {
    return (
      <PlanUpgradeBanner
        tier="streamer"
        title={t("plan_banner.fullbench.title")}
        description={t("plan_banner.fullbench.desc")}
        features={[
          { icon: Cpu, title: t("plan_banner.fullbench.f1_t"), desc: t("plan_banner.fullbench.f1_d") },
          { icon: MemoryStick, title: t("plan_banner.fullbench.f2_t"), desc: t("plan_banner.fullbench.f2_d") },
          { icon: HardDrive, title: t("plan_banner.fullbench.f3_t"), desc: t("plan_banner.fullbench.f3_d") },
          { icon: Thermometer, title: t("plan_banner.fullbench.f4_t"), desc: t("plan_banner.fullbench.f4_d") },
        ]}
        currentPlan={state.lockInfo?.current || "starter"}
        testid="fullbench-locked"
      />
    );
  }

  if (!state.latest) {
    return (
      <div className="border border-dashed border-[#2A2A35] bg-[#0A0A0F] p-8 text-center" data-testid="fullbench-empty">
        <Zap size={36} className="mx-auto text-[#E5FF00] mb-3" />
        <h3 className="font-display font-black text-xl mb-2">{isEnFB() ? "No Full Benchmark yet" : "Nessun Full Benchmark ancora"}</h3>
        <p className="text-sm text-zinc-400 mb-4 max-w-md mx-auto">
          {isEnFB() ? "The Full Benchmark measures CPU multi-thread burst+sustained, RAM L2/L3/DRAM bandwidth, multi-QD disk, extended network and thermal trace. Takes 2-4 minutes." : "Il Full Benchmark misura CPU multi-thread burst+sustained, RAM L2/L3/DRAM bandwidth, disco multi-QD, rete estesa e traccia termica. Dura 2-4 minuti."}
        </p>
        <div className="flex justify-center">
          <OneClickLaunchButton
            mode="fullbench"
            label={isEnFB() ? "Run Full Benchmark" : "Avvia Full Benchmark"}
            timeoutMs={300000}
            onLaunch={() => {}}
            detectDone={async () => {
              try {
                const { data } = await api.get("/pc-benchmark/full");
                return !!data?.latest;
              } catch { return false; }
            }}
            onDone={load}
            testid="fullbench-launch"
          />
        </div>
        <p className="text-[10px] text-zinc-600 mt-4 font-mono uppercase tracking-widest">
          richiede FrameForge Agent installato
        </p>
      </div>
    );
  }

  const f = state.latest.full;
  const pf = state.prev?.full;
  const ranAt = new Date(state.latest.created_at).toLocaleString();
  const trace = Array.isArray(f.thermal_trace) ? f.thermal_trace : [];
  const netHosts = Object.entries(f.network || {});

  return (
    <div className="space-y-6" data-testid="fullbench-report">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#0F0F12] border border-[#2A2A35] p-4">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono">Ultimo Full Benchmark</div>
          <div className="text-lg font-bold text-white" data-testid="fullbench-ran-at">{ranAt}</div>
          <div className="text-xs text-zinc-500">Durata: {f.duration_s || "--"}s · v{f.version}</div>
        </div>
        <OneClickLaunchButton
          mode="fullbench"
          label="Ripeti Full Benchmark"
          timeoutMs={300000}
          onLaunch={() => {}}
          detectDone={async () => {
            try {
              const { data } = await api.get("/pc-benchmark/full");
              if (!data?.latest) return false;
              return new Date(data.latest.created_at).getTime() > new Date(state.latest.created_at).getTime();
            } catch { return false; }
          }}
          onDone={load}
          testid="fullbench-relaunch"
        />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* CPU */}
        <Card title="CPU multi-thread" icon={Cpu} accent="text-[#00E0FF]" testid="fullbench-cpu">
          <StatRow
            label="Burst (30s)"
            value={fmtMops(f.cpu_mt_burst_mops)}
            deltaProps={{ delta: pctDelta(f.cpu_mt_burst_mops, pf?.cpu_mt_burst_mops), positive: "up" }}
            testid="cpu-burst"
          />
          <StatRow
            label="Sustained (30s dopo burst)"
            value={fmtMops(f.cpu_mt_sustained_mops)}
            sub={`Ratio ${(f.cpu_sustained_ratio*100).toFixed(1)}% vs burst`}
            deltaProps={{ delta: pctDelta(f.cpu_mt_sustained_mops, pf?.cpu_mt_sustained_mops), positive: "up" }}
            testid="cpu-sustained"
          />
          {f.cpu_thermal_throttle && (
            <div className="mt-3 flex items-start gap-2 bg-[#FF9500]/10 border border-[#FF9500]/40 p-2" data-testid="thermal-warning">
              <AlertTriangle size={14} className="text-[#FF9500] shrink-0 mt-0.5" />
              <div className="text-[11px] text-[#FFB347]">
                <strong>Thermal throttling rilevato</strong>: prestazioni scese oltre il 15% dopo 30s di carico continuo. Considera un migliore dissipatore.
              </div>
            </div>
          )}
        </Card>

        {/* RAM */}
        <Card title="RAM hierarchy" icon={MemoryStick} accent="text-[#B388FF]" testid="fullbench-ram">
          <StatRow label="L2 cache (1MB)" value={fmtMbps(f.ram_bw_l2_mbps)} deltaProps={{ delta: pctDelta(f.ram_bw_l2_mbps, pf?.ram_bw_l2_mbps), positive: "up" }} testid="ram-l2" />
          <StatRow label="L3 cache (32MB)" value={fmtMbps(f.ram_bw_l3_mbps)} deltaProps={{ delta: pctDelta(f.ram_bw_l3_mbps, pf?.ram_bw_l3_mbps), positive: "up" }} testid="ram-l3" />
          <StatRow label="DRAM (512MB)" value={fmtMbps(f.ram_bw_dram_mbps)} deltaProps={{ delta: pctDelta(f.ram_bw_dram_mbps, pf?.ram_bw_dram_mbps), positive: "up" }} testid="ram-dram" />
        </Card>

        {/* Disk */}
        <Card title="Disk I/O multi-queue" icon={HardDrive} accent="text-[#00FF66]" testid="fullbench-disk">
          <StatRow label="Sequential QD1 (128KB)" value={fmtMbps(f.disk_seq_qd1_mbps)} deltaProps={{ delta: pctDelta(f.disk_seq_qd1_mbps, pf?.disk_seq_qd1_mbps), positive: "up" }} testid="disk-seq" />
          <StatRow label="Random 4K QD1" value={fmtIops(f.disk_rand_4k_qd1_iops)} sub="Latenza a bassa profondita' (gaming)" deltaProps={{ delta: pctDelta(f.disk_rand_4k_qd1_iops, pf?.disk_rand_4k_qd1_iops), positive: "up" }} testid="disk-rand-qd1" />
          <StatRow label="Random 4K QD32" value={fmtIops(f.disk_rand_4k_qd32_iops)} sub="Async parallelo (asset streaming)" deltaProps={{ delta: pctDelta(f.disk_rand_4k_qd32_iops, pf?.disk_rand_4k_qd32_iops), positive: "up" }} testid="disk-rand-qd32" />
        </Card>

        {/* Network */}
        <Card title="Network extended (30 ping x 3 host)" icon={Globe} accent="text-[#E5FF00]" testid="fullbench-network">
          {netHosts.length === 0 && <div className="text-xs text-zinc-500">{isEnFB() ? "No network data available." : "Nessun dato rete disponibile."}</div>}
          {netHosts.map(([host, m]) => (
            <StatRow
              key={host}
              label={host}
              value={fmtMs(m.avg)}
              sub={`p95 ${m.p95}ms · min ${m.min}ms · max ${m.max}ms · loss ${m.loss_pct}%`}
              testid={`net-${host.replace(/[^a-z0-9]/gi, '_')}`}
            />
          ))}
        </Card>
      </div>

      {/* Thermal Trace Chart */}
      {trace.length > 0 && (
        <Card title="Thermal trace (temperature durante il test)" icon={Thermometer} accent="text-[#FF6B6B]" testid="fullbench-thermal">
          <div className="flex flex-wrap gap-4 mb-3 text-xs">
            <div><span className="text-zinc-500">CPU max:</span> <span className="font-bold text-white">{f.cpu_temp_max || "--"}°C</span> <span className="text-zinc-600">(avg {f.cpu_temp_avg || "--"}°C)</span></div>
            {f.gpu_temp_max > 0 && (
              <div><span className="text-zinc-500">GPU max:</span> <span className="font-bold text-white">{f.gpu_temp_max}°C</span> <span className="text-zinc-600">(avg {f.gpu_temp_avg}°C)</span></div>
            )}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trace} margin={{ top: 5, right: 15, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2A2A35" />
              <XAxis dataKey="ts" stroke="#71717A" fontSize={10} label={{ value: "secondi", position: "insideBottom", offset: -3, fill: "#71717A", fontSize: 10 }} />
              <YAxis stroke="#71717A" fontSize={10} label={{ value: "°C", angle: -90, position: "insideLeft", fill: "#71717A", fontSize: 10 }} />
              <ReTooltip
                contentStyle={{ backgroundColor: "#16161C", border: "1px solid #00E0FF", fontSize: 12 }}
                labelStyle={{ color: "#F4F4F5" }}
                itemStyle={{ color: "#F4F4F5" }}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: "#A1A1AA" }} />
              <Line type="monotone" dataKey="cpu_temp" stroke="#00E0FF" strokeWidth={2} dot={false} name="CPU °C" />
              <Line type="monotone" dataKey="gpu_temp" stroke="#B388FF" strokeWidth={2} dot={false} name="GPU °C" />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Trend History */}
      {state.history.length > 1 && (
        <Card title={`Storico Full Benchmark (ultimi ${state.history.length})`} icon={TrendingUp} accent="text-[#00E0FF]" testid="fullbench-history">
          <div className="overflow-x-auto -mx-2 px-2">
            <table className="w-full text-xs">
              <thead className="text-zinc-500 uppercase tracking-widest text-[10px]">
                <tr className="border-b border-[#2A2A35]">
                  <th className="text-left py-2">Data</th>
                  <th className="text-right py-2">CPU burst</th>
                  <th className="text-right py-2">CPU sust.</th>
                  <th className="text-right py-2">DRAM</th>
                  <th className="text-right py-2">Disk seq</th>
                  <th className="text-right py-2">CPU max °C</th>
                </tr>
              </thead>
              <tbody>
                {state.history.map((h, i) => (
                  <tr key={h.created_at} className="border-b border-[#2A2A35]/40 hover:bg-[#0F0F12]/60" data-testid={`history-row-${i}`}>
                    <td className="py-2 text-zinc-400">{new Date(h.created_at).toLocaleDateString()} {new Date(h.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                    <td className="text-right py-2 font-mono">{h.full.cpu_mt_burst_mops || "--"}</td>
                    <td className="text-right py-2 font-mono">{h.full.cpu_mt_sustained_mops || "--"}</td>
                    <td className="text-right py-2 font-mono">{h.full.ram_bw_dram_mbps ? `${(h.full.ram_bw_dram_mbps/1000).toFixed(1)}GB/s` : "--"}</td>
                    <td className="text-right py-2 font-mono">{h.full.disk_seq_qd1_mbps ? `${(h.full.disk_seq_qd1_mbps/1000).toFixed(1)}GB/s` : "--"}</td>
                    <td className="text-right py-2 font-mono">{h.full.cpu_temp_max ? `${h.full.cpu_temp_max}°` : "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
