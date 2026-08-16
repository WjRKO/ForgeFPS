import { NavLink, Link, useNavigate, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { LayoutDashboard, MessageSquareCode, Cpu, LineChart, MonitorDown, LogOut, Bell, Zap, X, BellRing, BellOff, Activity, Rocket, Shield, Radio, Gamepad2, SlidersHorizontal, TerminalSquare, Swords, Gauge, Menu, Settings, FileBarChart, Sparkles, MessageSquare, Trophy, FlaskConical, Check } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { DeviceSwitcher } from "@/components/DeviceSwitcher";
import FreshnessBadge from "@/components/FreshnessBadge";
import OnboardingTour from "@/components/OnboardingTour";
import MobileHandoffModal from "@/components/MobileHandoffModal";
import PlanStatusBanner from "@/components/PlanStatusBanner";
import ProfileMenu from "@/components/ProfileMenu";
import FeedbackModal from "@/components/FeedbackModal";
import AgentUpdateBanner from "@/components/AgentUpdateBanner";
import XpSidebarWidget from "@/components/XpSidebarWidget";
import { MissionCelebration } from "@/components/MissionCelebration";
import { Smartphone } from "lucide-react";
import api from "@/lib/api";
import { pushSupported, getPushState, enablePush, disablePush } from "@/lib/push";

const NAV_GROUPS = [
  { section: null, items: [
    { to: "/app", label: "nav.dashboard", icon: LayoutDashboard, end: true, id: "dashboard" },
    { to: "/app/milestones", label: "nav.milestones", icon: Swords, id: "milestones" },
  ]},
  { section: "section.pc", items: [
    { to: "/app/pc", label: "nav.pc", icon: Activity, id: "pc" },
    { to: "/app/lab", label: "nav.lab", icon: FlaskConical, id: "lab" },
    { to: "/app/network", label: "nav.network", icon: Gauge, id: "network" },
    { to: "/app/bios", label: "nav.bios", icon: SlidersHorizontal, id: "bios" },
  ]},
  { section: "section.gaming", items: [
    { to: "/app/gaming", label: "nav.gaming", icon: Gamepad2, id: "gaming" },
    { to: "/app/advisor", label: "nav.advisor", icon: MessageSquareCode, id: "advisor" },
  ]},
  { section: "section.buy", items: [
    { to: "/app/builds", label: "nav.builds", icon: Cpu, id: "builds" },
    { to: "/app/upgrade", label: "nav.upgrade", icon: Rocket, id: "upgrade" },
    { to: "/app/tracker", label: "nav.tracker", icon: LineChart, id: "tracker" },
  ]},
  { section: "section.tools", items: [
    { to: "/app/desktop", label: "nav.desktop", icon: MonitorDown, id: "desktop" },
    { to: "/app/report", label: "nav.report", icon: FileBarChart, id: "report" },
    { to: "/app/commands", label: "nav.commands", icon: TerminalSquare, id: "commands" },
  ]},
  { section: null, items: [
    { to: "/app/admin", label: "nav.admin", icon: Shield, id: "admin", adminOnly: true },
  ]},
  { section: "section.community", items: [
    { to: "/app/changelog", label: "nav.changelog", icon: Sparkles, id: "changelog", badge: "unseen" },
    { action: "feedback", label: "nav.feedback", icon: MessageSquare, id: "feedback" },
  ]},
];

const NAV = NAV_GROUPS.flatMap((g) => g.items);

function Notifications() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [pushState, setPushState] = useState("default");
  const [pushBusy, setPushBusy] = useState(false);
  const unread = items.filter((n) => !n.read).length;

  const load = async () => {
    try { const { data } = await api.get("/notifications"); setItems(data); } catch {}
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);
  useEffect(() => { getPushState().then(setPushState); }, []);

  const markAll = async () => { await api.post("/notifications/read-all"); load(); };

  // Prima si poteva solo azzerare tutto: una notifica letta si portava dietro
  // tutte le altre non ancora viste.
  const markOne = async (id) => {
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
    try { await api.post(`/notifications/${id}/read`); } catch { load(); }
  };

  const togglePush = async () => {
    setPushBusy(true);
    try {
      if (pushState === "subscribed") {
        await disablePush();
        setPushState("default");
        toast.success(t("notif.push_disabled"));
      } else {
        await enablePush();
        setPushState("subscribed");
        toast.success(t("notif.push_enabled"));
        await api.post("/push/test").catch(() => {});
      }
    } catch (e) {
      if (e.code === "blocked") {
        setPushState("denied");
        toast.error(t("notif.push_blocked_help"), { duration: 10000 });
      } else if (e.code === "dismissed") {
        toast.error(t("notif.push_dismissed_help"), { duration: 8000 });
      } else {
        toast.error(e.message || t("notif.push_err"));
      }
    } finally { setPushBusy(false); }
  };

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
        <div className="absolute right-0 mt-2 w-80 bg-[#0F0F12] border border-[#2A2A35] z-50 max-h-[28rem] overflow-auto">
          <div className="flex items-center justify-between p-3 border-b border-[#2A2A35]">
            <span className="text-xs uppercase tracking-widest text-zinc-500">{t("notif.title")}</span>
            <div className="flex gap-2">
              <button onClick={markAll} className="text-xs text-[#E5FF00] hover:underline" data-testid="mark-all-read-btn">{t("notif.mark_read")}</button>
              <button onClick={() => setOpen(false)}><X size={14} /></button>
            </div>
          </div>
          {pushSupported() && (
            <div className="border-b border-[#1A1A24]">
              <button data-testid="toggle-push-btn" onClick={togglePush} disabled={pushBusy || pushState === "denied"}
                className="w-full flex items-center gap-2 px-3 py-2.5 text-xs hover:bg-[#141419] transition-colors disabled:opacity-50">
                {pushState === "subscribed" ? <BellOff size={14} className="text-[#FF3B30]" /> : <BellRing size={14} className="text-[#00FF66]" />}
                {pushState === "denied" ? t("notif.push_blocked")
                  : pushState === "subscribed" ? t("notif.push_off") : t("notif.push_on")}
              </button>
              {pushState === "denied" && (
                <div data-testid="push-unblock-hint" className="px-3 pb-2.5 text-[11px] text-amber-400/90 leading-snug">
                  {t("notif.push_unblock_hint")}
                </div>
              )}
            </div>
          )}
          {items.length === 0 && <div className="p-4 text-sm text-zinc-500">{t("notif.empty")}</div>}
          {items.map((n) => {
            const known = ["target", "price_drop", "recap", "regression", "broadcast",
                           "unlock", "badge", "access", "refresh", "fps_drop", "hitch"];
            const label = t(`notif.${known.includes(n.type) ? n.type : "generic"}`);
            const text = n.body || n.message || "";
            const Row = (
              <>
                <div className="flex items-start justify-between gap-2">
                  <div className={`text-xs font-bold uppercase mb-1 ${n.type === "regression" ? "text-[#FF3B30]" : "text-[#00FF66]"}`}>{label}</div>
                  {!n.read && (
                    <button
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); markOne(n.id); }}
                      title={t("notif.mark_one_read")}
                      aria-label={t("notif.mark_one_read")}
                      data-testid="mark-one-read-btn"
                      className="shrink-0 text-zinc-600 hover:text-[#E5FF00] transition-colors"
                    >
                      <Check size={13} />
                    </button>
                  )}
                </div>
                <div className="text-zinc-200 truncate">{n.title}</div>
                {text && <div className="text-zinc-400 text-xs mt-1">{text} {n.currency || ""}</div>}
              </>
            );
            const cls = `p-3 border-b border-[#1A1A24] text-sm block ${n.read ? "opacity-60" : ""}`;
            return n.link ? (
              <Link key={n.id} to={n.link} onClick={() => { markOne(n.id); setOpen(false); }} className={`${cls} hover:bg-[#12121A]`}>
                {Row}
              </Link>
            ) : (
              <div key={n.id} className={cls}>{Row}</div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [changelogUnseen, setChangelogUnseen] = useState(0);

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  useEffect(() => {
    let stop = false;
    const load = () => api.get("/changelog/status").then(({ data }) => {
      if (!stop) setChangelogUnseen(data?.unseen || 0);
    }).catch(() => {});
    load();
    const t = setInterval(load, 60_000);
    return () => { stop = true; clearInterval(t); };
  }, [location.pathname]);

  // v0.7.4: rimosso `prefetchAdvisorSync` (era hover-triggered con threshold 5min).
  // Faceva partire una silent-sync su ogni hover dell'Advisor navlink -> popup
  // "Aprire FrameForge?" ripetitivi e (con exe non allineato) finestre PowerShell
  // visibili. L'utente ora aggiorna manualmente col FreshnessBadge.

  const doLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="min-h-screen flex bg-[#050505] text-zinc-100">
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/60 z-40 md:hidden" onClick={() => setMobileOpen(false)} data-testid="sidebar-overlay" />
      )}
      <aside className={`w-60 border-r border-[#2A2A35] bg-[#0A0A0C] flex flex-col fixed h-full z-50 transition-transform duration-200 ${mobileOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`} data-testid="sidebar">
        <div className="p-5 border-b border-[#2A2A35] flex items-center gap-2">
          <div className="w-8 h-8 bg-[#E5FF00] flex items-center justify-center"><Zap size={18} className="text-black" /></div>
          <span className="font-display font-black tracking-tighter text-lg">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_GROUPS.map((group, gi) => {
            const items = group.items.filter((n) => !n.adminOnly || user?.role === "admin");
            if (items.length === 0) return null;
            return (
              <div key={gi} className={group.section ? "pt-3" : ""}>
                {group.section && (
                  <div className="px-3 pb-1.5 text-[10px] uppercase tracking-[0.2em] text-zinc-600 font-bold">{t(group.section)}</div>
                )}
                {items.map((n) => {
                  if (n.action === "feedback") {
                    return (
                      <button
                        key={`action-${n.id}`}
                        type="button"
                        onClick={() => setFeedbackOpen(true)}
                        data-testid={`nav-${n.id}`}
                        className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-zinc-400 hover:text-white hover:bg-[#141419] transition-colors"
                      >
                        <n.icon size={17} /> {t(n.label)}
                      </button>
                    );
                  }
                  const badgeCount = n.badge === "unseen" ? changelogUnseen : 0;
                  return (
                    <NavLink key={n.to} to={n.to} end={n.end} data-testid={`nav-${n.id}`}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-3 py-2.5 text-sm transition-colors ${
                          isActive ? "bg-[#E5FF00] text-black font-bold" : "text-zinc-400 hover:text-white hover:bg-[#141419]"
                        }`}>
                      <n.icon size={17} />
                      <span className="flex-1">{t(n.label)}</span>
                      {badgeCount > 0 && (
                        <span
                          className="min-w-[18px] h-[18px] px-1.5 flex items-center justify-center bg-[#FF3B30] text-white text-[10px] font-bold rounded-full"
                          data-testid={`nav-${n.id}-badge`}
                        >
                          {badgeCount > 9 ? "9+" : badgeCount}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>
        <XpSidebarWidget />
      </aside>

      <div className="flex-1 md:ml-60 flex flex-col min-w-0">
        <header className="h-16 border-b border-[#2A2A35] bg-black/60 backdrop-blur-xl sticky top-0 z-40 flex items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <button className="md:hidden p-2 border border-[#2A2A35] hover:border-[#E5FF00] transition-colors" onClick={() => setMobileOpen(true)} data-testid="sidebar-toggle" aria-label="Menu">
              <Menu size={18} />
            </button>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 truncate" data-testid="page-title">
              {(() => { const n = NAV.find((x) => (x.end ? location.pathname === x.to : location.pathname.startsWith(x.to))); return n ? t(n.label) : t("common.console"); })()}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <FreshnessBadge />
            <button
              type="button"
              onClick={() => setHandoffOpen(true)}
              className="hidden sm:inline-flex items-center gap-1.5 border border-[#2A2A35] text-zinc-400 hover:text-[#E5FF00] hover:border-[#E5FF00] px-2.5 py-1.5 text-xs transition-colors"
              title={t("mobile.handoff_title", { defaultValue: "Continua sul telefono" })}
              data-testid="mobile-handoff-header-btn">
              <Smartphone size={14} />
              <span className="hidden lg:inline">{t("mobile.handoff_short", { defaultValue: "Telefono" })}</span>
            </button>
            <DeviceSwitcher />
            <LanguageSwitcher />
            <Notifications />
            <ProfileMenu />
          </div>
        </header>
        <AgentUpdateBanner />
        <PlanStatusBanner />
        <main className="flex-1 grid-bg overflow-x-hidden">
          <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
            <Outlet />
          </div>
        </main>
      </div>
      <OnboardingTour />
      <MissionCelebration />
      <MobileHandoffModal open={handoffOpen} onClose={() => setHandoffOpen(false)} />
      <FeedbackModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </div>
  );
}
