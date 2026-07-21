import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { TrendingUp } from "lucide-react";
import api from "@/lib/api";

/**
 * Mini sparkline of benchmark scores over the last N days.
 * Falls back to "overall" when the newer "score" field is missing
 * (older records only stored overall).
 */
export default function BenchmarkSparkline({ days = 30, refreshKey = 0 }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/benchmarks/history?days=${days}`);
        if (alive) setData(data);
      } catch (e) {
        console.error("benchmarks/history failed", e);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [days, refreshKey]);

  if (loading) return null;
  const points = (data?.points || [])
    .map((p) => ({ ts: p.ts, v: p.score ?? p.overall }))
    .filter((p) => p.v != null);
  if (points.length < 2) return null;

  const w = 320, h = 60, pad = 4;
  const min = Math.min(...points.map((p) => p.v));
  const max = Math.max(...points.map((p) => p.v));
  const span = Math.max(max - min, 1);
  const xs = (i) => (i / (points.length - 1)) * (w - pad * 2) + pad;
  const ys = (v) => h - pad - ((v - min) / span) * (h - pad * 2);
  const line = points.map((p, i) => `${xs(i)},${ys(p.v)}`).join(" ");
  const areaFill = `${xs(0)},${h - pad} ${line} ${xs(points.length - 1)},${h - pad}`;
  const latest = points[points.length - 1];
  const first = points[0];
  const trendPct = first.v ? Math.round(((latest.v - first.v) / first.v) * 100) : 0;

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-4 mb-4" data-testid="benchmark-sparkline">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
          <TrendingUp size={12} /> {t("bench.spark_title", { defaultValue: "Andamento" })} · {days}gg
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-zinc-600">{t("bench.spark_min", { defaultValue: "min" })}: <span className="text-zinc-300 font-bold">{min}</span></span>
          <span className="text-zinc-600">{t("bench.spark_max", { defaultValue: "max" })}: <span className="text-zinc-300 font-bold">{max}</span></span>
          <span className={`font-bold ${trendPct >= 0 ? "text-[#00FF66]" : "text-[#FF3B30]"}`}>
            {trendPct > 0 ? "+" : ""}{trendPct}%
          </span>
        </div>
      </div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="block">
        <defs>
          <linearGradient id="ff-spark-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#00E0FF" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#00E0FF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon fill="url(#ff-spark-fill)" points={areaFill} />
        <polyline fill="none" stroke="#00E0FF" strokeWidth="2" points={line} />
        {points.map((p, i) => (
          <circle key={i} cx={xs(i)} cy={ys(p.v)} r={i === points.length - 1 ? 3.5 : 2}
            fill={i === points.length - 1 ? "#E5FF00" : "#00E0FF"} />
        ))}
      </svg>
      <div className="text-xs text-zinc-600 mt-1">
        {t("bench.spark_runs", { defaultValue: "Run totali" })}: <span className="text-zinc-300 font-bold">{data?.stats?.count ?? points.length}</span>
      </div>
    </div>
  );
}
