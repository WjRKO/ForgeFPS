/**
 * Lab.jsx — Laboratorio Automatico delle Prestazioni (Fase 1).
 * Il backend orchestre la pipeline SNAPSHOT -> BASELINE x3 -> TEST LOOP -> REPORT;
 * l'agent locale (mode=lab) applica/misura/annulla i tweak uno alla volta.
 */
import { useCallback, useEffect, useState } from "react";
import { FlaskConical, Play, ShieldAlert, StopCircle, CheckCircle2, XCircle, RotateCcw, Timer, Activity, FileBarChart } from "lucide-react";
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
  return <span data-testid="lab-status-pill" className={`px-2.5 py-1 text-[10px] uppercase tracking-widest font-bold ${cls}`}>{label}</span>;
};

const Stepper = ({ status }) => {
  const idx = PHASE_IDX[status] ?? -1;
  return (
    <div className="flex items-center gap-1 flex-wrap" data-testid="lab-stepper">
      {PHASES.map((p, i) => (
        <div key={p.id} className="flex items-center gap-1">
          <div className={`px-2.5 py-1 text-[10px] uppercase tracking-widest border ${i < idx ? "border-[#00FF66]/40 text-[#00FF66]" : i === idx ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/10" : "border-[#2A2A35] text-zinc-600"}`}>
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
    <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest font-bold text-[#00FF66]"><CheckCircle2 size={12} /> {T("Mantenuto", "Kept")}</span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest font-bold text-orange-400"><RotateCcw size={12} /> Rollback</span>
  );

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
          <div className="text-[11px] text-zinc-500 mt-1.5">{T("Fase 1: solo tweak senza riavvio, tutti con rollback automatico.", "Phase 1: no-reboot tweaks only, all auto-reversible.")}</div>
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
        <div className="text-[10px] uppercase tracking-widest text-zinc-600 pt-1">{T("Oppure metodo manuale sicuro:", "Or secure manual method:")}</div>
        <SecureRunBlock token={token} mode="lab" testid="lab-run-cmd" />
      </div>
    </HUDCard>
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
            <div><div className="text-2xl font-black text-white tabular-nums">{b0.fps_avg}</div><div className="text-[10px] text-zinc-500 uppercase">FPS avg</div></div>
            <div><div className="text-lg font-bold text-zinc-300 tabular-nums">{b0.fps_p1}</div><div className="text-[10px] text-zinc-500 uppercase">1% low</div></div>
            <div><div className="text-lg font-bold text-zinc-300 tabular-nums">{b0.cv_pct}%</div><div className="text-[10px] text-zinc-500 uppercase">CV</div></div>
            {stats && stats.fps_avg !== b0.fps_avg && (
              <div><div className="text-lg font-bold text-[#00FF66] tabular-nums">{stats.fps_avg}</div><div className="text-[10px] text-zinc-500 uppercase">{T("attuale", "current")}</div></div>
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
              <div className="text-[10px] text-zinc-500">{r.reason}</div>
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
            <div className="text-[10px] text-zinc-400">{cur.applied ? T(`run ${(cur.runs || []).length}/3 in corso...`, `run ${(cur.runs || []).length}/3 running...`) : T("applicazione...", "applying...")}</div>
          </div>
        )}
        {queue.map((tid) => (
          <div key={tid} className="flex items-center justify-between gap-2 border border-[#2A2A35]/60 px-3 py-1.5 opacity-50">
            <div className="text-xs text-zinc-500">{names[tid] || tid}</div>
            <div className="text-[10px] text-zinc-600">{T("in coda", "queued")}</div>
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

function ReportCard({ report, onNew }) {
  if (!report) return null;
  const gain = report.total_gain_pct;
  return (
    <HUDCard featured testid="lab-report-card">
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-white flex items-center gap-2"><FileBarChart size={16} className="text-[#E5FF00]" /> {T("Report finale", "Final report")}</div>
          {report.game && <span className="text-[11px] text-zinc-500">{report.game}</span>}
        </div>
        <div className="flex items-end gap-6 flex-wrap">
          <div><div className="text-3xl font-black text-white tabular-nums">{report.baseline?.fps_avg} → {report.final?.fps_avg}</div><div className="text-[10px] text-zinc-500 uppercase">FPS avg</div></div>
          <div><div className={`text-3xl font-black tabular-nums ${(gain || 0) > 0 ? "text-[#00FF66]" : "text-zinc-400"}`} data-testid="lab-report-gain">{(gain || 0) > 0 ? "+" : ""}{gain}%</div><div className="text-[10px] text-zinc-500 uppercase">{T("Guadagno totale", "Total gain")}</div></div>
          <div><div className="text-xl font-bold text-zinc-300 tabular-nums">{report.baseline?.fps_p1} → {report.final?.fps_p1}</div><div className="text-[10px] text-zinc-500 uppercase">1% low</div></div>
          {report.total_duration_min != null && <div><div className="text-xl font-bold text-zinc-300 tabular-nums">{report.total_duration_min} min</div><div className="text-[10px] text-zinc-500 uppercase">{T("Durata", "Duration")}</div></div>}
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
                <div className="text-[10px] text-zinc-500">{s.reason} · p={s.p_value}</div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[11px] text-zinc-400 tabular-nums">{s.before} → {s.after}</span>
                <span className={`text-sm font-bold tabular-nums ${(s.delta_pct || 0) > 0 ? "text-[#00FF66]" : "text-zinc-400"}`}>{(s.delta_pct || 0) > 0 ? "+" : ""}{s.delta_pct}%</span>
                <DecisionBadge decision={s.decision} />
              </div>
            </div>
          ))}
        </div>
        <ValidationBlock validation={report.validation} />
        {(report.synergies_found || []).length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] uppercase tracking-widest text-zinc-500">{T("Sinergie verificate", "Verified synergies")}</div>
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
        {report.auto_stop_reason && <div className="text-[11px] text-amber-400">{report.auto_stop_reason}</div>}
        <button onClick={onNew} data-testid="lab-new-session-btn" className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-300 uppercase tracking-widest text-xs px-5 py-2.5 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors">
          <Play size={13} /> {T("Nuova sessione", "New session")}
        </button>
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

      {needSetup && <SetupCard onStart={start} starting={starting} />}

      {session && active && (
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
          <ReportCard report={session.report} onNew={() => setShowSetup(true)} />
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
