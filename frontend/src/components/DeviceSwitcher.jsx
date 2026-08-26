import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Monitor, Gamepad2, Video, Laptop, ChevronDown, Check } from "lucide-react";
import api from "@/lib/api";

export const ROLE_ICONS = { gaming: Gamepad2, streaming: Video, laptop: Laptop, other: Monitor };


export const DeviceSwitcher = () => {
  const { t, i18n } = useTranslation();
  const c = t("deviceswitcher", { returnObjects: true });
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    api.get("/devices").then(({ data: d }) => setData(d)).catch(() => {});
  }, []);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  if (!data || (data.devices || []).length < 2) return null;
  const active = data.devices.find((d) => d.is_active) || data.devices[0];
  const AIcon = ROLE_ICONS[active.role] || Monitor;

  const switchTo = async (d) => {
    if (d.is_active || busy) { setOpen(false); return; }
    setBusy(true);
    try {
      await api.post(`/devices/${d.device_id}/activate`);
      window.location.reload();
    } catch { setBusy(false); }
  };

  return (
    <div className="relative" ref={ref} data-testid="device-switcher">
      <button onClick={() => setOpen((o) => !o)} data-testid="device-switcher-btn"
        className="flex items-center gap-2 border border-hud px-2.5 py-1.5 text-xs text-zinc-300 hover:border-volt transition-colors max-w-[180px]">
        <AIcon size={13} className="text-volt shrink-0" />
        <span className="truncate hidden sm:inline">{active.name}</span>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${active.online ? "bg-ok" : "bg-zinc-600"}`} />
        <ChevronDown size={12} className="shrink-0 text-zinc-500" />
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-64 bg-panel border border-hud shadow-xl z-50" data-testid="device-switcher-menu">
          <div className="px-3 py-2 text-[11px] font-mono uppercase tracking-widest text-zinc-600 border-b border-hud-soft">
            {c.title} · {data.devices.length}
          </div>
          {data.devices.map((d) => {
            const I = ROLE_ICONS[d.role] || Monitor;
            return (
              <button key={d.device_id} onClick={() => switchTo(d)} data-testid={`device-option-${d.device_id}`}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-[#141420] transition-colors">
                <I size={14} className={d.is_active ? "text-volt" : "text-zinc-500"} />
                <span className="flex-1 min-w-0">
                  <span className="block text-xs text-zinc-200 truncate">{d.name}</span>
                  <span className="block text-[11px] text-zinc-600">
                    {c[d.role] || d.role}{d.health_score != null ? ` · Health ${d.health_score}` : ""}
                  </span>
                </span>
                <span className={`w-1.5 h-1.5 rounded-full ${d.online ? "bg-ok" : "bg-zinc-600"}`} />
                {d.is_active && <Check size={13} className="text-volt" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
