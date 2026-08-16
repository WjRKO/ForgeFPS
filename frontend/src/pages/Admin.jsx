import { useEffect, useMemo, useState, Fragment } from "react";
import {
  Shield, Users, Package, Cpu, Trash2, Loader2, ShieldCheck, ShieldOff,
  Search, ChevronDown, ChevronUp, Send, Sparkles, Activity, MonitorCheck,
  MessageSquare, Gauge, X, ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown,
  Gift,
} from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const isEn = () => i18n.language?.startsWith("en");
import { PageHeader } from "@/components/hud";
import PasswordResetsPanel from "@/components/PasswordResetsPanel";
import AdminToolsPanel from "@/components/AdminToolsPanel";

const PAGE_SIZE = 20;
const DISCORD_COLOR = "#5865F2";

function StatCard({ icon: Icon, label, value, hint, accent = "text-[#E5FF00]", testid }) {
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 panel-hover" data-testid={testid}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">{label}</span>
        <Icon size={16} className={`${accent} icon-pop`} />
      </div>
      <div className="font-display font-black text-2xl tracking-tighter">{value}</div>
      {hint && <div className="mt-1 text-[11px] text-zinc-500 font-mono">{hint}</div>}
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("it-IT", { day: "2-digit", month: "short", year: "2-digit" }); }
  catch { return "—"; }
}
function fmtRelative(iso) {
  const en = (i18n.resolvedLanguage || i18n.language || "it").toLowerCase().startsWith("en");
  if (!iso) return en ? "never" : "mai";
  try {
    const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    const rtf = new Intl.RelativeTimeFormat(en ? "en" : "it", { numeric: "auto", style: "narrow" });
    if (s < 60) return rtf.format(0, "minute");
    if (s < 3600) return rtf.format(-Math.floor(s / 60), "minute");
    if (s < 86400) return rtf.format(-Math.floor(s / 3600), "hour");
    if (s < 86400 * 30) return rtf.format(-Math.floor(s / 86400), "day");
    return rtf.format(-Math.floor(s / (86400 * 30)), "month");
  } catch { return "—"; }
}

function GrantPlanModal({ open, onClose, user, onGranted }) {
  const [plan, setPlan] = useState("pro");
  const [months, setMonths] = useState(1);
  const [saving, setSaving] = useState(false);
  if (!open || !user) return null;
  const submit = async () => {
    setSaving(true);
    try {
      const { data } = await api.post(`/admin/users/${user.id}/grant-plan`, { plan, months: Number(months) });
      toast.success(`${user.email} → ${plan.toUpperCase()} ${isEn() ? "for" : "per"} ${months === 0 ? (isEn() ? "ever" : "sempre") : months + (isEn() ? " months" : " mesi")}`);
      onGranted?.(data);
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (isEn() ? "Error" : "Errore"));
    } finally { setSaving(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80" onClick={onClose} data-testid="grant-plan-modal">
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md bg-[#0F0F12] border border-[#E5FF00]/40 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-[#E5FF00] mb-1">// grant plan</div>
            <h3 className="font-display font-black text-xl">{isEn() ? "Grant paid plan" : "Concedi piano paid"}</h3>
            <p className="text-xs text-zinc-500 mt-1">{isEn() ? "To" : "A"}: <span className="font-mono text-zinc-300">{user.email}</span></p>
          </div>
          <button onClick={onClose} aria-label={i18n.t("a11y.close")} className="text-zinc-500 hover:text-zinc-200"><X size={18} /></button>
        </div>
        <div className="space-y-3 mb-5">
          <div>
            <label className="text-xs uppercase tracking-widest text-zinc-500 block mb-1">{isEn() ? "Plan" : "Piano"}</label>
            <select value={plan} onChange={(e) => setPlan(e.target.value)}
              className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none"
              data-testid="grant-plan-select">
              <option value="pro">Pro (€7/{isEn() ? "month equiv." : "mese equiv."})</option>
              <option value="streamer">Streamer (€16/{isEn() ? "month equiv." : "mese equiv."})</option>
              <option value="starter">Starter ({isEn() ? "revoke plan" : "revoca piano"})</option>
            </select>
          </div>
          {plan !== "starter" && (
            <div>
              <label className="text-xs uppercase tracking-widest text-zinc-500 block mb-1">{isEn() ? "Duration (months) · 0 = perpetual" : "Durata (mesi) · 0 = perpetuo"}</label>
              <input type="number" min={0} max={120} value={months} onChange={(e) => setMonths(e.target.value)}
                className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none"
                data-testid="grant-plan-months" />
              <div className="text-[10px] text-zinc-600 mt-1 font-mono">
                {Number(months) === 0 ? (isEn() ? "Perpetual plan (no expiry)" : "Piano perpetuo (senza scadenza)")
                 : `${isEn() ? "Expires" : "Scade il"} ${new Date(Date.now() + Number(months) * 30 * 86400000).toLocaleDateString(isEn() ? "en-US" : "it-IT")}`}
              </div>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} disabled={saving} className="px-4 py-2 border border-[#2A2A35] text-sm hover:border-zinc-500 transition-colors disabled:opacity-50">{isEn() ? "Cancel" : "Annulla"}</button>
          <button onClick={submit} disabled={saving} data-testid="grant-plan-submit"
            className="flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EE00] transition-colors disabled:opacity-50">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Gift size={14} />}
            {saving ? (isEn() ? "Saving..." : "Salvo...") : (isEn() ? "Grant" : "Concedi")}
          </button>
        </div>
      </div>
    </div>
  );
}

function BroadcastModal({ open, onClose }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [link, setLink] = useState("");
  const [scope, setScope] = useState("all");
  const [sending, setSending] = useState(false);

  const send = async () => {
    if (!title.trim()) { toast.error(isEn() ? "Title is required" : "Titolo obbligatorio"); return; }
    setSending(true);
    try {
      const { data } = await api.post("/admin/broadcast", {
        title: title.trim(), body: body.trim(), link: link.trim(), scope,
      });
      toast.success(isEn() ? `Broadcast sent to ${data.recipients} recipients (${data.scope})` : `Broadcast inviato a ${data.recipients} destinatari (${data.scope})`);
      setTitle(""); setBody(""); setLink("");
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (isEn() ? "Broadcast send error" : "Errore invio broadcast"));
    } finally { setSending(false); }
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80" onClick={onClose} data-testid="broadcast-modal">
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg bg-[#0F0F12] border border-[#E5FF00]/40 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-[#E5FF00] mb-1">// broadcast in-app</div>
            <h3 className="font-display font-black text-xl">{isEn() ? "Send notification to everyone" : "Invia notifica a tutti"}</h3>
          </div>
          <button onClick={onClose} aria-label={i18n.t("a11y.close")} className="text-zinc-500 hover:text-zinc-200" data-testid="broadcast-close"><X size={18} /></button>
        </div>

        <div className="space-y-3 mb-5">
          <div>
            <label className="text-xs uppercase tracking-widest text-zinc-500 block mb-1">{isEn() ? "Title" : "Titolo"} <span className="text-[#FF3B30]">*</span></label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120}
              placeholder={isEn() ? "E.g.: v0.7.4 is live — new live monitor" : "Es: v0.7.4 è online — nuovo monitor live"}
              className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none"
              data-testid="broadcast-title" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-zinc-500 block mb-1">{isEn() ? "Body (optional)" : "Corpo (facoltativo)"}</label>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={500} rows={3}
              placeholder={isEn() ? "Details in 1-2 lines. Max 500 characters." : "Dettagli in 1-2 righe. Massimo 500 caratteri."}
              className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none resize-none"
              data-testid="broadcast-body" />
            <div className="text-[10px] text-zinc-600 text-right mt-0.5">{body.length}/500</div>
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-zinc-500 block mb-1">{isEn() ? "CTA link (optional)" : "Link CTA (facoltativo)"}</label>
            <input value={link} onChange={(e) => setLink(e.target.value)}
              placeholder={isEn() ? "/app/desktop  or  https://..." : "/app/desktop  oppure  https://..."}
              className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none"
              data-testid="broadcast-link" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-zinc-500 block mb-1">{isEn() ? "Recipients" : "Destinatari"}</label>
            <select value={scope} onChange={(e) => setScope(e.target.value)}
              className="w-full bg-black border border-[#2A2A35] px-3 py-2 text-sm focus:border-[#E5FF00] outline-none"
              data-testid="broadcast-scope">
              <option value="all">{isEn() ? "All users" : "Tutti gli utenti"}</option>
              <option value="has_agent">{isEn() ? "Only users with agent installed (pc_specs)" : "Solo utenti con agent installato (pc_specs)"}</option>
              <option value="boosted">{isEn() ? "Only Discord-linked users (Boosted)" : "Solo utenti Discord-linkati (Boosted)"}</option>
              <option value="admins">{isEn() ? "Admins only (test)" : "Solo admin (test)"}</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button onClick={onClose} disabled={sending}
            className="px-4 py-2 border border-[#2A2A35] text-sm hover:border-zinc-500 transition-colors disabled:opacity-50"
            data-testid="broadcast-cancel">{isEn() ? "Cancel" : "Annulla"}</button>
          <button onClick={send} disabled={sending || !title.trim()}
            className="flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EE00] transition-colors disabled:opacity-50"
            data-testid="broadcast-send">
            {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            {sending ? (isEn() ? "Sending..." : "Invio...") : (isEn() ? "Send" : "Invia")}
          </button>
        </div>
      </div>
    </div>
  );
}

function UserDetailsRow({ userId, colspan }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.get(`/admin/users/${userId}/details`).then(({ data }) => setD(data))
      .catch((e) => setErr(e?.response?.data?.detail || (isEn() ? "Loading error" : "Errore caricamento")));
  }, [userId]);

  if (err) return <tr><td colSpan={colspan} className="p-4 bg-[#141419] text-xs text-[#FF3B30]" data-testid={`user-details-err-${userId}`}>{err}</td></tr>;
  if (!d) return <tr><td colSpan={colspan} className="p-4 bg-[#141419] text-xs text-zinc-500" data-testid={`user-details-loading-${userId}`}><Loader2 size={12} className="inline animate-spin mr-2" /> {isEn() ? "Loading…" : "Caricamento…"}</td></tr>;

  const hw = d.pc_specs?.data || {};
  const health = d.last_health;
  const healthColor = (s) => s >= 85 ? "text-[#00FF66]" : s >= 70 ? "text-[#E5FF00]" : s >= 50 ? "text-[#FFA500]" : "text-[#FF3B30]";

  return (
    <tr className="bg-black/60">
      <td colSpan={colspan} className="p-5 border-b border-[#2A2A35]" data-testid={`user-details-${userId}`}>
        <div className="grid md:grid-cols-3 gap-5 text-xs">
          <div>
            <div className="uppercase tracking-widest text-zinc-500 mb-2">// account</div>
            <div className="space-y-1 text-zinc-300">
              <div><span className="text-zinc-500">{isEn() ? "Signed up:" : "Registrato:"}</span> {fmtDate(d.created_at)} · <span className="text-zinc-400">{fmtRelative(d.created_at)}</span></div>
              <div><span className="text-zinc-500">Plan:</span> <span className="text-[#E5FF00] font-bold uppercase">{d.plan}</span></div>
              <div><span className="text-zinc-500">Discord:</span> {d.discord_user_id ? (<span style={{ color: DISCORD_COLOR }} className="font-mono">{d.discord_user_id}</span>) : (<span className="text-zinc-600">{isEn() ? "not linked" : "non collegato"}</span>)}</div>
              <div className="pt-2 flex flex-wrap gap-3 text-[11px]">
                <span><span className="text-zinc-500">{isEn() ? "Products:" : "Prodotti:"}</span> <span className="text-zinc-200 font-bold">{d.products_count}</span></span>
                <span><span className="text-zinc-500">Build:</span> <span className="text-zinc-200 font-bold">{d.builds_count}</span></span>
                <span><span className="text-zinc-500">Benchmark:</span> <span className="text-zinc-200 font-bold">{d.benchmarks_count}</span></span>
                <span><span className="text-zinc-500">{isEn() ? "Unread notifications:" : "Notifiche non lette:"}</span> <span className="text-zinc-200 font-bold">{d.notifications_unread}</span></span>
              </div>
            </div>
          </div>

          <div>
            <div className="uppercase tracking-widest text-zinc-500 mb-2">// hardware & agent</div>
            {d.pc_specs ? (
              <div className="space-y-1 text-zinc-300">
                <div><span className="text-zinc-500">CPU:</span> <span className="text-[#00E0FF]">{hw.cpu || "—"}</span></div>
                <div><span className="text-zinc-500">GPU:</span> <span className="text-[#00E0FF]">{hw.gpu || "—"}</span></div>
                <div><span className="text-zinc-500">RAM:</span> <span className="text-[#00E0FF]">{hw.ram ? `${hw.ram} GB` : "—"}</span></div>
                <div><span className="text-zinc-500">OS:</span> {hw.os || "—"}</div>
                <div><span className="text-zinc-500">{isEn() ? "Last sync:" : "Ultima sync:"}</span> <span className="text-zinc-200">{fmtRelative(d.pc_specs.updated_at)}</span></div>
              </div>
            ) : (
              <div className="text-zinc-600">{isEn() ? "The user hasn't installed the agent yet (no pc_specs document)." : "L'utente non ha ancora installato l'agent (nessun documento pc_specs)."}</div>
            )}
          </div>

          <div>
            <div className="uppercase tracking-widest text-zinc-500 mb-2">{isEn() ? "// last PC health" : "// ultima salute PC"}</div>
            {health && health.score != null ? (
              <div className="space-y-1 text-zinc-300">
                <div className="flex items-baseline gap-2">
                  <span className={`font-display font-black text-3xl ${healthColor(health.score)}`}>{health.score}</span>
                  <span className="text-zinc-500 text-xs uppercase tracking-widest">/100 · {health.grade || "—"}</span>
                </div>
                <div className="text-zinc-500">{isEn() ? "Recorded" : "Registrato"} {fmtRelative(health.created_at)}</div>
              </div>
            ) : (
              <div className="text-zinc-600">{isEn() ? "No health snapshots yet." : "Nessuno snapshot health finora."}</div>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}

export default function Admin() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [busy, setBusy] = useState({});
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc"); // asc | desc
  const [expanded, setExpanded] = useState(null); // user id
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [grantTarget, setGrantTarget] = useState(null); // user object to grant plan to

  const load = async () => {
    try { const { data } = await api.get("/admin/stats"); setStats(data); }
    catch (e) { console.warn("[Admin] load stats failed", e); }
    try { const { data } = await api.get("/admin/users"); setUsers(data); }
    catch (e) { console.warn("[Admin] load users failed", e); }
  };
  useEffect(() => { load(); }, []);

  const toggleRole = async (u) => {
    const newRole = u.role === "admin" ? "user" : "admin";
    setBusy((b) => ({ ...b, [u.id]: true }));
    try { await api.patch(`/admin/users/${u.id}/role`, { role: newRole }); toast.success(`${u.email} → ${newRole}`); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || t("admin.error", { defaultValue: "Errore" })); }
    finally { setBusy((b) => ({ ...b, [u.id]: false })); }
  };

  const removeUser = async (u) => {
    if (!window.confirm(t("admin.confirm_delete", { email: u.email, defaultValue: `Cancellare ${u.email}? Operazione irreversibile.` }))) return;
    setBusy((b) => ({ ...b, [u.id]: true }));
    try { await api.delete(`/admin/users/${u.id}`); toast.success(t("admin.deleted", { defaultValue: "Utente eliminato" })); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || t("admin.error", { defaultValue: "Errore" })); }
    finally { setBusy((b) => ({ ...b, [u.id]: false })); }
  };

  const changeSort = (col) => {
    if (sortBy === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortBy(col); setSortDir(col === "created_at" || col === "tracked_products" || col === "builds" ? "desc" : "asc"); }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = users;
    if (q) list = users.filter((u) =>
      (u.email || "").toLowerCase().includes(q) ||
      (u.name || "").toLowerCase().includes(q));
    // sort
    const arr = [...list];
    arr.sort((a, b) => {
      let va = a[sortBy], vb = b[sortBy];
      if (sortBy === "email" || sortBy === "role") { va = (va || "").toLowerCase(); vb = (vb || "").toLowerCase(); }
      if (va == null) va = "";
      if (vb == null) vb = "";
      if (va < vb) return sortDir === "asc" ? -1 : 1;
      if (va > vb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [users, query, sortBy, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const paginated = filtered.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  // Reset page when filter/sort changes
  useEffect(() => { setPage(1); setExpanded(null); }, [query, sortBy, sortDir]);

  const SortHeader = ({ col, label }) => {
    const active = sortBy === col;
    const Icon = !active ? ArrowUpDown : sortDir === "asc" ? ArrowUp : ArrowDown;
    return (
      <button onClick={() => changeSort(col)} className={`inline-flex items-center gap-1 hover:text-zinc-200 transition-colors ${active ? "text-[#E5FF00]" : ""}`} data-testid={`sort-${col}`}>
        {label} <Icon size={11} />
      </button>
    );
  };

  return (
    <div className="max-w-7xl mx-auto fade-up">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
        <PageHeader eyebrow={<span className="inline-flex items-center gap-2"><Shield size={13} className="text-[#E5FF00]" /> {t("admin.eyebrow", { defaultValue: "// admin" })}</span>} title={t("admin.title", { defaultValue: "Pannello amministratore" })} />
        <button onClick={() => setBroadcastOpen(true)} data-testid="broadcast-open-btn"
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2 text-sm hover:bg-[#D4EE00] transition-colors">
          <Send size={14} /> Broadcast
        </button>
      </div>

      {/* Extended stats — 8 cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 stagger">
        <StatCard icon={Users} label={isEn() ? "Users" : "Utenti"} value={stats?.total_users ?? "—"} hint={stats ? `${stats.signups_last_7d} ${isEn() ? "in the last 7d" : "negli ultimi 7gg"}` : null} testid="stat-users" />
        <StatCard icon={ShieldCheck} label="Admin" value={stats?.total_admins ?? "—"} accent="text-[#00E0FF]" testid="stat-admins" />
        <StatCard icon={Sparkles} label="Signup 24h" value={stats?.signups_last_24h ?? "—"} hint={isEn() ? "new signups" : "nuove registrazioni"} accent="text-[#00FF66]" testid="stat-signup-24h" />
        <StatCard icon={MonitorCheck} label={isEn() ? "With agent" : "Con agent"} value={stats?.users_with_agent ?? "—"} hint={stats ? `${Math.round((stats.users_with_agent / Math.max(1, stats.total_users)) * 100)}% ${isEn() ? "of users" : "degli utenti"}` : null} accent="text-[#00E0FF]" testid="stat-agent" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8 stagger">
        <StatCard icon={Package} label={isEn() ? "Tracked products" : "Prodotti tracciati"} value={stats?.total_products ?? "—"} testid="stat-products" />
        <StatCard icon={Cpu} label={isEn() ? "Saved builds" : "Build salvate"} value={stats?.total_builds ?? "—"} testid="stat-builds" />
        <StatCard icon={Gauge} label={isEn() ? "Total benchmarks" : "Benchmark totali"} value={stats?.total_benchmarks ?? "—"} hint={stats ? `${stats.total_health_snapshots} ${isEn() ? "health snapshots" : "snapshot health"}` : null} accent="text-[#E5FF00]" testid="stat-benchmarks" />
        <StatCard icon={MessageSquare} label="Discord linked" value={stats?.users_discord_linked ?? "—"} accent="text-[#5865F2]" testid="stat-discord" />
      </div>

      {/* Users table with search + pagination + sort + expand */}
      <div className="bg-[#0F0F12] border border-[#2A2A35] mb-8">
        <div className="p-4 border-b border-[#2A2A35] flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
            {isEn() ? "Users" : "Utenti"} · <span className="text-zinc-300 font-bold">{filtered.length}</span>{query && <span className="text-zinc-500"> / {users.length}</span>}
          </div>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder={isEn() ? "Search by email or name…" : "Cerca per email o nome…"}
              className="bg-black border border-[#2A2A35] pl-8 pr-3 py-1.5 text-sm w-64 focus:border-[#E5FF00] outline-none"
              data-testid="user-search" />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-widest text-zinc-500 border-b border-[#2A2A35]">
                <th className="p-4 w-10"></th>
                <th className="p-4"><SortHeader col="email" label={isEn() ? "User" : "Utente"} /></th>
                <th className="p-4"><SortHeader col="role" label={isEn() ? "Role" : "Ruolo"} /></th>
                <th className="p-4"><SortHeader col="created_at" label="Signup" /></th>
                <th className="p-4">Agent</th>
                <th className="p-4">Discord</th>
                <th className="p-4"><SortHeader col="tracked_products" label={isEn() ? "Products" : "Prodotti"} /></th>
                <th className="p-4"><SortHeader col="builds" label="Build" /></th>
                <th className="p-4 text-right">{isEn() ? "Actions" : "Azioni"}</th>
              </tr>
            </thead>
            <tbody>
              {paginated.length === 0 && (
                <tr><td colSpan={9} className="p-8 text-center text-zinc-500 text-sm" data-testid="users-empty">
                  {query ? (isEn() ? `No users found for "${query}".` : `Nessun utente trovato per "${query}".`) : (isEn() ? "No users." : "Nessun utente.")}
                </td></tr>
              )}
              {paginated.map((u) => {
                const isExpanded = expanded === u.id;
                return (
                  <Fragment key={u.id}>
                    <tr data-testid={`user-row-${u.id}`} className={`border-b border-[#1A1A24] hover:bg-[#141419] transition-colors ${isExpanded ? "bg-[#141419]" : ""}`}>
                      <td className="p-4">
                        <button onClick={() => setExpanded(isExpanded ? null : u.id)}
                          className="p-1 hover:bg-black transition-colors" data-testid={`expand-${u.id}`}
                          title={isExpanded ? (isEn() ? "Close details" : "Chiudi dettagli") : (isEn() ? "Open details" : "Apri dettagli")}>
                          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                      </td>
                      <td className="p-4">
                        <div className="text-zinc-100">{u.name || "—"}</div>
                        <div className="text-xs text-zinc-500 font-mono">{u.email}{u.id === user?.id && <span className="text-[#E5FF00] font-sans"> · {isEn() ? "you" : "tu"}</span>}</div>
                      </td>
                      <td className="p-4">
                        <span className={`text-xs font-bold uppercase px-2 py-0.5 ${u.role === "admin" ? "bg-[#E5FF00]/20 text-[#E5FF00]" : "bg-zinc-700/30 text-zinc-400"}`}>{u.role}</span>
                      </td>
                      <td className="p-4 text-zinc-400 text-xs">{fmtRelative(u.created_at)}</td>
                      <td className="p-4">
                        {u.has_agent ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-[#00FF66]" title={`${isEn() ? "Last sync" : "Ultima sync"}: ${fmtRelative(u.last_pc_sync)}`}>
                            <MonitorCheck size={12} /> {fmtRelative(u.last_pc_sync)}
                          </span>
                        ) : (
                          <span className="text-[11px] text-zinc-600">{isEn() ? "not installed" : "non installato"}</span>
                        )}
                      </td>
                      <td className="p-4">
                        {u.discord_linked ? (
                          <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: DISCORD_COLOR }}>
                            <Activity size={12} /> {isEn() ? "linked" : "linkato"}
                          </span>
                        ) : (
                          <span className="text-[11px] text-zinc-600">—</span>
                        )}
                      </td>
                      <td className="p-4 text-zinc-400">{u.tracked_products}</td>
                      <td className="p-4 text-zinc-400">{u.builds}</td>
                      <td className="p-4">
                        <div className="flex items-center justify-end gap-2">
                          <button data-testid={`grant-plan-${u.id}`} onClick={() => setGrantTarget(u)} disabled={busy[u.id]}
                            title={isEn() ? "Grant/revoke paid plan manually" : "Concedi/revoca piano paid manualmente"}
                            className="p-2 border border-[#2A2A35] hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors disabled:opacity-40">
                            <Gift size={14} />
                          </button>
                          <button data-testid={`toggle-role-${u.id}`} onClick={() => toggleRole(u)} disabled={busy[u.id] || u.id === user?.id}
                            title={u.role === "admin" ? (isEn() ? "Remove admin" : "Rimuovi admin") : (isEn() ? "Promote to admin" : "Promuovi ad admin")}
                            className="p-2 border border-[#2A2A35] hover:border-[#E5FF00] transition-colors disabled:opacity-40">
                            {busy[u.id] ? <Loader2 size={14} className="animate-spin" /> : u.role === "admin" ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
                          </button>
                          <button data-testid={`delete-user-${u.id}`} onClick={() => removeUser(u)} disabled={busy[u.id] || u.id === user?.id}
                            title={isEn() ? "Delete account (irreversible)" : "Elimina account (irreversibile)"}
                            className="p-2 border border-[#2A2A35] hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors disabled:opacity-40">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isExpanded && <UserDetailsRow key={`d-${u.id}`} userId={u.id} colspan={9} />}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination footer */}
        {filtered.length > PAGE_SIZE && (
          <div className="p-3 border-t border-[#2A2A35] flex items-center justify-between text-xs text-zinc-500" data-testid="user-pagination">
            <div>{isEn() ? "Page" : "Pagina"} <span className="text-zinc-200 font-bold">{pageSafe}</span> {isEn() ? "of" : "di"} {totalPages} · {isEn() ? "showing" : "mostrando"} {(pageSafe - 1) * PAGE_SIZE + 1}-{Math.min(pageSafe * PAGE_SIZE, filtered.length)} {isEn() ? "of" : "di"} {filtered.length}</div>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={pageSafe === 1}
                className="p-1.5 border border-[#2A2A35] hover:border-[#E5FF00] disabled:opacity-30 transition-colors" data-testid="page-prev">
                <ChevronLeft size={14} />
              </button>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={pageSafe === totalPages}
                className="p-1.5 border border-[#2A2A35] hover:border-[#E5FF00] disabled:opacity-30 transition-colors" data-testid="page-next">
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Password Resets Panel */}
      <PasswordResetsPanel />

      {/* Registrazioni, email di prova, release annunciate */}
      <AdminToolsPanel />

      {/* Broadcast Modal */}
      <BroadcastModal open={broadcastOpen} onClose={() => setBroadcastOpen(false)} />

      {/* Grant Plan Modal */}
      <GrantPlanModal open={!!grantTarget} onClose={() => setGrantTarget(null)} user={grantTarget} onGranted={() => load()} />
    </div>
  );
}
