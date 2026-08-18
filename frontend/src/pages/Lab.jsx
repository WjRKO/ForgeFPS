/**
 * Lab.jsx — Laboratorio Automatico delle Prestazioni (Fase 1).
 * Il backend orchestre la pipeline SNAPSHOT -> BASELINE x3 -> TEST LOOP -> REPORT;
 * l'agent locale (mode=lab) applica/misura/annulla i tweak uno alla volta.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { FlaskConical, Play, ShieldAlert, StopCircle, CheckCircle2, XCircle, RotateCcw, Timer, Activity, FileBarChart, Share2, Users, Wrench, Zap, RefreshCw, History } from "lucide-react";
import { toPng } from "html-to-image";
import { toast } from "sonner";
import api from "@/lib/api";
import i18n from "@/i18n";
import { PageHeader, HUDCard, Badge } from "@/components/hud";
import { SecureRunBlock } from "@/components/SecureRunBlock";
import OneClickLaunchButton from "@/components/OneClickLaunchButton";

const isEn = () => i18n.language?.startsWith("en");
const T = (it, en) => (isEn() ? en : it);

const PHASES = [
  { id: "snapshot", it: "Snapshot", en: "Snapshot" },
  { id: "baseline", it: "Baseline", en: "Baseline" },
  { id: "testing", it: "Test tweak", en: "Tweak tests" },
  { id: "synergy", it: "Synergy", en: "Synergy" },
  { id: "validation", it: "Validazione", en: "Validation" },
  { id: "completed", it: "Report", en: "Report" },
];
const PHASE_IDX = { waiting_agent: -1, snapshot: 0, baseline: 1, testing: 2, awaiting_reboot: 2, synergy: 3, validation: 4, completed: 5, aborting: 2, aborted: -1 };

const StatusPill = ({ status }) => {
  const map = {
    waiting_agent: ["bg-amber-500/15 text-amber-400", T("In attesa agent", "Waiting for agent")],
    snapshot: ["bg-cyan-500/15 text-cyan-400", T("Snapshot in corso", "Snapshotting")],
    baseline: ["bg-cyan-500/15 text-cyan-400", T("Baseline in corso", "Baseline running")],
    testing: ["bg-[#E5FF00]/15 text-[#E5FF00]", T("Test in corso", "Testing")],
    awaiting_reboot: ["bg-orange-500/15 text-orange-400", T("Riavvio richiesto", "Reboot required")],
    synergy: ["bg-purple-500/15 text-purple-400", T("Synergy pass", "Synergy pass")],
    validation: ["bg-[#00E0FF]/15 text-[#00E0FF]", T("Validazione in gioco", "In-game validation")],
    aborting: ["bg-orange-500/15 text-orange-400", T("Interruzione...", "Aborting...")],
    aborted: ["bg-zinc-500/15 text-zinc-400", T("Interrotta", "Aborted")],
    completed: ["bg-[#00FF66]/15 text-[#00FF66]", T("Completata", "Completed")],
  };
  const [cls, label] = map[status] || map.waiting_agent;
  return <span data-testid="lab-status-pill" className={`px-2.5 py-1 text-[11px] uppercase tracking-widest font-bold ${cls}`}>{label}</span>;
};

const Stepper = ({ status }) => {
  const idx = PHASE_IDX[status] ?? -1;
  return (
    <div className="flex items-center gap-1 flex-wrap" data-testid="lab-stepper">
      {PHASES.map((p, i) => (
        <div key={p.id} className="flex items-center gap-1">
          <div className={`px-2.5 py-1 text-[11px] uppercase tracking-widest border ${i < idx ? "border-[#00FF66]/40 text-[#00FF66]" : i === idx ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/10" : "border-[#2A2A35] text-zinc-600"}`}>
            {i + 1}. {isEn() ? p.en : p.it}
          </div>
          {i < PHASES.length - 1 && <div className={`w-4 h-px ${i < idx ? "bg-[#00FF66]/40" : "bg-[#2A2A35]"}`} />}
        </div>
      ))}
    </div>
  );
};

const DecisionBadge = ({ decision }) =>
  decision === "kept" ? (
    <span className="inline-flex items-center gap-1 text-[11px] uppercase tracking-widest font-bold text-[#00FF66]"><CheckCircle2 size={12} /> {T("Mantenuto", "Kept")}</span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[11px] uppercase tracking-widest font-bold text-orange-400"><RotateCcw size={12} /> Rollback</span>
  );

function FleetValidationCard() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/lab/fleet-validation").then(({ data: d }) => setData(d)).catch(() => {});
  }, []);
  if (!data) return null;
  const items = (data.items || []).filter((i) => i.tested >= 1);
  return (
    <HUDCard testid="fleet-validation-card">
      <div className="p-5">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2">
            <Users size={13} className="text-[#00E0FF]" /> {T("Validati dalla flotta", "Fleet-validated")}
          </div>
          <span className="text-[11px] font-mono text-zinc-500">
            {data.total_tests} {T("test anonimi", "anonymous tests")} · {T("fascia hw", "hw class")}: <span className="text-zinc-300">{data.hw_class}</span>
          </span>
        </div>
        <div className="text-[11px] text-zinc-500 mb-4">
          {T("Risultati reali e anonimi degli esperimenti Lab di tutti gli utenti FrameForge.",
             "Real, anonymous results from Lab experiments across all FrameForge users.")}
        </div>
        {items.length === 0 ? (
          <div className="border border-dashed border-[#2A2A35] p-5 text-center text-sm text-zinc-500" data-testid="fleet-empty">
            {T("La flotta sta ancora raccogliendo dati — completa un esperimento per contribuire ai primi risultati.",
               "The fleet is still gathering data — complete an experiment to contribute the first results.")}
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-2">
            {items.map((it) => (
              <div key={it.tweak_id} className="border border-[#1A1A24] bg-black/30 p-3" data-testid={`fleet-tweak-${it.tweak_id}`}>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-200 flex-1 truncate">{it.name}</span>
                  <span className={`text-sm font-mono font-black tabular-nums ${it.success_pct >= 60 ? "text-[#00FF66]" : it.success_pct >= 40 ? "text-[#E5FF00]" : "text-zinc-400"}`}>
                    {it.success_pct}%
                  </span>
                </div>
                <div className="mt-1.5 h-1 bg-[#0A0A0C] border border-[#1A1A24] overflow-hidden">
                  <div className={`h-full ${it.success_pct >= 60 ? "bg-[#00FF66]" : it.success_pct >= 40 ? "bg-[#E5FF00]" : "bg-zinc-600"}`} style={{ width: `${it.success_pct}%` }} />
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-[11px] font-mono text-zinc-500">
                  <span>{it.tested} test</span>
                  <span>·</span>
                  <span>{it.avg_delta_pct >= 0 ? "+" : ""}{it.avg_delta_pct}% FPS {T("medio", "avg")}</span>
                  {it.hw && (
                    <span className="ml-auto text-[#00E0FF]" data-testid={`fleet-hw-${it.tweak_id}`}>
                      {T("tuo hw", "your hw")}: {it.hw.success_pct}% ({it.hw.tested})
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </HUDCard>
  );
}

function SetupCard({ registry, onStart, starting }) {
  const [risk, setRisk] = useState("medium");
  const [win, setWin] = useState(90);
  const [reboot, setReboot] = useState(true);
  const [preview, setPreview] = useState(registry);
  useEffect(() => {
    api.get(`/lab/registry?risk_level=${risk}&include_reboot=${reboot}`).then(({ data }) => setPreview(data)).catch(() => {});
  }, [risk, reboot]);
  const n = preview?.candidates?.length || 0;
  const nReboot = (preview?.candidates || []).filter((c) => c.requires_reboot).length;
  const fleetN = (preview?.candidates || []).reduce((acc, c) => acc + (c.fleet?.tested || 0), 0);
  const estMin = Math.round(((3 + n * 3) * (win + 8)) / 60) + 5;
  return (
    <HUDCard testid="lab-setup-card">
      <div className="p-5 space-y-5">
        <div>
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{T("1 · Livello di rischio", "1 · Risk level")}</div>
          <div className="flex gap-2">
            {[
              { id: "safe", it: "Solo sicuri", en: "Safe only" },
              { id: "medium", it: "Sicuri + Medi", en: "Safe + Medium" },
            ].map((o) => (
              <button key={o.id} data-testid={`lab-risk-${o.id}`} onClick={() => setRisk(o.id)}
                className={`px-4 py-2 text-xs uppercase tracking-widest border transition-colors ${risk === o.id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/10" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-500"}`}>
                {isEn() ? o.en : o.it}
              </button>
            ))}
          </div>
          <div className="text-[11px] text-zinc-500 mt-1.5">{T("Tutti i tweak sono reversibili automaticamente (backup mirato + punto di ripristino).", "All tweaks are automatically reversible (targeted backup + restore point).")}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{T("2 · Finestra di misura per run", "2 · Measurement window per run")}</div>
          <div className="flex gap-2">
            {[90, 120].map((s) => (
              <button key={s} data-testid={`lab-window-${s}`} onClick={() => setWin(s)}
                className={`px-4 py-2 text-xs border transition-colors ${win === s ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/10" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-500"}`}>
                {s}s
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{T("3 · Tweak con riavvio", "3 · Reboot tweaks")}</div>
          <button data-testid="lab-reboot-toggle" onClick={() => setReboot(!reboot)}
            className={`px-4 py-2 text-xs uppercase tracking-widest border transition-colors ${reboot ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/10" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-500"}`}>
            {reboot ? T("Inclusi (consigliato)", "Included (recommended)") : T("Esclusi", "Excluded")}
          </button>
          <div className="text-[11px] text-zinc-500 mt-1.5">{T("MPO, GPU MSI mode, timer resolution: il Lab si mette in pausa, riavvii e riprende da solo.", "MPO, GPU MSI mode, timer resolution: the Lab pauses, you reboot, it resumes automatically.")}</div>
        </div>
        <div className="border border-[#2A2A35] bg-black/40 p-3 text-xs text-zinc-400" data-testid="lab-candidates-preview">
          <span className="text-[#00E0FF] font-bold">{n}</span> {T("tweak candidati per il tuo hardware", "candidate tweaks for your hardware")}
          {nReboot > 0 && <span className="text-orange-400"> ({nReboot} {T("con riavvio", "with reboot")})</span>}
          {n > 0 && <span className="text-zinc-600"> · {preview.candidates.map((c) => c.tweak_id).join(", ")}</span>}
          <div className="text-zinc-600 mt-1 flex items-center gap-1"><Timer size={11} /> {T(`Durata stimata: ~${estMin} min (baseline ×3 + 3 run per tweak + synergy + validazione)`, `Estimated duration: ~${estMin} min (baseline ×3 + 3 runs per tweak + synergy + validation)`)}</div>
          {fleetN > 0 && (
            <div className="text-[#00E0FF]/80 mt-1 flex items-center gap-1" data-testid="lab-fleet-hint">
              <Users size={11} /> {T(`Priorità arricchite dai dati fleet: ${fleetN} test su PC con hardware simile al tuo`, `Priorities enriched with fleet data: ${fleetN} tests on PCs with hardware similar to yours`)}
            </div>
          )}
          {(preview?.candidates || []).some((c) => c.fleet?.tested >= 3) && (
            <div className="mt-2 space-y-1" data-testid="lab-evidence-list">
              <div className="text-[11px] uppercase tracking-widest text-zinc-500">{T("Evidenza misurata dalla community", "Community-measured evidence")}</div>
              {(preview.candidates || []).filter((c) => c.fleet?.tested >= 3).slice(0, 5).map((c) => (
                <div key={c.tweak_id} className="flex items-center justify-between gap-2 border border-[#1F1F28] bg-black/30 px-2.5 py-1.5" data-testid={`lab-evidence-${c.tweak_id}`}>
                  <span className="text-zinc-300 truncate">{c.name || c.tweak_id}</span>
                  <span className="text-[#00E0FF] shrink-0 tabular-nums">
                    {T(`${c.fleet.tested} PC · ${c.fleet.avg_delta_pct > 0 ? "+" : ""}${c.fleet.avg_delta_pct}% medio · tenuto ${Math.round((c.fleet.kept / c.fleet.tested) * 100)}%`,
                       `${c.fleet.tested} PCs · ${c.fleet.avg_delta_pct > 0 ? "+" : ""}${c.fleet.avg_delta_pct}% avg · kept ${Math.round((c.fleet.kept / c.fleet.tested) * 100)}%`)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        <button onClick={() => onStart(risk, win, reboot)} disabled={starting || n === 0} data-testid="lab-start-btn"
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#D4EC00] transition-colors disabled:opacity-50">
          <FlaskConical size={15} /> {starting ? T("Avvio...", "Starting...") : T("Avvia sessione Lab", "Start Lab session")}
        </button>
      </div>
    </HUDCard>
  );
}

function ConnectCard({ token, onDetect }) {
  return (
    <HUDCard featured testid="lab-connect-card">
      <div className="p-5 space-y-4">
        <div className="text-sm font-bold text-white">{T("Sessione creata — ora collega l'agent", "Session created — now connect the agent")}</div>
        <div className="flex items-start gap-2 border border-amber-500/30 bg-amber-500/5 p-3 text-[11px] text-amber-300" data-testid="lab-admin-note">
          <ShieldAlert size={14} className="shrink-0 mt-0.5" />
          <span>{T("Il Lab richiede PowerShell come AMMINISTRATORE (tweak di sistema + punto di ripristino). Con l'agent installato verrà chiesta la conferma UAC.", "The Lab requires ADMINISTRATOR PowerShell (system tweaks + restore point). With the installed agent you'll get a UAC prompt.")}</span>
        </div>
        <OneClickLaunchButton mode="lab" label={T("Avvia il Lab con 1 click", "Start the Lab with 1 click")} testid="lab-launch" detectDone={onDetect} timeoutMs={90000} />
        <div className="text-[11px] uppercase tracking-widest text-zinc-600 pt-1">{T("Oppure metodo manuale sicuro:", "Or secure manual method:")}</div>
        <SecureRunBlock token={token} mode="lab" testid="lab-run-cmd" />
      </div>
    </HUDCard>
  );
}

const RebootBanner = ({ session }) => (
  <div className="flex items-start gap-3 border border-orange-500/40 bg-orange-500/5 p-4" data-testid="lab-reboot-banner">
    <RotateCcw size={18} className="text-orange-400 shrink-0 mt-0.5" />
    <div>
      <div className="text-sm font-bold text-orange-300">{T("Riavvio richiesto", "Reboot required")}: {session.current?.tweak_id}</div>
      <div className="text-xs text-zinc-400 mt-1">
        {T("Il tweak applicato ha effetto solo dopo il riavvio. Riavvia il PC: il Lab riprenderà automaticamente al login (conferma UAC) con 1 run di warm-up prima delle misure.", "The applied tweak only takes effect after a reboot. Restart your PC: the Lab resumes automatically at login (UAC prompt) with 1 warm-up run before measuring.")}
      </div>
    </div>
  </div>
);

function SynergyCard({ session }) {
  const syn = session.synergy;
  if (!syn) return null;
  return (
    <HUDCard testid="lab-synergy-card">
      <div className="p-4 space-y-2">
        <div className="text-xs uppercase tracking-widest text-zinc-500 mb-1">{T("Synergy pass", "Synergy pass")} · {Math.min(syn.idx + 1, syn.pairs.length)}/{syn.pairs.length}</div>
        {syn.pairs.map((p, i) => {
          const res = syn.results[i];
          return (
            <div key={i} className="flex items-center justify-between gap-2 border border-[#2A2A35] bg-black/30 px-3 py-2" data-testid={`lab-synergy-pair-${i}`}>
              <div className="text-xs text-white">{p.a} + {p.b}</div>
              {res ? (
                <span className={`text-[11px] font-bold ${res.is_synergy ? "text-[#00FF66]" : "text-zinc-500"}`}>
                  {res.is_synergy ? T("SINERGIA", "SYNERGY") : T("nessuna sinergia", "no synergy")} · {res.combined_delta_pct}% vs {res.individual_sum_pct}%
                </span>
              ) : i === syn.idx ? (
                <span className="text-[11px] text-purple-400">{T(`misura ${syn.stage.toUpperCase()} in corso...`, `measuring ${syn.stage.toUpperCase()}...`)}</span>
              ) : (
                <span className="text-[11px] text-zinc-600">{T("in coda", "queued")}</span>
              )}
            </div>
          );
        })}
      </div>
    </HUDCard>
  );
}

function ValidationBlock({ validation }) {
  if (!validation) return null;
  return (
    <div className={`border p-3 text-xs ${validation.discrepancy ? "border-amber-500/40 bg-amber-500/5" : "border-[#00E0FF]/30 bg-[#00E0FF]/5"}`} data-testid="lab-validation-block">
      <div className="uppercase tracking-widest text-[11px] text-zinc-500 mb-1">{T("Validazione in gioco reale", "Real-game validation")} · {Math.round((validation.duration_s || 0) / 60)} min</div>
      <div className="text-zinc-300">
        {T("Guadagno reale", "Real gain")}: <b className={validation.real_gain_pct > 0 ? "text-[#00FF66]" : "text-zinc-300"}>{validation.real_gain_pct}%</b>
        <span className="text-zinc-500"> · {T("previsto dal benchmark", "predicted by benchmark")}: {validation.predicted_gain_pct}%</span>
      </div>
      {validation.discrepancy && (
        <div className="text-amber-400 mt-1">{T("⚠ Discrepanza: il guadagno reale è sotto il 50% di quello previsto. I benchmark sintetici sopravvalutavano l'effetto sul tuo gioco.", "⚠ Discrepancy: real gain is below 50% of predicted. Synthetic benchmarks overestimated the effect on your game.")}</div>
      )}
    </div>
  );
}

function BaselineCard({ session }) {
  const runs = session.baseline?.runs || [];
  const stats = session.baseline?.stats;
  const b0 = session.baseline0;
  return (
    <HUDCard testid="lab-baseline-card">
      <div className="p-4">
        <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2 flex items-center gap-1.5"><Activity size={12} /> Baseline</div>
        {b0 ? (
          <div className="flex items-end gap-4">
            <div><div className="text-2xl font-black text-white tabular-nums">{b0.fps_avg}</div><div className="text-[11px] text-zinc-500 uppercase">FPS avg</div></div>
            <div><div className="text-lg font-bold text-zinc-300 tabular-nums">{b0.fps_p1}</div><div className="text-[11px] text-zinc-500 uppercase">1% low</div></div>
            <div><div className="text-lg font-bold text-zinc-300 tabular-nums">{b0.cv_pct}%</div><div className="text-[11px] text-zinc-500 uppercase">CV</div></div>
            {stats && stats.fps_avg !== b0.fps_avg && (
              <div><div className="text-lg font-bold text-[#00FF66] tabular-nums">{stats.fps_avg}</div><div className="text-[11px] text-zinc-500 uppercase">{T("attuale", "current")}</div></div>
            )}
          </div>
        ) : (
          <div className="text-xs text-zinc-400">{T(`Run completati: ${runs.length}/3`, `Runs done: ${runs.length}/3`)} {runs.map((r) => r.fps_avg).filter(Boolean).map((f, i) => <span key={i} className="ml-2 text-zinc-300 tabular-nums">{f}</span>)}</div>
        )}
        {b0?.game && <div className="text-[11px] text-zinc-600 mt-2">{T("Gioco", "Game")}: {b0.game}</div>}
      </div>
    </HUDCard>
  );
}

function Timeline({ session }) {
  const results = session.results || [];
  const cur = session.current;
  const queue = session.queue || [];
  const names = Object.fromEntries((session.candidates || []).map((c) => [c.tweak_id, c.name]));
  return (
    <HUDCard testid="lab-timeline">
      <div className="p-4 space-y-2">
        <div className="text-xs uppercase tracking-widest text-zinc-500 mb-1">{T("Timeline tweak", "Tweak timeline")}</div>
        {results.length === 0 && !cur && <div className="text-xs text-zinc-600">{T("Nessun tweak testato ancora.", "No tweaks tested yet.")}</div>}
        {results.map((r) => (
          <div key={r.test_id} className="flex items-center justify-between gap-2 border border-[#2A2A35] bg-black/30 px-3 py-2" data-testid={`lab-result-${r.tweak_id}`}>
            <div className="min-w-0">
              <div className="text-xs text-white truncate">{names[r.tweak_id] || r.tweak_id}</div>
              <div className="text-[11px] text-zinc-500">{r.reason}</div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className={`text-sm font-bold tabular-nums ${(r.delta?.fps_avg_pct || 0) > 0 ? "text-[#00FF66]" : "text-zinc-400"}`}>
                {(r.delta?.fps_avg_pct || 0) > 0 ? "+" : ""}{r.delta?.fps_avg_pct}%
              </span>
              <DecisionBadge decision={r.decision} />
            </div>
          </div>
        ))}
        {cur && (
          <div className="flex items-center justify-between gap-2 border border-[#E5FF00]/40 bg-[#E5FF00]/5 px-3 py-2" data-testid="lab-current-tweak">
            <div className="text-xs text-[#E5FF00]">{names[cur.tweak_id] || cur.tweak_id}</div>
            <div className="text-[11px] text-zinc-400">{cur.applied ? T(`run ${(cur.runs || []).length}/3 in corso...`, `run ${(cur.runs || []).length}/3 running...`) : T("applicazione...", "applying...")}</div>
          </div>
        )}
        {queue.map((tid) => (
          <div key={tid} className="flex items-center justify-between gap-2 border border-[#2A2A35]/60 px-3 py-1.5 opacity-50">
            <div className="text-xs text-zinc-500">{names[tid] || tid}</div>
            <div className="text-[11px] text-zinc-600">{T("in coda", "queued")}</div>
          </div>
        ))}
      </div>
    </HUDCard>
  );
}

function LogFeed({ logs }) {
  return (
    <HUDCard testid="lab-log">
      <div className="p-4">
        <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">Live log</div>
        <div className="space-y-1 max-h-64 overflow-y-auto font-mono text-[11px]">
          {[...(logs || [])].reverse().map((l, i) => (
            <div key={i} className={l.level === "ok" ? "text-[#00FF66]" : l.level === "warn" ? "text-amber-400" : "text-zinc-400"}>
              <span className="text-zinc-600">{(l.ts || "").slice(11, 19)}</span> {l.msg}
            </div>
          ))}
        </div>
      </div>
    </HUDCard>
  );
}

function BiosSuggestions({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="space-y-1.5" data-testid="lab-report-bios">
      <div className="text-[11px] uppercase tracking-widest text-zinc-500 flex items-center gap-1.5"><Wrench size={11} /> {T("Prossimo livello: BIOS (manuale, guidato)", "Next level: BIOS (manual, guided)")}</div>
      {items.map((b) => (
        <details key={b.id} className="border border-[#2A2A35] bg-black/30 px-3 py-2" data-testid={`lab-bios-${b.id}`}>
          <summary className="cursor-pointer text-xs text-white flex items-center justify-between gap-2">
            <span>{b.title}</span>
            <span className="text-[11px] text-[#00FF66] shrink-0">{b.expected_gain}</span>
          </summary>
          <div className="text-[11px] text-zinc-400 mt-2">{b.why}</div>
          <ol className="text-[11px] text-zinc-300 mt-1.5 space-y-0.5 list-decimal list-inside">
            {b.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        </details>
      ))}
    </div>
  );
}

const CHECK_LABELS = {
  bios_xmp: ["Verifica XMP", "XMP verification"],
  bios_rebar: ["Verifica Resizable BAR", "Resizable BAR verification"],
  bios_dual: ["Verifica dual channel", "Dual channel verification"],
  driver_update: ["Re-test dopo aggiornamento driver", "Re-test after driver update"],
  manual: ["Verifica rapida", "Quick check"],
};
const checkLabel = (r) => { const l = CHECK_LABELS[r] || CHECK_LABELS.manual; return T(l[0], l[1]); };

function InsightsCard({ onCheck, busy }) {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/lab/insights").then(({ data }) => setData(data)).catch(() => {}); }, []);
  if (!data || !data.items?.length) return null;
  const META = {
    bios_xmp: { icon: Zap, it: "XMP attivo rilevato", en: "XMP now active", descIt: "La tua RAM ora gira più veloce: misura il guadagno reale con un mini-lab (2 run).", descEn: "Your RAM now runs faster: measure the real gain with a mini-lab (2 runs).", btnIt: "Verifica il guadagno", btnEn: "Verify the gain" },
    bios_dual: { icon: Zap, it: "Dual channel rilevato", en: "Dual channel detected", descIt: "Secondo modulo RAM rilevato: misura il guadagno reale (2 run).", descEn: "Second RAM stick detected: measure the real gain (2 runs).", btnIt: "Verifica il guadagno", btnEn: "Verify the gain" },
    bios_rebar: { icon: Wrench, it: "Hai attivato Resizable BAR?", en: "Did you enable Resizable BAR?", descIt: "Se hai seguito la guida BIOS, conferma e misura il guadagno reale (2 run).", descEn: "If you followed the BIOS guide, confirm and measure the real gain (2 runs).", btnIt: "L'ho attivato — verifica", btnEn: "I enabled it — verify" },
    driver_update: { icon: RefreshCw, it: "Driver GPU cambiato", en: "GPU driver changed", descIt: "Un re-test rapido (2 run) verifica che gli FPS non siano peggiorati.", descEn: "A quick re-test (2 runs) checks FPS didn't regress.", btnIt: "Re-test rapido", btnEn: "Quick re-test" },
  };
  return (
    <HUDCard testid="lab-insights-card">
      <div className="p-4 space-y-2.5">
        <div className="text-[11px] uppercase tracking-widest text-zinc-500">{T("Verifiche consigliate", "Suggested checks")}</div>
        {data.items.map((it) => {
          const m = META[it.id];
          if (!m) return null;
          const Icon = m.icon;
          return (
            <div key={it.id} className="flex items-center justify-between gap-3 border border-[#2A2A35] bg-black/30 px-3 py-2.5" data-testid={`lab-insight-${it.id}`}>
              <div className="min-w-0">
                <div className="text-xs text-white flex items-center gap-1.5"><Icon size={13} className="text-[#00E0FF]" /> {T(m.it, m.en)} {it.detail && <span className="text-zinc-500">· {it.detail}</span>}</div>
                <div className="text-[11px] text-zinc-500 mt-0.5">{T(m.descIt, m.descEn)}</div>
              </div>
              <button onClick={() => onCheck(it.id)} disabled={busy} data-testid={`lab-check-start-${it.id}`}
                className="shrink-0 border border-[#00E0FF]/40 text-[#00E0FF] uppercase tracking-widest text-[11px] px-3 py-1.5 hover:bg-[#00E0FF]/10 transition-colors disabled:opacity-50">
                {T(m.btnIt, m.btnEn)}
              </button>
            </div>
          );
        })}
      </div>
    </HUDCard>
  );
}

function HistoryCard() {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get("/lab/history").then(({ data }) => setRows(data.sessions)).catch(() => {}); }, []);
  if (!rows || rows.length === 0) return null;
  return (
    <HUDCard testid="lab-history-card">
      <div className="p-4 space-y-2">
        <div className="text-[11px] uppercase tracking-widest text-zinc-500 flex items-center gap-1.5"><History size={11} /> {T("Storico sessioni", "Session history")}</div>
        {rows.map((s) => (
          <div key={s.session_id} className="flex items-center justify-between gap-3 border border-[#1F1F28] bg-black/30 px-3 py-2" data-testid={`lab-history-row-${s.session_id}`}>
            <div className="flex items-center gap-2 min-w-0">
              <span className={`text-[11px] uppercase tracking-widest font-bold px-1.5 py-0.5 shrink-0 ${s.kind === "check" ? "bg-[#00E0FF]/15 text-[#00E0FF]" : "bg-[#E5FF00]/15 text-[#E5FF00]"}`}>{s.kind === "check" ? "CHECK" : "LAB"}</span>
              <span className="text-[11px] text-zinc-400 shrink-0">{(s.started_at || "").slice(0, 10)}</span>
              <span className="text-xs text-white truncate">{s.game || "—"}</span>
              {s.kind === "check" && s.check_reason && <span className="text-[11px] text-zinc-500 truncate">{checkLabel(s.check_reason)}</span>}
            </div>
            <div className="flex items-center gap-3 shrink-0 text-[11px] tabular-nums">
              {s.baseline_fps != null && <span className="text-zinc-500">{s.baseline_fps} → {s.final_fps} FPS</span>}
              <span className={`font-bold ${(s.total_gain_pct || 0) > 0 ? "text-[#00FF66]" : s.regression ? "text-red-400" : "text-zinc-400"}`}>{(s.total_gain_pct || 0) > 0 ? "+" : ""}{s.total_gain_pct}%</span>
              {s.regression && <span className="text-[11px] uppercase font-bold text-red-400">{T("Regressione", "Regression")}</span>}
            </div>
          </div>
        ))}
      </div>
    </HUDCard>
  );
}

function CheckProgress({ session }) {
  const done = session.baseline?.runs?.length || 0;
  const ref = session.check_ref || {};
  return (
    <HUDCard testid="lab-check-progress">
      <div className="p-5 space-y-3">
        <div className="text-sm font-bold text-white flex items-center gap-2"><Timer size={15} className="text-[#00E0FF]" /> {checkLabel(session.check_reason)}</div>
        <div className="text-xs text-zinc-400">{T(`Run ${done}/2 · riferimento: ${ref.fps_avg} FPS (${ref.game || "n/d"})`, `Run ${done}/2 · reference: ${ref.fps_avg} FPS (${ref.game || "n/a"})`)}</div>
        <div className="flex gap-1.5">{[0, 1].map((i) => <div key={i} className={`h-1.5 flex-1 ${i < done ? "bg-[#00E0FF]" : "bg-[#2A2A35]"}`} />)}</div>
      </div>
    </HUDCard>
  );
}

function CheckResultCard({ report, onNew }) {
  const gain = report.total_gain_pct;
  return (
    <HUDCard featured testid="lab-check-result">
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-white flex items-center gap-2"><FileBarChart size={16} className="text-[#00E0FF]" /> {checkLabel(report.check_reason)}</div>
          {report.game && <span className="text-[11px] text-zinc-500">{report.game}</span>}
        </div>
        <div className="flex items-end gap-6 flex-wrap">
          <div><div className="text-3xl font-black text-white tabular-nums">{report.baseline?.fps_avg} → {report.final?.fps_avg}</div><div className="text-[11px] text-zinc-500 uppercase">FPS avg</div></div>
          <div><div className={`text-3xl font-black tabular-nums ${(gain || 0) > 0 ? "text-[#00FF66]" : report.regression ? "text-red-400" : "text-zinc-400"}`} data-testid="lab-check-gain">{(gain || 0) > 0 ? "+" : ""}{gain}%</div><div className="text-[11px] text-zinc-500 uppercase">{T("vs riferimento", "vs reference")}</div></div>
        </div>
        {report.regression ? (
          <div className="border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-xs text-red-300" data-testid="lab-check-regression">
            {T("Regressione rilevata: gli FPS sono calati rispetto all'ultimo Lab. Consigliato un nuovo Lab completo per ritrovare la configurazione ottimale.", "Regression detected: FPS dropped vs your last Lab. A new full Lab is recommended to re-optimize.")}
          </div>
        ) : (
          <div className="border border-[#00FF66]/30 bg-[#00FF66]/10 px-3 py-2.5 text-xs text-[#00FF66]" data-testid="lab-check-ok">
            {(gain || 0) > 0 ? T(`Guadagno confermato: +${gain}% rispetto al riferimento.`, `Gain confirmed: +${gain}% vs reference.`) : T("Nessuna regressione: le prestazioni sono in linea con il riferimento.", "No regression: performance in line with reference.")}
          </div>
        )}
        <button onClick={onNew} data-testid="lab-new-session-btn" className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-300 uppercase tracking-widest text-xs px-5 py-2.5 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors">
          <Play size={13} /> {T("Nuovo Lab completo", "New full Lab")}
        </button>
      </div>
    </HUDCard>
  );
}

function ShareCard({ report, innerRef }) {
  const keptSteps = (report.steps || []).filter((s) => s.decision === "kept");
  return (
    <div className="fixed -left-[9999px] top-0">
      <div ref={innerRef} style={{ width: 620 }} className="bg-[#0A0A0D] border border-[#2A2A35] p-8 font-sans">
        <div className="flex items-center justify-between mb-5">
          <div className="text-[11px] font-mono uppercase tracking-[0.25em] text-[#E5FF00]">FRAMEFORGE LAB</div>
          <div className="text-[11px] font-mono text-zinc-500">{T("REPORT VERIFICATO STATISTICAMENTE", "STATISTICALLY VERIFIED REPORT")}</div>
        </div>
        <div className="text-zinc-400 text-xs mb-1">{report.game || "PC Gaming"}</div>
        <div className="flex items-end gap-5 mb-5">
          <div style={{ fontSize: 56, lineHeight: 1 }} className={`font-black ${(report.total_gain_pct || 0) > 0 ? "text-[#00FF66]" : "text-zinc-300"}`}>
            {(report.total_gain_pct || 0) > 0 ? "+" : ""}{report.total_gain_pct}%
          </div>
          <div className="pb-1">
            <div className="text-white text-xl font-bold">{report.baseline?.fps_avg} → {report.final?.fps_avg} FPS</div>
            <div className="text-zinc-500 text-xs">1% low: {report.baseline?.fps_p1} → {report.final?.fps_p1}</div>
          </div>
        </div>
        <div className="space-y-1.5 mb-4">
          {keptSteps.map((s, i) => (
            <div key={i} className="flex items-center justify-between border border-[#1F1F28] bg-black/40 px-3 py-1.5">
              <span className="text-zinc-200 text-xs">{s.tweak}</span>
              <span className="text-[#00FF66] text-xs font-bold">+{s.delta_pct}% (p={s.p_value})</span>
            </div>
          ))}
        </div>
        {report.validation && (
          <div className="text-[11px] text-zinc-400 mb-4">
            {T("Validato in gioco reale", "Validated in real gameplay")}: <span className="text-[#00E0FF] font-bold">{report.validation.real_gain_pct}%</span> · {Math.round((report.validation.duration_s || 0) / 60)} min
          </div>
        )}
        <div className="flex items-center justify-between border-t border-[#1F1F28] pt-3">
          <div className="text-[11px] text-zinc-500">{T(`${report.tweaks_tested} tweak testati · baseline ×3 · Welch t-test · rollback automatico`, `${report.tweaks_tested} tweaks tested · baseline ×3 · Welch t-test · auto rollback`)}</div>
          <div className="text-[11px] font-mono text-[#E5FF00]">forgefps.dev</div>
        </div>
      </div>
    </div>
  );
}

function ReportCard({ report, onNew }) {
  const shareRef = useRef(null);
  const [sharing, setSharing] = useState(false);
  const share = async () => {
    if (!shareRef.current || sharing) return;
    setSharing(true);
    try {
      const dataUrl = await toPng(shareRef.current, { pixelRatio: 2, cacheBust: true, backgroundColor: "#0A0A0D", skipFonts: true });
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], "frameforge-lab-report.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "FrameForge Lab" });
      } else {
        const a = document.createElement("a");
        a.href = dataUrl;
        a.download = "frameforge-lab-report.png";
        a.click();
        toast.success(T("Immagine scaricata!", "Image downloaded!"));
      }
    } catch (e) {
      if (e?.name !== "AbortError") toast.error(T("Export fallito, riprova", "Export failed, retry"));
    }
    setSharing(false);
  };
  if (!report) return null;
  const gain = report.total_gain_pct;
  return (
    <HUDCard featured testid="lab-report-card">
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-white flex items-center gap-2"><FileBarChart size={16} className="text-[#E5FF00]" /> {T("Report finale", "Final report")}</div>
          <div className="flex items-center gap-3">
            {report.game && <span className="text-[11px] text-zinc-500">{report.game}</span>}
            <button onClick={share} disabled={sharing} data-testid="lab-share-btn"
              className="inline-flex items-center gap-1.5 border border-[#E5FF00]/40 text-[#E5FF00] uppercase tracking-widest text-[11px] px-3 py-1.5 hover:bg-[#E5FF00]/10 transition-colors disabled:opacity-50">
              <Share2 size={12} /> {sharing ? T("Genero...", "Generating...") : T("Condividi", "Share")}
            </button>
          </div>
        </div>
        <div className="flex items-end gap-6 flex-wrap">
          <div><div className="text-3xl font-black text-white tabular-nums">{report.baseline?.fps_avg} → {report.final?.fps_avg}</div><div className="text-[11px] text-zinc-500 uppercase">FPS avg</div></div>
          <div><div className={`text-3xl font-black tabular-nums ${(gain || 0) > 0 ? "text-[#00FF66]" : "text-zinc-400"}`} data-testid="lab-report-gain">{(gain || 0) > 0 ? "+" : ""}{gain}%</div><div className="text-[11px] text-zinc-500 uppercase">{T("Guadagno totale", "Total gain")}</div></div>
          <div><div className="text-xl font-bold text-zinc-300 tabular-nums">{report.baseline?.fps_p1} → {report.final?.fps_p1}</div><div className="text-[11px] text-zinc-500 uppercase">1% low</div></div>
          {report.total_latency_delta_ms != null && <div><div className={`text-xl font-bold tabular-nums ${report.total_latency_delta_ms < 0 ? "text-[#00E0FF]" : "text-zinc-300"}`} data-testid="lab-report-latency">{report.total_latency_delta_ms > 0 ? "+" : ""}{report.total_latency_delta_ms} ms</div><div className="text-[11px] text-zinc-500 uppercase">Input lag</div></div>}
          {report.total_duration_min != null && <div><div className="text-xl font-bold text-zinc-300 tabular-nums">{report.total_duration_min} min</div><div className="text-[11px] text-zinc-500 uppercase">{T("Durata", "Duration")}</div></div>}
        </div>
        {report.performance_index && (
          <div className="flex gap-4 text-[11px] text-zinc-400 border-t border-[#2A2A35] pt-3">
            <span>{T("Prestazioni", "Performance")}: <b className="text-white">{report.performance_index.prestazioni}</b></span>
            <span>{T("Fluidità", "Smoothness")}: <b className="text-white">{report.performance_index.fluidita}</b></span>
            <span>{T("Stabilità", "Stability")}: <b className="text-white">{report.performance_index.stabilita}</b></span>
            <span>{T("Voto", "Score")}: <b className="text-[#E5FF00]">{report.performance_index.voto_finale}</b></span>
          </div>
        )}
        <div className="space-y-1.5">
          {(report.steps || []).map((s, i) => (
            <div key={i} className="flex items-center justify-between gap-2 border border-[#2A2A35] bg-black/30 px-3 py-2" data-testid={`lab-report-step-${s.tweak_id}`}>
              <div className="min-w-0">
                <div className="text-xs text-white truncate">{s.tweak}</div>
                <div className="text-[11px] text-zinc-500">
                  {s.reason} · p={s.p_value}
                  {s.ci_pct && <span className="text-zinc-600"> · IC95 {s.ci_pct[0] > 0 ? "+" : ""}{s.ci_pct[0]}/{s.ci_pct[1] > 0 ? "+" : ""}{s.ci_pct[1]}%</span>}
                  {s.decision === "kept" && s.holm_ok === false && <span className="text-amber-500/90"> · {T("non confermato dopo correzione Holm", "not confirmed after Holm correction")}</span>}
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[11px] text-zinc-400 tabular-nums">{s.before} → {s.after}</span>
                {s.p1_delta_pct != null && <span className="text-[11px] text-zinc-500 tabular-nums">1% low {s.p1_delta_pct > 0 ? "+" : ""}{s.p1_delta_pct}%</span>}
                {s.latency_delta_ms != null && <span className={`text-[11px] tabular-nums ${s.latency_delta_ms < 0 ? "text-[#00E0FF]" : "text-zinc-500"}`}>{s.latency_delta_ms > 0 ? "+" : ""}{s.latency_delta_ms}ms lat</span>}
                <span className={`text-sm font-bold tabular-nums ${(s.delta_pct || 0) > 0 ? "text-[#00FF66]" : "text-zinc-400"}`}>{(s.delta_pct || 0) > 0 ? "+" : ""}{s.delta_pct}%</span>
                <DecisionBadge decision={s.decision} />
              </div>
            </div>
          ))}
        </div>
        <ValidationBlock validation={report.validation} />
        {report.multiple_testing && report.multiple_testing.kept_total > 0 && (
          <div className="text-[11px] text-zinc-500 border border-[#1F1F28] bg-black/30 px-3 py-2" data-testid="lab-report-rigor">
            {T(`Rigore statistico: ${report.multiple_testing.kept_confirmed}/${report.multiple_testing.kept_total} tweak mantenuti restano significativi dopo correzione Holm-Bonferroni (test multipli, α=${report.multiple_testing.alpha}).`,
               `Statistical rigor: ${report.multiple_testing.kept_confirmed}/${report.multiple_testing.kept_total} kept tweaks remain significant after Holm-Bonferroni correction (multiple testing, α=${report.multiple_testing.alpha}).`)}
            {(report.drift_events || []).length > 0 && (
              <span className="text-amber-500/90"> {T(`· ${report.drift_events.length} drift baseline rilevati e compensati (schema A/B/A).`, `· ${report.drift_events.length} baseline drifts detected and compensated (A/B/A scheme).`)}</span>
            )}
          </div>
        )}
        {(report.synergies_found || []).length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[11px] uppercase tracking-widest text-zinc-500">{T("Sinergie verificate", "Verified synergies")}</div>
            {report.synergies_found.map((s, i) => (
              <div key={i} className="flex items-center justify-between gap-2 border border-[#2A2A35] bg-black/30 px-3 py-2" data-testid={`lab-report-synergy-${i}`}>
                <div className="text-xs text-white">{s.pair?.join(" + ")}</div>
                <span className={`text-[11px] font-bold ${s.is_synergy ? "text-[#00FF66]" : "text-zinc-500"}`}>
                  {s.is_synergy ? T("SINERGIA", "SYNERGY") : T("additivi", "additive")} · {s.combined_delta_pct}% vs {s.individual_sum_pct}%
                </span>
              </div>
            ))}
          </div>
        )}
        {report.reboots_required > 0 && (
          <div className="text-[11px] text-zinc-500">{T(`Riavvii eseguiti durante il lab: ${report.reboots_required}`, `Reboots performed during the lab: ${report.reboots_required}`)}</div>
        )}
        <BiosSuggestions items={report.bios_suggestions} />
        {report.auto_stop_reason && <div className="text-[11px] text-amber-400">{report.auto_stop_reason}</div>}
        <button onClick={onNew} data-testid="lab-new-session-btn" className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-300 uppercase tracking-widest text-xs px-5 py-2.5 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors">
          <Play size={13} /> {T("Nuova sessione", "New session")}
        </button>
        <ShareCard report={report} innerRef={shareRef} />
      </div>
    </HUDCard>
  );
}

export default function Lab() {
  const [session, setSession] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [token, setToken] = useState("");
  const [starting, setStarting] = useState(false);
  const [showSetup, setShowSetup] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/lab/session");
      setSession(data.session);
    } catch {}
    setLoaded(true);
  }, []);

  useEffect(() => {
    load();
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch(() => {});
  }, [load]);

  const active = session && ["waiting_agent", "snapshot", "baseline", "testing", "awaiting_reboot", "synergy", "validation", "aborting"].includes(session.status);
  useEffect(() => {
    if (!active) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [active, load]);

  const start = async (risk, win, reboot) => {
    setStarting(true);
    try {
      const { data } = await api.post("/lab/start", { risk_level: risk, run_seconds: win, include_reboot: reboot });
      setSession(data.session);
      setShowSetup(false);
      toast.success(T("Sessione Lab creata! Ora avvia l'agent.", "Lab session created! Now start the agent."));
    } catch (e) {
      toast.error(e?.response?.data?.detail || T("Avvio fallito", "Start failed"));
    }
    setStarting(false);
  };

  const abort = async () => {
    try {
      const { data } = await api.post("/lab/abort");
      setSession(data.session);
      toast.info(T("Interruzione richiesta: l'agent annullerà i tweak applicati.", "Abort requested: the agent will roll back applied tweaks."));
    } catch {}
  };

  const startCheck = async (reason) => {
    setStarting(true);
    try {
      const { data } = await api.post("/lab/check", { reason });
      setSession(data.session);
      setShowSetup(false);
      toast.success(T("Mini-lab creato! Ora avvia l'agent (comando Lab).", "Mini-lab created! Now start the agent (Lab command)."));
    } catch (e) {
      toast.error(e?.response?.data?.detail || T("Avvio fallito", "Start failed"));
    }
    setStarting(false);
  };

  const isCheck = session?.kind === "check";

  const showReport = session && session.status === "completed" && !showSetup;
  const showAborted = session && session.status === "aborted" && !showSetup;
  const needSetup = loaded && (!session || showSetup || (!active && !showReport && !showAborted));

  return (
    <div className="space-y-6" data-testid="lab-page">
      <PageHeader
        eyebrow="FrameForge Lab"
        title={T("Laboratorio Automatico", "Automatic Performance Lab")}
        subtitle={T("Testa i tweak uno alla volta sul tuo gioco: baseline ×3, statistica reale (Welch t-test), rollback automatico di ciò che non funziona.", "Tests tweaks one at a time on your game: baseline ×3, real statistics (Welch t-test), automatic rollback of what doesn't work.")}
        actions={active && session.status !== "aborting" ? (
          <button onClick={abort} data-testid="lab-abort-btn" className="inline-flex items-center gap-2 border border-red-500/40 text-red-400 uppercase tracking-widest text-xs px-4 py-2 hover:bg-red-500/10 transition-colors">
            <StopCircle size={14} /> {T("Interrompi", "Abort")}
          </button>
        ) : null}
      />

      {!loaded && <div className="text-zinc-500 text-sm">{T("Caricamento...", "Loading...")}</div>}

      {needSetup && (
        <>
          <SetupCard onStart={start} starting={starting} />
          <FleetValidationCard />
          <InsightsCard onCheck={startCheck} busy={starting} />
          <HistoryCard />
        </>
      )}

      {session && active && isCheck && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="text-xs uppercase tracking-widest text-[#00E0FF]">{T("Mini-lab di verifica", "Verification mini-lab")}</div>
            <StatusPill status={session.status} />
          </div>
          {session.status === "waiting_agent" ? (
            <ConnectCard token={token} onDetect={async () => {
              const { data } = await api.get("/lab/session");
              return data.session && data.session.status !== "waiting_agent";
            }} />
          ) : (
            <div className="grid lg:grid-cols-2 gap-4">
              <CheckProgress session={session} />
              <LogFeed logs={session.logs} />
            </div>
          )}
        </div>
      )}

      {session && active && !isCheck && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <Stepper status={session.status} />
            <StatusPill status={session.status} />
          </div>
          {session.status === "waiting_agent" && <ConnectCard token={token} onDetect={async () => {
            const { data } = await api.get("/lab/session");
            return data.session && data.session.status !== "waiting_agent";
          }} />}
          {session.status === "awaiting_reboot" && <RebootBanner session={session} />}
          {session.status !== "waiting_agent" && (
            <div className="grid lg:grid-cols-2 gap-4">
              <div className="space-y-4">
                <BaselineCard session={session} />
                <Timeline session={session} />
                {(session.status === "synergy" || session.synergy) && <SynergyCard session={session} />}
              </div>
              <LogFeed logs={session.logs} />
            </div>
          )}
        </div>
      )}

      {showReport && (
        <div className="space-y-4">
          {session.report?.kind === "check" ? (
            <CheckResultCard report={session.report} onNew={() => setShowSetup(true)} />
          ) : (
            <ReportCard report={session.report} onNew={() => setShowSetup(true)} />
          )}
          <InsightsCard onCheck={startCheck} busy={starting} />
          <HistoryCard />
          <LogFeed logs={session.logs} />
        </div>
      )}

      {showAborted && (
        <HUDCard testid="lab-aborted-card">
          <div className="p-5 space-y-3">
            <div className="flex items-center gap-2 text-sm text-zinc-300"><XCircle size={16} className="text-orange-400" /> {T("Ultima sessione interrotta: tutti i tweak del Lab sono stati annullati.", "Last session aborted: all Lab tweaks were rolled back.")}</div>
            <button onClick={() => setShowSetup(true)} data-testid="lab-new-session-btn" className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-300 uppercase tracking-widest text-xs px-5 py-2.5 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors">
              <Play size={13} /> {T("Nuova sessione", "New session")}
            </button>
          </div>
        </HUDCard>
      )}
    </div>
  );
}
