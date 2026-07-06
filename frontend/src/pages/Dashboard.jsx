import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LineChart, Cpu, MessageSquareCode, PiggyBank, Bell, ArrowRight, Zap, MonitorDown } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function Stat({ icon: Icon, label, value, accent, testid }) {
  return (
    <div data-testid={testid} className="bg-[#0F0F12] border border-[#2A2A35] p-6 card-hover">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">{label}</span>
        <Icon size={18} className={accent || "text-[#E5FF00]"} />
      </div>
      <div className="font-display font-black text-3xl tracking-tighter">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [stats, setStats] = useState(null);
  const [products, setProducts] = useState([]);

  useEffect(() => {
    api.get("/stats").then(({ data }) => setStats(data)).catch(() => {});
    api.get("/products").then(({ data }) => setProducts(data.slice(0, 5))).catch(() => {});
  }, []);

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <div className="mb-8">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("dashboard.eyebrow")}</div>
        <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter">{t("dashboard.greeting", { name: user?.name || "Gamer" })}</h1>
      </div>

      <div className="mb-8 bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/30 p-5" data-testid="onboarding-box">
        <div className="text-sm font-bold text-[#E5FF00] mb-3">{t("dashboard.start3")}</div>
        <div className="grid sm:grid-cols-3 gap-3">
          <Link to="/app/desktop" data-testid="step-connect" className="group bg-black/40 border border-[#2A2A35] p-4 hover:border-[#E5FF00] transition-colors">
            <div className="flex items-center gap-2 mb-1"><span className="w-6 h-6 bg-[#E5FF00] text-black text-xs font-black flex items-center justify-center">1</span><MonitorDown size={16} className="text-[#E5FF00]" /></div>
            <div className="text-sm font-semibold mt-1">{t("dashboard.step1_title")}</div>
            <div className="text-xs text-zinc-500">{t("dashboard.step1_desc")}</div>
          </Link>
          <Link to="/app/advisor" data-testid="step-optimize" className="group bg-black/40 border border-[#2A2A35] p-4 hover:border-[#E5FF00] transition-colors">
            <div className="flex items-center gap-2 mb-1"><span className="w-6 h-6 bg-[#E5FF00] text-black text-xs font-black flex items-center justify-center">2</span><MessageSquareCode size={16} className="text-[#E5FF00]" /></div>
            <div className="text-sm font-semibold mt-1">{t("dashboard.step2_title")}</div>
            <div className="text-xs text-zinc-500">{t("dashboard.step2_desc")}</div>
          </Link>
          <Link to="/app/tracker" data-testid="step-track" className="group bg-black/40 border border-[#2A2A35] p-4 hover:border-[#E5FF00] transition-colors">
            <div className="flex items-center gap-2 mb-1"><span className="w-6 h-6 bg-[#E5FF00] text-black text-xs font-black flex items-center justify-center">3</span><LineChart size={16} className="text-[#E5FF00]" /></div>
            <div className="text-sm font-semibold mt-1">{t("dashboard.step3_title")}</div>
            <div className="text-xs text-zinc-500">{t("dashboard.step3_desc")}</div>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Stat testid="stat-tracked" icon={LineChart} label={t("dashboard.stat_tracked")} value={stats?.tracked_products ?? "—"} />
        <Stat testid="stat-builds" icon={Cpu} label={t("dashboard.stat_builds")} value={stats?.builds ?? "—"} />
        <Stat testid="stat-chats" icon={MessageSquareCode} label={t("dashboard.stat_chats")} value={stats?.chat_sessions ?? "—"} />
        <Stat testid="stat-saved" icon={PiggyBank} label={t("dashboard.stat_saved")} value={stats ? stats.total_saved : "—"} accent="text-[#00FF66]" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Link to="/app/advisor" data-testid="quick-advisor" className="bg-[#0F0F12] border border-[#2A2A35] p-6 card-hover group">
          <MessageSquareCode size={22} className="text-[#E5FF00] mb-4" />
          <h3 className="font-display font-semibold text-lg mb-1">{t("dashboard.quick_advisor_title")}</h3>
          <p className="text-zinc-500 text-sm mb-3">{t("dashboard.quick_advisor_desc")}</p>
          <span className="text-[#E5FF00] text-sm inline-flex items-center gap-1">{t("common.open")} <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" /></span>
        </Link>
        <Link to="/app/builds" data-testid="quick-builds" className="bg-[#0F0F12] border border-[#2A2A35] p-6 card-hover group">
          <Cpu size={22} className="text-[#E5FF00] mb-4" />
          <h3 className="font-display font-semibold text-lg mb-1">{t("dashboard.quick_builds_title")}</h3>
          <p className="text-zinc-500 text-sm mb-3">{t("dashboard.quick_builds_desc")}</p>
          <span className="text-[#E5FF00] text-sm inline-flex items-center gap-1">{t("common.open")} <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" /></span>
        </Link>
        <Link to="/app/tracker" data-testid="quick-tracker" className="bg-[#0F0F12] border border-[#2A2A35] p-6 card-hover group">
          <LineChart size={22} className="text-[#E5FF00] mb-4" />
          <h3 className="font-display font-semibold text-lg mb-1">{t("dashboard.quick_tracker_title")}</h3>
          <p className="text-zinc-500 text-sm mb-3">{t("dashboard.quick_tracker_desc")}</p>
          <span className="text-[#E5FF00] text-sm inline-flex items-center gap-1">{t("common.open")} <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" /></span>
        </Link>
      </div>

      <div className="mt-8 bg-[#0F0F12] border border-[#2A2A35]">
        <div className="p-5 border-b border-[#2A2A35] flex items-center justify-between">
          <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">{t("dashboard.recent")}</span>
          <Link to="/app/tracker" className="text-[#E5FF00] text-xs hover:underline">{t("dashboard.see_all")}</Link>
        </div>
        {products.length === 0 ? (
          <div className="p-8 text-center text-zinc-500 text-sm">{t("dashboard.empty")} <Link to="/app/tracker" className="text-[#E5FF00]">{t("dashboard.add_one")}</Link>.</div>
        ) : (
          products.map((p) => (
            <Link to={`/app/tracker/${p.id}`} key={p.id} className="flex items-center gap-4 p-4 border-b border-[#1A1A24] hover:bg-[#141419] transition-colors">
              <div className="w-10 h-10 bg-black border border-[#2A2A35] flex items-center justify-center overflow-hidden">
                {p.image ? <img src={p.image} alt="" className="w-full h-full object-contain" /> : <Zap size={14} className="text-zinc-600" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate">{p.title}</div>
                <div className="text-xs text-zinc-500">{p.platform}</div>
              </div>
              <div className="text-sm font-bold">{p.current_price != null ? `${p.current_price} ${p.currency}` : "—"}</div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
