import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { LineChart, Cpu, MessageSquareCode, PiggyBank, ArrowRight, Zap, MonitorDown } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, SkeletonCard, SkeletonRow, EmptyState, stagger, item } from "@/components/hud";

const QUICK = [
  { to: "/app/advisor", icon: MessageSquareCode, k: "advisor", testid: "quick-advisor" },
  { to: "/app/builds", icon: Cpu, k: "builds", testid: "quick-builds" },
  { to: "/app/tracker", icon: LineChart, k: "tracker", testid: "quick-tracker" },
];

const STEPS = [
  { to: "/app/desktop", icon: MonitorDown, n: 1, testid: "step-connect", k: "step1" },
  { to: "/app/advisor", icon: MessageSquareCode, n: 2, testid: "step-optimize", k: "step2" },
  { to: "/app/tracker", icon: LineChart, n: 3, testid: "step-track", k: "step3" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [stats, setStats] = useState(null);
  const [products, setProducts] = useState(null);

  useEffect(() => {
    api.get("/stats").then(({ data }) => setStats(data)).catch(() => setStats({}));
    api.get("/products").then(({ data }) => setProducts(data.slice(0, 5))).catch(() => setProducts([]));
  }, []);

  const showOnboarding = !stats || !(stats.tracked_products > 0 && stats.builds > 0);

  return (
    <div className="max-w-6xl mx-auto">
      <PageHeader eyebrow={t("dashboard.eyebrow")} title={t("dashboard.greeting", { name: user?.name || "Gamer" })} />

      {/* onboarding */}
      {showOnboarding && (
      <div className="mb-8 bg-gradient-to-br from-[#E5FF00]/10 to-transparent border border-[#E5FF00]/30 p-5" data-testid="onboarding-box">
        <div className="text-sm font-bold text-[#E5FF00] mb-3 flex items-center gap-2"><Zap size={15} /> {t("dashboard.start3")}</div>
        <motion.div variants={stagger} initial="hidden" animate="show" className="grid sm:grid-cols-3 gap-3">
          {STEPS.map((s) => (
            <motion.div variants={item} key={s.n}>
              <Link to={s.to} data-testid={s.testid} className="group block bg-black/40 border border-[#2A2A35] hover:border-[#E5FF00] hud-tick p-4 transition-colors h-full">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-6 h-6 bg-[#E5FF00] text-black text-xs font-black flex items-center justify-center">{s.n}</span>
                  <s.icon size={16} className="text-[#E5FF00] icon-pop" />
                </div>
                <div className="text-sm font-semibold mt-1">{t(`dashboard.${s.k}_title`)}</div>
                <div className="text-xs text-zinc-500">{t(`dashboard.${s.k}_desc`)}</div>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>
      )}

      {/* stats */}
      {!stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} className="h-24" />)}
        </div>
      ) : (
        <motion.div variants={stagger} initial="hidden" animate="show" className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard testid="stat-tracked" icon={LineChart} label={t("dashboard.stat_tracked")} value={stats.tracked_products ?? "—"} />
          <StatCard testid="stat-builds" icon={Cpu} label={t("dashboard.stat_builds")} value={stats.builds ?? "—"} />
          <StatCard testid="stat-chats" icon={MessageSquareCode} label={t("dashboard.stat_chats")} value={stats.chat_sessions ?? "—"} />
          <StatCard testid="stat-saved" icon={PiggyBank} label={t("dashboard.stat_saved")} value={stats.total_saved ?? "—"} accent="text-[#00FF66]" />
        </motion.div>
      )}

      {/* quick actions */}
      <motion.div variants={stagger} initial="hidden" animate="show" className="grid lg:grid-cols-3 gap-4">
        {QUICK.map((q) => (
          <motion.div variants={item} key={q.k}>
            <Link to={q.to} data-testid={q.testid} className="group block bg-[#0F0F12] border border-[#1A1A24] hover:border-[#2A2A35] card-hover hud-tick p-6 h-full">
              <q.icon size={22} className="text-[#E5FF00] mb-4 icon-pop" />
              <h3 className="font-display font-semibold text-lg mb-1">{t(`dashboard.quick_${q.k}_title`)}</h3>
              <p className="text-zinc-500 text-sm mb-3">{t(`dashboard.quick_${q.k}_desc`)}</p>
              <span className="text-[#E5FF00] text-sm inline-flex items-center gap-1">{t("common.open")} <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" /></span>
            </Link>
          </motion.div>
        ))}
      </motion.div>

      {/* recent */}
      <div className="mt-8 bg-[#0F0F12] border border-[#1A1A24]">
        <div className="p-5 border-b border-[#1A1A24] flex items-center justify-between">
          <span className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">{t("dashboard.recent")}</span>
          <Link to="/app/tracker" className="text-[#E5FF00] text-xs hover:underline">{t("dashboard.see_all")}</Link>
        </div>
        {products === null ? (
          <>{[0, 1, 2].map((i) => <SkeletonRow key={i} />)}</>
        ) : products.length === 0 ? (
          <div className="p-6">
            <EmptyState icon={LineChart}
              description={t("dashboard.empty")}
              action={<Link to="/app/tracker" data-testid="dash-add-product" className="mt-2 border border-[#E5FF00] text-[#E5FF00] hover:bg-[#E5FF00] hover:text-black px-5 py-2 text-xs font-mono uppercase tracking-widest transition-colors">{t("dashboard.add_one")}</Link>} />
          </div>
        ) : (
          products.map((p) => (
            <Link to={`/app/tracker/${p.id}`} key={p.id} className="flex items-center gap-4 p-4 border-b border-[#1A1A24] last:border-0 row-hover">
              <div className="w-10 h-10 bg-black border border-[#2A2A35] flex items-center justify-center overflow-hidden shrink-0">
                {p.image ? <img src={p.image} alt="" className="w-full h-full object-contain" /> : <Zap size={14} className="text-zinc-600" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate">{p.title}</div>
                <div className="text-xs text-zinc-500">{p.store || p.platform}</div>
              </div>
              <div className="text-sm font-bold">{p.current_price != null ? `${p.current_price} ${p.currency}` : "—"}</div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
