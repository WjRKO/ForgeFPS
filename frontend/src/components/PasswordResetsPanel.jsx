/**
 * PasswordResetsPanel — Admin-only.
 *
 * Mostra gli ultimi N token di reset password generati. Finché l'invio email non
 * e' integrato (Resend/SendGrid), l'admin usa questa lista per consegnare
 * manualmente il link agli utenti (via Discord DM, email personale, ecc.).
 *
 * Sicurezza:
 * - Backend richiede require_admin.
 * - Il link mostrato e' relativo (/reset-password?token=xxx). Il "Copia" combina
 *   con l'origin corrente per produrre un URL assoluto (https://forgefps.dev/...).
 * - Token attivi mostrati per intero (necessario per il workaround). Sconsigliato
 *   loggare screenshot pubblici.
 */
import { useEffect, useState } from "react";
import { Copy, Check, Clock, KeyRound, RotateCw, Loader2 } from "lucide-react";
import api from "@/lib/api";
import { toast } from "sonner";

const STATUS_STYLES = {
  active:  { bg: "bg-[#00FF66]/10", border: "border-[#00FF66]/40", text: "text-[#00FF66]", label: "ATTIVO" },
  used:    { bg: "bg-zinc-700/20", border: "border-zinc-700", text: "text-zinc-400", label: "USATO" },
  expired: { bg: "bg-[#FF3B30]/10", border: "border-[#FF3B30]/40", text: "text-[#FF3B30]", label: "SCADUTO" },
};

function timeAgo(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const s = Math.floor((Date.now() - d.getTime()) / 1000);
    if (s < 60) return `${s}s fa`;
    if (s < 3600) return `${Math.floor(s / 60)}m fa`;
    if (s < 86400) return `${Math.floor(s / 3600)}h fa`;
    return `${Math.floor(s / 86400)}g fa`;
  } catch { return "—"; }
}

export default function PasswordResetsPanel() {
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copiedIdx, setCopiedIdx] = useState(-1);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/password-resets");
      setItems(data.items || []);
    } catch (e) {
      toast.error("Impossibile caricare i reset token: " + (e?.response?.data?.detail || e.message));
      setItems([]);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const copy = async (relLink, idx) => {
    const full = `${window.location.origin}${relLink}`;
    try {
      await navigator.clipboard.writeText(full);
      setCopiedIdx(idx);
      toast.success("Link copiato negli appunti");
      setTimeout(() => setCopiedIdx(-1), 2000);
    } catch {
      toast.error("Copia fallita — seleziona e copia manualmente");
    }
  };

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-6 mt-8" data-testid="password-resets-panel">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">// admin · reset password</div>
          <h2 className="font-display font-bold text-xl tracking-tight flex items-center gap-2">
            <KeyRound size={18} className="text-[#E5FF00]" />
            Reset password richiesti
          </h2>
          <p className="text-xs text-zinc-500 mt-1 max-w-2xl">
            Ultimi 20 link generati dagli utenti. L'invio email vero e' TODO — nel frattempo copia il link
            e mandalo tu al destinatario (Discord DM / email personale).
          </p>
        </div>
        <button onClick={load} disabled={loading} data-testid="password-resets-refresh"
          className="inline-flex items-center gap-2 text-xs px-3 py-2 border border-[#2A2A35] hover:border-[#E5FF00] transition-colors disabled:opacity-50">
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RotateCw size={12} />}
          Aggiorna
        </button>
      </div>

      {loading && items === null ? (
        <div className="text-center py-8 text-zinc-500 text-sm">Caricamento...</div>
      ) : !items || items.length === 0 ? (
        <div className="text-center py-8 text-zinc-500 text-sm">
          Nessun reset richiesto negli ultimi 30 giorni.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="password-resets-table">
            <thead>
              <tr className="text-xs uppercase tracking-widest text-zinc-500 border-b border-[#2A2A35]">
                <th className="text-left py-2 px-3">Email</th>
                <th className="text-left py-2 px-3">Quando</th>
                <th className="text-left py-2 px-3">IP</th>
                <th className="text-left py-2 px-3">Stato</th>
                <th className="text-right py-2 px-3">Azione</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, i) => {
                const sty = STATUS_STYLES[it.status] || STATUS_STYLES.expired;
                return (
                  <tr key={i} className="border-b border-[#2A2A35]/50 hover:bg-black/30" data-testid={`reset-row-${i}`}>
                    <td className="py-2 px-3 text-zinc-200 font-mono text-xs">{it.email}</td>
                    <td className="py-2 px-3 text-zinc-400 text-xs">
                      <Clock size={10} className="inline mr-1" />
                      {timeAgo(it.created_at)}
                    </td>
                    <td className="py-2 px-3 text-zinc-500 font-mono text-xs">{it.ip || "—"}</td>
                    <td className="py-2 px-3">
                      <span className={`text-[10px] font-bold uppercase px-2 py-0.5 border ${sty.border} ${sty.bg} ${sty.text}`}>
                        {sty.label}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right">
                      {it.status === "active" ? (
                        <button onClick={() => copy(it.link, i)} data-testid={`reset-copy-${i}`}
                          className="inline-flex items-center gap-1.5 text-xs px-2 py-1 border border-[#2A2A35] hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors">
                          {copiedIdx === i ? <><Check size={11} /> Copiato</> : <><Copy size={11} /> Copia link</>}
                        </button>
                      ) : (
                        <span className="text-xs text-zinc-600">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
