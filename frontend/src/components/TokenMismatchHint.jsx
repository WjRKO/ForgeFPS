/**
 * TokenMismatchHint
 *
 * Mostrato sulla pagina "FrameForge Agent" per gli utenti che potrebbero
 * avere un exe installato con il token di un ALTRO account.
 *
 * Sintomo tipico:
 *   - Il banner "primo scan" appare anche se hanno gia' dati reali
 *   - "Sincronizza ora" apre una GUI visibile che stampa "Primo scan..."
 *   - I dati non arrivano mai nel dashboard di questo account
 *
 * Causa: %APPDATA%\FrameForge\token.dat contiene il token dell'altro account.
 *   La firma HMAC dell'URI frameforge:// fallisce → l'exe cade sul fallback
 *   securegui che apre la finestra visibile.
 *
 * Fix: scaricare /api/agent/launcher-bat (bat file col token corrente) e
 *   lanciarlo una volta. L'exe verra' invocato con --token X che sovrascrive
 *   il file .dat con il token dell'account attualmente loggato.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Download, ChevronDown, ChevronUp, User, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

export default function TokenMismatchHint() {
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "").startsWith("en");
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.get("/auth/me").then(({ data }) => setEmail(data?.email || "")).catch(() => {});
  }, []);

  const downloadBat = async () => {
    setDownloading(true);
    try {
      const resp = await api.get("/agent/launcher-bat", { responseType: "blob", timeout: 30000 });
      const url = window.URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "forgefps-launcher.bat";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(
        en
          ? "Launcher downloaded. Move it next to the extracted 'forgefps-agent' folder and double-click."
          : "Launcher scaricato. Mettilo accanto alla cartella 'forgefps-agent' estratta e fai doppio click."
      );
    } catch (e) {
      toast.error(en ? "Download failed. Retry in a moment." : "Download fallito. Riprova tra un momento.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="border border-[#FFAA00]/40 bg-[#FFAA00]/5 p-5 mb-6" data-testid="token-mismatch-hint">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 text-left"
        data-testid="token-mismatch-toggle"
      >
        <AlertTriangle size={18} className="shrink-0 text-[#FFAA00] mt-0.5" />
        <div className="min-w-0 flex-1">
          <div className="text-xs uppercase tracking-[0.2em] text-[#FFAA00] mb-1">
            {en ? "// sync not working?" : "// sync non funziona?"}
          </div>
          <h3 className="font-display font-black text-lg text-zinc-100">
            {en
              ? "The agent might be linked to another account"
              : "L'agent potrebbe essere collegato ad un altro account"}
          </h3>
          <p className="text-xs text-zinc-400 leading-relaxed mt-1">
            {en
              ? "If \"Sync now\" opens a visible PowerShell window that runs a full first scan, or the first-scan banner keeps showing even after syncing, the local exe still holds an OLD token from a previous account."
              : "Se \"Sincronizza ora\" apre una finestra PowerShell visibile che fa un primo scan completo, oppure il banner \"fai il tuo primo scan\" continua a comparire dopo la sync, l'exe locale sta usando un VECCHIO token di un account precedente."}
          </p>
        </div>
        {open ? <ChevronUp size={16} className="text-zinc-400 shrink-0" /> : <ChevronDown size={16} className="text-zinc-400 shrink-0" />}
      </button>

      {open && (
        <div className="mt-4 pt-4 border-t border-[#FFAA00]/20 space-y-4" data-testid="token-mismatch-detail">
          {email && (
            <div className="flex items-center gap-2 text-xs">
              <User size={13} className="text-[#00E0FF]" />
              <span className="text-zinc-500">{en ? "Currently logged in as:" : "Attualmente loggato come:"}</span>
              <span className="font-mono text-[#00E0FF] font-semibold" data-testid="current-account-email">{email}</span>
            </div>
          )}

          <div>
            <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">
              {en ? "// how to fix (30 seconds)" : "// come sistemare (30 secondi)"}
            </div>
            <ol className="text-sm text-zinc-300 space-y-2 leading-relaxed list-decimal pl-5">
              <li>
                {en
                  ? "Download the personalized launcher .bat below (contains your current token)."
                  : "Scarica il launcher .bat personalizzato qui sotto (contiene il tuo token attuale)."}
              </li>
              <li>
                {en ? (
                  <>Place it in the <strong>same folder</strong> where you extracted <code className="text-[#00E0FF] bg-black px-1">forgefps-agent</code> (the folder that contains <code className="text-[#00E0FF] bg-black px-1">forgefps-agent.exe</code>).</>
                ) : (
                  <>Mettilo nella <strong>stessa cartella</strong> dove hai estratto <code className="text-[#00E0FF] bg-black px-1">forgefps-agent</code> (quella che contiene <code className="text-[#00E0FF] bg-black px-1">forgefps-agent.exe</code>).</>
                )}
              </li>
              <li>
                {en ? (
                  <>Double-click <strong>forgefps-launcher.bat</strong>. The exe will start with the current account's token and overwrite the old one in <code className="text-[#00E0FF] bg-black px-1 text-[10px]">%APPDATA%\FrameForge\token.dat</code>.</>
                ) : (
                  <>Doppio click su <strong>forgefps-launcher.bat</strong>. L'exe si avvia con il token dell'account attuale e sovrascrive quello vecchio in <code className="text-[#00E0FF] bg-black px-1 text-[10px]">%APPDATA%\FrameForge\token.dat</code>.</>
                )}
              </li>
              <li>
                {en
                  ? "Close the GUI, come back here, press \"Sync now\" — it will run silent in the background."
                  : "Chiudi la GUI, torna qui e premi \"Sincronizza ora\": ora girerà silenzioso in background."}
              </li>
            </ol>
          </div>

          <button
            onClick={downloadBat}
            disabled={downloading}
            data-testid="download-launcher-bat-btn"
            className="inline-flex items-center gap-2 bg-[#FFAA00] text-black font-bold px-4 py-2.5 text-sm hover:bg-[#FFC13F] transition-colors disabled:opacity-60"
          >
            {downloading ? <RefreshCw size={15} className="animate-spin" /> : <Download size={15} />}
            {downloading
              ? (en ? "Preparing..." : "Preparo...")
              : (en ? "Download personal launcher .bat" : "Scarica launcher .bat personale")}
          </button>

          <div className="text-[11px] text-zinc-600 leading-relaxed border-t border-[#FFAA00]/20 pt-3">
            {en ? (
              <>Alternative: open <code className="text-zinc-400">forgefps-agent.exe</code> directly, click <strong>"Cambia account"</strong> in the header, then paste the token shown in the "Advanced / PowerShell" section of this page.</>
            ) : (
              <>Alternativa: apri <code className="text-zinc-400">forgefps-agent.exe</code> direttamente, clicca <strong>"Cambia account"</strong> in alto, poi incolla il token mostrato nella sezione "Avanzato / PowerShell" di questa pagina.</>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
