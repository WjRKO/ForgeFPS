import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ScanSearch, AlertTriangle, AlertOctagon, Info, CheckCircle2 } from "lucide-react";
import api from "@/lib/api";

const SEV = {
  high: { icon: AlertOctagon, cls: "text-bad", border: "border-l-bad", badge: "bg-bad/15 text-bad" },
  medium: { icon: AlertTriangle, cls: "text-volt", border: "border-l-volt", badge: "bg-volt/15 text-volt" },
  low: { icon: Info, cls: "text-info", border: "border-l-info", badge: "bg-info/15 text-info" },
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
    <div className="bg-panel border border-hud hud-tick mb-4" data-testid="hw-insights-panel">
      <div className="p-5 border-b border-hud flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2">
          <ScanSearch size={14} className="text-volt" /> {t("hwins.title")}
        </span>
        {insights.length > 0 && (
          <span className="text-xs font-mono text-zinc-500" data-testid="hw-insights-count">
            {t("hwins.found", { count: insights.length })}
          </span>
        )}
      </div>
      {insights.length === 0 ? (
        <div className="p-5 flex items-center gap-2 text-sm text-zinc-400" data-testid="hw-insights-ok">
          <CheckCircle2 size={16} className="text-ok" /> {t("hwins.all_ok")}
        </div>
      ) : (
        <div>
          {insights.map((i, idx) => {
            const s = SEV[i.severity] || SEV.low;
            const Icon = s.icon;
            return (
              <div key={`${i.id}-${idx}`} className={`flex items-start gap-3 p-4 border-b border-hud-soft border-l-2 ${s.border}`} data-testid={`hw-insight-${i.id}`}>
                <Icon size={17} className={`${s.cls} mt-0.5 shrink-0`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-zinc-100">{t(`hwins.i.${i.id}.title`, i.params)}</span>
                    <span className={`text-[11px] font-bold uppercase px-1.5 py-0.5 ${s.badge}`}>{t(`hwins.sev.${i.severity}`)}</span>
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">{t(`hwins.i.${i.id}.desc`, i.params)}</div>
                  <div className="text-xs text-ok mt-1">→ {t(`hwins.i.${i.id}.fix`, i.params)}</div>
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
