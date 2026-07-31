import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Swords, ArrowRight, Target } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

export const ActiveMissionsCard = () => {
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "it").startsWith("en");
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/missions").then(({ data: d }) => {
      setData(d);
      (d.just_completed || []).forEach((m) => {
        toast.success(
          t("missions.completed_toast", {
            name: en ? m.name_en : m.name_it,
            xp: m.xp,
            defaultValue: `Missione completata: ${en ? m.name_en : m.name_it} (+${m.xp} XP)`,
          })
        );
      });
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return null;
  const active = data.active || [];

  return (
    <div className="border border-[#2A2A35] bg-[#0F0F12] hud-tick" data-testid="active-missions-card">
      <div className="p-4 border-b border-[#2A2A35] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Swords size={14} className="text-[#E5FF00]" />
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            {t("missions.dash_title", "Missioni attive")}
          </span>
          <span className="text-[10px] font-mono text-zinc-600">{data.slots.used}/{data.slots.max}</span>
        </div>
        <Link to="/app/milestones" data-testid="missions-see-all" className="text-[10px] font-mono uppercase text-[#E5FF00] hover:underline">
          {t("missions.dash_all", "Tutte")} →
        </Link>
      </div>
      {active.length === 0 ? (
        <Link to="/app/milestones" data-testid="missions-empty-cta" className="flex items-center gap-3 p-4 text-sm text-zinc-400 hover:text-[#E5FF00] transition-colors">
          <Target size={16} className="text-zinc-600" />
          {t("missions.dash_pick", "Nessuna missione attiva — scegli le tue missioni →")}
        </Link>
      ) : (
        <div className="divide-y divide-[#1A1A24]">
          {active.map((m) => {
            const pct = Math.max(0, Math.min(100, Math.round((m.progress / m.target) * 100)));
            return (
              <Link
                key={m.code}
                to={m.link}
                data-testid={`mission-active-${m.code}`}
                className="group flex items-center gap-4 p-4 hover:bg-[#141420] transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-sm font-semibold text-zinc-100 truncate">{en ? m.name_en : m.name_it}</span>
                    <span className="text-[10px] font-mono text-[#E5FF00] shrink-0">+{m.xp} XP</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-[#0A0A0C] border border-[#2A2A35] overflow-hidden">
                      <div className="h-full bg-[#E5FF00] transition-all duration-500" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-[10px] font-mono text-zinc-500 tabular-nums shrink-0">{m.progress}/{m.target}</span>
                  </div>
                </div>
                <span className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest text-zinc-500 group-hover:text-[#E5FF00] transition-colors shrink-0">
                  {en ? m.cta_en : m.cta_it}
                  <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
};
