import { NavLink, useNavigate, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { LayoutDashboard, MessageSquareCode, Cpu, LineChart, MonitorDown, LogOut, Bell, Zap, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true, id: "dashboard" },
  { to: "/app/advisor", label: "AI Advisor", icon: MessageSquareCode, id: "advisor" },
  { to: "/app/builds", label: "Build Generator", icon: Cpu, id: "builds" },
  { to: "/app/tracker", label: "Price Tracker", icon: LineChart, id: "tracker" },
  { to: "/app/desktop", label: "Desktop Agent", icon: MonitorDown, id: "desktop" },
];

function Notifications() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const unread = items.filter((n) => !n.read).length;

  const load = async () => {
    try { const { data } = await api.get("/notifications"); setItems(data); } catch {}
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);

  const markAll = async () => { await api.post("/notifications/read-all"); load(); };

  return (
    <div className="relative">
      <button data-testid="notifications-btn" onClick={() => setOpen((o) => !o)}
        className="relative p-2 border border-[#2A2A35] hover:border-[#E5FF00] transition-colors">
        <Bell size={18} />
        {unread > 0 && (
          <span data-testid="notif-count" className="absolute -top-1 -right-1 bg-[#E5FF00] text-black text-[10px] font-bold px-1.5 rounded-sm">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-[#0F0F12] border border-[#2A2A35] z-50 max-h-96 overflow-auto">
          <div className="flex items-center justify-between p-3 border-b border-[#2A2A35]">
            <span className="text-xs uppercase tracking-widest text-zinc-500">Notifiche</span>
            <div className="flex gap-2">
              <button onClick={markAll} className="text-xs text-[#E5FF00] hover:underline" data-testid="mark-all-read-btn">Segna lette</button>
              <button onClick={() => setOpen(false)}><X size={14} /></button>
            </div>
          </div>
          {items.length === 0 && <div className="p-4 text-sm text-zinc-500">Nessuna notifica</div>}
          {items.map((n) => (
            <div key={n.id} className={`p-3 border-b border-[#1A1A24] text-sm ${n.read ? "opacity-60" : ""}`}>
              <div className="text-[#00FF66] text-xs font-bold uppercase mb-1">{n.type === "target" ? "Target!" : "Calo prezzo"}</div>
              <div className="text-zinc-200 truncate">{n.title}</div>
              <div className="text-zinc-400 text-xs mt-1">{n.message} {n.currency}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const doLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="min-h-screen flex bg-[#050505] text-zinc-100">
      <aside className="w-60 border-r border-[#2A2A35] bg-[#0A0A0C] flex flex-col fixed h-full">
        <div className="p-5 border-b border-[#2A2A35] flex items-center gap-2">
          <div className="w-8 h-8 bg-[#E5FF00] flex items-center justify-center"><Zap size={18} className="text-black" /></div>
          <span className="font-display font-black tracking-tighter text-lg">BOOST<span className="text-[#E5FF00]">PC</span></span>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} data-testid={`nav-${n.id}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 text-sm transition-colors ${
                  isActive ? "bg-[#E5FF00] text-black font-bold" : "text-zinc-400 hover:text-white hover:bg-[#141419]"
                }`}>
              <n.icon size={17} /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-[#2A2A35]">
          <div className="px-3 py-2 text-xs text-zinc-500 truncate">{user?.email}</div>
          <button onClick={doLogout} data-testid="logout-btn"
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-zinc-400 hover:text-[#FF3B30] transition-colors">
            <LogOut size={17} /> Esci
          </button>
        </div>
      </aside>

      <div className="flex-1 ml-60 flex flex-col">
        <header className="h-16 border-b border-[#2A2A35] bg-black/60 backdrop-blur-xl sticky top-0 z-40 flex items-center justify-between px-6">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500" data-testid="page-title">
            {NAV.find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)))?.label || "Console"}
          </div>
          <Notifications />
        </header>
        <main className="flex-1 p-6 grid-bg">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
