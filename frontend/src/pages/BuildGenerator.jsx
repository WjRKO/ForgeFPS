import { useEffect, useState } from "react";
import { Cpu, Loader2, Save, Trash2, Zap, Sparkles } from "lucide-react";
import api, { formatApiErrorDetail } from "@/lib/api";

const USE_CASES = ["Streaming + Gaming", "Gaming competitivo (FPS)", "Streaming professionale", "Content creation + Gaming"];
const RESOLUTIONS = ["1080p", "1440p", "4K"];

function BuildCard({ data, onSave, saving }) {
  const b = data.build;
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] fade-up">
      <div className="p-6 border-b border-[#2A2A35]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-display font-bold text-2xl tracking-tight">{b.name}</h3>
            <p className="text-zinc-400 text-sm mt-2 max-w-xl">{b.summary}</p>
          </div>
          {onSave && (
            <button data-testid="save-build-btn" onClick={onSave} disabled={saving}
              className="shrink-0 flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 hover:bg-[#D4EC00] transition-colors disabled:opacity-60">
              {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Salva
            </button>
          )}
        </div>
        <div className="flex gap-6 mt-4">
          <div><div className="text-xs uppercase tracking-widest text-zinc-500">Totale stimato</div><div className="font-display font-black text-xl text-[#E5FF00]">€{b.estimated_total}</div></div>
          <div><div className="text-xs uppercase tracking-widest text-zinc-500">Performance</div><div className="font-display font-black text-xl text-[#00FF66]">{b.estimated_fps}</div></div>
        </div>
      </div>
      <div className="divide-y divide-[#1A1A24]">
        {(b.components || []).map((c, i) => (
          <div key={i} className="flex items-start gap-4 p-4">
            <div className="w-24 shrink-0 text-xs uppercase tracking-widest text-[#E5FF00] pt-0.5">{c.category}</div>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-zinc-100">{c.name}</div>
              <div className="text-xs text-zinc-500 mt-0.5">{c.reason}</div>
            </div>
            <div className="text-sm font-bold shrink-0">€{c.price}</div>
          </div>
        ))}
      </div>
      {b.streaming_tips?.length > 0 && (
        <div className="p-6 border-t border-[#2A2A35]">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2"><Sparkles size={13} className="text-[#E5FF00]" /> Streaming tips</div>
          <ul className="space-y-1.5">
            {b.streaming_tips.map((t, i) => <li key={i} className="text-sm text-zinc-400 flex gap-2"><span className="text-[#00FF66]">▸</span>{t}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function BuildGenerator() {
  const [budget, setBudget] = useState(1500);
  const [useCase, setUseCase] = useState(USE_CASES[0]);
  const [resolution, setResolution] = useState("1440p");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState([]);

  const loadSaved = async () => { try { const { data } = await api.get("/builds"); setSaved(data); } catch {} };
  useEffect(() => { loadSaved(); }, []);

  const generate = async () => {
    setLoading(true); setError(""); setResult(null);
    try {
      const { data } = await api.post("/builds/generate", { budget, use_case: useCase, resolution, notes });
      setResult(data);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || "Errore generazione");
    } finally { setLoading(false); }
  };

  const save = async () => {
    if (!result) return;
    setSaving(true);
    try { await api.post("/builds/save", result); await loadSaved(); } finally { setSaving(false); }
  };

  const remove = async (id) => { await api.delete(`/builds/${id}`); loadSaved(); };

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Build Generator</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Genera la tua build</h1>
      </div>

      <div className="grid lg:grid-cols-[340px_1fr] gap-4">
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 h-fit">
          <div className="mb-5">
            <div className="flex justify-between text-xs uppercase tracking-widest text-zinc-500 mb-2">
              <span>Budget</span><span className="text-[#E5FF00] font-bold">€{budget}</span>
            </div>
            <input data-testid="budget-slider" type="range" min="500" max="6000" step="100" value={budget}
              onChange={(e) => setBudget(Number(e.target.value))} className="w-full accent-[#E5FF00]" />
          </div>
          <div className="mb-5">
            <label className="text-xs uppercase tracking-widest text-zinc-500">Uso</label>
            <select data-testid="usecase-select" value={useCase} onChange={(e) => setUseCase(e.target.value)}
              className="w-full bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none py-2 px-2 mt-1 text-sm">
              {USE_CASES.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div className="mb-5">
            <label className="text-xs uppercase tracking-widest text-zinc-500">Risoluzione</label>
            <div className="flex gap-2 mt-1">
              {RESOLUTIONS.map((r) => (
                <button key={r} data-testid={`res-${r}`} onClick={() => setResolution(r)}
                  className={`flex-1 py-2 text-sm border transition-colors ${resolution === r ? "bg-[#E5FF00] text-black border-[#E5FF00] font-bold" : "border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>{r}</button>
              ))}
            </div>
          </div>
          <div className="mb-5">
            <label className="text-xs uppercase tracking-widest text-zinc-500">Note (opzionale)</label>
            <textarea data-testid="notes-input" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
              placeholder="es. preferenza NVIDIA, case bianco..."
              className="w-full bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none py-2 px-2 mt-1 text-sm resize-none" />
          </div>
          <button data-testid="generate-build-btn" onClick={generate} disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 hover:bg-[#D4EC00] transition-colors disabled:opacity-60">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Cpu size={16} />} Genera build
          </button>
          {error && <div data-testid="build-error" className="mt-3 text-xs text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-3 py-2">{error}</div>}
        </div>

        <div className="space-y-4">
          {loading && (
            <div className="bg-[#0F0F12] border border-[#2A2A35] p-12 flex flex-col items-center justify-center text-center">
              <Loader2 size={32} className="animate-spin text-[#E5FF00] mb-4" />
              <p className="text-zinc-400 text-sm">L'AI sta assemblando la build perfetta...</p>
            </div>
          )}
          {result && <BuildCard data={result} onSave={save} saving={saving} />}
          {!result && !loading && saved.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">Build salvate</div>
              <div className="space-y-3">
                {saved.map((s) => (
                  <div key={s.id} className="bg-[#0F0F12] border border-[#2A2A35] p-5 card-hover">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-display font-semibold">{s.build?.name}</h4>
                        <div className="text-xs text-zinc-500 mt-1">{s.use_case} · {s.resolution} · €{s.build?.estimated_total}</div>
                      </div>
                      <button data-testid={`delete-build-${s.id}`} onClick={() => remove(s.id)} className="text-zinc-500 hover:text-[#FF3B30]"><Trash2 size={16} /></button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!result && !loading && saved.length === 0 && (
            <div className="bg-[#0F0F12] border border-[#2A2A35] p-12 flex flex-col items-center justify-center text-center">
              <Zap size={32} className="text-[#E5FF00] mb-4" />
              <p className="text-zinc-400 text-sm">Configura i parametri e genera la tua prima build.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
