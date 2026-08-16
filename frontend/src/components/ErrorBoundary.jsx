import { Component } from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";

/**
 * Rete di sicurezza contro gli errori di render.
 *
 * Senza, un solo errore in una qualsiasi delle pagine lazy (un `undefined.map()`
 * su una risposta inattesa del backend) fa sparire l'intera applicazione: React
 * smonta l'albero e resta una pagina bianca, senza messaggio e senza via d'uscita.
 *
 * Deve essere una classe: `componentDidCatch` non ha un equivalente fra gli hook.
 *
 * Non usa `useTranslation` per la stessa ragione, quindi la lingua viene letta
 * direttamente dallo storage: in uno stato di errore e' meglio non dipendere da
 * altri provider, che potrebbero essere proprio quelli rotti.
 */
const T = {
  it: {
    title: "Qualcosa si è rotto in questa sezione",
    body: "Il resto dell'app funziona. Puoi riprovare a caricare questa pagina o tornare alla dashboard.",
    retry: "Riprova",
    home: "Vai alla dashboard",
    details: "Dettagli tecnici",
  },
  en: {
    title: "Something broke in this section",
    body: "The rest of the app is fine. You can retry loading this page or go back to the dashboard.",
    retry: "Retry",
    home: "Go to dashboard",
    details: "Technical details",
  },
};

function lang() {
  try {
    const stored = window.localStorage.getItem("boostpc_lang") ||
      window.localStorage.getItem("i18nextLng") ||
      window.navigator.language;
    return String(stored || "it").toLowerCase().startsWith("en") ? "en" : "it";
  } catch {
    return "it";
  }
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Nessun servizio di error tracking configurato: il minimo utile e' lasciare
    // la traccia in console, cosi' resta recuperabile da chi segnala il problema.
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info?.componentStack);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const c = T[lang()];
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6" data-testid="error-boundary">
        <div className="bg-[#0F0F12] border border-[#FF3B30]/40 hud-tick p-8 max-w-lg w-full">
          <div className="flex items-center gap-2 text-[#FF3B30] mb-3">
            <AlertTriangle size={18} />
            <span className="text-xs uppercase tracking-[0.2em]">{c.title}</span>
          </div>
          <p className="text-sm text-zinc-400 mb-6">{c.body}</p>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={this.handleRetry}
              data-testid="error-boundary-retry"
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black text-sm font-semibold px-4 py-2 hover:bg-[#d4ee00] transition-colors"
            >
              <RotateCcw size={14} /> {c.retry}
            </button>
            <a
              href="/app"
              data-testid="error-boundary-home"
              className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-300 text-sm px-4 py-2 hover:border-[#E5FF00]/50 transition-colors"
            >
              <Home size={14} /> {c.home}
            </a>
          </div>

          <details className="mt-6">
            <summary className="text-[11px] uppercase tracking-wider text-zinc-600 cursor-pointer">
              {c.details}
            </summary>
            <pre className="mt-2 text-[11px] text-zinc-500 whitespace-pre-wrap break-words max-h-40 overflow-auto">
              {String(error?.stack || error?.message || error)}
            </pre>
          </details>
        </div>
      </div>
    );
  }
}
