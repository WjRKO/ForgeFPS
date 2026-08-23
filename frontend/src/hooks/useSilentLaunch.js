import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";

/**
 * Hook per lanciare l'agent Desktop in modalita' SILENT via protocollo
 * custom `frameforge://` (v0.7.1+).
 *
 * Flusso:
 *   1. beforeLaunch()  -> fotografia dello stato prima di partire
 *   2. GET /api/agent/launch-uri?mode=X&silent=1 -> URI firmato HMAC
 *   3. window.location.href = uri -> Windows lancia l'exe nascosto
 *   4. polling di detectDone() finche' non e' fatto o scade timeoutMs
 *   5a. se riesce, summarize(fotografia) dice COSA e' cambiato
 *   5b. se scade,  diagnose(fotografia) dice COSA e' andato storto
 *
 * --- Perche' `diagnose` e non un messaggio fisso ---
 *
 * Un timeout non e' una causa, e' l'assenza di una risposta. Lo stesso silenzio
 * significa agent non installato, protocollo non registrato, token locale di un
 * altro account, limite PC del piano raggiunto, oppure - il caso peggiore -
 * sync RIUSCITO su un altro PC mentre la pagina guardava quello sbagliato.
 * Prima erano tutti la stessa frase, che ne accusava uno solo e nemmeno il piu'
 * probabile: chi vedeva "il tuo token e' disallineato" spesso aveva solo il
 * device attivo diverso da quello davanti a cui era seduto.
 *
 * `diagnose` riceve la fotografia di `beforeLaunch` e torna una stringa oppure
 * `{ message, action: { label, onClick } }`, cosi' la spiegazione puo' portarsi
 * dietro il rimedio invece di descriverlo a parole.
 *
 * `summarize` e' il suo gemello sul ramo riuscito: "Completato" e' vero e non
 * dice niente, mentre "Driver GPU: 566.36 -> 572.16" e' il motivo per cui uno
 * preme il pulsante. Torna una stringa, o null per lasciare l'etichetta `done`.
 *
 * --- Etichette ---
 *
 * `""` significa "non mostrare quel toast" e viene rispettato: la risoluzione
 * usa `??`, non `||`. Con `||` una stringa vuota e' falsa, quindi chi chiedeva
 * silenzio otteneva i testi di default - in italiano, anche in inglese.
 * Chi non passa nulla riceve comunque i default.
 */

const ETICHETTE = {
  starting: "Avvio in corso...",
  running: "In esecuzione...",
  done: "Completato",
  failed: "Non risponde. Hai installato FrameForge?",
  launchFailed: "Non e' stato possibile avviare l'operazione. Riprova fra poco.",
  cancel: "Annulla",
  cancelled: "Operazione annullata.",
};

// I primi secondi sono quelli in cui vale la pena guardare spesso; dopo, un
// sondaggio ogni due secondi e' solo traffico. Cosi' un'attesa da 60s costa
// circa 18 richieste invece di 30.
const PAUSA_INIZIALE_MS = 2000;
const PAUSA_LUNGA_MS = 4000;
const SOGLIA_PAUSA_MS = 12000;

export function useSilentLaunch({
  mode,
  detectDone,
  beforeLaunch,
  diagnose,
  summarize,
  onDone,
  timeoutMs = 90000,
  labels = {},
} = {}) {
  const [running, setRunning] = useState(false);
  const abortRef = useRef({ stop: false });
  const toastRef = useRef(null);
  const labelsRef = useRef(ETICHETTE);

  // Un solo modo di annullare, usato sia dal bottone dentro il toast sia da chi
  // chiama l'hook: due percorsi diversi mostrerebbero due toast di annullamento.
  const cancel = useCallback(() => {
    abortRef.current.stop = true;
    if (toastRef.current != null) {
      toast.dismiss(toastRef.current);
      toastRef.current = null;
    }
    if (labelsRef.current.cancelled) toast.info(labelsRef.current.cancelled);
    setRunning(false);
  }, []);

  const launch = useCallback(async () => {
    if (running) return;
    const l = { ...ETICHETTE };
    for (const k of Object.keys(ETICHETTE)) {
      if (labels[k] !== undefined) l[k] = labels[k];
    }
    labelsRef.current = l;

    setRunning(true);
    abortRef.current = { stop: false };
    toastRef.current = null;

    // Un'etichetta vuota non diventa un toast vuoto: si salta e basta.
    const mostra = (fn, testo, extra = {}) => {
      if (!testo) return;
      const opts = { ...extra };
      if (toastRef.current != null) opts.id = toastRef.current;
      toastRef.current = fn(testo, opts);
    };

    mostra(toast.loading, l.starting);
    let fotografia = null;
    try {
      // Prima di lanciare: com'era il mondo. Serve solo a diagnose, quindi un
      // errore qui non deve impedire il sync.
      if (beforeLaunch) {
        try {
          fotografia = await beforeLaunch();
        } catch (e) {
          console.error("beforeLaunch failed", e);
        }
      }

      const { data } = await api.get(`/agent/launch-uri?mode=${encodeURIComponent(mode)}&silent=1`);
      if (!data?.uri) throw new Error("no uri");
      window.location.href = data.uri;

      mostra(toast.loading, l.running, {
        action: l.cancel ? { label: l.cancel, onClick: cancel } : undefined,
      });

      const startTs = Date.now();
      while (Date.now() - startTs < timeoutMs) {
        const trascorso = Date.now() - startTs;
        await new Promise((r) => setTimeout(r, trascorso < SOGLIA_PAUSA_MS ? PAUSA_INIZIALE_MS : PAUSA_LUNGA_MS));
        // Il toast di annullamento lo ha gia' mostrato `cancel`: qui si esce e basta.
        if (abortRef.current.stop) return;
        try {
          if (await detectDone?.()) {
            // "Completato" e' vero e non dice niente. Se chi ci chiama sa cosa
            // e' cambiato, lo dice al posto nostro.
            let riepilogo = null;
            if (summarize) {
              try {
                riepilogo = await summarize(fotografia);
              } catch (e) {
                console.error("summarize failed", e);
              }
            }
            mostra(toast.success, riepilogo || l.done, riepilogo ? { duration: 8000 } : undefined);
            onDone?.();
            return;
          }
        } catch (e) {
          console.error("detectDone error", e);
        }
      }

      // Scaduto: chiediamo a chi ci ha chiamato di spiegare il silenzio.
      let esito = null;
      if (diagnose) {
        try {
          esito = await diagnose(fotografia);
        } catch (e) {
          console.error("diagnose failed", e);
        }
      }
      const testo = (typeof esito === "string" ? esito : esito?.message) || l.failed;
      mostra(toast.error, testo, { duration: 10000, action: esito?.action });
    } catch (e) {
      console.error("silent launch error", e);
      // Qui la richiesta non e' nemmeno uscita dal browser, o il backend ha
      // risposto male: parlare del token locale dell'agent sarebbe accusare una
      // macchina che non e' stata interrogata.
      mostra(toast.error, l.launchFailed, { duration: 8000 });
    } finally {
      setRunning(false);
    }
  }, [mode, detectDone, beforeLaunch, diagnose, summarize, onDone, timeoutMs, running, labels, cancel]);

  return { launch, cancel, running };
}
