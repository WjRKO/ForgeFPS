import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Monitor, Check, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { ROLE_ICONS } from "@/components/DeviceSwitcher";


export const DevicesPanel = () => {
  const { t, i18n } = useTranslation();
  const c = t("devicespanel", { returnObjects: true });
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null); // device_id in rename
  const [name, setName] = useState("");

  const load = () => api.get("/devices").then(({ data: d }) => setData(d)).catch(() => {});
  useEffect(() => { load(); }, []);

  if (!data || (data.devices || []).length < 2) return null;

  const save = async (did, patch) => {
    try { await api.put(`/devices/${did}`, patch); toast.success(c.renamed); setEditing(null); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const activate = async (did) => {
    try { await api.post(`/devices/${did}/activate`); window.location.reload(); } catch {}
  };
  const remove = async (did) => {
    if (!window.confirm(c.del_confirm)) return;
    try { await api.delete(`/devices/${did}`); toast.success(c.deleted); window.location.reload(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="border border-[#2A2A35] bg-[#0F0F12] hud-tick mb-6" data-testid="devices-panel">
      <div className="p-4 border-b border-[#2A2A35] flex items-center gap-2">
        <Monitor size={14} className="text-[#E5FF00]" />
        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">{c.title}</span>
        <span className="text-[10px] font-mono text-zinc-600">{data.devices.length}/{data.limit}</span>
      </div>
      <div className="divide-y divide-[#1A1A24]">
        {data.devices.map((d) => {
          const I = ROLE_ICONS[d.role] || Monitor;
          return (
            <div key={d.device_id} className="flex flex-wrap items-center gap-3 p-3" data-testid={`device-row-${d.device_id}`}>
              <I size={16} className={d.is_active ? "text-[#E5FF00]" : "text-zinc-500"} />
              <div className="flex-1 min-w-[160px]">
                {editing === d.device_id ? (
                  <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && save(d.device_id, { name })}
                    onBlur={() => save(d.device_id, { name })}
                    data-testid={`device-name-input-${d.device_id}`}
                    className="bg-black border border-[#E5FF00] px-2 py-1 text-sm outline-none w-full max-w-[220px]" />
                ) : (
                  <button onClick={() => { setEditing(d.device_id); setName(d.name); }}
                    data-testid={`device-rename-${d.device_id}`}
                    className="flex items-center gap-1.5 text-sm font-semibold text-zinc-100 hover:text-[#E5FF00] transition-colors">
                    {d.name} <Pencil size={11} className="text-zinc-600" />
                  </button>
                )}
                <div className="text-[10px] text-zinc-600 font-mono">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${d.online ? "bg-[#00FF66]" : "bg-zinc-600"}`} />
                  {c.last}: {d.last_seen ? new Date(d.last_seen).toLocaleString() : c.never}
                  {d.health_score != null && ` · Health ${d.health_score}`}
                </div>
              </div>
              <select value={d.role} onChange={(e) => save(d.device_id, { role: e.target.value })}
                data-testid={`device-role-${d.device_id}`}
                className="bg-black border border-[#2A2A35] text-xs text-zinc-300 px-2 py-1.5 outline-none focus:border-[#E5FF00]">
                {["gaming", "streaming", "laptop", "other"].map((r) => <option key={r} value={r}>{c[r]}</option>)}
              </select>
              {d.is_active ? (
                <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-[#E5FF00] border border-[#E5FF00]/40 bg-[#E5FF00]/10 px-2 py-1.5" data-testid={`device-active-${d.device_id}`}>
                  <Check size={11} /> {c.active}
                </span>
              ) : (
                <button onClick={() => activate(d.device_id)} data-testid={`device-activate-${d.device_id}`}
                  className="text-[10px] font-bold uppercase tracking-widest border border-[#2A2A35] text-zinc-400 px-2 py-1.5 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors">
                  {c.use}
                </button>
              )}
              <button onClick={() => remove(d.device_id)} data-testid={`device-delete-${d.device_id}`}
                className="text-zinc-600 hover:text-[#FF3B30] transition-colors p-1"><Trash2 size={14} /></button>
            </div>
          );
        })}
      </div>
    </div>
  );
};
