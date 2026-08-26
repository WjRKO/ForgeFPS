import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Gamepad2, PlayCircle, Radio } from "lucide-react";
import api from "@/lib/api";

// v0.7.7 Universal Game Detector — banner ricco quando l'agent riconosce un gioco.
// Sorgenti (via telemetry payload):
//   - steam_registry: 100% affidabile (usa Steam Store API per cover)
//   - fg_steam / pm_steam: exe matchato con appmanifest
//   - fg_epic / fg_gog / fg_xbox: launcher DB
//   - fg_fullscreen / presentmon: rilevato ma senza store metadata
const SOURCE_LABEL = {
  steam_registry: "STEAM",
  fg_steam: "STEAM",
  pm_steam: "STEAM · DX/VK",
  fg_epic: "EPIC",
  fg_gog: "GOG",
  fg_xbox: "XBOX",
  fg_fullscreen: "FULLSCREEN",
  presentmon: "DX/VK",
};

// Il nome del gioco e gli FPS arrivano da due catene indipendenti: il
// rilevatore (registro Steam / finestra in primo piano / mappa dei giochi
// installati) e PresentMon, che riporta chi disegna piu' frame. Quando non
// coincidono la pagina mostrava il nome di un gioco e i numeri di un altro
// processo, senza che niente lo segnalasse. Il confronto onesto e' fra due nomi
// di eseguibile: `exe` dal rilevatore, `fpsApp` da PresentMon.
const stessoProcesso = (a, b) => {
  const n = (x) => String(x || "").toLowerCase().replace(/\.exe$/, "").trim();
  return !n(a) || !n(b) || n(a) === n(b);
};

export default function CurrentGameCard({ appid, gameName, source, exe, fullscreen, fpsApp }) {
  const { t } = useTranslation();
  const [info, setInfo] = useState(null);

  useEffect(() => {
    if (!appid) { setInfo(null); return; }
    let cancelled = false;
    api.get(`/game/details/${appid}`)
      .then(({ data }) => { if (!cancelled) setInfo(data?.found ? data : null); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [appid]);

  if (!gameName) return null;
  const displayName = info?.name || gameName;
  const discorde = !stessoProcesso(exe, fpsApp);
  const sourceLabel = SOURCE_LABEL[source] || (source || "").toUpperCase();

  return (
    <div
      className="relative overflow-hidden border border-hud mb-4 group"
      data-testid="current-game-card"
    >
      {/* header cover as bg */}
      {info?.header_image && (
        <div
          className="absolute inset-0 opacity-25 bg-cover bg-center transition-opacity group-hover:opacity-40"
          style={{ backgroundImage: `url(${info.header_image})` }}
          aria-hidden
        />
      )}
      <div className="absolute inset-0 bg-gradient-to-r from-panel via-panel/85 to-transparent" aria-hidden />
      <div className="relative flex items-center gap-4 p-4">
        {info?.capsule_image ? (
          <img
            src={info.capsule_image}
            alt={displayName}
            className="w-28 h-11 object-cover shrink-0 border border-hud"
            data-testid="current-game-cover"
          />
        ) : (
          <div className="w-28 h-11 shrink-0 border border-hud bg-black flex items-center justify-center">
            <Gamepad2 size={20} className="text-volt" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap text-[11px] uppercase tracking-widest text-zinc-500">
            <span className="flex items-center gap-1 text-ok">
              <Radio size={11} className="animate-pulse" />
              {t("live.game_now_playing", "Ora in gioco")}
            </span>
            <span className="text-zinc-700">·</span>
            <span className="font-mono font-bold text-volt" data-testid="current-game-source">{sourceLabel}</span>
            {fullscreen && (
              <>
                <span className="text-zinc-700">·</span>
                <span className="text-zinc-400">{t("live.game_fullscreen", "FULLSCREEN")}</span>
              </>
            )}
          </div>
          <div className="text-xl font-black font-display text-zinc-100 truncate mt-0.5" data-testid="current-game-name">
            {displayName}
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500 mt-0.5 flex-wrap">
            {info?.developers?.length > 0 && (
              <span data-testid="current-game-dev">{info.developers.slice(0, 2).join(", ")}</span>
            )}
            {info?.genres?.length > 0 && (
              <>
                {info?.developers?.length > 0 && <span className="text-zinc-700">·</span>}
                <span className="text-info" data-testid="current-game-genres">{info.genres.slice(0, 3).join(" · ")}</span>
              </>
            )}
            {exe && !info?.developers?.length && (
              <span className="font-mono text-zinc-600">{exe}.exe</span>
            )}
          </div>
          {discorde && (
            <div className="text-[11px] text-volt mt-1" data-testid="current-game-mismatch">
              {t("live.game_fps_mismatch", { app: fpsApp, defaultValue: "Gli FPS mostrati sono di {{app}}, non di questo gioco." })}
            </div>
          )}
        </div>
        {appid && (
          <a
            href={`https://store.steampowered.com/app/${appid}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden md:flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-zinc-500 hover:text-volt transition-colors"
            data-testid="current-game-steam-link"
          >
            <PlayCircle size={13} /> Steam
          </a>
        )}
      </div>
    </div>
  );
}
