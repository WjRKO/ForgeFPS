import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { TrendingUp, Mail, Megaphone, Loader2, Send } from "lucide-react";
import api from "@/lib/api";

/**
 * Tre strumenti admin che esistevano solo come endpoint, senza interfaccia:
 * andamento registrazioni, invio email di prova, marcatura release come annunciate.
 */

const TEMPLATES = ["welcome", "trial_started", "trial_ending", "payment_success", "payment_failed"];

const CARD = "bg-[#0F0F12] border border-[#2A2A35] p-6 mb-6";
const EYEBROW = "text-xs uppercase tracking-widest text-zinc-500 font-mono mb-1 flex items-center gap-2";
const INPUT = "bg-black border border-[#2A2A35] px-3 py-2 text-sm text-zinc-200 focus:border-[#E5FF00] outline-none";
const BTN = "inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EC00] transition-colors disabled:opacity-50";

export default function AdminToolsPanel() {
  const { t, i18n } = useTranslation();
  const c = t("admintools", { returnObjects: true });

  const [points, setPoints] = useState(null);
  const [tpl, setTpl] = useState(TEMPLATES[0]);
  const [to, setTo] = useState("");
  const [sending, setSending] = useState(false);
  const [versions, setVersions] = useState("");
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    api.get("/admin/signups-timeline?days=30")
      .then(({ data }) => setPoints(Array.isArray(data) ? data : data?.points || []))
      .catch(() => setPoints([]));
  }, []);

  const sendEmail = async () => {
    setSending(true);
    try {
      await api.post("/admin/test-email", { template: tpl, ...(to.trim() ? { to: to.trim() } : {}) });
      toast.success(c.email_ok);
    } catch (e) {
      toast.error(e?.response?.data?.detail || c.email_fail);
    } finally { setSending(false); }
  };

  const markAnnounced = async () => {
    const list = versions.split(",").map((v) => v.trim()).filter(Boolean);
    if (!list.length) { toast.error(c.rel_empty); return; }
    setMarking(true);
    try {
      const { data } = await api.post("/admin/releases/mark-announced", { versions: list });
      toast.success(c.rel_ok, {
        description: [
          data?.marked?.length ? `marked: ${data.marked.join(", ")}` : null,
          data?.already?.length ? `already: ${data.already.join(", ")}` : null,
        ].filter(Boolean).join(" · ") || undefined,
      });
      setVersions("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || c.rel_fail);
    } finally { setMarking(false); }
  };

  const total = (points || []).reduce((sum, p) => sum + (p.count || 0), 0);

  return (
    <>
      <div className={CARD} data-testid="admin-signups-card">
        <div className={EYEBROW}><TrendingUp size={14} className="text-[#E5FF00]" /> {c.signups}</div>
        <p className="text-xs text-zinc-600 mb-4">{c.signups_sub}</p>
        {points === null ? (
          <Loader2 size={16} className="animate-spin text-zinc-600" />
        ) : total === 0 ? (
          <p className="text-sm text-zinc-600">{c.signups_empty}</p>
        ) : (
          <>
            <div className="text-sm text-zinc-400 mb-3">
              {c.signups_total}: <span className="text-[#E5FF00] font-mono font-bold">{total}</span>
            </div>
            <div style={{ width: "100%", height: 200 }}>
              <ResponsiveContainer>
                <LineChart data={points} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1A1A24" />
                  <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 10 }} stroke="#2A2A35" />
                  <YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#2A2A35" />
                  <Tooltip contentStyle={{ background: "#0A0A0C", border: "1px solid #2A2A35", fontSize: 12 }} labelStyle={{ color: "#a1a1aa" }} />
                  <Line type="monotone" dataKey="count" stroke="#E5FF00" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>

      <div className={CARD} data-testid="admin-test-email-card">
        <div className={EYEBROW}><Mail size={14} className="text-[#E5FF00]" /> {c.email}</div>
        <p className="text-xs text-zinc-600 mb-4">{c.email_sub}</p>
        <div className="flex flex-wrap items-center gap-3">
          <select value={tpl} onChange={(e) => setTpl(e.target.value)} className={INPUT} data-testid="test-email-template" aria-label={c.email}>
            {TEMPLATES.map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
          <input
            type="email" value={to} onChange={(e) => setTo(e.target.value)}
            placeholder={c.email_to} aria-label={c.email_to}
            className={`${INPUT} flex-1 min-w-[220px]`} data-testid="test-email-to"
          />
          <button onClick={sendEmail} disabled={sending} className={BTN} data-testid="test-email-send">
            {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} {c.email_send}
          </button>
        </div>
      </div>

      <div className={CARD} data-testid="admin-releases-card">
        <div className={EYEBROW}><Megaphone size={14} className="text-[#E5FF00]" /> {c.rel}</div>
        <p className="text-xs text-zinc-600 mb-4">{c.rel_sub}</p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={versions} onChange={(e) => setVersions(e.target.value)}
            placeholder={c.rel_ph} aria-label={c.rel}
            className={`${INPUT} flex-1 min-w-[220px] font-mono`} data-testid="releases-versions"
          />
          <button onClick={markAnnounced} disabled={marking} className={BTN} data-testid="releases-mark">
            {marking ? <Loader2 size={14} className="animate-spin" /> : <Megaphone size={14} />} {c.rel_mark}
          </button>
        </div>
      </div>
    </>
  );
}
