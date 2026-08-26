import { useEffect, useState } from "react";
import { Cpu, Loader2, Save, Trash2, Zap, Sparkles, LineChart as LineIcon, ChevronDown, Crosshair, Video, Monitor } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api, { formatApiErrorDetail } from "@/lib/api";
import { HUDCard, PageHeader } from "@/components/hud";

const RESOLUTIONS = ["1080p", "1440p", "4K"];

function BuildCard({ data, onSave, saving }) {
  const { t } = useTranslation();
  const b = data.build;
  return (
    <div className="bg-panel border border-hud fade-up">
      <div className="p-6 border-b border-hud">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-display font-bold text-2xl tracking-tight">{b.name}</h3>
            <p className="text-zinc-400 text-sm mt-2 max-w-xl">{b.summary}</p>
          </div>
          {onSave && (
            <button data-testid="save-build-btn" onClick={onSave} disabled={saving}
              className="shrink-0 flex items-center gap-2 bg-volt text-black font-bold px-4 py-2 hover:bg-volt-dim transition-colors disabled:opacity-60 btn-volt">
              {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} {t("build.save")}
            </button>
          )}
        </div>
        <div className="flex gap-6 mt-4">
          <div><div className="text-xs uppercase tracking-widest text-zinc-500">{t("build.estimated_total")}</div><div className="font-display font-black text-xl text-volt">€{b.estimated_total}</div></div>
          <div><div className="text-xs uppercase tracking-widest text-zinc-500">{t("build.performance")}</div><div className="font-display font-black text-xl text-ok">{b.estimated_fps}</div></div>
        </div>
      </div>
      <div className="divide-y divide-hud-soft">
        {(b.components || []).map((c, i) => (
          <div key={i} className="flex items-start gap-4 p-4">
            <div className="w-24 shrink-0 text-xs uppercase tracking-widest text-volt pt-0.5">{c.category}</div>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-zinc-100">{c.name}</div>
              <div className="text-xs text-zinc-500 mt-0.5">{c.reason}</div>
            </div>
            <div className="text-sm font-bold shrink-0">€{c.price}</div>
          </div>
        ))}
      </div>
      {b.streaming_tips?.length > 0 && (
        <div className="p-6 border-t border-hud">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2"><Sparkles size={13} className="text-volt" /> {t("build.streaming_tips")}</div>
          <ul className="space-y-1.5">
            {b.streaming_tips.map((t, i) => <li key={i} className="text-sm text-zinc-400 flex gap-2"><span className="text-ok">▸</span>{t}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function BuildGenerator() {
  const { t } = useTranslation();
  const USE_CASES = t("build.usecases", { returnObjects: true });
  const [budget, setBudget] = useState(1500);
  const [useCase, setUseCase] = useState(USE_CASES[0]);
  const [resolution, setResolution] = useState("1440p");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState([]);

  const loadSaved = async () => {
    try { const { data } = await api.get("/builds"); setSaved(data); }
    catch (e) { console.warn("[BuildGenerator] loadSaved failed", e); }
  };
  useEffect(() => { loadSaved(); }, []);

  const generate = async (ov = {}) => {
    setLoading(true); setError(""); setResult(null);
    try {
      const { data } = await api.post("/builds/generate", { budget, use_case: useCase, resolution, notes, ...ov });
      setResult(data);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || t("build.err_generate"));
    } finally { setLoading(false); }
  };

  const save = async () => {
    if (!result) return;
    setSaving(true);
    try { await api.post("/builds/save", result); await loadSaved(); } finally { setSaving(false); }
  };

  const remove = async (id) => { await api.delete(`/builds/${id}`); loadSaved(); };

  const [openId, setOpenId] = useState(null);

  const PRESETS = [
    { id: "competitive", icon: Crosshair, budget: 1200, resolution: "1080p", ucIndex: 1 },
    { id: "streaming", icon: Video, budget: 1800, resolution: "1440p", ucIndex: 0 },
    { id: "ultra", icon: Monitor, budget: 3000, resolution: "4K", ucIndex: 3 },
  ];
  const PRESET_DEFS = t("build.preset_defs", { returnObjects: true });

  const applyPreset = (p) => {
    if (loading) return;
    const uc = USE_CASES[p.ucIndex] || USE_CASES[0];
    setBudget(p.budget); setResolution(p.resolution); setUseCase(uc);
    generate({ budget: p.budget, resolution: p.resolution, use_case: uc });
  };

  const trackBuild = async (id) => {
    try { const { data } = await api.post(`/builds/${id}/track`); toast.success(t("build.toast_tracked", { count: data.tracked })); }
    catch { toast.error(t("build.toast_track_err")); }
  };

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <PageHeader eyebrow={t("build.eyebrow")} title={t("build.title")} />

      {/* Preset one-click */}
      <div className="mb-4">
        <div className="text-[11px] uppercase tracking-[0.2em] text-zinc-600 font-bold mb-2">{t("build.presets_title")}</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {PRESETS.map((p, i) => {
            const def = PRESET_DEFS[i] || {};
            const Icon = p.icon;
            return (
              <button key={p.id} data-testid={`build-preset-${p.id}`} onClick={() => applyPreset(p)} disabled={loading}
                className="text-left bg-panel border border-hud p-4 hover:border-volt transition-colors disabled:opacity-50 group">
                <div className="flex items-center justify-between mb-1">
                  <span className="flex items-center gap-2 font-display font-bold text-sm">
                    <Icon size={15} className="text-volt" /> {def.name}
                  </span>
                  <span className="font-mono text-xs text-volt">€{p.budget}</span>
                </div>
                <div className="text-xs text-zinc-500">{def.desc} · {p.resolution}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid lg:grid-cols-[340px_1fr] gap-4">
        <HUDCard pad="p-6" className="h-fit">
          <div className="mb-5">
            <div className="flex justify-between text-xs uppercase tracking-widest text-zinc-500 mb-2">
              <span>{t("build.budget")}</span><span className="text-volt font-bold">€{budget}</span>
            </div>
            <input data-testid="budget-slider" type="range" min="500" max="6000" step="100" value={budget}
              onChange={(e) => setBudget(Number(e.target.value))} className="w-full accent-volt" />
          </div>
          <div className="mb-5">
            <label className="text-xs uppercase tracking-widest text-zinc-500">{t("build.use")}</label>
            <select data-testid="usecase-select" value={useCase} onChange={(e) => setUseCase(e.target.value)}
              className="w-full bg-black border border-hud focus:border-volt outline-none py-2 px-2 mt-1 text-sm">
              {USE_CASES.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div className="mb-5">
            <label className="text-xs uppercase tracking-widest text-zinc-500">{t("build.resolution")}</label>
            <div className="flex gap-2 mt-1">
              {RESOLUTIONS.map((r) => (
                <button key={r} data-testid={`res-${r}`} onClick={() => setResolution(r)}
                  className={`flex-1 py-2 text-sm border transition-colors ${resolution === r ? "bg-volt text-black border-volt font-bold" : "border-hud text-zinc-400 hover:border-volt"}`}>{r}</button>
              ))}
            </div>
          </div>
          <div className="mb-5">
            <label className="text-xs uppercase tracking-widest text-zinc-500">{t("build.notes")}</label>
            <textarea data-testid="notes-input" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
              placeholder={t("build.notes_ph")}
              className="w-full bg-black border border-hud focus:border-volt outline-none py-2 px-2 mt-1 text-sm resize-none" />
          </div>
          <button data-testid="generate-build-btn" onClick={() => generate()} disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-volt text-black font-bold py-3 hover:bg-volt-dim transition-colors disabled:opacity-60 btn-volt">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Cpu size={16} />} {t("build.generate")}
          </button>
          {error && <div data-testid="build-error" className="mt-3 text-xs text-bad border border-bad/40 bg-bad/10 px-3 py-2">{error}</div>}
        </HUDCard>

        <div className="space-y-4">
          {loading && (
            <div className="bg-panel border border-hud p-12 flex flex-col items-center justify-center text-center">
              <Loader2 size={32} className="animate-spin text-volt mb-4" />
              <p className="text-zinc-400 text-sm">{t("build.assembling")}</p>
            </div>
          )}
          {result && <BuildCard data={result} onSave={save} saving={saving} />}
          {!result && !loading && saved.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">{t("build.saved_builds")}</div>
              <div className="space-y-3">
                {saved.map((s) => (
                  <div key={s.id} className="bg-panel border border-hud card-hover">
                    <div className="p-5 cursor-pointer" data-testid={`saved-build-${s.id}`} onClick={() => setOpenId(openId === s.id ? null : s.id)}>
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-display font-semibold">{s.build?.name}</h4>
                          <div className="text-xs text-zinc-500 mt-1">{s.use_case} · {s.resolution} · €{s.build?.estimated_total}</div>
                        </div>
                        <div className="flex items-center gap-3">
                          <button data-testid={`delete-build-${s.id}`} onClick={(e) => { e.stopPropagation(); remove(s.id); }} className="text-zinc-500 hover:text-bad"><Trash2 size={16} /></button>
                          <ChevronDown size={16} className={`text-zinc-500 transition-transform ${openId === s.id ? "rotate-180" : ""}`} />
                        </div>
                      </div>
                      <button data-testid={`track-build-${s.id}`} onClick={(e) => { e.stopPropagation(); trackBuild(s.id); }}
                        className="mt-3 flex items-center gap-2 border border-hud px-3 py-1.5 text-xs hover:border-volt transition-colors">
                        <LineIcon size={13} /> {t("build.track_parts")}
                      </button>
                    </div>
                    {openId === s.id && (
                      <div className="border-t border-hud p-4" data-testid={`saved-build-detail-${s.id}`}>
                        <BuildCard data={s} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {!result && !loading && saved.length === 0 && (
            <div className="bg-panel border border-hud p-12 flex flex-col items-center justify-center text-center">
              <Zap size={32} className="text-volt mb-4" />
              <p className="text-zinc-400 text-sm">{t("build.empty")}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
