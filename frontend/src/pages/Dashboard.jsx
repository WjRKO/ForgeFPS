import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  LineChart, Cpu, MessageSquareCode, PiggyBank, ArrowRight, Zap,
  MonitorDown, Gauge, Gamepad2, Activity, TrendingUp, TrendingDown,
  MessagesSquare, CheckCircle2, Circle, Share2, Bell, Download,
  Sparkles, ShieldCheck, Wifi,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import NextActionBanner from "@/components/NextActionBanner";
import BottleneckDetector from "@/components/BottleneckDetector";
import { ActiveMissionsCard } from "@/components/ActiveMissionsCard";
import { AutoPilotCard } from "@/components/AutoPilotCard";
import { PageHeader, EmptyState, HealthRing, Sparkline, HUDCard, Badge, SkeletonCard,
  stagger, item, BTN_CLASSES } from "@/components/hud";
import { AGENT_EXE_URL, AGENT_EXE_VERSION, AGENT_RELEASES_URL } from "@/config/agent";
import { trackConversion } from "@/lib/gtag";

const DEFAULT_DISCORD_INVITE = "https://discord.gg/KU3m9YFFnm";
const AGENT_SEEN_KEY = `ff_agent_seen_${AGENT_EXE_VERSION}`;

/* ---------------------------------- helpers --------------------------------- */
const fmtDate = (iso, lang) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(lang.startsWith("en") ? "en-US" : "it-IT", {
      day: "numeric", month: "short",
    });
  } catch { return ""; }
};
const relTime = (iso, en) => {
  if (!iso) return "";
  const d = new Date(iso).getTime();
  const diff = (Date.now() - d) / 1000;
  if (diff < 60) return en ? "just now" : "adesso";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}g`;
  return fmtDate(iso, en ? "en" : "it");
};

/* ---------------------------------- widgets --------------------------------- */

function PcHeroCard({ specs, health, t, en }) {
  const hasSpecs = !!(specs?.data?.cpu || specs?.data?.gpu);
  const score = health?.score;
  const color = score >= 80 ? "text-ok" : score >= 55 ? "text-volt" : "text-bad";

  if (!hasSpecs) {
    return (
      <HUDCard testid="pc-empty-card" className="border-volt/30">
        <EmptyState
          icon={MonitorDown}
          title={t("dashboard.pc_no_specs_title")}
          description={t("dashboard.pc_no_specs_desc")}
          action={
            <Link
              to="/app/desktop"
              data-testid="pc-connect-cta"
              className={`mt-3 ${BTN_CLASSES.primaryMono}`}
            >
              <MonitorDown size={14} /> {t("dashboard.pc_connect")}
            </Link>
          }
        />
      </HUDCard>
    );
  }

  const badges = [
    { label: "CPU", value: specs.data.cpu, icon: Cpu },
    { label: "GPU", value: specs.data.gpu, icon: Zap },
    { label: "RAM", value: specs.data.ram, icon: Activity },
  ].filter((b) => b.value);

  const checks = health?.checks || [];
  const bad = checks.filter((c) => c.status === "bad").length;
  const warn = checks.filter((c) => c.status === "warn").length;

  return (
    <HUDCard testid="pc-hero-card" featured className="lg:col-span-2 gap-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Gauge size={16} className="text-volt" />
          <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            {t("dashboard.pc_title")}
          </span>
          {health?.updated_at && (
            <span className="text-[11px] text-zinc-600 font-mono">
              · {t("dashboard.pc_updated")} {relTime(health.updated_at, en)}
            </span>
          )}
        </div>
        <Link
          to="/app/pc"
          data-testid="pc-open-mypc"
          className="text-xs font-mono uppercase tracking-widest text-volt hover:underline"
        >
          {t("dashboard.pc_open")} →
        </Link>
      </div>

      <div className="flex items-center gap-6 flex-wrap">
        {score != null && <HealthRing score={score} size={128} label={health?.grade_key ? t(`mypcpage.health.grade.${health.grade_key}`, health?.grade) : health?.grade} />}

        <div className="flex-1 min-w-0 space-y-2">
          <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-500">
            {t("dashboard.pc_hw")}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {badges.map((b) => (
              <span
                key={b.label}
                className="inline-flex items-center gap-1.5 px-2 py-1 border border-hud bg-panel-deep text-xs text-zinc-300"
                data-testid={`pc-badge-${b.label.toLowerCase()}`}
              >
                <b.icon size={11} className="text-info" />
                <span className="text-zinc-500 font-mono text-[11px]">{b.label}</span>
                <span className="truncate max-w-[160px]">{b.value}</span>
              </span>
            ))}
          </div>

          {(bad > 0 || warn > 0) && (
            <div className="flex items-center gap-2 pt-1">
              {bad > 0 && (
                <Badge tone="red" icon={ShieldCheck} testid="pc-bad-badge">
                  {bad} {bad === 1 ? "issue" : "issues"}
                </Badge>
              )}
              {warn > 0 && (
                <Badge tone="volt" testid="pc-warn-badge">
                  {warn} warn
                </Badge>
              )}
            </div>
          )}
        </div>
      </div>

      <Link
        to="/app/desktop"
        data-testid="pc-optimize-cta"
        className={`inline-flex items-center justify-center gap-2 border py-2.5 text-xs font-mono uppercase tracking-widest transition-colors ${
          score < 55
            ? "border-bad/60 bg-bad/10 text-bad hover:bg-bad/20"
            : "border-volt/60 bg-volt/10 text-volt hover:bg-volt/20"
        }`}
      >
        <Sparkles size={13} /> {t("dashboard.pc_optimize")}
      </Link>
    </HUDCard>
  );
}

function BenchmarkCard({ bench, discord, t, onShare }) {
  const latest = bench?.latest;
  const history = (bench?.history || []).slice(0, 8).reverse();
  const series = history.map((h) => h?.after?.overall || h?.after?.score || 0).filter(Boolean);
  const current = latest?.after?.overall || latest?.after?.score || 0;

  if (!latest || !current) {
    return (
      <HUDCard testid="bench-empty-card">
        <EmptyState
          icon={TrendingUp}
          title={t("dashboard.bench_none_title")}
          description={t("dashboard.bench_none_desc")}
          action={
            <Link
              to="/app/desktop"
              data-testid="bench-empty-cta"
              className={`mt-3 ${BTN_CLASSES.secondaryMono}`}
            >
              {t("dashboard.bench_none_cta")}
            </Link>
          }
        />
      </HUDCard>
    );
  }

  const prev = history.length > 1 ? (history[history.length - 2]?.after?.overall || 0) : 0;
  const delta = prev ? Math.round(((current - prev) / prev) * 100) : 0;
  const positive = delta >= 0;

  return (
    <HUDCard testid="bench-card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp size={14} className="text-ok" />
          <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            {t("dashboard.bench_title")}
          </span>
        </div>
        {discord?.linked && (
          <button
            onClick={onShare}
            data-testid="bench-share-btn"
            className="inline-flex items-center gap-1 text-[11px] font-mono uppercase tracking-widest text-[#5865F2] hover:underline"
          >
            <Share2 size={11} /> {t("dashboard.bench_share")}
          </button>
        )}
      </div>

      <div className="flex items-end gap-4">
        <div>
          <div className="font-display font-black text-4xl tracking-tighter text-white tabular-nums">
            {current.toLocaleString()}
          </div>
          {prev > 0 && (
            <div
              className={`flex items-center gap-1 text-xs font-mono mt-1 ${
                positive ? "text-ok" : "text-bad"
              }`}
              data-testid="bench-delta"
            >
              {positive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {positive ? "+" : ""}{delta}% {t("dashboard.bench_delta")}
            </div>
          )}
        </div>
        {series.length >= 2 && (
          <div className="ml-auto">
            <Sparkline data={series} color={positive ? "#00FF66" : "#E5FF00"} width={140} height={44} />
          </div>
        )}
      </div>
    </HUDCard>
  );
}

function QuickActionsCard({ t }) {
  const actions = [
    { to: "/app/advisor", icon: MessageSquareCode, label: t("dashboard.quick_advisor_title"), testid: "qa-advisor" },
    { to: "/app/desktop", icon: MonitorDown, label: t("dashboard.act_agent"), testid: "qa-agent" },
    { to: "/app/gaming?tab=games", icon: Gamepad2, label: t("dashboard.act_games"), testid: "qa-games" },
    { to: "/app/tracker", icon: LineChart, label: t("dashboard.quick_tracker_title"), testid: "qa-tracker" },
    { to: "/app/builds", icon: Cpu, label: t("dashboard.quick_builds_title"), testid: "qa-builds" },
    { to: "/app/network", icon: Wifi, label: "Network", testid: "qa-network" },
  ];
  return (
    <HUDCard testid="quick-actions-card">
      <div className="flex items-center gap-2 mb-3">
        <Zap size={13} className="text-volt" />
        <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
          {t("dashboard.actions_title")}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {actions.map((a) => (
          <Link
            key={a.to}
            to={a.to}
            data-testid={a.testid}
            className="flex flex-col items-start gap-1.5 border border-hud hover:border-volt p-2.5 transition-colors"
          >
            <a.icon size={14} className="text-volt" />
            <span className="text-[11px] text-zinc-200 leading-tight">{a.label}</span>
          </Link>
        ))}
      </div>
    </HUDCard>
  );
}

function DiscordCard({ discord, user, t }) {
  if (!discord) return <SkeletonCard className="h-32" />;
  const linked = discord.linked;
  return (
    <HUDCard testid="discord-card" className="gap-3">
      <div className="flex items-center gap-2">
        <MessagesSquare size={13} className="text-[#5865F2]" />
        <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
          {t("dashboard.discord_title")}
        </span>
      </div>
      {linked ? (
        <>
          <div className="flex items-center gap-3">
            {user?.discord_avatar || discord.avatar_url ? (
              <img
                src={
                  discord.avatar_url ||
                  `https://cdn.discordapp.com/avatars/${discord.discord_user_id || user?.discord_user_id}/${
                    user?.discord_avatar
                  }.png`
                }
                alt=""
                className="w-9 h-9 rounded-full border border-[#5865F2]/40"
              />
            ) : (
              <div className="w-9 h-9 rounded-full bg-[#5865F2]/20 border border-[#5865F2]/40 flex items-center justify-center">
                <MessagesSquare size={16} className="text-[#5865F2]" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold truncate">
                {discord.username || user?.discord_username || t("dashboard.discord_linked")}
              </div>
              <div className="text-[11px] text-ok font-mono">✓ {t("dashboard.discord_linked")}</div>
            </div>
          </div>
          <a
            href={discord.invite_url || DEFAULT_DISCORD_INVITE}
            target="_blank"
            rel="noreferrer"
            data-testid="discord-open"
            className="inline-flex items-center justify-center gap-1 text-[11px] font-mono uppercase tracking-widest text-[#5865F2] hover:underline"
          >
            {t("dashboard.discord_open")}
          </a>
        </>
      ) : (
        <>
          <p className="text-xs text-zinc-500 leading-relaxed">{t("dashboard.discord_unlinked")}</p>
          <Link
            to="/app/account"
            data-testid="discord-link-cta"
            className="inline-flex items-center justify-center gap-1.5 bg-[#5865F2] text-white font-bold px-3 py-2 text-[11px] font-mono uppercase tracking-widest hover:bg-[#4752C4] transition-colors"
          >
            <MessagesSquare size={12} /> {t("dashboard.discord_link_cta")}
          </Link>
        </>
      )}
    </HUDCard>
  );
}

function AgentCard({ t }) {
  const seen = typeof window !== "undefined" && localStorage.getItem(AGENT_SEEN_KEY) === "1";
  const markSeen = () => {
    try { localStorage.setItem(AGENT_SEEN_KEY, "1"); } catch {}
    trackConversion("agent_download");
  };
  return (
    <HUDCard testid="agent-card" className="gap-3 border-info/40 bg-gradient-to-br from-info/10 to-transparent">
      <div className="flex items-center gap-2">
        <MonitorDown size={13} className="text-info" />
        <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
          {t("dashboard.agent_title")}
        </span>
        {!seen && <span className="ml-auto text-[11px] font-mono uppercase text-info border border-info/40 px-1">NEW</span>}
      </div>
      <div>
        <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-500">
          {t("dashboard.agent_latest")}
        </div>
        <div className="text-lg font-display font-black tracking-tight text-white">{AGENT_EXE_VERSION}</div>
      </div>
      <a
        href={AGENT_EXE_URL}
        target="_blank"
        rel="noreferrer"
        onClick={markSeen}
        data-testid="agent-download-btn"
        className="inline-flex items-center justify-center gap-1.5 bg-info text-black font-bold py-2 text-[11px] font-mono uppercase tracking-widest hover:bg-[#33e8ff] transition-colors"
      >
        <Download size={12} /> {t("dashboard.agent_download")}
      </a>
      <a
        href={AGENT_RELEASES_URL}
        target="_blank"
        rel="noreferrer"
        data-testid="agent-view-releases"
        className="text-center text-[11px] font-mono text-zinc-500 hover:text-info"
      >
        {t("dashboard.agent_view")} →
      </a>
    </HUDCard>
  );
}

function ActivityFeed({ notifs, bench, agentUpdateSeen, t, en }) {
  const events = useMemo(() => {
    const list = [];
    (notifs || []).slice(0, 6).forEach((n) =>
      list.push({
        id: `n-${n.id}`,
        kind: "drop",
        icon: Bell,
        color: "text-ok",
        label: n.title || t("dashboard.feed_drop"),
        detail: `${n.old_price} → ${n.new_price} ${n.currency || "€"}`,
        at: n.created_at,
        to: `/app/tracker/${n.product_id}`,
      })
    );
    if (bench?.latest) {
      list.push({
        id: "b-latest",
        kind: "bench",
        icon: TrendingUp,
        color: "text-volt",
        label: t("dashboard.feed_bench"),
        detail: `${(bench.latest.after?.overall || bench.latest.after?.score || 0).toLocaleString()} pts`,
        at: bench.latest.created_at || bench.latest.ts,
        to: "/app/pc",
      });
    }
    if (!agentUpdateSeen) {
      list.push({
        id: "a-release",
        kind: "release",
        icon: Download,
        color: "text-info",
        label: t("dashboard.feed_release"),
        detail: AGENT_EXE_VERSION,
        at: new Date().toISOString(),
        to: "/app/desktop",
      });
    }
    return list.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()).slice(0, 6);
  }, [notifs, bench, agentUpdateSeen, t]);

  return (
    <HUDCard testid="activity-feed">
      <div className="flex items-center gap-2 mb-3">
        <Activity size={13} className="text-info" />
        <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
          {t("dashboard.feed_title")}
        </span>
      </div>
      {events.length === 0 ? (
        <p className="text-xs text-zinc-500 py-2">{t("dashboard.feed_none")}</p>
      ) : (
        <ul className="divide-y divide-hud-soft">
          {events.map((e) => (
            <li key={e.id}>
              <Link
                to={e.to}
                data-testid={`feed-${e.kind}`}
                className="flex items-center gap-3 py-2.5 hover:bg-[#141420] -mx-2 px-2 transition-colors"
              >
                <e.icon size={14} className={`${e.color} shrink-0`} />
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-zinc-200 truncate">{e.label}</div>
                  <div className="text-[11px] text-zinc-500 font-mono">{e.detail}</div>
                </div>
                <span className="text-[11px] font-mono text-zinc-600">{relTime(e.at, en)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </HUDCard>
  );
}

function RecentProductsCard({ products, t }) {
  return (
    <HUDCard testid="recent-products-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <LineChart size={13} className="text-volt" />
          <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            {t("dashboard.recent")}
          </span>
        </div>
        <Link to="/app/tracker" className="text-[11px] font-mono uppercase text-volt hover:underline">
          {t("dashboard.see_all")} →
        </Link>
      </div>
      {products.length === 0 ? (
        <EmptyState
          icon={LineChart}
          description={t("dashboard.empty")}
          action={
            <Link
              to="/app/tracker"
              data-testid="dash-add-product"
              className="mt-2 border border-volt text-volt hover:bg-volt hover:text-black px-5 py-2 text-xs font-mono uppercase tracking-widest transition-colors"
            >
              {t("dashboard.add_one")}
            </Link>
          }
        />
      ) : (
        <ul className="divide-y divide-hud-soft">
          {products.map((p) => (
            <li key={p.id}>
              <Link
                to={`/app/tracker/${p.id}`}
                className="flex items-center gap-3 py-2.5 hover:bg-[#141420] -mx-2 px-2 transition-colors"
              >
                <div className="w-9 h-9 bg-black border border-hud flex items-center justify-center overflow-hidden shrink-0">
                  {p.image ? (
                    <img src={p.image} alt="" className="w-full h-full object-contain" />
                  ) : (
                    <Zap size={12} className="text-zinc-600" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs truncate text-zinc-200">{p.title}</div>
                  <div className="text-[11px] text-zinc-500 font-mono uppercase tracking-widest">
                    {p.store || p.platform || "—"}
                  </div>
                </div>
                <div className="text-xs font-bold text-white tabular-nums">
                  {p.current_price != null ? `${p.current_price} ${p.currency || "€"}` : "—"}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </HUDCard>
  );
}

function HeroEmpty({ t }) {
  const items = [
    { icon: Gauge, label: t("dashboard.cta_scan"), to: "/app/desktop", testid: "hero-scan" },
    { icon: Cpu, label: t("dashboard.cta_build"), to: "/app/builds", testid: "hero-build" },
    { icon: LineChart, label: t("dashboard.cta_track"), to: "/app/tracker", testid: "hero-track" },
  ];
  return (
    <div
      className="border border-volt/30 bg-gradient-to-br from-volt/10 via-info/5 to-transparent p-8 mb-6"
      data-testid="hero-empty"
    >
      <div className="max-w-2xl">
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-volt/10 border border-volt/30 mb-4">
          <Sparkles size={12} className="text-volt" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-volt">
            {t("dashboard.eyebrow")}
          </span>
        </div>
        <h2 className="font-display font-black text-3xl tracking-tighter mb-2">
          {t("dashboard.hero_empty_title")}
        </h2>
        <p className="text-zinc-400 text-sm mb-6">{t("dashboard.hero_empty_desc")}</p>
        <div className="grid sm:grid-cols-3 gap-3">
          {items.map((it, i) => (
            <Link
              key={it.to}
              to={it.to}
              data-testid={it.testid}
              className="group flex flex-col gap-2 bg-black/40 border border-hud hover:border-volt p-4 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 bg-volt text-black text-xs font-black flex items-center justify-center">
                  {i + 1}
                </span>
                <it.icon size={14} className="text-volt" />
              </div>
              <span className="text-sm font-semibold text-zinc-100">{it.label}</span>
              <ArrowRight
                size={13}
                className="text-volt group-hover:translate-x-1 transition-transform"
              />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ================================== page =================================== */

export default function Dashboard() {
  const { user } = useAuth();
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "it").startsWith("en");
  const [stats, setStats] = useState(null);
  const [products, setProducts] = useState(null);
  const [specs, setSpecs] = useState(null);
  const [health, setHealth] = useState(null);
  const [bench, setBench] = useState(null);
  const [discord, setDiscord] = useState(null);
  const [notifs, setNotifs] = useState(null);
  const [missions, setMissions] = useState(null);

  // Una sola richiesta: prima erano otto, e /pc-specs e /pc-health facevano
  // molto piu' lavoro di quanto questa pagina disegni.
  useEffect(() => {
    api.get("/dashboard").then(({ data }) => {
      setStats(data.stats);
      setProducts(data.products || []);
      setSpecs(data.specs);
      setHealth(data.health?.available ? data.health : null);
      setBench(data.benchmark?.latest ? data.benchmark : null);
      setDiscord(data.discord);
      setNotifs(data.notifications || []);
      setMissions(data.missions);
      if (data.missions?.just_completed?.length) {
        window.dispatchEvent(new CustomEvent("ff-mission-completed", { detail: data.missions.just_completed }));
      }
    }).catch(() => {
      setStats({}); setProducts([]); setSpecs({}); setHealth(null);
      setBench(null); setDiscord({ linked: false }); setNotifs([]); setMissions(null);
    });
  }, []);

  const shareBench = async () => {
    if (!bench?.latest) return;
    try {
      await api.post("/discord/share-score", {
        kind: "benchmark",
        score:
          bench.latest.after?.overall ||
          bench.latest.after?.score ||
          0,
        metrics: {},
      });
      toast.success(en ? "Score shared to Discord" : "Score condiviso su Discord");
    } catch (e) {
      const msg = e.response?.data?.detail || "";
      toast.error(msg || (en ? "Share failed" : "Condivisione fallita"));
    }
  };

  const hasSpecs = !!(specs?.data?.cpu || specs?.data?.gpu);
  const isBrandNew =
    stats &&
    !hasSpecs &&
    (stats.tracked_products || 0) === 0 &&
    (stats.builds || 0) === 0 &&
    (stats.chat_sessions || 0) === 0;

  const agentUpdateSeen =
    typeof window !== "undefined" && localStorage.getItem(AGENT_SEEN_KEY) === "1";

  const greeting = useMemo(() => {
    const name = user?.name || "Gamer";
    if (health?.score != null) {
      return `${t("dashboard.greeting", { name })} — ${t("dashboard.greet_health", { score: health.score })}`;
    }
    if ((stats?.total_saved || 0) > 0) {
      return `${t("dashboard.greeting", { name })} — ${t("dashboard.greet_saved", { saved: stats.total_saved })}`;
    }
    return `${t("dashboard.greeting", { name })} · ${t("dashboard.greet_ready")}`;
  }, [user, health, stats, t]);

  return (
    <div className="max-w-7xl mx-auto">
      <PageHeader eyebrow={t("dashboard.eyebrow")} title={greeting} actions={<BottleneckDetector compact />} />

      {isBrandNew && <HeroEmpty t={t} />}

      {!isBrandNew && !specs?.data?.cpu && <NextActionBanner kind="no-hw" />}
      {!isBrandNew && specs?.data?.cpu && !bench?.latest
        && !(missions?.active?.length || (missions?.chain && !missions.chain.done))
        && <NextActionBanner kind="post-sync" />}

      <div className="grid lg:grid-cols-[1fr_320px] gap-6 items-start">
        {/* LEFT: main content */}
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="show"
          className="min-w-0 space-y-4"
        >
          <motion.div variants={item}>
            <AutoPilotCard />
          </motion.div>

          <motion.div variants={item}>
            <ActiveMissionsCard data={missions} />
          </motion.div>

          <motion.div variants={item} className="grid md:grid-cols-3 gap-4">
            <PcHeroCard specs={specs} health={health} t={t} en={en} />
            <BenchmarkCard bench={bench} discord={discord} t={t} onShare={shareBench} />
          </motion.div>

          <motion.div variants={item}>
            <ActivityFeed
              notifs={notifs}
              bench={bench}
              agentUpdateSeen={agentUpdateSeen}
              t={t}
              en={en}
            />
          </motion.div>

          {products !== null && (
            <motion.div variants={item}>
              <RecentProductsCard products={products} t={t} />
            </motion.div>
          )}
        </motion.div>

        {/* RIGHT: sticky panel */}
        <aside className="lg:sticky lg:top-6 lg:self-start space-y-4" data-testid="dashboard-sticky">
          <QuickActionsCard t={t} />
          <DiscordCard discord={discord} user={user} t={t} />
          {!agentUpdateSeen && <AgentCard t={t} />}
        </aside>
      </div>
    </div>
  );
}
