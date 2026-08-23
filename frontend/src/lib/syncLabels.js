/**
 * La sincronizzazione silent: durata dell'attesa ed etichette, in un posto solo.
 *
 * Il sync parte da due punti - il pulsante "Sincronizza ora" di "Il mio PC" e il
 * badge di freschezza nell'header - che facevano la stessa cosa con copie
 * diverse. Il pulsante passava stringhe tradotte; il badge passava stringhe
 * vuote sperando nel silenzio e otteneva invece i default italiani dell'hook,
 * mostrati anche a chi usa l'app in inglese. E il timeout era scritto due volte.
 *
 * Un'operazione sola aspetta lo stesso tempo e parla con una voce sola.
 */

// Quanto si aspetta l'agent prima di dire che non ha risposto. Il numero entra
// anche nel messaggio di errore: "non ha risposto entro 60 secondi" e' un fatto,
// "non risponde" e' un'impressione.
export const SYNC_TIMEOUT_MS = 60000;

export function syncLabels(t) {
  const sec = Math.round(SYNC_TIMEOUT_MS / 1000);
  return {
    starting: t("mypcpage.silent_sync_start", { defaultValue: "Sincronizzazione in avvio..." }),
    running: t("mypcpage.silent_sync_running", { defaultValue: "Sincronizzazione hardware in corso..." }),
    done: t("mypcpage.silent_sync_done", { defaultValue: "Sync completato. Dati aggiornati." }),
    failed: t("mypcpage.silent_sync_failed", {
      sec,
      defaultValue: "L'agent non ha risposto entro {{sec}} secondi. Controlla di averlo installato e aggiornato dalla pagina 'FrameForge Agent'.",
    }),
    launchFailed: t("mypcpage.sync_launch_failed", {
      defaultValue: "Non e' stato possibile avviare la sincronizzazione. Controlla la connessione e riprova.",
    }),
    cancel: t("mypcpage.sync_cancel", { defaultValue: "Annulla" }),
    cancelled: t("mypcpage.sync_cancelled", { defaultValue: "Sincronizzazione annullata." }),
  };
}
