import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { Activity } from "lucide-react";
import api from "@/lib/api";

/**
 * Compact 7-day sync activity strip: one cell per day with intensity based
 * on the number of syncs. Encourages retention (gamification) without adding
 * heavy visual weight to the MyPc dashboard.
 */
export default function SyncTimeline({ days = 7 }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get(`/pc/sync-history?days=${days}`);
        if (alive) setData(data);
      } catch (e) {
        console.error("pc/sync-history failed", e);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [days]);

  if (loading || !data) return null;
  const events = data.events || [];
  if (events.length === 0) return null;

  // Build a fixed-length calendar of the last N days (right = today).
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const byDay = new Map((data.by_day || []).map((b) => [b.day, b.count]));
  const cells = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    cells.push({ iso, count: byDay.get(iso) || 0, date: d });
  }
  const maxCount = Math.max(1, ...cells.map((c) => c.count));

  const intensity = (c) => {
    if (c.count === 0) return "#1A1A24";
    const ratio = c.count / maxCount;
    if (ratio >= 0.75) return "#00FF66";
    if (ratio >= 0.5) return "#7BE00B";
    if (ratio >= 0.25) return "#E5FF00";
    return "#4A5D00";
  };

  const lang = (i18n.resolvedLanguage || i18n.language || "en").slice(0, 2);
  const totalSyncs = events.length;
  const lastScore = events[events.length - 1]?.score;

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-4 mb-4" data-testid="sync-timeline">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
          <Activity size={12} className="text-[#00FF66]" /> {t("mypcpage.sync_activity", { defaultValue: "Attività sync" })} · {days}gg
        </div>
        <div className="text-xs text-zinc-500">
          {t("mypcpage.sync_total", { defaultValue: "Sync" })}: <span className="text-zinc-300 font-bold">{totalSyncs}</span>
          {lastScore != null && <span className="ml-3">Health: <span className="text-[#E5FF00] font-bold">{lastScore}</span></span>}
        </div>
      </div>
      <div className="flex items-end gap-1">
        {cells.map((c) => (
          <div key={c.iso} className="flex-1 group relative" data-testid={`sync-cell-${c.iso}`}>
            <div
              className="w-full transition-transform group-hover:scale-y-110 origin-bottom"
              style={{
                height: `${20 + Math.min(1, c.count / maxCount) * 28}px`,
                backgroundColor: intensity(c),
              }}
              title={`${c.date.toLocaleDateString(lang, { weekday: "short", day: "2-digit", month: "short" })} — ${c.count} sync`}
            />
            <div className="text-[10px] text-zinc-600 text-center mt-1 uppercase">
              {c.date.toLocaleDateString(lang, { weekday: "narrow" })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
