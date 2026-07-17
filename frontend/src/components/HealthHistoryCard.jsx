import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { LineChart as LineIcon } from "lucide-react";
import api from "@/lib/api";

const T = {
  it: { title: "Storico salute & temperature", sub: "Andamento nel tempo di Health Score e temperature CPU/GPU.",
        empty: "Servono almeno 2 sincronizzazioni dall'agent per mostrare l'andamento.", score: "Health Score", cpu: "Temp CPU", gpu: "Temp GPU" },
  en: { title: "Health & temperature history", sub: "Health Score and CPU/GPU temperatures over time.",
        empty: "At least 2 agent syncs are needed to show the trend.", score: "Health Score", cpu: "CPU temp", gpu: "GPU temp" },
};

const fmtTime = (iso) => {
  try {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch { return ""; }
};

export default function HealthHistoryCard() {
  const { i18n } = useTranslation();
  const c = T[i18n.language && i18n.language.startsWith("en") ? "en" : "it"];
  const [points, setPoints] = useState([]);

  useEffect(() => {
    api.get("/health-history").then(({ data }) => setPoints(data.points || [])).catch(() => {});
  }, []);

  if (!points || points.length < 2) return null;
  const rows = points.map((p) => ({ ...p, label: fmtTime(p.created_at) }));

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick p-6 mb-4" data-testid="health-history-card">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1 flex items-center gap-2">
        <LineIcon size={14} className="text-[#E5FF00]" /> {c.title}
      </div>
      <p className="text-xs text-zinc-600 mb-4">{c.sub}</p>
      <div style={{ width: "100%", height: 240 }}>
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1A1A24" />
            <XAxis dataKey="label" tick={{ fill: "#71717a", fontSize: 10 }} stroke="#2A2A35" />
            <YAxis yAxisId="score" domain={[0, 100]} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#2A2A35" />
            <YAxis yAxisId="temp" orientation="right" domain={[0, 110]} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#2A2A35" />
            <Tooltip contentStyle={{ background: "#0A0A0C", border: "1px solid #2A2A35", fontSize: 12 }} labelStyle={{ color: "#a1a1aa" }} />
            <Line yAxisId="score" type="monotone" dataKey="score" name={c.score} stroke="#E5FF00" strokeWidth={2} dot={false} connectNulls />
            <Line yAxisId="temp" type="monotone" dataKey="cpu_temp" name={c.cpu} stroke="#00E0FF" strokeWidth={2} dot={false} connectNulls />
            <Line yAxisId="temp" type="monotone" dataKey="gpu_temp" name={c.gpu} stroke="#FF3B30" strokeWidth={2} dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-4 mt-3 text-xs">
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#E5FF00]" /> {c.score}</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#00E0FF]" /> {c.cpu}</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#FF3B30]" /> {c.gpu}</span>
      </div>
    </div>
  );
}
