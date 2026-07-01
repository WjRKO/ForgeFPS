import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, RefreshCw, ExternalLink, Zap, Target, Euro, Loader2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import api from "@/lib/api";

export default function ProductDetail() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [manual, setManual] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const { data } = await api.get(`/products/${id}`);
    setP(data);
    setTarget(data.target_price ?? "");
  };
  useEffect(() => { load(); }, [id]);

  const refresh = async () => { setBusy(true); try { await api.post(`/products/${id}/refresh`); await load(); } finally { setBusy(false); } };
  const saveManual = async () => { if (!manual) return; await api.put(`/products/${id}/price`, { price: Number(manual) }); setManual(""); load(); };
  const saveTarget = async () => { if (target === "") return; await api.put(`/products/${id}/target`, { target_price: Number(target) }); load(); };

  if (!p) return <div className="max-w-4xl mx-auto"><Loader2 className="animate-spin text-[#E5FF00]" /></div>;

  const chartData = (p.history || []).map((h) => ({
    date: new Date(h.recorded_at).toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit" }),
    price: h.price,
  }));

  return (
    <div className="max-w-4xl mx-auto fade-up">
      <Link to="/app/tracker" className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-[#E5FF00] mb-6" data-testid="back-btn">
        <ArrowLeft size={16} /> Torna al tracker
      </Link>

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-4">
        <div className="flex gap-5">
          <div className="w-24 h-24 bg-black border border-[#2A2A35] flex items-center justify-center overflow-hidden shrink-0">
            {p.image ? <img src={p.image} alt="" className="w-full h-full object-contain" /> : <Zap size={24} className="text-zinc-600" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs uppercase tracking-widest text-zinc-500">{p.platform}</div>
            <h1 className="font-display font-bold text-xl tracking-tight mt-1 mb-3">{p.title}</h1>
            <div className="flex flex-wrap gap-6">
              <div><div className="text-xs text-zinc-500">Attuale</div><div className="font-display font-black text-2xl text-[#E5FF00]">{p.current_price ?? "—"} <span className="text-sm text-zinc-500">{p.currency}</span></div></div>
              <div><div className="text-xs text-zinc-500">Minimo</div><div className="font-display font-black text-2xl text-[#00FF66]">{p.lowest_price ?? "—"}</div></div>
              <div><div className="text-xs text-zinc-500">Iniziale</div><div className="font-display font-black text-2xl text-zinc-400">{p.initial_price ?? "—"}</div></div>
            </div>
          </div>
          <div className="flex flex-col gap-2 shrink-0">
            <button data-testid="detail-refresh-btn" onClick={refresh} disabled={busy} className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] transition-colors">
              <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Aggiorna
            </button>
            <a href={p.url} target="_blank" rel="noreferrer" className="flex items-center gap-2 border border-[#2A2A35] px-3 py-2 text-sm hover:border-[#E5FF00] transition-colors">
              <ExternalLink size={14} /> Store
            </a>
          </div>
        </div>
        {p.status && p.status !== "ok" && (
          <div className="mt-4 text-xs text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-3 py-2">
            {p.last_error || "Lo store ha bloccato la lettura automatica. Inserisci il prezzo manualmente qui sotto."}
          </div>
        )}
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mb-4">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4">Storico prezzi</div>
        {chartData.length < 2 ? (
          <div className="h-56 flex items-center justify-center text-sm text-zinc-500">Dati insufficienti. Aggiorna o inserisci prezzi per costruire lo storico.</div>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid stroke="#2A2A35" strokeDasharray="3 3" />
                <XAxis dataKey="date" stroke="#52525B" fontSize={11} />
                <YAxis stroke="#52525B" fontSize={11} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#0F0F12", border: "1px solid #2A2A35", fontFamily: "JetBrains Mono", fontSize: 12 }} />
                <Line type="monotone" dataKey="price" stroke="#E5FF00" strokeWidth={2} dot={{ fill: "#00FF66", r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2"><Euro size={13} className="text-[#E5FF00]" /> Prezzo manuale</div>
          <div className="flex gap-2">
            <input data-testid="manual-price-input" type="number" value={manual} onChange={(e) => setManual(e.target.value)} placeholder="es. 549.99"
              className="flex-1 bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm" />
            <button data-testid="save-manual-btn" onClick={saveManual} className="bg-[#E5FF00] text-black font-bold px-4 hover:bg-[#D4EC00] transition-colors">Salva</button>
          </div>
        </div>
        <div className="bg-[#0F0F12] border border-[#2A2A35] p-6">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2"><Target size={13} className="text-[#00FF66]" /> Prezzo target (avviso)</div>
          <div className="flex gap-2">
            <input data-testid="target-price-input" type="number" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Avvisami sotto..."
              className="flex-1 bg-black border border-[#2A2A35] focus:border-[#00FF66] outline-none px-3 py-2 text-sm" />
            <button data-testid="save-target-btn" onClick={saveTarget} className="bg-[#00FF66] text-black font-bold px-4 hover:opacity-90 transition-opacity">Imposta</button>
          </div>
        </div>
      </div>
    </div>
  );
}
