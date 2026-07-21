import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Trophy, Users, TrendingUp, TrendingDown, Minus } from "lucide-react";
import api from "@/lib/api";

/**
 * Ranks the user's latest benchmark against the fleet and against a segment
 * of similar hardware. Silently renders nothing when the fleet is too small
 * (<3 users) which is a valid state on a fresh install.
 */
export default function FleetPercentileCard() {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get("/benchmarks/fleet-percentile");
        if (alive) setData(data);
      } catch (e) {
        console.error("fleet-percentile failed", e);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (loading || !data?.available) return null;
  const { fleet_percentile, fleet_count, similar_percentile, similar_count, delta } = data;
  if (fleet_percentile == null && similar_percentile == null && !delta) return null;

  const barColor = (p) => (p >= 75 ? "#00FF66" : p >= 50 ? "#E5FF00" : p >= 25 ? "#FFA500" : "#FF3B30");

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick p-6 mb-4" data-testid="fleet-percentile-card">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4 flex items-center gap-2">
        <Trophy size={14} className="text-[#E5FF00]" /> {t("bench.fleet_title", { defaultValue: "Classifica FrameForge" })}
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        {fleet_percentile != null && (
          <div className="bg-black border border-[#1A1A24] p-4" data-testid="fleet-percentile-global">
            <div className="text-xs uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
              <Users size={12} /> {t("bench.fleet_global", { defaultValue: "vs. tutti gli utenti" })}
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display font-black text-4xl" style={{ color: barColor(fleet_percentile) }}>{fleet_percentile}%</span>
              <span className="text-xs text-zinc-500">{t("bench.fleet_faster", { defaultValue: "più veloce di loro" })}</span>
            </div>
            <div className="h-1.5 bg-[#1A1A24] mt-3 relative">
              <div className="h-full" style={{ width: `${fleet_percentile}%`, backgroundColor: barColor(fleet_percentile) }} />
            </div>
            <div className="text-xs text-zinc-600 mt-2">n = {fleet_count} {t("bench.fleet_users", { defaultValue: "utenti nel dataset" })}</div>
          </div>
        )}
        {similar_percentile != null && (
          <div className="bg-black border border-[#00E0FF]/30 p-4" data-testid="fleet-percentile-similar">
            <div className="text-xs uppercase tracking-widest text-[#00E0FF] flex items-center gap-1.5">
              <Users size={12} /> {t("bench.fleet_similar", { defaultValue: "vs. hardware simile" })}
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display font-black text-4xl" style={{ color: barColor(similar_percentile) }}>{similar_percentile}%</span>
              <span className="text-xs text-zinc-500">{t("bench.fleet_faster", { defaultValue: "più veloce di loro" })}</span>
            </div>
            <div className="h-1.5 bg-[#1A1A24] mt-3 relative">
              <div className="h-full" style={{ width: `${similar_percentile}%`, backgroundColor: barColor(similar_percentile) }} />
            </div>
            <div className="text-xs text-zinc-600 mt-2">n = {similar_count} {t("bench.fleet_users_similar", { defaultValue: "utenti con CPU/GPU simile" })}</div>
          </div>
        )}
      </div>

      {delta && delta.delta_pct != null && (
        <div className="mt-4 border-t border-[#1A1A24] pt-3 flex items-center gap-3" data-testid="bench-delta">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 border ${delta.improved ? "bg-[#00FF66]/10 border-[#00FF66]/50 text-[#00FF66]" : "bg-[#FF3B30]/10 border-[#FF3B30]/50 text-[#FF3B30]"}`}>
            {delta.delta_pct > 0 ? <TrendingUp size={14} /> : delta.delta_pct < 0 ? <TrendingDown size={14} /> : <Minus size={14} />}
            <span className="text-sm font-bold">{delta.delta_pct > 0 ? "+" : ""}{delta.delta_pct}%</span>
          </div>
          <div className="text-xs text-zinc-400">
            {t("bench.delta_vs_prev", { defaultValue: "vs. benchmark precedente" })}
            <span className="text-zinc-600 ml-2">({delta.previous} → {delta.current})</span>
          </div>
        </div>
      )}
    </div>
  );
}
