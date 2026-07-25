/**
 * Tweaks — pagina di selezione tweak per il FrameForge Agent.
 *
 * Legge il catalogo da GET /api/tweaks/catalog (16 tweak in 6 categorie).
 * User seleziona checkbox individuali o categorie intere -> POST /api/tweaks/apply-uri
 * ritorna URI custom-protocol firmato -> window.location = uri triggera l'agent locale.
 *
 * Filosofia UX: mostrare "why" e "impact" di ogni tweak = zero magia oscura,
 * l'utente capisce esattamente cosa sta applicando.
 */
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Zap, Gamepad2, Shield, Trash2, Cpu, Sparkles, Package,
  Check, Info, RefreshCw, ChevronDown, ChevronRight, PlayCircle, Loader2,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageHeader } from "@/components/hud";

const ICON_MAP = { zap: Zap, gamepad2: Gamepad2, shield: Shield, trash2: Trash2, cpu: Cpu, sparkles: Sparkles };

const DIFFICULTY_MAP = {
  safe: { color: "#00FF66", label_it: "SAFE", label_en: "SAFE" },
  moderate: { color: "#FFB020", label_it: "MEDIO", label_en: "MEDIUM" },
  advanced: { color: "#FF3B30", label_it: "AVANZATO", label_en: "ADVANCED" },
};

function CategorySection({ cat, catId, tweaks, selected, onToggle, onToggleAll, expanded, onExpand, en }) {
  const Icon = ICON_MAP[cat.icon] || Package;
  const allSelected = tweaks.every((t) => selected.has(t.id));
  const someSelected = tweaks.some((t) => selected.has(t.id));

  return (
    <section
      className="border border-[#1A1A24] bg-[#0F0F12]"
      data-testid={`tweak-category-${catId}`}
    >
      <header
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-[#141419] transition-colors"
        onClick={() => onExpand(catId)}
      >
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggleAll(catId, !allSelected); }}
          className={`w-5 h-5 border-2 flex items-center justify-center transition-colors shrink-0 ${
            allSelected ? "text-black" : someSelected ? "text-black" : "border-[#2A2A35]"
          }`}
          style={allSelected || someSelected ? { backgroundColor: cat.color, borderColor: cat.color } : {}}
          data-testid={`toggle-category-${catId}`}
          aria-label={`Toggle category ${catId}`}
        >
          {allSelected && <Check size={14} strokeWidth={3} />}
          {!allSelected && someSelected && <div className="w-2 h-2 bg-black" />}
        </button>
        <div className="w-10 h-10 flex items-center justify-center shrink-0" style={{ color: cat.color }}>
          <Icon size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-display font-black text-lg tracking-tight text-white">{cat.name}</h3>
            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
              [{tweaks.length}]
            </span>
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">{en ? cat.desc_en : cat.desc}</p>
        </div>
        {expanded ? <ChevronDown size={18} className="text-zinc-500" /> : <ChevronRight size={18} className="text-zinc-500" />}
      </header>

      {expanded && (
        <div className="border-t border-[#1A1A24] divide-y divide-[#1A1A24]">
          {tweaks.map((t) => {
            const diff = DIFFICULTY_MAP[t.difficulty] || DIFFICULTY_MAP.safe;
            const isSel = selected.has(t.id);
            return (
              <label
                key={t.id}
                className="flex items-start gap-3 p-4 cursor-pointer hover:bg-[#141419] transition-colors"
                data-testid={`tweak-row-${t.id}`}
              >
                <input
                  type="checkbox"
                  checked={isSel}
                  onChange={(e) => onToggle(t.id, e.target.checked)}
                  className="sr-only"
                  data-testid={`toggle-tweak-${t.id}`}
                />
                <span
                  className={`w-5 h-5 border-2 flex items-center justify-center shrink-0 mt-0.5 transition-colors ${
                    isSel ? "text-black" : "border-[#2A2A35]"
                  }`}
                  style={isSel ? { backgroundColor: cat.color, borderColor: cat.color } : {}}
                >
                  {isSel && <Check size={12} strokeWidth={3} />}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center flex-wrap gap-2 mb-1">
                    <span className="font-bold text-sm text-white">{t.name}</span>
                    <span
                      className="text-[9px] font-mono uppercase tracking-widest border px-1.5 py-0.5"
                      style={{ borderColor: `${diff.color}55`, color: diff.color }}
                    >
                      {en ? diff.label_en : diff.label_it}
                    </span>
                    {t.requires_reboot && (
                      <span className="text-[9px] font-mono uppercase tracking-widest text-[#FFB020] bg-[#FFB020]/10 border border-[#FFB020]/30 px-1.5 py-0.5">
                        {en ? "REBOOT" : "REBOOT"}
                      </span>
                    )}
                    {t.conditional && (
                      <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 bg-black/40 border border-[#2A2A35] px-1.5 py-0.5">
                        {t.conditional}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400 mb-1.5 leading-relaxed">{t.why}</p>
                  <div className="text-[11px] text-zinc-500 flex items-center gap-1 font-mono">
                    <span style={{ color: cat.color }}>▸</span> {t.impact}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function Tweaks() {
  const { i18n } = useTranslation();
  const en = (i18n.resolvedLanguage || i18n.language || "it").startsWith("en");
  const [catalog, setCatalog] = useState({ categories: {}, tweaks: [] });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [expanded, setExpanded] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/tweaks/catalog").then(({ data }) => {
      setCatalog(data);
      setLoading(false);
      // Auto-expand la prima categoria
      if (data.categories && Object.keys(data.categories).length > 0) {
        setExpanded({ [Object.keys(data.categories)[0]]: true });
      }
    }).catch(() => {
      setLoading(false);
      toast.error(en ? "Cannot load tweak catalog" : "Impossibile caricare il catalogo tweak");
    });
  }, [en]);

  const byCategory = useMemo(() => {
    const map = {};
    for (const t of catalog.tweaks || []) {
      (map[t.category] = map[t.category] || []).push(t);
    }
    return map;
  }, [catalog]);

  const toggleOne = (id, on) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(id); else next.delete(id);
      return next;
    });
  };

  const toggleCategory = (catId, on) => {
    const ids = (byCategory[catId] || []).map((t) => t.id);
    setSelected((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
      return next;
    });
  };

  const selectAll = () => setSelected(new Set((catalog.tweaks || []).map((t) => t.id)));
  const selectNone = () => setSelected(new Set());
  const recommended = () => setSelected(new Set((catalog.tweaks || []).filter((t) => t.difficulty === "safe").map((t) => t.id)));

  const applySelected = async (silent = true) => {
    if (selected.size === 0) {
      toast.error(en ? "Select at least one tweak" : "Seleziona almeno un tweak");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post("/tweaks/apply-uri", {
        tweak_ids: selected.size === 1 ? Array.from(selected) : [],
        categories: selected.size > 1 ? Object.keys(byCategory).filter((c) => (byCategory[c] || []).every((t) => selected.has(t.id))) : [],
        silent,
        action: "apply",
      });
      // Trigger protocol handler
      window.location.href = data.uri;
      toast.success(en ? `Launching agent · ${selected.size} tweaks` : `Avvio agent · ${selected.size} tweak`);
    } catch (e) {
      toast.error(en ? "Failed to generate launch URI" : "Errore nella generazione dell'URI");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto fade-up" data-testid="tweaks-page">
      <PageHeader
        eyebrow={en ? "// recipe system · v0.7.6" : "// recipe system · v0.7.6"}
        title={en ? "Windows Tweaks" : "Ottimizzazioni Windows"}
      />
      <p className="text-sm text-zinc-400 mb-6 max-w-2xl">
        {en
          ? "Every tweak has a real explanation of what it does and how much FPS/latency you gain. Choose what makes sense for you — or use 'Recommended' for a safe combo."
          : "Ogni tweak ha una spiegazione reale di cosa fa e quanto FPS/latenza ti fa guadagnare. Scegli cio' che ha senso per te — oppure usa 'Consigliati' per un mix sicuro."}
      </p>

      {loading && (
        <div className="text-center py-12 text-zinc-500 text-sm" data-testid="tweaks-loading">
          {en ? "Loading..." : "Caricamento..."}
        </div>
      )}

      {!loading && (
        <>
          {/* Toolbar */}
          <div className="mb-4 flex flex-wrap items-center gap-2 pb-4 border-b border-[#1A1A24]">
            <div className="text-xs text-zinc-500 font-mono mr-auto" data-testid="tweaks-selected-count">
              {selected.size}/{catalog.tweaks?.length || 0} {en ? "selected" : "selezionati"}
            </div>
            <button
              type="button"
              onClick={recommended}
              data-testid="btn-select-recommended"
              className="text-xs font-bold uppercase tracking-widest text-[#E5FF00] border border-[#E5FF00]/40 hover:bg-[#E5FF00]/10 px-3 py-1.5 transition-colors inline-flex items-center gap-1.5"
            >
              <Sparkles size={12} /> {en ? "Recommended" : "Consigliati"}
            </button>
            <button type="button" onClick={selectAll} data-testid="btn-select-all"
              className="text-xs uppercase tracking-widest text-zinc-400 hover:text-white border border-[#2A2A35] hover:border-zinc-500 px-3 py-1.5 transition-colors">
              {en ? "All" : "Tutti"}
            </button>
            <button type="button" onClick={selectNone} data-testid="btn-select-none"
              className="text-xs uppercase tracking-widest text-zinc-400 hover:text-white border border-[#2A2A35] hover:border-zinc-500 px-3 py-1.5 transition-colors">
              {en ? "None" : "Nessuno"}
            </button>
          </div>

          {/* Categories */}
          <div className="space-y-3">
            {Object.entries(catalog.categories || {}).map(([catId, cat]) => (
              <CategorySection
                key={catId}
                catId={catId}
                cat={cat}
                tweaks={byCategory[catId] || []}
                selected={selected}
                onToggle={toggleOne}
                onToggleAll={toggleCategory}
                expanded={!!expanded[catId]}
                onExpand={(id) => setExpanded((p) => ({ ...p, [id]: !p[id] }))}
                en={en}
              />
            ))}
          </div>

          {/* Apply footer */}
          <div className="mt-6 sticky bottom-4 flex items-center gap-3 bg-[#0F0F12] border border-[#E5FF00]/40 p-4 shadow-2xl">
            <Info size={16} className="text-[#E5FF00] shrink-0" />
            <div className="text-xs text-zinc-400 flex-1 min-w-0">
              {en
                ? "Selection is applied by the local FrameForge Agent. Not installed? Get it from the Desktop Agent page."
                : "La selezione viene applicata dal FrameForge Agent locale. Non installato? Scaricalo dalla pagina Desktop Agent."}
            </div>
            <button
              type="button"
              onClick={() => applySelected(true)}
              disabled={busy || selected.size === 0}
              data-testid="btn-apply-selected"
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold uppercase tracking-widest text-xs px-5 py-2.5 hover:bg-[#F5FF66] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {busy ? <Loader2 size={13} className="animate-spin" /> : <PlayCircle size={13} />}
              {en ? "Apply" : "Applica"} ({selected.size})
            </button>
          </div>
        </>
      )}
    </div>
  );
}
