import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Swords, ArrowRight, Target, Flame } from "lucide-react";
import api from "@/lib/api";

export const ActiveMissionsCard = ({ data: dataProp }) => {
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "it").startsWith("en");
  const [fetched, setFetched] = useState(null);
  const data = dataProp !== undefined ? dataProp : fetched;

  useEffect(() => {
    if (dataProp !== undefined) return;
    api.get("/missions").then(({ data: d }) => {
      setFetched(d);
      if (d.just_completed?.length) {
        window.dispatchEvent(new CustomEvent("ff-mission-completed", { detail: d.just_completed }));
      }
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return null;
  const active = data.active || [];
  const chainStep = data.chain && !data.chain.done
    ? (data.chain.steps || []).find((s) => s.status === "active")
    : null;
  const weekly = (data.weekly?.missions || []).filter((m) => !m.completed_at);
  const daily = (data.daily?.missions || []).filter((m) => !m.completed_at);
  const streak = data.daily?.streak || 0;
  const isEmpty = active.length === 0 && !chainStep && weekly.length === 0 && daily.length === 0;

  const Row = ({ m, badge, badgeCls, testid }) => {
    const pct = Math.max(0, Math.min(100, Math.round((m.progress / m.target) * 100)));
    return (
      <Link key={m.code} to={m.link} data-testid={testid}
        className="group flex items-center gap-4 p-4 hover:bg-[#141420] transition-colors">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            {badge && (
              <span className={`text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 shrink-0 ${badgeCls}`}>{badge}</span>
            )}
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
  };

  return (
    <div className="border border-[#2A2A35] bg-[#0F0F12] hud-tick" data-testid="active-missions-card">
      <div className="p-4 border-b border-[#2A2A35] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Swords size={14} className="text-[#E5FF00]" />
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            {t("missions.dash_title", "Missioni attive")}
          </span>
          <span className="text-[10px] font-mono text-zinc-600">{data.slots.used}/{data.slots.max}</span>
          {streak > 0 && (
            <span className="flex items-center gap-0.5 text-[10px] font-mono text-[#FF9F1C]" data-testid="daily-streak-badge">
              <Flame size={11} /> {streak}
            </span>
          )}
          {data.tier && (
            <span className="text-[9px] font-black uppercase tracking-widest px-1.5 py-0.5 border border-[#2A2A35] text-zinc-400" data-testid="missions-card-tier">
              {data.tier} · {data.xp} XP
            </span>
          )}
        </div>
        <Link to="/app/milestones" data-testid="missions-see-all" className="text-[10px] font-mono uppercase text-[#E5FF00] hover:underline">
          {t("missions.dash_all", "Tutte")} →
        </Link>
      </div>
      {isEmpty ? (
        <Link to="/app/milestones" data-testid="missions-empty-cta" className="flex items-center gap-3 p-4 text-sm text-zinc-400 hover:text-[#E5FF00] transition-colors">
          <Target size={16} className="text-zinc-600" />
          {t("missions.dash_pick", "Nessuna missione attiva — scegli le tue missioni →")}
        </Link>
      ) : (
        <div className="divide-y divide-[#1A1A24]">
          {chainStep && (
            <Row m={chainStep} badge={t("missions.chain_badge", "Recluta")}
              badgeCls="bg-[#E5FF00]/15 text-[#E5FF00] border border-[#E5FF00]/40"
              testid={`mission-chain-${chainStep.code}`} />
          )}
          {daily.map((m) => (
            <Row key={m.code} m={m} badge={t("missions.daily_badge", "Oggi")}
              badgeCls="bg-[#FF9F1C]/15 text-[#FF9F1C] border border-[#FF9F1C]/40"
              testid={`mission-daily-${m.template}`} />
          ))}
          {weekly.map((m) => (
            <Row key={m.code} m={m} badge={t("missions.weekly_badge", "Week")}
              badgeCls="bg-[#00E0FF]/15 text-[#00E0FF] border border-[#00E0FF]/40"
              testid={`mission-weekly-${m.template}`} />
          ))}
          {active.map((m) => (
            <Row key={m.code} m={m} testid={`mission-active-${m.code}`} />
          ))}
        </div>
      )}
    </div>
  );
};
