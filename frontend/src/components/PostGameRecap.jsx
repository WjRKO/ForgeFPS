import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Timer, Thermometer, Zap, TrendingUp, TrendingDown, Gamepad2, Activity } from "lucide-react";
import api from "@/lib/api";

const isEnLang = (lng) => (lng || "it").startsWith("en");

export const PostGameRecap = () => {
  const { t, i18n } = useTranslation();
  const en = isEnLang(i18n.language);
  const [rows, setRows] = useState(null);

  useEffect(() => {
    api.get("/booster/sessions").then(({ data }) => setRows(data.sessions || [])).catch(() => setRows([]));
  }, []);

  if (!rows) return <div className="text-zinc-500 text-sm py-6">{t("common.loading", "Caricamento...")}</div>;

  if (rows.length === 0) {
    return (
      <div className="border border-dashed border-[#2A2A35] p-8 text-center" data-testid="recap-empty">
        <Gamepad2 size={22} className="mx-auto mb-3 text-zinc-600" />
        <div className="text-sm text-zinc-400">
          {en
            ? "No boosted sessions yet. Start the Game Booster from the agent, play a match and your recap will appear here."
            : "Nessuna sessione boostata ancora. Avvia il Game Booster dall'agent, gioca una partita e il recap apparirà qui."}
        </div>
      </div>
    );
  }

  const withRecap = rows.filter((s) => s.recap?.fps_avg);
  const latest = withRecap[0] || rows[0];
  const rec = latest.recap || {};
  const prev = withRecap.find((s) => s !== latest && s.game === latest.game);
  const delta = prev && rec.fps_avg ? rec.fps_avg - prev.recap.fps_avg : null;
  const mins = Math.round((latest.duration_s || 0) / 60);

  return (
    <div className="space-y-4" data-testid="postgame-recap">
      {/* Ultima sessione */}
      <div className="border border-[#2A2A35] bg-[#0F0F12]">
        <div className="p-4 border-b border-[#2A2A35] flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
              {en ? "Last session" : "Ultima sessione"}
            </span>
            <span className="font-display font-black text-lg">{latest.game}</span>
          </div>
          <span className="text-[11px] font-mono text-zinc-500 flex items-center gap-1.5">
            <Timer size={12} /> {mins} min · {new Date(latest.created_at).toLocaleString(en ? "en-US" : "it-IT")}
          </span>
        </div>
        {rec.fps_avg ? (
          <div className="p-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat big label="FPS" value={rec.fps_avg} accent="#E5FF00" testid="recap-fps-avg"
                sub={delta != null ? (
                  <span className={`flex items-center gap-1 ${delta >= 0 ? "text-[#00FF66]" : "text-[#FF3B30]"}`}>
                    {delta >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                    {delta >= 0 ? "+" : ""}{delta} {en ? "vs last time" : "vs ultima volta"}
                  </span>
                ) : (en ? "average" : "medi")} />
              <Stat label={en ? "1% low" : "1% low"} value={rec.fps_low ?? "—"} testid="recap-fps-low"
                sub={`min ${rec.fps_min ?? "—"} · max ${rec.fps_max ?? "—"}`} />
              <Stat label="GPU" value={rec.gpu_temp_max ? `${rec.gpu_temp_max}°C` : "—"} testid="recap-gpu-temp"
                accent={rec.gpu_temp_max >= 83 ? "#FF3B30" : undefined}
                sub={rec.gpu_temp_avg ? (en ? `avg ${rec.gpu_temp_avg}°C` : `media ${rec.gpu_temp_avg}°C`) : (en ? "peak" : "picco")} />
              <Stat label={en ? "Latency" : "Latenza"} value={rec.latency_ms ? `${rec.latency_ms} ms` : "—"} testid="recap-latency"
                sub={rec.hitches ? `${rec.hitches} hitch` : (en ? "average" : "media")} />
            </div>
            {(latest.actions || []).length > 0 && (
              <div className="mt-4 flex items-center gap-2 flex-wrap">
                <Zap size={12} className="text-[#E5FF00]" />
                {(latest.actions || []).map((a, i) => (
                  <span key={i} className="text-[11px] font-mono uppercase tracking-widest px-2 py-0.5 border border-[#2A2A35] text-zinc-400">{a}</span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="p-4 text-sm text-zinc-500" data-testid="recap-no-metrics">
            {en
              ? "This session has no FPS metrics — update the agent (relaunch it) to get the full post-game recap."
              : "Questa sessione non ha metriche FPS — aggiorna l'agent (riavvialo) per avere il recap completo di fine partita."}
          </div>
        )}
      </div>

      {/* Storico compatto */}
      {rows.length > 1 && (
        <div className="border border-[#2A2A35] bg-[#0F0F12]" data-testid="recap-history">
          <div className="p-3 border-b border-[#1A1A24] text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2">
            <Activity size={12} /> {en ? "Previous sessions" : "Sessioni precedenti"}
          </div>
          <div className="divide-y divide-[#1A1A24]">
            {rows.slice(1, 8).map((s, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2.5 text-sm" data-testid={`recap-row-${i}`}>
                <span className="font-semibold text-zinc-200 flex-1 truncate">{s.game}</span>
                <span className="text-[11px] font-mono text-zinc-500">{Math.round((s.duration_s || 0) / 60)} min</span>
                {s.recap?.fps_avg ? (
                  <span className="text-[11px] font-mono text-[#E5FF00] tabular-nums">{s.recap.fps_avg} FPS</span>
                ) : (
                  <span className="text-[11px] font-mono text-zinc-600">—</span>
                )}
                {s.recap?.gpu_temp_max ? (
                  <span className="text-[11px] font-mono text-zinc-400 flex items-center gap-1"><Thermometer size={10} />{s.recap.gpu_temp_max}°</span>
                ) : null}
                <span className="text-[11px] font-mono text-zinc-600 hidden sm:block">{new Date(s.created_at).toLocaleDateString(en ? "en-US" : "it-IT")}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

function Stat({ label, value, sub, accent, big, testid }) {
  return (
    <div className="border border-[#1A1A24] bg-black/30 p-3" data-testid={testid}>
      <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className={`font-mono font-black tabular-nums ${big ? "text-3xl" : "text-2xl"}`} style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {sub && <div className="text-[11px] font-mono text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  );
}
