/**
 * FirstScanBanner
 *
 * Mostrato solo agli utenti che NON hanno ancora eseguito il primo sync
 * (nessun documento in `pc_specs`). Fa da guida step-by-step:
 *
 *   1. Scarica lo ZIP (bottone che scrolla al blocco Download)
 *   2. Estrai la cartella
 *   3. Doppio click su `Avvia-FrameForge.bat` (o `forgefps-agent.exe`)
 *   4. La GUI si apre e fa il primo scan automatico
 *
 * Mentre e' visibile, polla /pc-specs ogni 3s (con exponential backoff dopo
 * 60s per non sprecare cicli). Non appena arriva un documento, il banner
 * diventa verde "Scan completato" e mostra un CTA per tornare al Dashboard.
 *
 * Si nasconde automaticamente dopo un successo (persistente per la sessione).
 */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Download, FolderOpen, MousePointerClick, Sparkles, ArrowRight, Loader2 } from "lucide-react";
import api from "@/lib/api";

const POLL_INTERVAL_MS = 3000;
// Dopo 60s di polling senza risultato, allunga a 10s per non sprecare risorse
// nel caso l'utente abbia lasciato la scheda aperta e sia andato via.
const POLL_SLOW_AFTER_MS = 60_000;
const POLL_SLOW_INTERVAL_MS = 10_000;

export default function FirstScanBanner() {
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "").startsWith("en");
  const [status, setStatus] = useState("checking"); // checking | pending | done | error
  const [specs, setSpecs] = useState(null);
  const pollRef = useRef(null);
  const startedAtRef = useRef(0);

  const checkOnce = async () => {
    try {
      const { data } = await api.get("/pc-specs");
      if (data && data.data && Object.keys(data.data).length > 0) {
        setSpecs(data.data);
        setStatus("done");
        return true;
      }
      return false;
    } catch (e) {
      // 404 = ancora nessuna sync (utente nuovo). Non e' un errore reale.
      return false;
    }
  };

  useEffect(() => {
    let stopped = false;
    startedAtRef.current = Date.now();

    (async () => {
      const found = await checkOnce();
      if (stopped) return;
      if (!found) {
        setStatus("pending");
        // Polling loop
        const tick = async () => {
          if (stopped) return;
          const found2 = await checkOnce();
          if (stopped || found2) return;
          const elapsed = Date.now() - startedAtRef.current;
          const nextMs = elapsed > POLL_SLOW_AFTER_MS ? POLL_SLOW_INTERVAL_MS : POLL_INTERVAL_MS;
          pollRef.current = setTimeout(tick, nextMs);
        };
        pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      }
    })();

    return () => {
      stopped = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  // Ancora in caricamento (< 500ms): non mostrare nulla per evitare flash
  if (status === "checking") return null;
  // Utente ha gia' fatto lo scan tempo fa: nascondi tutto silenziosamente
  if (status === "done" && !specs) return null;

  // Success state — mostra brevemente il successo, poi il componente si
  // nasconde da solo perche' status=done implica specs presenti nel DB e al
  // prossimo mount la condizione iniziale returna null.
  if (status === "done") {
    return (
      <div className="border border-[#00FF66]/40 bg-[#00FF66]/5 p-5 mb-6" data-testid="first-scan-done">
        <div className="flex items-start gap-3">
          <CheckCircle2 size={20} className="shrink-0 text-[#00FF66] mt-0.5" />
          <div className="min-w-0 flex-1">
            <div className="text-xs uppercase tracking-[0.2em] text-[#00FF66] mb-1">
              {en ? "// scan complete" : "// scan completato"}
            </div>
            <h3 className="font-display font-black text-lg text-zinc-100 mb-1">
              {en ? "Your first scan is in!" : "Il tuo primo scan e' arrivato!"}
            </h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              {en ? "Detected: " : "Rilevato: "}
              <span className="text-[#00E0FF] font-semibold">{specs?.cpu || "CPU"}</span>
              {" · "}
              <span className="text-[#00E0FF] font-semibold">{specs?.gpu || "GPU"}</span>
              {specs?.ram && <> {" · "} <span className="text-[#00E0FF] font-semibold">{specs.ram}</span></>}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                to="/app/mypc"
                data-testid="first-scan-goto-mypc"
                className="inline-flex items-center gap-1.5 bg-[#00FF66] text-black font-bold text-xs px-3 py-1.5 hover:bg-[#33FF99] transition-colors"
              >
                {en ? "See my PC" : "Vedi il mio PC"} <ArrowRight size={12} />
              </Link>
              <Link
                to="/app"
                data-testid="first-scan-goto-dashboard"
                className="inline-flex items-center gap-1.5 border border-[#00FF66]/40 text-[#00FF66] font-bold text-xs px-3 py-1.5 hover:bg-[#00FF66]/10 transition-colors"
              >
                {en ? "Back to dashboard" : "Torna al dashboard"}
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Pending state — la vera guida step-by-step
  const scrollToDownload = () => {
    const el = document.querySelector('[data-testid="exe-download-block"]') || document.querySelector('[data-testid="quick-actions"]');
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const steps = en
    ? [
        { icon: Download, title: "1. Download the ZIP", desc: "Personalized with your token — no manual paste needed.", cta: "Download now", action: scrollToDownload },
        { icon: FolderOpen, title: "2. Extract the folder", desc: "Right click -> Extract all. Keep it wherever you want." },
        { icon: MousePointerClick, title: "3. Double-click Avvia-FrameForge.bat", desc: "(Or forgefps-agent.exe.) The secure GUI opens instantly." },
        { icon: Sparkles, title: "4. Scan runs automatically", desc: "Hardware + health + startup + games detected in ~5s. This page will update the moment your data arrives." },
      ]
    : [
        { icon: Download, title: "1. Scarica lo ZIP", desc: "Personalizzato col tuo token — nessun copia-incolla manuale.", cta: "Scarica ora", action: scrollToDownload },
        { icon: FolderOpen, title: "2. Estrai la cartella", desc: "Tasto destro -> Estrai tutto. Puoi tenerla ovunque." },
        { icon: MousePointerClick, title: "3. Doppio click su Avvia-FrameForge.bat", desc: "(Oppure forgefps-agent.exe.) La GUI sicura si apre in un istante." },
        { icon: Sparkles, title: "4. Lo scan parte da solo", desc: "Hardware + salute + avvio + giochi rilevati in ~5s. Questa pagina si aggiorna nel momento in cui i dati arrivano." },
      ];

  return (
    <div className="border border-[#E5FF00]/40 bg-gradient-to-br from-[#E5FF00]/10 via-[#00E0FF]/5 to-transparent p-6 mb-6" data-testid="first-scan-pending">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 border border-[#E5FF00]/50 bg-black flex items-center justify-center shrink-0">
          <Loader2 size={18} className="text-[#E5FF00] animate-spin" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#E5FF00] mb-1">
            {en ? "// first scan · waiting..." : "// primo scan · in attesa..."}
          </div>
          <h2 className="font-display font-black text-2xl tracking-tighter text-zinc-100 mb-1">
            {en ? "4 steps to your first scan" : "4 step per il tuo primo scan"}
          </h2>
          <p className="text-xs text-zinc-400 leading-relaxed max-w-xl">
            {en
              ? "This page listens in real time. As soon as the FrameForge Agent starts on your PC, the scan arrives here automatically."
              : "Questa pagina ascolta in tempo reale. Non appena FrameForge Agent parte sul tuo PC, lo scan arriva qui da solo."}
          </p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {steps.map((step, i) => (
          <div
            key={i}
            className="bg-black/40 border border-[#2A2A35] hover:border-[#E5FF00]/40 p-4 transition-colors"
            data-testid={`first-scan-step-${i + 1}`}
          >
            <step.icon size={18} className="text-[#E5FF00] mb-2" />
            <div className="text-sm font-bold text-zinc-100 mb-1">{step.title}</div>
            <div className="text-xs text-zinc-500 leading-relaxed">{step.desc}</div>
            {step.cta && (
              <button
                onClick={step.action}
                data-testid={`first-scan-step-${i + 1}-cta`}
                className="mt-3 text-xs font-bold text-[#E5FF00] hover:text-[#F5FF66] inline-flex items-center gap-1"
              >
                {step.cta} <ArrowRight size={12} />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-2 text-[11px] text-zinc-500">
        <span className="w-1.5 h-1.5 bg-[#E5FF00] rounded-full animate-pulse" />
        {en
          ? "Polling every 3s. Leave this tab open — no refresh needed."
          : "Aggiorno ogni 3s. Tieni questa scheda aperta — nessun refresh necessario."}
      </div>
    </div>
  );
}
