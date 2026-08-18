import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Swords, ArrowRight } from "lucide-react";
import api from "@/lib/api";

// Striscia compatta mostrata nelle pagine di destinazione quando una missione
// attiva (normale, catena o settimanale) riguarda cio' che si fa in QUELLA pagina.
export const MissionContextStrip = ({ metrics = [] }) => {
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "it").startsWith("en");
  const [mission, setMission] = useState(null);

  useEffect(() => {
    api.get("/missions").then(({ data: d }) => {
      if (d.just_completed?.length) {
        window.dispatchEvent(new CustomEvent("ff-mission-completed", { detail: d.just_completed }));
      }
      const pool = [
        ...(!d.chain?.done ? (d.chain?.steps || []).filter((s) => s.status === "active") : []),
        ...(d.weekly?.missions || []).filter((m) => !m.completed_at),
        ...(d.active || []),
      ];
      setMission(pool.find((m) => metrics.includes(m.metric)) || null);
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!mission) return null;
  const pct = Math.max(0, Math.min(100, Math.round((mission.progress / mission.target) * 100)));

  return (
    <div className="flex items-center gap-3 border border-[#E5FF00]/40 bg-[#E5FF00]/[0.05] px-4 py-2.5 mb-5" data-testid="mission-context-strip">
      <Swords size={14} className="text-[#E5FF00] shrink-0" />
      <span className="text-[11px] font-black uppercase tracking-widest text-[#E5FF00] shrink-0">
        {t("missions.strip_label", "Missione attiva")}
      </span>
      <span className="text-sm text-zinc-200 truncate">{en ? mission.name_en : mission.name_it}</span>
      <div className="hidden sm:block flex-1 max-w-[140px] h-1.5 bg-[#0A0A0C] border border-[#2A2A35] overflow-hidden ml-auto">
        <div className="h-full bg-[#E5FF00]" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] font-mono text-zinc-400 tabular-nums shrink-0">{mission.progress}/{mission.target}</span>
      <span className="text-[11px] font-mono text-[#E5FF00] shrink-0">+{mission.xp} XP</span>
      <Link to="/app/milestones" data-testid="mission-strip-link" className="text-zinc-500 hover:text-[#E5FF00] transition-colors shrink-0">
        <ArrowRight size={13} />
      </Link>
    </div>
  );
};
