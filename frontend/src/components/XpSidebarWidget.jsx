import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Trophy, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

// v0.7.7 Milestone widget — piedone della sidebar.
// Mostra XP corrente + tier + progress bar verso il prossimo tier.
// Polling ogni 30s per pending_notify (toast animato on unlock).

const TIER_COLORS = {
  bronze:   { text: "text-[#C99A5A]", bar: "bg-[#C99A5A]",   ring: "border-[#C99A5A]/40" },
  silver:   { text: "text-[#B0B7C3]", bar: "bg-[#B0B7C3]",   ring: "border-[#B0B7C3]/40" },
  gold:     { text: "text-[#FFB800]", bar: "bg-[#FFB800]",   ring: "border-[#FFB800]/40" },
  platinum: { text: "text-[#00E0FF]", bar: "bg-[#00E0FF]",   ring: "border-[#00E0FF]/40" },
};

const TIER_MIN = { bronze: 0, silver: 100, gold: 300, platinum: 800 };

export function XpSidebarWidget() {
  const { t } = useTranslation();
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const shown = new Set(); // codes already toasted this session
    async function poll() {
      try {
        const { data: d } = await api.get("/milestones/me");
        if (cancelled) return;
        setData(d);
        // Toast on new pending notifications
        for (const p of (d.pending_notify || [])) {
          if (shown.has(p.code)) continue;
          shown.add(p.code);
          const displayLang = (localStorage.getItem("i18nextLng") || "it").startsWith("en") ? "en" : "it";
          const name = displayLang === "en" ? (p.name_en || p.name_it) : (p.name_it || p.name_en);
          const desc = displayLang === "en" ? (p.desc_en || p.desc_it) : (p.desc_it || p.desc_en);
          toast.success(name, {
            description: `${desc}  •  +${p.xp} XP`,
            duration: 8000,
            action: {
              label: t("milestones.view", "Vedi"),
              onClick: () => { window.location.hash = "/app/milestones"; },
            },
          });
          // Auto-dismiss server-side after showing
          api.post(`/milestones/dismiss/${p.code}`).catch(() => {});
        }
      } catch {}
    }
    poll();
    const id = setInterval(poll, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, [t]);

  if (!data) return null;
  const tier = data.tier || "bronze";
  const col = TIER_COLORS[tier] || TIER_COLORS.bronze;
  const min = TIER_MIN[tier] || 0;
  const next = data.next_tier_at || 100;
  const isMax = tier === "platinum";
  const pct = isMax ? 100 : Math.max(0, Math.min(100, Math.round(((data.xp - min) / (next - min)) * 100)));

  return (
    <NavLink
      to="/app/milestones"
      data-testid="xp-widget"
      className="block border-t border-[#2A2A35] p-3 hover:bg-[#141419] transition-colors group"
    >
      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 flex items-center justify-center border ${col.ring} ${col.text}`}>
          <Trophy size={13} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-[10px] font-black uppercase tracking-widest ${col.text}`} data-testid="xp-widget-tier">
            {tier}
          </div>
          <div className="text-xs text-zinc-300 font-mono tabular-nums" data-testid="xp-widget-xp">
            {data.xp} XP · <span className="text-zinc-500">{data.unlocked_count}/{data.total_count}</span>
          </div>
        </div>
        <ChevronRight size={13} className="text-zinc-600 group-hover:text-white transition-colors" />
      </div>
      <div className="h-1 bg-[#141419] overflow-hidden">
        <div
          className={`h-full ${col.bar} transition-all duration-500`}
          style={{ width: `${pct}%` }}
          data-testid="xp-widget-bar"
        />
      </div>
      {!isMax && (
        <div className="text-[9px] font-mono text-zinc-600 mt-1">
          {next - data.xp} XP {t("milestones.to_next", "al prossimo tier")}
        </div>
      )}
    </NavLink>
  );
}

export default XpSidebarWidget;
