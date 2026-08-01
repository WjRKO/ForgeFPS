import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Trophy, Search, Sparkles, Zap, Radio, Wrench, Cpu, Activity,
  HeartPulse, Gamepad2, Library, Clock, Timer, Crown, Star,
  CheckCircle2, Lock, Filter, Swords, Gauge, ArrowRight, X, Target, Flame,
} from "lucide-react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";

const ICONS = {
  Search, Sparkles, Zap, Radio, Wrench, Cpu, Activity,
  HeartPulse, Gamepad2, Library, Clock, Timer, Crown, Star, Gauge, Swords,
};

const TIER_META = {
  bronze:   { color: "text-[#C99A5A]", ring: "border-[#C99A5A]",   bg: "bg-[#C99A5A]/10" },
  silver:   { color: "text-[#B0B7C3]", ring: "border-[#B0B7C3]",   bg: "bg-[#B0B7C3]/10" },
  gold:     { color: "text-[#FFB800]", ring: "border-[#FFB800]",   bg: "bg-[#FFB800]/10" },
  platinum: { color: "text-[#00E0FF]", ring: "border-[#00E0FF]",   bg: "bg-[#00E0FF]/10" },
};

const CATEGORY_LABELS = {
  onboarding: { it: "Onboarding", en: "Onboarding" },
  performance: { it: "Performance", en: "Performance" },
  gaming: { it: "Gaming", en: "Gaming" },
  meta: { it: "Community", en: "Community" },
  secret: { it: "Segreti", en: "Secret" },
};

const RARITY = (pct) => {
  if (pct == null) return null;
  if (pct < 5) return { it: "Leggendario", en: "Legendary", cls: "text-[#B26BFF] border-[#B26BFF]/50 bg-[#B26BFF]/10" };
  if (pct < 20) return { it: "Epico", en: "Epic", cls: "text-[#00E0FF] border-[#00E0FF]/50 bg-[#00E0FF]/10" };
  if (pct < 50) return { it: "Raro", en: "Rare", cls: "text-[#00FF66] border-[#00FF66]/50 bg-[#00FF66]/10" };
  return { it: "Comune", en: "Common", cls: "text-zinc-400 border-zinc-600 bg-zinc-800/40" };
};

const TIER_PERKS = [
  { tier: "bronze", xp: 0, slots: 3 },
  { tier: "silver", xp: 100, slots: 4 },
  { tier: "gold", xp: 300, slots: 5 },
  { tier: "platinum", xp: 800, slots: 6 },
];

export default function Milestones() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState("missions");
  const lang = (i18n.language || "it").startsWith("en") ? "en" : "it";

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto" data-testid="milestones-page">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500 mb-2">// {t("milestones.eyebrow", "Progressi")}</div>
        <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter">
          {t("missions.title", "Missioni")}
        </h1>
        <p className="text-zinc-400 mt-2 max-w-2xl">
          {t("missions.subtitle", "Obiettivi verificati sui dati reali del tuo PC: completali per guadagnare XP. I trofei si sbloccano da soli nel tempo.")}
        </p>
      </div>

      <div className="flex items-center gap-2 mb-6 border-b border-[#2A2A35]">
        <TabButton active={tab === "missions"} onClick={() => setTab("missions")} testid="tab-missions" icon={Swords}>
          {t("missions.tab_missions", "Missioni")}
        </TabButton>
        <TabButton active={tab === "trophies"} onClick={() => setTab("trophies")} testid="tab-trophies" icon={Trophy}>
          {t("missions.tab_trophies", "Trofei")}
        </TabButton>
      </div>

      {tab === "missions" ? <MissionsTab t={t} lang={lang} /> : <TrophiesTab t={t} lang={lang} />}
    </div>
  );
}

function TabButton({ active, onClick, children, testid, icon: Icon }) {
  return (
    <button
      onClick={onClick}
      data-testid={testid}
      className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase tracking-widest transition-colors border-b-2 -mb-px ${
        active ? "border-[#E5FF00] text-[#E5FF00]" : "border-transparent text-zinc-500 hover:text-white"
      }`}
    >
      <Icon size={14} /> {children}
    </button>
  );
}

/* ================================ MISSIONI ================================ */

function MissionsTab({ t, lang }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const en = lang === "en";

  const load = () =>
    api.get("/missions").then(({ data: d }) => {
      setData(d);
      if (d.just_completed?.length) {
        window.dispatchEvent(new CustomEvent("ff-mission-completed", { detail: d.just_completed }));
      }
    }).catch(() => {});

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (kind, code) => {
    setBusy(code);
    try {
      await api.post(`/missions/${kind}/${code}`);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error");
    } finally {
      setBusy("");
    }
  };

  if (!data) {
    return <div className="text-zinc-500 text-sm py-8" data-testid="missions-loading">{t("common.loading", "Caricamento...")}</div>;
  }

  return (
    <div data-testid="missions-tab">
      {/* Catena Recluta */}
      {data.chain && !data.chain.done && (
        <>
          <SectionLabel icon={Crown} text={`${t("missions.chain_title", "Catena Recluta")} · ${data.chain.steps.filter((s) => s.status === "completed").length}/${data.chain.steps.length}`} />
          <div className="border border-[#2A2A35] bg-[#0F0F12] mb-8 divide-y divide-[#1A1A24]" data-testid="chain-block">
            {data.chain.steps.map((s) => (
              <ChainStepRow key={s.code} s={s} en={en} />
            ))}
          </div>
        </>
      )}

      {/* Giornaliere */}
      {data.daily?.missions?.length > 0 && (
        <>
          <SectionLabel
            icon={Flame}
            text={`${t("missions.daily_title", "Missioni del giorno")}${data.daily.streak > 0 ? ` · ${t("missions.daily_streak", { count: data.daily.streak, defaultValue: `streak ${data.daily.streak}g` })}` : ""} · ${t("missions.daily_renew", "si rinnovano a mezzanotte")}`}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-2" data-testid="daily-block">
            {data.daily.missions.map((m) => (
              <WeeklyMissionCard key={m.code} m={m} en={en} t={t} variant="daily" />
            ))}
          </div>
          <p className="text-[11px] text-zinc-600 mb-8" data-testid="daily-streak-hint">
            {t("missions.daily_streak_hint", "Completa almeno 1 giornaliera al giorno: bonus +30 XP a 3 giorni, +70 XP a 7.")}
          </p>
        </>
      )}

      {/* Settimanali AI */}
      {data.weekly?.missions?.length > 0 && (
        <>
          <SectionLabel
            icon={Sparkles}
            text={`${t("missions.weekly_title", "Missioni della settimana")} · ${t("missions.weekly_expires", { date: new Date(data.weekly.expires_at).toLocaleDateString(en ? "en-US" : "it-IT"), defaultValue: `si rinnovano il ${new Date(data.weekly.expires_at).toLocaleDateString("it-IT")}` })}`}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8" data-testid="weekly-block">
            {data.weekly.missions.map((m) => (
              <WeeklyMissionCard key={m.code} m={m} en={en} t={t} />
            ))}
          </div>
        </>
      )}

      {/* Attive */}
      <SectionLabel icon={Swords} text={`${t("missions.active", "Missioni attive")} · ${data.slots.used}/${data.slots.max}`} />
      {data.active.length === 0 ? (
        <div className="border border-dashed border-[#2A2A35] p-6 text-center text-sm text-zinc-500 mb-8" data-testid="missions-none-active">
          <Target size={18} className="mx-auto mb-2 text-zinc-600" />
          {t("missions.none_active", "Nessuna missione attiva. Attivane una qui sotto!")}
        </div>
      ) : (
        <div className="space-y-3 mb-8">
          {data.active.map((m) => (
            <ActiveMissionRow key={m.code} m={m} en={en} t={t} busy={busy} onAbandon={() => act("abandon", m.code)} />
          ))}
        </div>
      )}

      {/* Disponibili */}
      {data.available.length > 0 && (
        <>
          <SectionLabel icon={Target} text={t("missions.available", "Disponibili")} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
            {data.available.map((m) => (
              <AvailableMissionCard
                key={m.code} m={m} en={en} t={t} busy={busy}
                slotsFull={data.slots.used >= data.slots.max}
                onActivate={() => act("activate", m.code)}
              />
            ))}
          </div>
        </>
      )}

      {/* Completate */}
      {data.completed.length > 0 && (
        <>
          <SectionLabel icon={CheckCircle2} text={`${t("missions.completed", "Completate")} · ${data.completed.length}`} />
          <div className="space-y-px" data-testid="missions-completed-list">
            {data.completed.map((m) => (
              <div key={m.code} className="flex items-center gap-3 bg-[#0F0F12] border border-[#1A1A24] px-4 py-2.5" data-testid={`mission-completed-${m.code}`}>
                <CheckCircle2 size={14} className="text-[#00FF66] shrink-0" />
                <span className="text-sm text-zinc-300 flex-1 truncate">{en ? m.name_en : m.name_it}</span>
                <span className="text-[10px] font-mono text-[#00FF66]">+{m.xp} XP</span>
                {m.completed_at && (
                  <span className="text-[10px] font-mono text-zinc-600">{new Date(m.completed_at).toLocaleDateString(en ? "en-US" : "it-IT")}</span>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function SectionLabel({ icon: Icon, text }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={13} className="text-[#E5FF00]" />
      <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">{text}</span>
    </div>
  );
}

function ChainStepRow({ s, en }) {
  const Icon = ICONS[s.icon] || Swords;
  const done = s.status === "completed";
  const locked = s.status === "locked";
  const pct = Math.max(0, Math.min(100, Math.round((s.progress / s.target) * 100)));
  return (
    <div className={`flex items-center gap-4 p-4 ${locked ? "opacity-40" : ""}`} data-testid={`chain-step-${s.code}`}>
      <div className={`w-9 h-9 flex items-center justify-center border shrink-0 ${
        done ? "border-[#00FF66] text-[#00FF66]" : locked ? "border-[#2A2A35] text-zinc-600" : "border-[#E5FF00] text-[#E5FF00]"
      }`}>
        {done ? <CheckCircle2 size={16} /> : locked ? <Lock size={14} /> : <Icon size={16} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-zinc-600">#{s.order}</span>
          <span className={`text-sm font-semibold ${done ? "text-zinc-500 line-through" : "text-zinc-100"}`}>
            {en ? s.name_en : s.name_it}
          </span>
          <span className="text-[10px] font-mono text-[#E5FF00]">+{s.xp} XP</span>
        </div>
        {!done && <div className="text-xs text-zinc-500 mt-0.5">{en ? s.desc_en : s.desc_it}</div>}
        {s.status === "active" && s.target > 1 && (
          <div className="flex items-center gap-3 mt-2">
            <div className="flex-1 h-1 bg-[#0A0A0C] border border-[#2A2A35] overflow-hidden">
              <div className="h-full bg-[#E5FF00]" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[10px] font-mono text-zinc-500">{s.progress}/{s.target}</span>
          </div>
        )}
      </div>
      {s.status === "active" && (
        <Link to={s.link} data-testid={`chain-go-${s.code}`}
          className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-black bg-[#E5FF00] hover:bg-[#D4EC00] px-3 py-1.5 transition-colors shrink-0">
          {en ? s.cta_en : s.cta_it} <ArrowRight size={11} />
        </Link>
      )}
    </div>
  );
}

function WeeklyMissionCard({ m, en, t, variant = "weekly" }) {
  const Icon = ICONS[m.icon] || Sparkles;
  const done = !!m.completed_at;
  const pct = Math.max(0, Math.min(100, Math.round((m.progress / m.target) * 100)));
  const why = en ? m.why_en : m.why_it;
  const daily = variant === "daily";
  const box = done ? "border-[#00FF66]/40 bg-[#00FF66]/[0.03]"
    : daily ? "border-[#FF9F1C]/30 bg-[#FF9F1C]/[0.03]" : "border-[#00E0FF]/30 bg-[#00E0FF]/[0.03]";
  const iconBox = done ? "border-[#00FF66]/50 text-[#00FF66]"
    : daily ? "border-[#FF9F1C]/50 text-[#FF9F1C]" : "border-[#00E0FF]/50 text-[#00E0FF]";
  const barCls = daily ? "bg-[#FF9F1C]" : "bg-[#00E0FF]";
  const goCls = daily ? "bg-[#FF9F1C] hover:bg-[#FFB54C]" : "bg-[#00E0FF] hover:bg-[#33E6FF]";
  return (
    <div className={`border p-4 ${box}`} data-testid={`${variant}-${m.template}`}>
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 flex items-center justify-center border shrink-0 ${iconBox}`}>
          {done ? <CheckCircle2 size={16} /> : <Icon size={16} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-semibold ${done ? "text-zinc-500 line-through" : ""}`}>{en ? m.name_en : m.name_it}</span>
            <span className="text-[10px] font-mono text-[#E5FF00]">+{m.xp} XP</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1">{en ? m.desc_en : m.desc_it}</div>
          {why && (
            <div className="text-[11px] text-[#00E0FF]/90 mt-1.5 italic">
              {t("missions.weekly_why", "Perché")}: {why}
            </div>
          )}
          {!done && (
            <div className="flex items-center gap-3 mt-3">
              <div className="flex-1 h-1.5 bg-[#0A0A0C] border border-[#2A2A35] overflow-hidden">
                <div className={`h-full ${barCls}`} style={{ width: `${pct}%` }} />
              </div>
              <span className="text-[10px] font-mono text-zinc-400 tabular-nums">{m.progress}/{m.target}</span>
              <Link to={m.link} data-testid={`${variant}-go-${m.template}`}
                className={`flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-black px-3 py-1.5 transition-colors ${goCls}`}>
                {en ? m.cta_en : m.cta_it} <ArrowRight size={11} />
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ActiveMissionRow({ m, en, t, busy, onAbandon }) {
  const Icon = ICONS[m.icon] || Swords;
  const pct = Math.max(0, Math.min(100, Math.round((m.progress / m.target) * 100)));
  return (
    <div className="border border-[#E5FF00]/30 bg-[#E5FF00]/[0.03] p-4" data-testid={`mission-row-${m.code}`}>
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 flex items-center justify-center border border-[#E5FF00]/40 text-[#E5FF00] shrink-0">
          <Icon size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-display font-black text-base">{en ? m.name_en : m.name_it}</span>
            <span className="text-[10px] font-mono text-[#E5FF00]">+{m.xp} XP</span>
            <button
              onClick={onAbandon}
              disabled={busy === m.code}
              data-testid={`mission-abandon-${m.code}`}
              title={t("missions.abandon", "Abbandona")}
              className="ml-auto text-zinc-600 hover:text-[#FF3B30] transition-colors disabled:opacity-40"
            >
              <X size={14} />
            </button>
          </div>
          <div className="text-xs text-zinc-400 mt-1">{en ? m.desc_en : m.desc_it}</div>
          <div className="flex items-center gap-3 mt-3">
            <div className="flex-1 h-1.5 bg-[#0A0A0C] border border-[#2A2A35] overflow-hidden">
              <div className="h-full bg-[#E5FF00] transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[10px] font-mono text-zinc-400 tabular-nums">{m.progress}/{m.target}</span>
            <Link
              to={m.link}
              data-testid={`mission-go-${m.code}`}
              className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-black bg-[#E5FF00] hover:bg-[#D4EC00] px-3 py-1.5 transition-colors"
            >
              {en ? m.cta_en : m.cta_it} <ArrowRight size={11} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function AvailableMissionCard({ m, en, t, busy, slotsFull, onActivate }) {
  const Icon = ICONS[m.icon] || Swords;
  return (
    <div className="border border-[#2A2A35] bg-[#0F0F12] p-4 hover:border-zinc-600 transition-colors" data-testid={`mission-avail-${m.code}`}>
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 flex items-center justify-center border border-[#2A2A35] text-zinc-500 shrink-0">
          <Icon size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">{en ? m.name_en : m.name_it}</span>
            <span className="text-[10px] font-mono text-[#E5FF00]">+{m.xp} XP</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1 leading-snug">{en ? m.desc_en : m.desc_it}</div>
          <button
            onClick={onActivate}
            disabled={busy === m.code || slotsFull}
            data-testid={`mission-activate-${m.code}`}
            className="mt-3 text-[10px] font-bold uppercase tracking-widest px-3 py-1.5 border border-[#E5FF00]/50 text-[#E5FF00] hover:bg-[#E5FF00] hover:text-black transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {slotsFull ? t("missions.slots_full", "Slot pieni") : t("missions.activate", "Attiva")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ================================= TROFEI ================================= */

function TrophiesTab({ t, lang }) {
  const [state, setState] = useState(null);
  const [filter, setFilter] = useState("all");
  const [category, setCategory] = useState("all");
  const [overlayToken, setOverlayToken] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get("/milestones").then(({ data }) => setState(data)).catch(() => {});
    api.get("/agent/token").then(({ data }) => setOverlayToken(data.token)).catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (!state) return [];
    return state.milestones.filter((m) => {
      if (filter === "unlocked" && !m.unlocked) return false;
      if (filter === "locked" && m.unlocked) return false;
      if (category !== "all" && m.category !== category) return false;
      return true;
    });
  }, [state, filter, category]);

  const overlayUrl = useMemo(() => {
    if (!overlayToken) return "";
    const backend = process.env.REACT_APP_BACKEND_URL || "";
    return `${backend}/api/milestones/overlay/${overlayToken}`;
  }, [overlayToken]);

  const copyOverlay = () => {
    if (!overlayUrl) return;
    navigator.clipboard.writeText(overlayUrl);
    setCopied(true);
    toast.success(t("milestones.overlay_copied", "URL Overlay copiato"));
    setTimeout(() => setCopied(false), 2000);
  };

  if (!state) {
    return (
      <div data-testid="milestones-loading">
        <div className="text-zinc-500 text-sm">{t("common.loading", "Caricamento...")}</div>
      </div>
    );
  }

  const tierMeta = TIER_META[state.tier] || TIER_META.bronze;
  const nextThresholds = { bronze: 100, silver: 300, gold: 800 };
  const nextAt = nextThresholds[state.tier] || 800;
  const isMax = state.tier === "platinum";
  const tierProgress = isMax ? 100 : Math.max(0, Math.min(100, Math.round((state.xp / nextAt) * 100)));

  return (
    <div data-testid="trophies-tab">
      {/* Stats banner */}
      <div className={`border-2 ${tierMeta.ring} ${tierMeta.bg} p-6 mb-6 flex flex-col md:flex-row md:items-center gap-6`} data-testid="milestones-stats">
        <div className={`w-20 h-20 flex items-center justify-center border-2 ${tierMeta.ring} ${tierMeta.color}`}>
          <Trophy size={32} />
        </div>
        <div className="flex-1">
          <div className={`text-xs font-black uppercase tracking-[0.3em] ${tierMeta.color}`} data-testid="stats-tier">
            {state.tier}
          </div>
          <div className="text-3xl font-black font-mono tabular-nums mt-1" data-testid="stats-xp">
            {state.xp} <span className="text-base text-zinc-500 font-normal">XP</span>
          </div>
          <div className="mt-3 h-2 bg-[#0A0A0C] border border-[#2A2A35] overflow-hidden">
            <div className={`h-full ${tierMeta.color.replace("text-", "bg-")} transition-all duration-500`} style={{ width: `${tierProgress}%` }} data-testid="stats-progress-bar" />
          </div>
          <div className="text-xs text-zinc-500 mt-1.5 font-mono">
            {isMax
              ? t("milestones.max_tier", "Livello massimo raggiunto 👑")
              : `${nextAt - state.xp} XP ${t("milestones.to_next_tier", "al prossimo tier")}`}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-widest text-zinc-500">{t("milestones.unlocked", "Sbloccati")}</div>
          <div className="text-3xl font-black font-mono tabular-nums" data-testid="stats-unlocked-count">
            {state.unlocked_count}<span className="text-base text-zinc-500 font-normal">/{state.total_count}</span>
          </div>
        </div>
      </div>

      {/* Vantaggi tier */}
      <div className="border border-[#2A2A35] bg-[#0F0F12] p-4 mb-6" data-testid="tier-perks-panel">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">
          {t("missions.perks_title", "Vantaggi tier")}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {TIER_PERKS.map((p) => {
            const meta = TIER_META[p.tier];
            const reached = state.xp >= p.xp;
            const isCurrent = state.tier === p.tier;
            return (
              <div key={p.tier} data-testid={`tier-perk-${p.tier}`}
                className={`border p-3 ${isCurrent ? `${meta.ring} ${meta.bg}` : reached ? "border-[#2A2A35]" : "border-[#1A1A24] opacity-50"}`}>
                <div className={`text-[10px] font-black uppercase tracking-widest ${meta.color} flex items-center gap-1.5`}>
                  {reached ? <CheckCircle2 size={11} /> : <Lock size={10} />}
                  {p.tier}
                  {isCurrent && <span className="ml-auto text-[8px] text-zinc-400 normal-case tracking-normal">{t("missions.perks_current", "il tuo tier")}</span>}
                </div>
                <div className="text-[11px] font-mono text-zinc-500 mt-1">{p.xp}+ XP</div>
                <div className="text-xs text-zinc-300 mt-1.5">
                  ⚔ {t("missions.perks_slots", { n: p.slots, defaultValue: `${p.slots} slot missioni` })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* OBS overlay copy */}
      {overlayUrl && (
        <div className="border border-[#2A2A35] bg-[#0F0F12] p-4 mb-6 flex items-center gap-3" data-testid="milestone-overlay-block">
          <Radio size={16} className="text-[#00FF66] shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs uppercase tracking-widest text-zinc-500 mb-0.5">{t("milestones.obs_overlay", "OBS Overlay — Milestone popup live")}</div>
            <div className="text-[11px] font-mono text-zinc-400 truncate">{overlayUrl}</div>
          </div>
          <button
            onClick={copyOverlay}
            className="text-xs font-bold uppercase tracking-widest px-3 py-2 bg-[#E5FF00] text-black hover:bg-[#B8CC00] transition-colors"
            data-testid="milestone-overlay-copy"
          >
            {copied ? t("milestones.copied", "COPIATO ✓") : t("milestones.copy_url", "COPIA URL")}
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Filter size={14} className="text-zinc-500" />
        <FilterButton value="all" current={filter} onClick={setFilter} testid="filter-all">{t("milestones.filter_all", "Tutti")}</FilterButton>
        <FilterButton value="unlocked" current={filter} onClick={setFilter} testid="filter-unlocked">{t("milestones.filter_unlocked", "Sbloccati")}</FilterButton>
        <FilterButton value="locked" current={filter} onClick={setFilter} testid="filter-locked">{t("milestones.filter_locked", "Da sbloccare")}</FilterButton>
        <span className="w-px h-4 bg-[#2A2A35] mx-1" />
        <FilterButton value="all" current={category} onClick={setCategory} testid="cat-all">{t("milestones.cat_all", "Tutte")}</FilterButton>
        {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
          <FilterButton key={k} value={k} current={category} onClick={setCategory} testid={`cat-${k}`}>{v[lang]}</FilterButton>
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="milestones-grid">
        {filtered.map((m) => (
          <MilestoneCard key={m.code} m={m} lang={lang} t={t} />
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full text-center text-zinc-500 py-12 border border-dashed border-[#2A2A35]" data-testid="milestones-empty">
            {t("milestones.empty", "Nessun traguardo in questa categoria")}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterButton({ value, current, onClick, children, testid }) {
  const active = value === current;
  return (
    <button
      onClick={() => onClick(value)}
      data-testid={testid}
      className={`text-[11px] font-bold uppercase tracking-widest px-3 py-1.5 transition-colors ${
        active ? "bg-[#E5FF00] text-black" : "bg-[#0F0F12] text-zinc-400 border border-[#2A2A35] hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}

function MilestoneCard({ m, lang, t }) {
  const Icon = ICONS[m.icon] || Trophy;
  const tierMeta = TIER_META[m.tier] || TIER_META.bronze;
  const name = lang === "en" ? m.name_en : m.name_it;
  const desc = lang === "en" ? m.desc_en : m.desc_it;
  const rewardLabel = m.reward ? (lang === "en" ? m.reward.label_en : m.reward.label_it) : null;
  const progressPct = Math.max(0, Math.min(100, Math.round((m.progress / m.threshold) * 100)));
  const rarity = RARITY(m.rarity_pct);

  return (
    <div
      className={`relative border p-4 transition-all ${
        m.unlocked
          ? `${tierMeta.ring} ${tierMeta.bg}`
          : "border-[#2A2A35] bg-[#0F0F12] opacity-70 hover:opacity-100"
      }`}
      data-testid={`milestone-${m.code}`}
    >
      <div className="flex items-start gap-3">
        <div className={`w-12 h-12 flex items-center justify-center border ${m.unlocked ? tierMeta.ring : "border-[#2A2A35]"} ${m.unlocked ? tierMeta.color : "text-zinc-600"} shrink-0`}>
          {m.unlocked ? <Icon size={20} /> : <Lock size={16} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className={`text-[9px] font-black uppercase tracking-widest ${tierMeta.color}`}>{m.tier}</span>
            <span className="text-zinc-700 text-[9px]">•</span>
            <span className="text-[9px] font-mono text-zinc-500">+{m.xp} XP</span>
            {m.secret && (
              <span className="text-[8px] font-black uppercase tracking-widest px-1 py-0.5 border border-[#B26BFF]/50 text-[#B26BFF]" data-testid={`milestone-${m.code}-secret`}>
                {lang === "en" ? "Secret" : "Segreto"}
              </span>
            )}
            {m.unlocked && (
              <CheckCircle2 size={12} className="ml-auto text-[#00FF66]" data-testid={`milestone-${m.code}-check`} />
            )}
          </div>
          <div className="font-display font-black text-base leading-tight" data-testid={`milestone-${m.code}-name`}>{name}</div>
          <div className="text-xs text-zinc-500 mt-1 leading-snug">{desc}</div>
          {rarity && (
            <div className="mt-2 flex items-center gap-1.5">
              <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 border ${rarity.cls}`} data-testid={`milestone-${m.code}-rarity`}>
                {lang === "en" ? rarity.en : rarity.it}
              </span>
              <span className="text-[9px] font-mono text-zinc-600">
                {m.rarity_pct}% {lang === "en" ? "of players" : "dei giocatori"}
              </span>
            </div>
          )}
          {rewardLabel && (
            <div className="mt-2 text-[10px] uppercase tracking-widest text-[#E5FF00] font-bold">
              🎁 {rewardLabel}
            </div>
          )}
          {!m.unlocked && m.threshold > 1 && (
            <>
              <div className="mt-2.5 h-1 bg-[#0A0A0C] overflow-hidden">
                <div className={`h-full ${tierMeta.color.replace("text-", "bg-")}`} style={{ width: `${progressPct}%` }} />
              </div>
              <div className="text-[10px] font-mono text-zinc-500 mt-1">
                {m.progress} / {m.threshold}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
