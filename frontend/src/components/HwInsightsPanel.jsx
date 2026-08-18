import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ScanSearch, AlertTriangle, AlertOctagon, Info, CheckCircle2 } from "lucide-react";
import api from "@/lib/api";

const SEV = {
  high: { icon: AlertOctagon, cls: "text-[#FF3B30]", border: "border-l-[#FF3B30]", badge: "bg-[#FF3B30]/15 text-[#FF3B30]" },
  medium: { icon: AlertTriangle, cls: "text-[#E5FF00]", border: "border-l-[#E5FF00]", badge: "bg-[#E5FF00]/15 text-[#E5FF00]" },
  low: { icon: Info, cls: "text-[#00E0FF]", border: "border-l-[#00E0FF]", badge: "bg-[#00E0FF]/15 text-[#00E0FF]" },
};

export const HwInsightsPanel = () => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/hw-insights").then(({ data }) => setData(data)).catch(() => setData(null));
  }, []);

  if (!data || !data.available) return null;
  const insights = data.insights || [];

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick mb-4" data-testid="hw-insights-panel">
      <div className="p-5 border-b border-[#2A2A35] flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2">
          <ScanSearch size={14} className="text-[#E5FF00]" /> {t("hwins.title")}
        </span>
        {insights.length > 0 && (
          <span className="text-xs font-mono text-zinc-500" data-testid="hw-insights-count">
            {t("hwins.found", { count: insights.length })}
          </span>
        )}
      </div>
      {insights.length === 0 ? (
        <div className="p-5 flex items-center gap-2 text-sm text-zinc-400" data-testid="hw-insights-ok">
          <CheckCircle2 size={16} className="text-[#00FF66]" /> {t("hwins.all_ok")}
        </div>
      ) : (
        <div>
          {insights.map((i, idx) => {
            const s = SEV[i.severity] || SEV.low;
            const Icon = s.icon;
            return (
              <div key={`${i.id}-${idx}`} className={`flex items-start gap-3 p-4 border-b border-[#1A1A24] border-l-2 ${s.border}`} data-testid={`hw-insight-${i.id}`}>
                <Icon size={17} className={`${s.cls} mt-0.5 shrink-0`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-zinc-100">{t(`hwins.i.${i.id}.title`, i.params)}</span>
                    <span className={`text-[11px] font-bold uppercase px-1.5 py-0.5 ${s.badge}`}>{t(`hwins.sev.${i.severity}`)}</span>
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">{t(`hwins.i.${i.id}.desc`, i.params)}</div>
                  <div className="text-xs text-[#00FF66] mt-1">→ {t(`hwins.i.${i.id}.fix`, i.params)}</div>
                </div>
              </div>
            );
          })}
          <div className="p-3 text-[11px] text-zinc-600">{t("hwins.footer")}</div>
        </div>
      )}
    </div>
  );
};
