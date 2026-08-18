/**
 * AppChangelog — timeline delle release (in-app, autenticato).
 * Legge da GET /api/changelog. Al mount POST /api/changelog/mark-seen
 * per resettare il badge NEW nella sidebar.
 * Differenza vs /changelog pubblico: quello e' curato manualmente per
 * marketing, questo e' generato dal file JSON versionato per patch note veloci.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Sparkles, Wrench, Zap, RefreshCw, Package, Calendar, ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { PageHeader } from "@/components/hud";

const TYPE_META = {
  feature: { icon: Sparkles, color: "#E5FF00", label_it: "NUOVO", label_en: "NEW" },
  fix: { icon: Wrench, color: "#00E0FF", label_it: "FIX", label_en: "FIX" },
  perf: { icon: Zap, color: "#B388FF", label_it: "PERF", label_en: "PERF" },
  refactor: { icon: RefreshCw, color: "#94A3B8", label_it: "REFACTOR", label_en: "REFACTOR" },
};

function ChangeItem({ change, en }) {
  const meta = TYPE_META[change.type] || TYPE_META.feature;
  const Icon = meta.icon;
  return (
    <li className="flex items-start gap-3 py-2" data-testid={`changelog-change-${change.type}`}>
      <span
        className="shrink-0 mt-0.5 inline-flex items-center gap-1 px-2 py-0.5 border text-[11px] font-mono uppercase tracking-widest"
        style={{ borderColor: `${meta.color}55`, color: meta.color }}
      >
        <Icon size={10} /> {en ? meta.label_en : meta.label_it}
      </span>
      <span className="text-sm text-zinc-300 leading-relaxed">{change.text}</span>
    </li>
  );
}

function ReleaseCard({ release, isLatest, en }) {
  return (
    <article className="border border-[#1A1A24] bg-[#0F0F12] p-6 relative" data-testid={`changelog-release-${release.version}`}>
      {isLatest && (
        <span className="absolute -top-2.5 right-4 bg-[#E5FF00] text-black text-[11px] font-mono uppercase tracking-widest px-2 py-0.5">
          {en ? "LATEST" : "ULTIMA"}
        </span>
      )}
      <header className="flex items-baseline flex-wrap gap-3 mb-4 pb-4 border-b border-[#1A1A24]">
        <div className="flex items-center gap-2">
          <Package size={16} className="text-[#E5FF00]" />
          <h2 className="font-display font-black text-2xl tracking-tighter text-white">v{release.version}</h2>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-zinc-500 font-mono">
          <Calendar size={12} /> {release.date}
        </div>
      </header>

      {release.highlights?.length > 0 && (
        <div className="mb-4">
          <div className="text-[11px] font-mono uppercase tracking-widest text-[#E5FF00] mb-2">// {en ? "highlights" : "in evidenza"}</div>
          <ul className="space-y-1">
            {release.highlights.map((h) => (
              <li key={h} className="text-sm text-zinc-200 flex items-start gap-2">
                <span className="text-[#E5FF00] mt-1 shrink-0">▸</span> {h}
              </li>
            ))}
          </ul>
        </div>
      )}

      {release.changes?.length > 0 && (
        <div>
          <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-500 mb-1">// {en ? "all changes" : "tutte le modifiche"}</div>
          <ul className="divide-y divide-[#1A1A24]">
            {release.changes.map((c, i) => <ChangeItem key={`${release.version}-${i}`} change={c} en={en} />)}
          </ul>
        </div>
      )}
    </article>
  );
}

export default function AppChangelog() {
  const { i18n, t } = useTranslation();
  const en = (i18n.resolvedLanguage || i18n.language || "it").startsWith("en");
  const [releases, setReleases] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/changelog").then(({ data }) => {
      setReleases(data.releases || []);
      setLoading(false);
      api.post("/changelog/mark-seen").catch(() => {});
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto fade-up" data-testid="app-changelog-page">
      <PageHeader
        eyebrow={en ? "// release notes" : "// note di rilascio"}
        title={t("app_changelog.title", { defaultValue: en ? "What's New" : "Novita'" })}
      />
      <p className="text-sm text-zinc-400 mb-8 max-w-xl">
        {en
          ? "Every meaningful improvement to FrameForge, from tiny fixes to big new features. Watch this space — it moves fast."
          : "Ogni miglioramento significativo di FrameForge, dai fix piccoli alle feature grandi. Tienila d'occhio — cambia spesso."}
      </p>

      {loading && <div className="text-center text-zinc-500 text-sm py-12" data-testid="app-changelog-loading">{en ? "Loading..." : "Caricamento..."}</div>}
      {!loading && releases.length === 0 && <div className="text-center text-zinc-500 text-sm py-12" data-testid="app-changelog-empty">{en ? "No releases yet." : "Nessuna release ancora."}</div>}

      <div className="space-y-4">
        {releases.map((rel, i) => <ReleaseCard key={rel.version} release={rel} isLatest={i === 0} en={en} />)}
      </div>

      <div className="mt-8 pt-6 border-t border-[#1A1A24] text-xs text-zinc-500 flex items-center justify-between">
        <Link to="/app" className="hover:text-[#E5FF00] inline-flex items-center gap-1.5" data-testid="app-changelog-back">
          <ArrowLeft size={12} /> {en ? "Back to dashboard" : "Torna al dashboard"}
        </Link>
        <span className="font-mono">{releases.length} {en ? "releases" : "release"}</span>
      </div>
    </div>
  );
}
