import { useEffect, useState } from "react";
import { Shield, Users, Package, Cpu, MessageSquareCode, Trash2, Loader2, ShieldCheck, ShieldOff } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">{label}</span>
        <Icon size={16} className="text-[#E5FF00]" />
      </div>
      <div className="font-display font-black text-2xl tracking-tighter">{value}</div>
    </div>
  );
}

export default function Admin() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [busy, setBusy] = useState({});

  const load = async () => {
    try { const { data } = await api.get("/admin/stats"); setStats(data); } catch {}
    try { const { data } = await api.get("/admin/users"); setUsers(data); } catch {}
  };
  useEffect(() => { load(); }, []);

  const toggleRole = async (u) => {
    const newRole = u.role === "admin" ? "user" : "admin";
    setBusy((b) => ({ ...b, [u.id]: true }));
    try { await api.patch(`/admin/users/${u.id}/role`, { role: newRole }); toast.success(`${u.email} → ${newRole}`); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Errore"); }
    finally { setBusy((b) => ({ ...b, [u.id]: false })); }
  };

  const removeUser = async (u) => {
    if (!window.confirm(`Eliminare ${u.email} e tutti i suoi dati?`)) return;
    setBusy((b) => ({ ...b, [u.id]: true }));
    try { await api.delete(`/admin/users/${u.id}`); toast.success("Utente eliminato"); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Errore"); }
    finally { setBusy((b) => ({ ...b, [u.id]: false })); }
  };

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2 flex items-center gap-2"><Shield size={13} className="text-[#E5FF00]" /> Admin</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">Pannello amministratore</h1>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Stat icon={Users} label="Utenti" value={stats?.total_users ?? "—"} />
        <Stat icon={ShieldCheck} label="Admin" value={stats?.total_admins ?? "—"} />
        <Stat icon={Package} label="Prodotti" value={stats?.total_products ?? "—"} />
        <Stat icon={Cpu} label="Build" value={stats?.total_builds ?? "—"} />
      </div>

      <div className="bg-[#0F0F12] border border-[#2A2A35]">
        <div className="p-5 border-b border-[#2A2A35] text-xs uppercase tracking-[0.2em] text-zinc-500">Utenti ({users.length})</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-widest text-zinc-500 border-b border-[#2A2A35]">
                <th className="p-4">Utente</th><th className="p-4">Ruolo</th><th className="p-4">Prodotti</th><th className="p-4">Build</th><th className="p-4 text-right">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} data-testid={`user-row-${u.id}`} className="border-b border-[#1A1A24] hover:bg-[#141419] transition-colors">
                  <td className="p-4">
                    <div className="text-zinc-100">{u.name || "—"}</div>
                    <div className="text-xs text-zinc-500">{u.email}{u.id === user?.id && <span className="text-[#E5FF00]"> (tu)</span>}</div>
                  </td>
                  <td className="p-4">
                    <span className={`text-xs font-bold uppercase px-2 py-0.5 ${u.role === "admin" ? "bg-[#E5FF00]/20 text-[#E5FF00]" : "bg-zinc-700/30 text-zinc-400"}`}>{u.role}</span>
                  </td>
                  <td className="p-4 text-zinc-400">{u.tracked_products}</td>
                  <td className="p-4 text-zinc-400">{u.builds}</td>
                  <td className="p-4">
                    <div className="flex items-center justify-end gap-2">
                      <button data-testid={`toggle-role-${u.id}`} onClick={() => toggleRole(u)} disabled={busy[u.id] || u.id === user?.id}
                        title={u.role === "admin" ? "Declassa a utente" : "Promuovi ad admin"}
                        className="p-2 border border-[#2A2A35] hover:border-[#E5FF00] transition-colors disabled:opacity-40">
                        {busy[u.id] ? <Loader2 size={14} className="animate-spin" /> : u.role === "admin" ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
                      </button>
                      <button data-testid={`delete-user-${u.id}`} onClick={() => removeUser(u)} disabled={busy[u.id] || u.id === user?.id}
                        className="p-2 border border-[#2A2A35] hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors disabled:opacity-40">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
