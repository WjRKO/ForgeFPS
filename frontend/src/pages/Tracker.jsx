import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Search, Loader2, RefreshCw, Trash2, Zap, TrendingDown, TrendingUp, ExternalLink, AlertTriangle, Pencil, Check, X } from "lucide-react";
import api, { formatApiErrorDetail } from "@/lib/api";

function PriceTag({ p }) {
  if (p.current_price == null) return <span className="text-zinc-500 text-sm">n/d</span>;
  const init = p.initial_price;
  const diff = init != null ? p.current_price - init : 0;
  return (
    <div className="text-right">
      <div className="font-display font-black text-lg">{p.current_price} <span className="text-xs text-zinc-500">{p.currency}</span></div>
      {diff !== 0 && (
        <div className={`text-xs flex items-center gap-1 justify-end ${diff < 0 ? "text-[#00FF66]" : "text-[#FF3B30]"}`}>
          {diff < 0 ? <TrendingDown size={12} /> : <TrendingUp size={12} />}{Math.abs(diff).toFixed(2)}
        </div>
      )}
    </div>
  );
}

export default function Tracker() {
  const [products, setProducts] = useState([]);
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState(null);
  const [refreshing, setRefreshing] = useState({});
  const [editing, setEditing] = useState(null);
  const [editTitle, setEditTitle] = useState("");

  const load = async () => { try { const { data } = await api.get("/products"); setProducts(data); } catch {} };
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

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">// Price Tracker</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Monitoraggio prezzi</h1>
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mb-8">
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3">Traccia da URL</div>
          <div className="flex gap-2">
            <input data-testid="track-url-input" value={url} onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && track()} placeholder="Incolla link Amazon o altro store..."
              className="flex-1 bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm" />
            <button data-testid="track-btn" onClick={() => track()} disabled={adding}
              className="bg-[#E5FF00] text-black px-4 font-bold hover:bg-[#D4EC00] transition-colors disabled:opacity-60 flex items-center gap-1">
              {adding ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
            </button>
          </div>
          {error && <div data-testid="track-error" className="mt-2 text-xs text-[#FF3B30]">{error}</div>}
          <div className="mt-2 text-[11px] text-zinc-600">Store supportati: Amazon, eBay, MediaWorld, Unieuro, Euronics, Newegg e la maggior parte degli e-commerce (via link diretto).</div>
        </div>

        <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3">Cerca (Amazon + eBay)</div>
          <div className="flex gap-2">
            <input data-testid="search-input" value={query} onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()} placeholder="es. RTX 4070, Elgato..."
              className="flex-1 bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm" />
            <button data-testid="search-btn" onClick={search} disabled={searching}
              className="bg-[#E5FF00] text-black px-4 font-bold hover:bg-[#D4EC00] transition-colors disabled:opacity-60 flex items-center gap-1">
              {searching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            </button>
          </div>
        </div>
      </div>

      {results && (
        <div className="mb-8">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">Risultati ricerca</div>
          {results.length === 0 ? (
            <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 text-sm text-zinc-500 flex items-center gap-2">
              <AlertTriangle size={16} className="text-[#FF3B30]" /> Nessun risultato (lo store potrebbe aver bloccato la richiesta). Prova a incollare il link diretto.
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {results.map((r, i) => (
                <div key={i} className="bg-[#0F0F12] border border-[#2A2A35] p-4 card-hover flex flex-col">
                  <div className="h-24 bg-black border border-[#2A2A35] flex items-center justify-center mb-3 overflow-hidden">
                    {r.image ? <img src={r.image} alt="" className="h-full object-contain" /> : <Zap size={18} className="text-zinc-600" />}
                  </div>
                  <div className="text-xs text-zinc-200 line-clamp-2 flex-1">{r.title}</div>
                  <div className="flex items-center justify-between mt-3">
                    <span className="font-bold text-sm">{r.price != null ? `${r.price} €` : "n/d"}</span>
                    <button data-testid={`add-result-${i}`} onClick={() => track(r.url)} className="text-xs bg-[#E5FF00] text-black font-bold px-2 py-1 hover:bg-[#D4EC00]">Traccia</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="bg-[#0F0F12] border border-[#2A2A35]">
        <div className="p-5 border-b border-[#2A2A35] text-xs uppercase tracking-[0.2em] text-zinc-500">
          I tuoi prodotti ({products.length})
        </div>
        {(() => {
          const groups = {};
          products.forEach((p) => { if (p.group) { groups[p.group] = groups[p.group] || { count: 0, total: 0 }; groups[p.group].count++; groups[p.group].total += p.current_price || 0; } });
          const entries = Object.entries(groups);
          if (!entries.length) return null;
          return (
            <div className="p-4 border-b border-[#2A2A35] flex flex-wrap gap-2" data-testid="group-summary">
              {entries.map(([name, g]) => (
                <div key={name} className="bg-black border border-[#2A2A35] px-3 py-2">
                  <div className="text-xs text-zinc-500 truncate max-w-[180px]">{name}</div>
                  <div className="text-sm font-bold">{g.count} pezzi · <span className="text-[#E5FF00]">€{g.total.toFixed(2)}</span></div>
                </div>
              ))}
            </div>
          );
        })()}
        {products.length === 0 ? (
          <div className="p-10 text-center text-zinc-500 text-sm">Nessun prodotto tracciato. Aggiungi un link o cerca un prodotto.</div>
        ) : (
          products.map((p) => (
            <div key={p.id} data-testid={`product-row-${p.id}`} className="flex items-center gap-4 p-4 border-b border-[#1A1A24] hover:bg-[#141419] transition-colors">
              <Link to={`/app/tracker/${p.id}`} className="w-12 h-12 bg-black border border-[#2A2A35] flex items-center justify-center overflow-hidden shrink-0">
                {p.image ? <img src={p.image} alt="" className="w-full h-full object-contain" /> : <Zap size={16} className="text-zinc-600" />}
              </Link>
              {editing === p.id ? (
                <div className="flex-1 min-w-0 flex items-center gap-2">
                  <input autoFocus data-testid={`edit-title-input-${p.id}`} value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") saveTitle(p.id); if (e.key === "Escape") setEditing(null); }}
                    placeholder="Nome del prodotto..."
                    className="flex-1 bg-black border border-[#E5FF00] outline-none px-2 py-1.5 text-sm" />
                  <button data-testid={`save-title-${p.id}`} onClick={() => saveTitle(p.id)} className="p-1.5 text-[#00FF66] hover:bg-[#141419]"><Check size={15} /></button>
                  <button onClick={() => setEditing(null)} className="p-1.5 text-zinc-500 hover:bg-[#141419]"><X size={15} /></button>
                </div>
              ) : (
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Link to={`/app/tracker/${p.id}`} className={`text-sm truncate hover:text-[#E5FF00] transition-colors ${p.title === "Prodotto senza titolo" ? "text-zinc-500 italic" : ""}`}>{p.title}</Link>
                    <button data-testid={`edit-title-${p.id}`} onClick={() => startEdit(p)} className="text-zinc-600 hover:text-[#E5FF00] shrink-0" title="Modifica nome"><Pencil size={12} /></button>
                  </div>
                  <div className="text-xs text-zinc-500 flex items-center gap-2">
                    {p.store || p.platform}
                    {p.status && !["ok", "no_title"].includes(p.status) && <span className="text-[#FF3B30] flex items-center gap-1"><AlertTriangle size={11} /> prezzo manuale</span>}
                    {p.target_price != null && <span className="text-[#00FF66]">· target {p.target_price}€</span>}
                  </div>
                </div>
              )}
              <PriceTag p={p} />
              <div className="flex gap-1 shrink-0">
                <a href={p.url} target="_blank" rel="noreferrer" className="p-2 text-zinc-500 hover:text-[#E5FF00]"><ExternalLink size={15} /></a>
                <button data-testid={`refresh-${p.id}`} onClick={() => refresh(p.id)} className="p-2 text-zinc-500 hover:text-[#E5FF00]">
                  <RefreshCw size={15} className={refreshing[p.id] ? "animate-spin" : ""} />
                </button>
                <button data-testid={`delete-product-${p.id}`} onClick={() => remove(p.id)} className="p-2 text-zinc-500 hover:text-[#FF3B30]"><Trash2 size={15} /></button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
