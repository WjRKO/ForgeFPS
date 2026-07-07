import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Plus, Search, Loader2, RefreshCw, Trash2, Zap, TrendingDown, TrendingUp, ExternalLink, AlertTriangle, Pencil, Check, X, Target } from "lucide-react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { PageHeader, EmptyState, Badge, Sparkline, SkeletonCard, stagger, item } from "@/components/hud";

function statusOf(p) {
  if (p.current_price == null) return null;
  if (p.target_price != null && p.current_price <= p.target_price) return "target";
  if (p.initial_price != null && p.current_price < p.initial_price) return "drop";
  if (p.initial_price != null && p.current_price > p.initial_price) return "up";
  return null;
}

function ProductCard({ p, t, editing, editTitle, setEditTitle, startEdit, saveTitle, setEditing, refresh, refreshing, remove }) {
  const st = statusOf(p);
  const spark = [p.initial_price, p.lowest_price, p.current_price].filter((v) => v != null);
  const dropping = st === "drop" || st === "target";
  const diff = p.initial_price != null && p.current_price != null ? p.current_price - p.initial_price : 0;
  let progress = null;
  if (p.target_price != null && p.initial_price != null && p.initial_price > p.target_price) {
    progress = Math.max(0, Math.min(100, ((p.initial_price - p.current_price) / (p.initial_price - p.target_price)) * 100));
  }
  const untitled = p.title === "Prodotto senza titolo";

  return (
    <motion.div variants={item} data-testid={`product-row-${p.id}`}
      className="group bg-[#0F0F12] border border-[#1A1A24] hover:border-[#2A2A35] hud-tick p-4 flex flex-col transition-colors">
      <div className="flex items-start gap-3">
        <Link to={`/app/tracker/${p.id}`} className="w-12 h-12 bg-black border border-[#2A2A35] flex items-center justify-center overflow-hidden shrink-0">
          {p.image ? <img src={p.image} alt="" className="w-full h-full object-contain" /> : <Zap size={16} className="text-zinc-600" />}
        </Link>
        <div className="flex-1 min-w-0">
          {editing === p.id ? (
            <div className="flex items-center gap-1">
              <input autoFocus data-testid={`edit-title-input-${p.id}`} value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") saveTitle(p.id); if (e.key === "Escape") setEditing(null); }}
                placeholder={t("tracker.name_ph")}
                className="flex-1 bg-black border border-[#E5FF00] outline-none px-2 py-1 text-sm min-w-0" />
              <button data-testid={`save-title-${p.id}`} onClick={() => saveTitle(p.id)} className="p-1 text-[#00FF66] hover:bg-[#141419]"><Check size={14} /></button>
              <button onClick={() => setEditing(null)} className="p-1 text-zinc-500 hover:bg-[#141419]"><X size={14} /></button>
            </div>
          ) : (
            <div className="flex items-start gap-1.5">
              <Link to={`/app/tracker/${p.id}`} className={`text-sm leading-snug line-clamp-2 hover:text-[#E5FF00] transition-colors ${untitled ? "text-zinc-500 italic" : ""}`}>{untitled ? t("tracker.no_title") : p.title}</Link>
              <button data-testid={`edit-title-${p.id}`} onClick={() => startEdit(p)} className="text-zinc-600 hover:text-[#E5FF00] shrink-0 mt-0.5" title={t("tracker.edit_name")}><Pencil size={12} /></button>
            </div>
          )}
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-600 mt-1">{p.store || p.platform}</div>
        </div>
      </div>

      <div className="flex items-end justify-between mt-4">
        <div>
          <div className="font-display font-black text-2xl tracking-tighter">{p.current_price != null ? p.current_price : "—"} <span className="text-xs text-zinc-500">{p.current_price != null ? p.currency : ""}</span></div>
          {diff !== 0 && (
            <div className={`text-xs font-mono flex items-center gap-1 mt-0.5 ${diff < 0 ? "text-[#00FF66]" : "text-[#FF3B30]"}`}>
              {diff < 0 ? <TrendingDown size={12} /> : <TrendingUp size={12} />}{Math.abs(diff).toFixed(2)} {p.currency}
            </div>
          )}
        </div>
        <div className="w-24">
          <Sparkline data={spark} color={dropping ? "#00FF66" : diff > 0 ? "#FF3B30" : "#00E0FF"} />
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 flex-wrap min-h-[22px]">
        {st === "target" && <Badge tone="green" icon={Target}>{t("tracker.status_target")}</Badge>}
        {st === "drop" && <Badge tone="green" icon={TrendingDown}>{t("tracker.status_drop")}</Badge>}
        {st === "up" && <Badge tone="red" icon={TrendingUp}>{t("tracker.status_up")}</Badge>}
        {p.status && !["ok", "no_title"].includes(p.status) && <Badge tone="red" icon={AlertTriangle}>{t("tracker.manual_price")}</Badge>}
      </div>

      {progress != null && (
        <div className="mt-2">
          <div className="flex justify-between text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1">
            <span>{t("tracker.target")} {p.target_price}€</span><span>{Math.round(progress)}% {t("tracker.to_target")}</span>
          </div>
          <div className="h-1.5 bg-black border border-[#1A1A24]">
            <div className="h-full bg-[#E5FF00] transition-all duration-700" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      <div className="flex items-center justify-end gap-1 mt-3 pt-3 border-t border-[#1A1A24]">
        <a href={p.url} target="_blank" rel="noreferrer" className="p-2 text-zinc-500 hover:text-[#E5FF00] transition-colors"><ExternalLink size={15} /></a>
        <button data-testid={`refresh-${p.id}`} onClick={() => refresh(p.id)} className="p-2 text-zinc-500 hover:text-[#E5FF00] transition-colors">
          <RefreshCw size={15} className={refreshing[p.id] ? "animate-spin" : ""} />
        </button>
        <button data-testid={`delete-product-${p.id}`} onClick={() => remove(p.id)} className="p-2 text-zinc-500 hover:text-[#FF3B30] transition-colors"><Trash2 size={15} /></button>
      </div>
    </motion.div>
  );
}

export default function Tracker() {
  const { t } = useTranslation();
  const [products, setProducts] = useState(null);
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState(null);
  const [refreshing, setRefreshing] = useState({});
  const [editing, setEditing] = useState(null);
  const [editTitle, setEditTitle] = useState("");

  const load = async () => { try { const { data } = await api.get("/products"); setProducts(data); } catch { setProducts([]); } };
  useEffect(() => { load(); }, []);

  const startEdit = (p) => { setEditing(p.id); setEditTitle(p.title === "Prodotto senza titolo" ? "" : p.title); };
  const saveTitle = async (id) => {
    if (!editTitle.trim()) { setEditing(null); return; }
    try { await api.put(`/products/${id}/title`, { title: editTitle.trim() }); setEditing(null); await load(); } catch {}
  };

  const track = async (u) => {
    const target = u ?? url;
    if (!target.trim()) return;
    setAdding(true); setError("");
    try {
      await api.post("/products/track", { url: target });
      setUrl(""); setResults(null); setQuery("");
      await load();
    } catch (e) { setError(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setAdding(false); }
  };

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true); setResults(null);
    try { const { data } = await api.post("/products/search", { query }); setResults(data.results); }
    catch { setResults([]); } finally { setSearching(false); }
  };

  const refresh = async (id) => {
    setRefreshing((r) => ({ ...r, [id]: true }));
    try { await api.post(`/products/${id}/refresh`); await load(); } finally { setRefreshing((r) => ({ ...r, [id]: false })); }
  };

  const remove = async (id) => { await api.delete(`/products/${id}`); load(); };

  const groups = {};
  (products || []).forEach((p) => { if (p.group) { groups[p.group] = groups[p.group] || { count: 0, total: 0 }; groups[p.group].count++; groups[p.group].total += p.current_price || 0; } });
  const groupEntries = Object.entries(groups);

  return (
    <div className="max-w-6xl mx-auto">
      <PageHeader eyebrow={t("tracker.eyebrow")} title={t("tracker.title")} />

      <div className="grid lg:grid-cols-2 gap-4 mb-8">
        <div className="bg-[#0F0F12] border border-[#1A1A24] hud-tick p-5">
          <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-3">{t("tracker.add_url_title")}</div>
          <div className="flex gap-2">
            <input data-testid="track-url-input" value={url} onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && track()} placeholder={t("tracker.url_ph")}
              className="flex-1 bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm" />
            <button data-testid="track-btn" onClick={() => track()} disabled={adding}
              className="bg-[#E5FF00] text-black px-4 font-bold hover:bg-[#D4EC00] transition-colors disabled:opacity-60 flex items-center gap-1 btn-volt">
              {adding ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
            </button>
          </div>
          {error && <div data-testid="track-error" className="mt-2 text-xs text-[#FF3B30]">{error}</div>}
          <div className="mt-2 text-[11px] text-zinc-600">{t("tracker.stores_hint")}</div>
        </div>

        <div className="bg-[#0F0F12] border border-[#1A1A24] hud-tick p-5">
          <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-3">{t("tracker.search_title")}</div>
          <div className="flex gap-2">
            <input data-testid="search-input" value={query} onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()} placeholder={t("tracker.search_ph")}
              className="flex-1 bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm" />
            <button data-testid="search-btn" onClick={search} disabled={searching}
              className="bg-[#E5FF00] text-black px-4 font-bold hover:bg-[#D4EC00] transition-colors disabled:opacity-60 flex items-center gap-1 btn-volt">
              {searching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            </button>
          </div>
        </div>
      </div>

      {results && (
        <div className="mb-8">
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">{t("tracker.search_results")}</div>
          {results.length === 0 ? (
            <EmptyState icon={AlertTriangle} description={t("tracker.no_results")} />
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {results.map((r, i) => (
                <div key={i} className="bg-[#0F0F12] border border-[#1A1A24] hover:border-[#2A2A35] card-hover hud-tick p-4 flex flex-col">
                  <div className="h-24 bg-black border border-[#2A2A35] flex items-center justify-center mb-3 overflow-hidden">
                    {r.image ? <img src={r.image} alt="" className="h-full object-contain" /> : <Zap size={18} className="text-zinc-600" />}
                  </div>
                  <div className="text-xs text-zinc-200 line-clamp-2 flex-1">{r.title}</div>
                  <div className="flex items-center justify-between mt-3">
                    <span className="font-bold text-sm">{r.price != null ? `${r.price} €` : "n/d"}</span>
                    <button data-testid={`add-result-${i}`} onClick={() => track(r.url)} className="text-xs bg-[#E5FF00] text-black font-bold px-2 py-1 hover:bg-[#D4EC00] btn-volt">{t("tracker.track_btn")}</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">{t("tracker.tracked_title")} ({(products || []).length})</span>
      </div>

      {groupEntries.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4" data-testid="group-summary">
          {groupEntries.map(([name, g]) => (
            <div key={name} className="bg-[#0F0F12] border border-[#2A2A35] px-3 py-2">
              <div className="text-[11px] font-mono text-zinc-500 truncate max-w-[180px]">{name}</div>
              <div className="text-sm font-bold">{g.count} {t("tracker.parts")} · <span className="text-[#E5FF00]">€{g.total.toFixed(2)}</span></div>
            </div>
          ))}
        </div>
      )}

      {products === null ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{[0, 1, 2].map((i) => <SkeletonCard key={i} className="h-52" />)}</div>
      ) : products.length === 0 ? (
        <EmptyState icon={Zap} title={t("tracker.empty_title")} description={t("tracker.empty")}
          action={<button data-testid="tracker-empty-focus" onClick={() => document.querySelector('[data-testid="track-url-input"]')?.focus()}
            className="mt-2 border border-[#E5FF00] text-[#E5FF00] hover:bg-[#E5FF00] hover:text-black px-5 py-2 text-xs font-mono uppercase tracking-widest transition-colors flex items-center gap-2"><Plus size={14} /> {t("tracker.add_url_title")}</button>} />
      ) : (
        <motion.div variants={stagger} initial="hidden" animate="show" className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {products.map((p) => (
            <ProductCard key={p.id} p={p} t={t} editing={editing} editTitle={editTitle} setEditTitle={setEditTitle}
              startEdit={startEdit} saveTitle={saveTitle} setEditing={setEditing} refresh={refresh} refreshing={refreshing} remove={remove} />
          ))}
        </motion.div>
      )}
    </div>
  );
}
