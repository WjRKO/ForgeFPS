/**
 * ObsOverlayPanel — panel per configurare l'OBS Browser Source overlay.
 *
 * - Solo Streamer (backend gate 402 -> mostriamo un banner upsell inline)
 * - Mostra URL da copiare, bottone Copia, Rigenera token, preview iframe live
 * - Setting: posizione (4 opzioni), tema (3 opzioni), toggle per singola metric
 */
import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Copy, RefreshCw, ExternalLink, Loader2, Check, Radio, Monitor, Zap, Layout } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import PlanUpgradeBanner from "@/components/PlanUpgradeBanner";

const POSITIONS = [
  { id: "top-left", label: "Alto SX" },
  { id: "top-right", label: "Alto DX" },
  { id: "bottom-left", label: "Basso SX" },
  { id: "bottom-right", label: "Basso DX" },
];
const THEMES = [
  { id: "neon", label: "Neon giallo", swatch: "#E5FF00" },
  { id: "dark", label: "Dark ciano", swatch: "#00E0FF" },
  { id: "minimal", label: "Minimal", swatch: "#FFFFFF" },
];
const METRIC_TOGGLES = [
  { key: "show_fps", label: "FPS" },
  { key: "show_cpu", label: "CPU %" },
  { key: "show_gpu", label: "GPU %" },
  { key: "show_ping", label: "Ping" },
  { key: "show_health", label: "Health Score" },
];

export default function ObsOverlayPanel() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const [lockedPlan, setLockedPlan] = useState("starter");
  const [cfg, setCfg] = useState(null);
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [previewKey, setPreviewKey] = useState(0); // per forzare reload iframe

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/overlay/config");
      setCfg(data);
      setLocked(false);
    } catch (e) {
      if (e?.response?.status === 402) {
        setLocked(true);
        setLockedPlan(e.response.data?.detail?.current || "starter");
      } else toast.error("Errore caricamento overlay");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateCfg = async (patch) => {
    try {
      const { data } = await api.put("/overlay/config", patch);
      setCfg(data);
      setPreviewKey((k) => k + 1);
    } catch {
      toast.error("Errore salvataggio impostazioni");
    }
  };

  const rotate = async () => {
    if (!window.confirm("Rigenera token? Il vecchio URL smettera' di funzionare (utile se lo hai condiviso).")) return;
    setRotating(true);
    try {
      const { data } = await api.post("/overlay/token");
      setCfg(data);
      setPreviewKey((k) => k + 1);
      toast.success("Nuovo token generato — aggiorna l'URL in OBS");
    } catch {
      toast.error("Errore rigenerazione token");
    } finally {
      setRotating(false);
    }
  };

  const copyUrl = async () => {
    if (!cfg?.url) return;
    try {
      await navigator.clipboard.writeText(cfg.url);
      setCopied(true);
      toast.success("URL copiato negli appunti");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Copia non riuscita — copia manualmente");
    }
  };

  if (loading) {
    return <div className="flex items-center gap-2 text-zinc-500 py-8 justify-center"><Loader2 size={16} className="animate-spin" /> Caricamento overlay...</div>;
  }

  if (locked) {
    return (
      <PlanUpgradeBanner
        tier="streamer"
        title={t("plan_banner.overlay.title")}
        description={t("plan_banner.overlay.desc")}
        features={[
          { icon: Radio, title: t("plan_banner.overlay.f1_t"), desc: t("plan_banner.overlay.f1_d") },
          { icon: Layout, title: t("plan_banner.overlay.f2_t"), desc: t("plan_banner.overlay.f2_d") },
          { icon: Monitor, title: t("plan_banner.overlay.f3_t"), desc: t("plan_banner.overlay.f3_d") },
          { icon: Zap, title: t("plan_banner.overlay.f4_t"), desc: t("plan_banner.overlay.f4_d") },
        ]}
        currentPlan={lockedPlan}
        compact
        testid="overlay-locked"
      />
    );
  }

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-5 space-y-5" data-testid="obs-overlay-panel">
      <div className="flex items-center gap-2 text-sm font-bold">
        <Radio size={16} className="text-[#00E0FF]" /> OBS Browser Overlay
      </div>
      <p className="text-xs text-zinc-500 -mt-3">
        Aggiungi questo URL come <strong className="text-zinc-300">Browser Source</strong> in OBS Studio (larghezza 300px, altezza 200px consigliati). Aggiorna in tempo reale mentre il Live Monitor gira.
      </p>

      {/* Warning se monitor non attivo */}
      <div className="flex items-start gap-2 bg-[#FF9500]/10 border border-[#FF9500]/40 p-3" data-testid="overlay-monitor-hint">
        <Radio size={14} className="text-[#FF9500] shrink-0 mt-0.5" />
        <div className="text-[11px] text-[#FFB347] leading-relaxed">
          <strong>Importante</strong>: l'overlay mostra i dati (FPS, CPU%, temp) solo quando il <strong className="text-white">Live Monitor gira sul PC</strong>. Se in OBS vedi valori vuoti, lancia il monitor con il bottone qui sopra. Health Score e temperatura CPU vengono mostrati sempre (persistono in DB).
        </div>
      </div>

      {/* URL row */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          readOnly
          value={cfg?.url || ""}
          data-testid="overlay-url-input"
          className="flex-1 min-w-[240px] bg-[#0A0A0F] border border-[#2A2A35] text-xs text-zinc-300 font-mono px-3 py-2 select-all"
          onFocus={(e) => e.target.select()}
        />
        <button
          onClick={copyUrl}
          data-testid="overlay-copy-btn"
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold uppercase tracking-widest text-xs px-4 py-2 hover:bg-[#D4EE00] transition-colors"
        >
          {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copiato" : "Copia URL"}
        </button>
        <a
          href={cfg?.url}
          target="_blank"
          rel="noreferrer"
          data-testid="overlay-open-btn"
          className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-300 hover:border-[#00E0FF] hover:text-[#00E0FF] text-xs px-3 py-2 transition-colors"
        >
          <ExternalLink size={12} /> Apri
        </a>
        <button
          onClick={rotate}
          disabled={rotating}
          data-testid="overlay-rotate-btn"
          className="inline-flex items-center gap-2 border border-[#FF9500]/50 text-[#FF9500] hover:bg-[#FF9500]/10 text-xs px-3 py-2 transition-colors disabled:opacity-60"
        >
          {rotating ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} Rigenera
        </button>
      </div>

      {/* Settings */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Position */}
        <div>
          <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono mb-2">Posizione</div>
          <div className="grid grid-cols-2 gap-1">
            {POSITIONS.map((p) => (
              <button
                key={p.id}
                onClick={() => updateCfg({ position: p.id })}
                data-testid={`overlay-pos-${p.id}`}
                className={`text-xs px-3 py-2 border transition-colors ${cfg?.position === p.id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        {/* Theme */}
        <div>
          <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono mb-2">Tema</div>
          <div className="grid grid-cols-3 gap-1">
            {THEMES.map((th) => (
              <button
                key={th.id}
                onClick={() => updateCfg({ theme: th.id })}
                data-testid={`overlay-theme-${th.id}`}
                className={`flex items-center gap-2 text-xs px-3 py-2 border transition-colors ${cfg?.theme === th.id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}
              >
                <span className="w-3 h-3 border border-[#2A2A35]" style={{ background: th.swatch }} />
                {th.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Metric toggles */}
      <div>
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono mb-2">Metriche mostrate</div>
        <div className="flex flex-wrap gap-2">
          {METRIC_TOGGLES.map((m) => {
            const active = !!cfg?.[m.key];
            return (
              <button
                key={m.key}
                onClick={() => updateCfg({ [m.key]: !active })}
                data-testid={`overlay-toggle-${m.key}`}
                className={`text-xs px-3 py-1.5 border transition-colors ${active ? "border-[#00E0FF] text-[#00E0FF] bg-[#00E0FF]/5" : "border-[#2A2A35] text-zinc-500 hover:border-zinc-600"}`}
              >
                {active ? <Check size={11} className="inline mr-1" /> : null}{m.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Live preview */}
      <div>
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono mb-2">Anteprima live</div>
        <div
          className="relative border border-[#2A2A35] overflow-hidden"
          style={{
            height: 220,
            backgroundImage: "linear-gradient(45deg, #1a1a20 25%, transparent 25%, transparent 75%, #1a1a20 75%), linear-gradient(45deg, #1a1a20 25%, transparent 25%, transparent 75%, #1a1a20 75%)",
            backgroundSize: "20px 20px",
            backgroundPosition: "0 0, 10px 10px",
            backgroundColor: "#0A0A0F",
          }}
        >
          {cfg?.token && (
            <iframe
              key={previewKey}
              /* Usa origin corrente per la preview iframe (in dev/preview il token e'
                 valido solo sul backend corrente; l'URL "copiabile" invece punta a
                 APP_ORIGIN che e' il dominio production dello streamer). */
              src={`${window.location.origin}/api/overlay/${cfg.token}`}
              title="OBS Overlay preview"
              className="absolute inset-0 w-full h-full"
              style={{ background: "transparent" }}
              data-testid="overlay-preview-iframe"
            />
          )}
        </div>
        <div className="text-[10px] text-zinc-600 mt-1 font-mono">
          Lo sfondo a scacchiera indica la trasparenza — in OBS non lo vedrai.
        </div>
      </div>

      {/* OBS setup instructions */}
      <details className="border-t border-[#2A2A35] pt-3">
        <summary className="text-[11px] text-zinc-500 cursor-pointer hover:text-zinc-300 font-mono uppercase tracking-widest">
          Come aggiungerlo in OBS Studio
        </summary>
        <ol className="mt-3 text-xs text-zinc-400 space-y-1.5 list-decimal list-inside">
          <li>In OBS, click <strong className="text-white">+</strong> nella lista Sources → <strong className="text-white">Browser</strong> (o "Sorgente browser")</li>
          <li>Dai un nome (es. "FrameForge Overlay") → OK</li>
          <li>URL: incolla quello sopra</li>
          <li>Larghezza <strong className="text-white">300</strong>, Altezza <strong className="text-white">200</strong> (regola come vuoi)</li>
          <li>Assicurati che <strong className="text-white">"Refresh browser when scene becomes active"</strong> sia disattivato</li>
          <li>OK — trascina in posizione sulla scena</li>
        </ol>
      </details>
    </div>
  );
}
