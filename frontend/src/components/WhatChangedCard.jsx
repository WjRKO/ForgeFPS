import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { History, TrendingDown, TrendingUp, Minus, AlertTriangle, ShieldCheck, ShieldAlert, Hourglass } from "lucide-react";
import api from "@/lib/api";

const T = {
  it: {
    title: "Cos'è cambiato nel tuo PC",
    sub: "Modifiche di configurazione rilevate dai sync, incrociate con l'andamento delle prestazioni.",
    down: "Le prestazioni sono calate del {pct}%",
    up: "Le prestazioni sono migliorate del {pct}%",
    stable: "Prestazioni stabili",
    vs: "rispetto alla mediana dei {n} rilevamenti precedenti",
    metricBench: "punteggio benchmark",
    metricHealth: "health score",
    suspects: "Cambiamenti nella stessa finestra temporale",
    disclaimer: "Nessuna prova di causalità: sono i sospetti nel periodo giusto, da cui partire.",
    timeline: "Ultimi cambiamenti rilevati",
    added: "aggiunti",
    removed: "rimossi",
    noTrend: "Servono almeno 3 rilevamenti per valutare un andamento.",
    wdRegressed: "Il boost non ha tenuto",
    wdRegressedBody: "Dopo l'ultimo {source} l'Health Score è passato da {from} a {to} ({pct}%). Puoi ripristinare il backup dei tweak dall'agent.",
    wdHeld: "Il boost ha tenuto",
    wdHeldBody: "A 48 ore dall'ultimo {source} le prestazioni sono stabili ({pct}%).",
    wdImproved: "Le prestazioni sono ulteriormente migliorate",
    wdImprovedBody: "Dopo l'ultimo {source}: {pct}% sull'Health Score.",
    wdPending: "Verifica in corso",
    wdPendingBody: "Ricontrolliamo l'effetto dell'ultimo {source} tra qualche giorno: continua a sincronizzare il PC.",
    srcAutopilot: "Auto-Pilot",
    srcLab: "Laboratorio",
  },
  en: {
    title: "What changed on your PC",
    sub: "Configuration changes detected across syncs, cross-referenced with your performance trend.",
    down: "Performance dropped by {pct}%",
    up: "Performance improved by {pct}%",
    stable: "Performance is stable",
    vs: "versus the median of the previous {n} readings",
    metricBench: "benchmark score",
    metricHealth: "health score",
    suspects: "Changes within the same time window",
    disclaimer: "No proof of causation: these are the suspects in the right window, a place to start.",
    timeline: "Latest detected changes",
    added: "added",
    removed: "removed",
    noTrend: "At least 3 readings are needed to assess a trend.",
    wdRegressed: "The boost did not hold",
    wdRegressedBody: "After the last {source} your Health Score went from {from} to {to} ({pct}%). You can restore the tweak backup from the agent.",
    wdHeld: "The boost held",
    wdHeldBody: "48 hours after the last {source}, performance is stable ({pct}%).",
    wdImproved: "Performance improved further",
    wdImprovedBody: "After the last {source}: {pct}% on the Health Score.",
    wdPending: "Verification pending",
    wdPendingBody: "We will re-check the effect of the last {source} in a few days: keep syncing your PC.",
    srcAutopilot: "Auto-Pilot",
    srcLab: "Lab",
  },
};

const LABELS = {
  it: {
    gpu_driver_version: "Driver GPU", ram_speed_mhz: "Velocità RAM", rebar_status: "Resizable BAR",
    cpu: "CPU", gpu: "GPU", ram: "RAM installata", ram_modules: "Moduli RAM",
    os_build: "Build di Windows", bios: "BIOS", motherboard: "Scheda madre",
    refresh_hz: "Refresh del monitor", resolution: "Risoluzione",
    gpu_secondary: "GPU secondaria", cpu_socket: "Socket CPU",
    startup_added: "Nuovi programmi all'avvio", startup_removed: "Programmi all'avvio rimossi",
  },
  en: {
    gpu_driver_version: "GPU driver", ram_speed_mhz: "RAM speed", rebar_status: "Resizable BAR",
    cpu: "CPU", gpu: "GPU", ram: "Installed RAM", ram_modules: "RAM modules",
    os_build: "Windows build", bios: "BIOS", motherboard: "Motherboard",
    refresh_hz: "Monitor refresh", resolution: "Resolution",
    gpu_secondary: "Secondary GPU", cpu_socket: "CPU socket",
    startup_added: "New startup programs", startup_removed: "Removed startup programs",
  },
};

const IMPACT_STYLE = {
  high: "border-[#FF3B30]/50 text-[#FF3B30]",
  medium: "border-[#E5FF00]/40 text-[#E5FF00]",
  low: "border-[#2A2A35] text-zinc-500",
};

const fmtDate = (iso) => {
  try {
    const d = new Date(iso);
    return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
  } catch { return ""; }
};

function ChangeRow({ change, lang, c }) {
  const label = LABELS[lang][change.kind] || change.kind;
  const isStartup = change.kind === "startup_added" || change.kind === "startup_removed";
  return (
    <li className={`border-l-2 pl-3 py-1.5 ${IMPACT_STYLE[change.impact] || IMPACT_STYLE.low}`}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-zinc-200">{label}</span>
        <span className="text-[11px] text-zinc-600 shrink-0">{fmtDate(change.created_at)}</span>
      </div>
      <div className="text-xs text-zinc-500 mt-0.5 break-words">
        {isStartup ? (
          <span>
            {change.count} {change.kind === "startup_added" ? c.added : c.removed}
            {(change.to || change.from) ? ` · ${change.to || change.from}` : ""}
          </span>
        ) : (
          <span className="font-mono">{change.from} → {change.to}</span>
        )}
      </div>
    </li>
  );
}

const WD_STYLE = {
  regressed: { icon: ShieldAlert, box: "border-[#FF3B30]/50 bg-[#FF3B30]/5", tone: "text-[#FF3B30]" },
  improved: { icon: ShieldCheck, box: "border-[#00E0FF]/40 bg-[#00E0FF]/5", tone: "text-[#00E0FF]" },
  held: { icon: ShieldCheck, box: "border-[#E5FF00]/30 bg-[#E5FF00]/5", tone: "text-[#E5FF00]" },
  pending: { icon: Hourglass, box: "border-[#2A2A35]", tone: "text-zinc-400" },
};

function WatchdogBanner({ wd, c }) {
  const st = WD_STYLE[wd.status];
  if (!st) return null;   // expired: niente da dire
  const source = wd.source === "lab" ? c.srcLab : c.srcAutopilot;
  const pct = wd.delta_pct == null ? "" : `${wd.delta_pct > 0 ? "+" : ""}${wd.delta_pct}%`;
  const title = { regressed: c.wdRegressed, improved: c.wdImproved, held: c.wdHeld, pending: c.wdPending }[wd.status];
  const body = { regressed: c.wdRegressedBody, improved: c.wdImprovedBody, held: c.wdHeldBody, pending: c.wdPendingBody }[wd.status]
    .replace("{source}", source)
    .replace("{from}", Math.round(wd.baseline ?? 0))
    .replace("{to}", Math.round(wd.observed ?? 0))
    .replace("{pct}", pct);
  const Icon = st.icon;
  return (
    <div className={`border ${st.box} p-4 mb-5 flex items-start gap-3`} data-testid="watchdog-banner">
      <Icon size={18} className={`${st.tone} shrink-0 mt-0.5`} />
      <div>
        <div className={`text-sm font-semibold ${st.tone}`}>{title}</div>
        <p className="text-xs text-zinc-400 mt-0.5">{body}</p>
      </div>
    </div>
  );
}

export default function WhatChangedCard() {
  const { i18n } = useTranslation();
  const lang = i18n.language && i18n.language.startsWith("en") ? "en" : "it";
  const c = T[lang];
  const [state, setState] = useState(null);
  const [wd, setWd] = useState(null);

  useEffect(() => {
    api.get("/pc/what-changed").then(({ data }) => setState(data)).catch(() => {});
    api.get("/pc/watchdog").then(({ data }) => setWd(data.available ? data.watchdog : null)).catch(() => {});
  }, []);

  if (!state) return null;
  const { trend, suspects = [], changes = [] } = state;
  const showWd = wd && WD_STYLE[wd.status];
  // Nessun trend valutabile, nessun cambiamento e nessuna verifica: niente da dire.
  if (!trend && changes.length === 0 && !showWd) return null;

  const dir = trend?.direction;
  const Icon = dir === "down" ? TrendingDown : dir === "up" ? TrendingUp : Minus;
  const tone = dir === "down" ? "text-[#FF3B30]" : dir === "up" ? "text-[#00E0FF]" : "text-zinc-400";
  const headline = dir === "down"
    ? c.down.replace("{pct}", Math.abs(trend.delta_pct))
    : dir === "up"
      ? c.up.replace("{pct}", Math.abs(trend.delta_pct))
      : c.stable;
  const metricLabel = state.metric === "benchmark" ? c.metricBench : c.metricHealth;

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick p-6 mb-4" data-testid="what-changed-card">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1 flex items-center gap-2">
        <History size={14} className="text-[#E5FF00]" /> {c.title}
      </div>
      <p className="text-xs text-zinc-600 mb-4">{c.sub}</p>

      {showWd && <WatchdogBanner wd={wd} c={c} />}

      {trend ? (
        <div className="flex items-start gap-3 mb-5" data-testid="what-changed-trend">
          <Icon size={20} className={`${tone} shrink-0 mt-0.5`} />
          <div>
            <div className={`text-sm font-semibold ${tone}`}>{headline}</div>
            <div className="text-xs text-zinc-500">
              {metricLabel} {trend.current} · {c.vs.replace("{n}", trend.samples - 1)} ({trend.baseline})
            </div>
          </div>
        </div>
      ) : (
        <p className="text-xs text-zinc-600 mb-5" data-testid="what-changed-no-trend">{c.noTrend}</p>
      )}

      {dir === "down" && suspects.length > 0 && (
        <div className="mb-5" data-testid="what-changed-suspects">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
            <AlertTriangle size={12} className="text-[#FF3B30]" /> {c.suspects}
          </div>
          <ul className="space-y-1.5">
            {suspects.map((s, i) => <ChangeRow key={`s-${i}`} change={s} lang={lang} c={c} />)}
          </ul>
          <p className="text-[11px] text-zinc-600 mt-2 italic">{c.disclaimer}</p>
        </div>
      )}

      {changes.length > 0 && (
        <div data-testid="what-changed-timeline">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-2">{c.timeline}</div>
          <ul className="space-y-1.5">
            {changes.slice(0, 6).map((ch, i) => <ChangeRow key={`c-${i}`} change={ch} lang={lang} c={c} />)}
          </ul>
        </div>
      )}
    </div>
  );
}
