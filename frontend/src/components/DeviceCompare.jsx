import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Monitor, AlertTriangle } from "lucide-react";
import api from "@/lib/api";
import { ROLE_ICONS } from "@/components/DeviceSwitcher";

const T = {
  it: { title: "Confronto PC", suffering: "Sta soffrendo", health: "Health", cpu_t: "Temp CPU", gpu_t: "Temp GPU",
        cpu_u: "CPU", gpu_u: "GPU", fps: "FPS medi", nd: "n/d", active: "Attivo",
        gaming: "Gaming", streaming: "Streaming", laptop: "Laptop", other: "Altro" },
  en: { title: "PC Comparison", suffering: "Struggling", health: "Health", cpu_t: "CPU temp", gpu_t: "GPU temp",
        cpu_u: "CPU", gpu_u: "GPU", fps: "Avg FPS", nd: "n/a", active: "Active",
        gaming: "Gaming", streaming: "Streaming", laptop: "Laptop", other: "Other" },
};

const scoreColor = (s) => (s == null ? "text-zinc-600" : s >= 80 ? "text-[#00FF66]" : s >= 60 ? "text-[#E5FF00]" : "text-[#FF3B30]");

export const DeviceCompare = () => {
  const { i18n } = useTranslation();
  const c = T[(i18n.language || "it").startsWith("en") ? "en" : "it"];
  const [devs, setDevs] = useState(null);

  useEffect(() => {
    api.get("/devices/compare").then(({ data }) => setDevs(data.devices || [])).catch(() => {});
  }, []);

  if (!devs || devs.length < 2) return null;

  // Chi soffre: score piu' basso; a parita', GPU piu' calda
  const scored = devs.filter((d) => d.health?.score != null);
  let sufferer = null;
  if (scored.length >= 2) {
    sufferer = scored.reduce((worst, d) =>
      d.health.score < worst.health.score ||
      (d.health.score === worst.health.score && (d.health.gpu_temp || 0) > (worst.health.gpu_temp || 0)) ? d : worst);
  }

  const Stat = ({ label, value, unit = "", warn = false }) => (
    <div>
      <div className={`text-lg font-black tabular-nums ${warn ? "text-[#FF9F1C]" : "text-zinc-200"}`}>
        {value != null ? `${value}${unit}` : c.nd}
      </div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-600">{label}</div>
    </div>
  );

  return (
    <div className="border border-[#2A2A35] bg-[#0F0F12] hud-tick mb-6" data-testid="device-compare">
      <div className="p-4 border-b border-[#2A2A35] flex items-center gap-2">
        <Monitor size={14} className="text-[#00E0FF]" />
        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">{c.title}</span>
      </div>
      <div className={`grid grid-cols-1 ${devs.length >= 3 ? "md:grid-cols-3" : "md:grid-cols-2"} divide-y md:divide-y-0 md:divide-x divide-[#1A1A24]`}>
        {devs.map((d) => {
          const I = ROLE_ICONS[d.role] || Monitor;
          const isSuffering = sufferer && sufferer.device_id === d.device_id;
          return (
            <div key={d.device_id} className="p-4" data-testid={`compare-${d.device_id}`}>
              <div className="flex items-center gap-2 mb-3">
                <I size={15} className={d.is_active ? "text-[#E5FF00]" : "text-zinc-500"} />
                <span className="text-sm font-bold truncate">{d.name}</span>
                <span className={`w-1.5 h-1.5 rounded-full ${d.online ? "bg-[#00FF66]" : "bg-zinc-600"}`} />
                <span className="text-[9px] font-mono uppercase text-zinc-600">{c[d.role] || d.role}</span>
                {isSuffering && (
                  <span className="ml-auto flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-1.5 py-0.5" data-testid={`compare-suffering-${d.device_id}`}>
                    <AlertTriangle size={9} /> {c.suffering}
                  </span>
                )}
              </div>
              <div className="flex items-end gap-2 mb-3">
                <span className={`text-4xl font-black tabular-nums ${scoreColor(d.health?.score)}`}>{d.health?.score ?? "--"}</span>
                <span className="text-xs font-mono text-zinc-600 mb-1.5">{c.health} {d.health?.grade ? `· ${d.health.grade}` : ""}</span>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <Stat label={c.cpu_t} value={d.live?.cpu_temp ?? d.health?.cpu_temp} unit="°" warn={(d.live?.cpu_temp ?? d.health?.cpu_temp) >= 85} />
                <Stat label={c.gpu_t} value={d.live?.gpu_temp ?? d.health?.gpu_temp} unit="°" warn={(d.live?.gpu_temp ?? d.health?.gpu_temp) >= 83} />
                <Stat label={c.fps} value={d.live?.fps} />
              </div>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <Stat label={`${c.cpu_u} %`} value={d.live?.cpu_util} unit="%" />
                <Stat label={`${c.gpu_u} %`} value={d.live?.gpu_util} unit="%" />
              </div>
              <div className="text-[10px] font-mono text-zinc-600 space-y-0.5">
                {d.specs?.cpu && <div className="truncate">{d.specs.cpu}</div>}
                {d.specs?.gpu && <div className="truncate">{d.specs.gpu}</div>}
                {d.specs?.ram_gb && <div>{d.specs.ram_gb} GB RAM</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
