import { useState } from "react";
import { ScanLine, Save, Loader2, X, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "@/lib/api";
import { detectBrowserSpecs } from "@/lib/detectSpecs";

const RAM_OPTIONS = ["", "8 GB", "16 GB", "32 GB", "64 GB", "128 GB"];
const RES_OPTIONS = ["", "1920x1080", "2560x1440", "3440x1440", "3840x2160"];

const FIELD = "w-full bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm transition-colors";
const LABEL = "text-xs uppercase tracking-widest text-zinc-500";

export default function SpecsForm({ initial = {}, onSaved, onCancel }) {
  const { t } = useTranslation();
  const [f, setF] = useState({
    cpu: initial.cpu || "", gpu: initial.gpu || "", ram: initial.ram || "",
    resolution: initial.resolution || "", os: initial.os || "",
    motherboard: initial.motherboard || "", cpu_socket: initial.cpu_socket || "", chipset: initial.chipset || "",
  });
  const [saving, setSaving] = useState(false);
  const [adv, setAdv] = useState(false);

  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  const detect = () => {
    const d = detectBrowserSpecs();
    setF((s) => ({ ...s, ...Object.fromEntries(Object.entries(d).filter(([, v]) => v)) }));
    toast.success(t("specs.detected_ok"));
  };

  const save = async () => {
    if (!f.cpu && !f.gpu) { toast.error(t("specs.need_cpu_gpu")); return; }
    setSaving(true);
    try {
      const { data } = await api.post("/pc-specs", { data: f, source: "manual" });
      toast.success(t("specs.saved"));
      onSaved?.(data);
    } catch {
      toast.error(t("specs.save_err"));
    } finally { setSaving(false); }
  };

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-6" data-testid="specs-form">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">{t("specs.title")}</div>
        <div className="flex gap-2">
          <button data-testid="detect-browser-btn" onClick={detect}
            className="flex items-center gap-2 border border-[#2A2A35] px-3 py-1.5 text-xs hover:border-[#E5FF00] transition-colors">
            <ScanLine size={14} className="text-[#E5FF00]" /> {t("specs.detect")}
          </button>
          {onCancel && <button onClick={onCancel} className="text-zinc-500 hover:text-white" data-testid="specs-cancel-btn"><X size={16} /></button>}
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div><label className={LABEL}>CPU</label>
          <input data-testid="specs-cpu" value={f.cpu} onChange={set("cpu")} placeholder="es. AMD Ryzen 7 5800X" className={FIELD} /></div>
        <div><label className={LABEL}>GPU</label>
          <input data-testid="specs-gpu" value={f.gpu} onChange={set("gpu")} placeholder="es. NVIDIA RTX 3070" className={FIELD} /></div>
        <div><label className={LABEL}>{t("specs.ram")}</label>
          <select data-testid="specs-ram" value={f.ram} onChange={set("ram")} className={FIELD}>
            {RAM_OPTIONS.map((o) => <option key={o} value={o}>{o || t("specs.select")}</option>)}
          </select></div>
        <div><label className={LABEL}>{t("specs.resolution")}</label>
          <select data-testid="specs-res" value={f.resolution} onChange={set("resolution")} className={FIELD}>
            {RES_OPTIONS.map((o) => <option key={o} value={o}>{o || t("specs.select")}</option>)}
          </select></div>
        <div className="sm:col-span-2"><label className={LABEL}>{t("specs.os")}</label>
          <input data-testid="specs-os" value={f.os} onChange={set("os")} placeholder="es. Windows 11" className={FIELD} /></div>
      </div>

      <button onClick={() => setAdv((a) => !a)} className="flex items-center gap-1 text-xs text-zinc-500 hover:text-[#E5FF00] mt-4">
        <ChevronDown size={14} className={`transition-transform ${adv ? "rotate-180" : ""}`} /> {t("specs.advanced")}
      </button>
      {adv && (
        <div className="grid sm:grid-cols-3 gap-4 mt-3">
          <div><label className={LABEL}>{t("specs.motherboard")}</label>
            <input data-testid="specs-mb" value={f.motherboard} onChange={set("motherboard")} placeholder="es. ASUS TUF X570-PLUS" className={FIELD} /></div>
          <div><label className={LABEL}>{t("specs.socket")}</label>
            <input data-testid="specs-socket" value={f.cpu_socket} onChange={set("cpu_socket")} placeholder="es. AM4" className={FIELD} /></div>
          <div><label className={LABEL}>{t("specs.chipset")}</label>
            <input data-testid="specs-chipset" value={f.chipset} onChange={set("chipset")} placeholder="es. X570" className={FIELD} /></div>
        </div>
      )}

      <div className="flex items-center justify-between mt-5">
        <p className="text-xs text-zinc-600 max-w-sm">{t("specs.note")}</p>
        <button data-testid="save-specs-btn" onClick={save} disabled={saving}
          className="flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 hover:bg-[#D4EC00] transition-colors disabled:opacity-60 btn-volt">
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} {t("specs.save")}
        </button>
      </div>
    </div>
  );
}
