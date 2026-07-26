import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Trophy, Search, Sparkles, Zap, Radio, Wrench, Cpu, Activity,
  HeartPulse, Gamepad2, Library, Clock, Timer, Crown, Star,
  CheckCircle2, Lock, Filter,
} from "lucide-react";
import api from "@/lib/api";
import { toast } from "sonner";

const ICONS = {
  Search, Sparkles, Zap, Radio, Wrench, Cpu, Activity,
  HeartPulse, Gamepad2, Library, Clock, Timer, Crown, Star,
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
};

export default function Milestones() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState(null);
  const [filter, setFilter] = useState("all"); // all / unlocked / locked
  const [category, setCategory] = useState("all");
  const [overlayToken, setOverlayToken] = useState(null);
  const [copied, setCopied] = useState(false);
  const lang = (i18n.language || "it").startsWith("en") ? "en" : "it";

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
      <div className="p-6" data-testid="milestones-loading">
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
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto" data-testid="milestones-page">
      {/* Header hero */}
      <div className="mb-8">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500 mb-2">// {t("milestones.eyebrow", "Progressi")}</div>
        <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter">
          {t("milestones.title", "Milestones")}
        </h1>
        <p className="text-zinc-400 mt-2 max-w-2xl">
          {t("milestones.subtitle", "Sblocca traguardi, guadagna XP e sblocca feature reali. I badge sono anche condivisibili in overlay OBS per i tuoi spettatori.")}
        </p>
      </div>

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
            {m.unlocked && (
              <CheckCircle2 size={12} className="ml-auto text-[#00FF66]" data-testid={`milestone-${m.code}-check`} />
            )}
          </div>
          <div className="font-display font-black text-base leading-tight" data-testid={`milestone-${m.code}-name`}>{name}</div>
          <div className="text-xs text-zinc-500 mt-1 leading-snug">{desc}</div>
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
