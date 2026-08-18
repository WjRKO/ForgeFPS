/**
 * ObsOverlayPanel — panel per configurare l'OBS Browser Source overlay.
 *
 * - Solo Streamer (backend gate 402 -> mostriamo un banner upsell inline)
 * - Mostra URL da copiare, bottone Copia, Rigenera token, preview iframe live
 * - Setting: posizione (4 opzioni), tema (3 opzioni), toggle per singola metric
 */
import { useEffect, useState, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Copy, RefreshCw, ExternalLink, Loader2, Check, Radio, Monitor, Zap, Layout } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import PlanUpgradeBanner from "@/components/PlanUpgradeBanner";
import i18n from "@/i18n";

const isEn = () => i18n.language?.startsWith("en");

const POSITIONS = [
  { id: "top-left", label: "Alto SX", en: "Top left" },
  { id: "top-right", label: "Alto DX", en: "Top right" },
  { id: "bottom-left", label: "Basso SX", en: "Bottom left" },
  { id: "bottom-right", label: "Basso DX", en: "Bottom right" },
];
const THEMES = [
  { id: "neon", label: "Neon giallo", en: "Neon yellow", swatch: "#E5FF00" },
  { id: "dark", label: "Dark ciano", en: "Dark cyan", swatch: "#00E0FF" },
  { id: "minimal", label: "Minimal", en: "Minimal", swatch: "#FFFFFF" },
];
const METRIC_TOGGLES = [
  { key: "show_fps", label: "FPS" },
  { key: "show_cpu", label: "CPU %" },
  { key: "show_gpu", label: "GPU %" },
  { key: "show_ping", label: "Ping" },
  { key: "show_health", label: "Health Score" },
];
const LAYOUTS = [
  { id: "card", label: "Card verticale", en: "Vertical card" },
  { id: "bar", label: "Barra orizzontale", en: "Horizontal bar" },
];
const SIZES = [
  { id: "small", label: "S" },
  { id: "medium", label: "M" },
  { id: "large", label: "L" },
];

export default function ObsOverlayPanel() {
  const { t } = useTranslation();
  const [devices, setDevices] = useState([]);
  useEffect(() => { api.get("/devices").then(({ data }) => setDevices(data.devices || [])).catch(() => {}); }, []);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const [lockedPlan, setLockedPlan] = useState("starter");
  const [cfg, setCfg] = useState(null);
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [previewKey, setPreviewKey] = useState(0); // per forzare reload iframe
  const accentTimer = useRef(null);
  const setAccentDebounced = (v) => {
    clearTimeout(accentTimer.current);
    accentTimer.current = setTimeout(() => updateCfg({ accent: v }), 400);
  };

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/overlay/config");
      setCfg(data);
      setLocked(false);
    } catch (e) {
      if (e?.response?.status === 402) {
        setLocked(true);
        setLockedPlan(e.response.data?.detail?.current || "starter");
      } else toast.error(isEn() ? "Error loading overlay" : "Errore caricamento overlay");
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
      toast.error(isEn() ? "Error saving settings" : "Errore salvataggio impostazioni");
    }
  };

  const rotate = async () => {
    if (!window.confirm(isEn() ? "Regenerate token? The old URL will stop working (useful if you shared it)." : "Rigenera token? Il vecchio URL smettera' di funzionare (utile se lo hai condiviso).")) return;
    setRotating(true);
    try {
      const { data } = await api.post("/overlay/token");
      setCfg(data);
      setPreviewKey((k) => k + 1);
      toast.success(isEn() ? "New token generated — update the URL in OBS" : "Nuovo token generato — aggiorna l'URL in OBS");
    } catch {
      toast.error(isEn() ? "Error regenerating token" : "Errore rigenerazione token");
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
      toast.error(isEn() ? "Copy failed — copy manually" : "Copia non riuscita — copia manualmente");
    }
  };

  if (loading) {
    return <div className="flex items-center gap-2 text-zinc-500 py-8 justify-center"><Loader2 size={16} className="animate-spin" /> {isEn() ? "Loading overlay..." : "Caricamento overlay..."}</div>;
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
        Aggiungi questo URL come <strong className="text-zinc-300">Browser Source</strong> in OBS Studio (larghezza 340px, altezza 260px consigliati — assicurati che "custom CSS" sia vuoto). Aggiorna in tempo reale mentre il Live Monitor gira.
      </p>

      {/* Warning se monitor non attivo */}
      <div className="flex items-start gap-2 bg-[#FF9500]/10 border border-[#FF9500]/40 p-3" data-testid="overlay-monitor-hint">
        <Radio size={14} className="text-[#FF9500] shrink-0 mt-0.5" />
        <div className="text-[11px] text-[#FFB347] leading-relaxed">
          {isEn() ? <><strong>Important</strong>: the overlay shows data (FPS, CPU%, temps) only while the <strong className="text-white">Live Monitor is running on your PC</strong>. If OBS shows empty values, launch the monitor with the button above. Health Score and CPU temperature are always shown (persisted in DB).</> : <><strong>Importante</strong>: l'overlay mostra i dati (FPS, CPU%, temp) solo quando il <strong className="text-white">Live Monitor gira sul PC</strong>. Se in OBS vedi valori vuoti, lancia il monitor con il bottone qui sopra. Health Score e temperatura CPU vengono mostrati sempre (persistono in DB).</>}
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
          {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? (isEn() ? "Copied" : "Copiato") : (isEn() ? "Copy URL" : "Copia URL")}
        </button>
        <a
          href={cfg?.url}
          target="_blank"
          rel="noreferrer"
          data-testid="overlay-open-btn"
          className="inline-flex items-center gap-2 border border-[#2A2A35] text-zinc-300 hover:border-[#00E0FF] hover:text-[#00E0FF] text-xs px-3 py-2 transition-colors"
        >
          <ExternalLink size={12} /> {isEn() ? "Open" : "Apri"}
        </a>
        <button
          onClick={rotate}
          disabled={rotating}
          data-testid="overlay-rotate-btn"
          className="inline-flex items-center gap-2 border border-[#FF9500]/50 text-[#FF9500] hover:bg-[#FF9500]/10 text-xs px-3 py-2 transition-colors disabled:opacity-60"
        >
          {rotating ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} {isEn() ? "Regenerate" : "Rigenera"}
        </button>
      </div>

      {/* Settings */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Position */}
        <div>
          <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">{isEn() ? "Position" : "Posizione"}</div>
          <div className="grid grid-cols-2 gap-1">
            {POSITIONS.map((p) => (
              <button
                key={p.id}
                onClick={() => updateCfg({ position: p.id })}
                data-testid={`overlay-pos-${p.id}`}
                className={`text-xs px-3 py-2 border transition-colors ${cfg?.position === p.id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}
              >
                {isEn() ? p.en : p.label}
              </button>
            ))}
          </div>
        </div>
        {/* Multi-PC: sorgente dati dell'overlay */}
        {devices.length >= 2 && (
          <div data-testid="overlay-source-section">
            <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">{isEn() ? "Data source (Multi-PC)" : "Sorgente dati (Multi-PC)"}</div>
            <div className="grid grid-cols-1 gap-1">
              <button onClick={() => updateCfg({ source_device: "" })} data-testid="overlay-source-active"
                className={`text-xs px-3 py-2 border text-left transition-colors ${!cfg?.source_device ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}>
                {isEn() ? "Active PC (default)" : "PC attivo (default)"}
              </button>
              {devices.map((d) => (
                <button key={d.device_id} onClick={() => updateCfg({ source_device: d.device_id })}
                  data-testid={`overlay-source-${d.device_id}`}
                  className={`text-xs px-3 py-2 border text-left transition-colors ${cfg?.source_device === d.device_id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}>
                  {d.name} <span className="text-zinc-600">· {d.role}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {/* Theme */}
        <div>
          <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">{isEn() ? "Theme" : "Tema"}</div>
          <div className="grid grid-cols-3 gap-1">
            {THEMES.map((th) => (
              <button
                key={th.id}
                onClick={() => updateCfg({ theme: th.id })}
                data-testid={`overlay-theme-${th.id}`}
                className={`flex items-center gap-2 text-xs px-3 py-2 border transition-colors ${cfg?.theme === th.id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}
              >
                <span className="w-3 h-3 border border-[#2A2A35]" style={{ background: th.swatch }} />
                {isEn() ? th.en : th.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Layout / Size / Accent */}
      <div className="grid md:grid-cols-3 gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">Layout</div>
          <div className="grid grid-cols-2 gap-1">
            {LAYOUTS.map((l) => (
              <button
                key={l.id}
                onClick={() => updateCfg({ layout: l.id })}
                data-testid={`overlay-layout-${l.id}`}
                className={`text-xs px-3 py-2 border transition-colors ${cfg?.layout === l.id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}
              >
                {isEn() ? l.en : l.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">{isEn() ? "Size" : "Dimensione"}</div>
          <div className="grid grid-cols-3 gap-1">
            {SIZES.map((s) => (
              <button
                key={s.id}
                onClick={() => updateCfg({ size: s.id })}
                data-testid={`overlay-size-${s.id}`}
                className={`text-xs px-3 py-2 border transition-colors ${(cfg?.size || "medium") === s.id ? "border-[#E5FF00] text-[#E5FF00] bg-[#E5FF00]/5" : "border-[#2A2A35] text-zinc-400 hover:border-zinc-600"}`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">{isEn() ? "Brand color" : "Colore brand"}</div>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={cfg?.accent || THEMES.find((th) => th.id === cfg?.theme)?.swatch || "#E5FF00"}
              onChange={(e) => setAccentDebounced(e.target.value)}
              data-testid="overlay-accent-picker"
              className="w-10 h-9 bg-[#0A0A0F] border border-[#2A2A35] cursor-pointer p-0.5"
              title={isEn() ? "Custom accent color" : "Colore accent personalizzato"}
            />
            <span className="font-mono text-xs text-zinc-400">{cfg?.accent || (isEn() ? "theme" : "tema")}</span>
            {cfg?.accent && (
              <button
                onClick={() => updateCfg({ accent: "" })}
                data-testid="overlay-accent-reset"
                className="text-[11px] uppercase tracking-widest text-zinc-500 border border-[#2A2A35] px-2 py-1.5 hover:border-zinc-500 transition-colors"
              >
                Reset
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Metric toggles */}
      <div>
        <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">{isEn() ? "Shown metrics" : "Metriche mostrate"}</div>
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
        <div className="text-[11px] uppercase tracking-widest text-zinc-500 font-mono mb-2">{isEn() ? "Live preview" : "Anteprima live"}</div>
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
              /* Stesso URL che si copia in OBS: unica fonte di verita'.
                 Prima l'anteprima usava window.location.origin perche' `cfg.url`
                 puntava ad APP_ORIGIN, che in locale e' la porta del front-end e
                 restituisce l'HTML della SPA invece dell'overlay. Ora il backend
                 costruisce `url` con AGENT_BACKEND_URL, quindi e' corretto sia in
                 locale sia in produzione, e l'anteprima mostra davvero cio' che
                 vedra' OBS. */
              src={cfg.url || `${window.location.origin}/api/overlay/${cfg.token}`}
              title="OBS Overlay preview"
              className="absolute inset-0 w-full h-full"
              style={{ background: "transparent" }}
              data-testid="overlay-preview-iframe"
            />
          )}
        </div>
        <div className="text-[11px] text-zinc-600 mt-1 font-mono">
          {isEn() ? "The checkerboard background indicates transparency — you won't see it in OBS." : "Lo sfondo a scacchiera indica la trasparenza — in OBS non lo vedrai."}
        </div>
      </div>

      {/* OBS setup instructions */}
      <details className="border-t border-[#2A2A35] pt-3">
        <summary className="text-[11px] text-zinc-500 cursor-pointer hover:text-zinc-300 font-mono uppercase tracking-widest">
          {isEn() ? "How to add it in OBS Studio" : "Come aggiungerlo in OBS Studio"}
        </summary>
        <ol className="mt-3 text-xs text-zinc-400 space-y-1.5 list-decimal list-inside">
          {isEn() ? (
            <>
              <li>In OBS, click <strong className="text-white">+</strong> in the Sources list → <strong className="text-white">Browser</strong></li>
              <li>Give it a name (e.g. "FrameForge Overlay") → OK</li>
              <li>URL: paste the one above</li>
              <li>Width <strong className="text-white">300</strong>, Height <strong className="text-white">200</strong> (adjust as you like)</li>
              <li>Make sure <strong className="text-white">"Refresh browser when scene becomes active"</strong> is disabled</li>
              <li>OK — drag it into position on the scene</li>
            </>
          ) : (
            <>
              <li>In OBS, click <strong className="text-white">+</strong> nella lista Sources → <strong className="text-white">Browser</strong> (o "Sorgente browser")</li>
              <li>Dai un nome (es. "FrameForge Overlay") → OK</li>
              <li>URL: incolla quello sopra</li>
              <li>Larghezza <strong className="text-white">300</strong>, Altezza <strong className="text-white">200</strong> (regola come vuoi)</li>
              <li>Assicurati che <strong className="text-white">"Refresh browser when scene becomes active"</strong> sia disattivato</li>
              <li>OK — trascina in posizione sulla scena</li>
            </>
          )}
        </ol>
      </details>
    </div>
  );
}
