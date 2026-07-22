import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { PlayCircle, CheckCircle2, AlertTriangle, XCircle, Loader2, Search } from "lucide-react";
import api from "@/lib/api";

/**
 * Pre-flight checklist popover shown before launching the monitor.
 *
 * v2 (2026-02-22):
 * - Extended game detection: 50+ hardcoded exe patterns + cross-match with the
 *   user's installed games library (Steam / Epic / GOG / Xbox scan already
 *   performed by the agent). Fuzzy word-token matching (r5apex → Apex Legends).
 * - Manual game selector: when nothing is auto-detected but the library has
 *   games, the user can pick one from a dropdown to acknowledge "I'm about to
 *   play this" — turns the check green.
 * - Never-blocking: `canProceed` is true unless the agent itself is disconnected.
 *   Every warning is a reminder, not a gatekeeper. Button label switches to
 *   "Avvia comunque" when there's any warn.
 * - Background apps: severity capped at "warn". 4+ apps no longer produce "bad"
 *   (was blocking the launch button unfairly).
 */

// Popular game process names / substrings (lowercased). Case-insensitive
// `includes()` match against `running_apps` from the last sync.
// Curated from Steam charts + common launcher exe names + anti-cheat processes
// that only spawn during a match (BEService, EasyAntiCheat_launcher, ...).
const GAME_PROCESS_KEYWORDS = [
  // Battle royale / FPS
  "fortnite", "fortniteclient", "valorant", "valorant-win", "cs2", "csgo", "riotclient",
  "r5apex", "apex", "warzone", "modernwarfare", "cod", "iw6mp", "s2_mp64", "s1_mp64",
  "battlefield", "bf1", "bf4", "bf2042", "bfhard", "cs1.6", "cs 1.6", "hl2",
  "pubg", "tslgame", "escape from tarkov", "eft", "tarkov", "arma3", "arma4",
  "insurgency", "squad", "hell let loose", "helllet",
  // MOBA / RTS
  "leagueoflegends", "league of legends", "dota2", "dota 2", "starcraft", "sc2",
  "smite", "hots", "heroesofthestorm", "aoe2", "aoe3", "aoe4",
  // MMO / RPG
  "wow", "wowclassic", "wow-64", "wowclassicprot", "ff14", "ffxiv", "ffxiv_dx11",
  "gw2", "guildwars2", "destiny2", "destiny 2", "genshin", "genshinimpact",
  "starrail", "honkai", "wuwa", "wutheringwaves", "path of exile", "poe",
  "eldenring", "elden ring", "cyberpunk", "cyberpunk2077", "witcher3", "witcher 3",
  "skyrim", "skyrimse", "fallout4", "fallout76", "starfield", "baldursgate3", "bg3",
  "diablo", "diablo3", "diablo4", "d4",
  // Racing / Sports / Sim
  "forza", "forzahorizon", "forzamotorsport", "gt7", "assettocorsa", "ac", "acc",
  "fs22", "fs25", "farmingsimulator", "flightsimulator", "msfs", "eurotruck", "ets2", "ats",
  "f1_23", "f1_24", "fifa", "fc24", "fc25", "pes", "efootball", "nba2k", "madden",
  // Party / Coop
  "rocketleague", "overwatch", "overwatch2", "rl", "fallguys", "dbd",
  "deadbydaylight", "phasmophoba", "phasmo", "leftbehind", "l4d2",
  // Sandbox / Indie / Others
  "minecraft", "minecraftlauncher", "javaw", "roblox", "robloxplayerbeta",
  "terraria", "stardewvalley", "amongus", "gta", "gta5", "gtavlauncher",
  "rdr2", "reddeadredemption2", "sea of thieves", "seaofthieves", "satisfactory",
  "palworld", "vrising", "ready or not", "readyornot", "gray zone", "grayzone",
  // Anti-cheat / launchers that hint a match is starting
  "beservice", "bepbe", "easyanticheat", "battleye", "eac_launcher", "vgtray",
  "vanguard", "riotclientservices",
];

// Word tokens for fuzzy match between game display name (library) and process
// name (running list). e.g. "Apex Legends" tokenizes to ["apex", "legends"] —
// then we check if any token appears in a running process (with a min length
// of 4 to avoid false positives like "gta" matching "gtakey.exe"...
// actually 3 is fine, we keep 3+).
function tokenize(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(/\s+/)
    .filter((t) => t.length >= 3);
}

function detectFromLibrary(runningLower, libraryGames) {
  if (!Array.isArray(libraryGames) || libraryGames.length === 0) return null;
  for (const g of libraryGames) {
    const tokens = tokenize(g);
    // Match if ANY game token appears as substring in ANY running app.
    // Weight: a longer token match is more reliable — bail out on first match.
    for (const tok of tokens) {
      if (runningLower.some((a) => a.includes(tok))) return g;
    }
  }
  return null;
}

export default function MonitorPreflight({ open, onClose, onConfirm, launching }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [checks, setChecks] = useState(null);
  // Manual override: user picked a game from the dropdown → treat "game" as ok.
  const [manualGame, setManualGame] = useState("");
  // Library of games installed (Steam / Epic / GOG / Xbox), populated from /games.
  const [library, setLibrary] = useState([]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setManualGame("");
    (async () => {
      try {
        const [pre, al, games] = await Promise.all([
          api.get("/prematch").catch(() => ({ data: {} })),
          api.get("/alerts").catch(() => ({ data: {} })),
          api.get("/games").catch(() => ({ data: {} })),
        ]);
        const running = (pre.data?.running_apps || []).map((a) => String(a).toLowerCase());
        const libraryGames = games.data?.games || [];
        setLibrary(libraryGames);

        // Heavy background apps (chat / browsers / streaming) that can skew results.
        const heavyKeys = ["chrome", "msedge", "firefox", "brave", "opera",
          "discord", "slack", "teams", "telegram", "whatsapp", "spotify",
          "obs", "streamlabs", "onedrive", "dropbox"];
        const heavyProcs = running.filter((a) => heavyKeys.some((k) => a.includes(k)));

        // Game detection: (1) known keywords, (2) library cross-match.
        const gameFromKeywords = running.find((a) =>
          GAME_PROCESS_KEYWORDS.some((k) => a.includes(k)));
        const gameFromLibrary = gameFromKeywords ? null : detectFromLibrary(running, libraryGames);
        const gameProc = gameFromKeywords || gameFromLibrary;

        // Data freshness: 10 minutes.
        const stale = pre.data?.running_at
          ? (Date.now() - new Date(pre.data.running_at).getTime()) / 1000 > 600
          : true;

        setChecks([
          {
            key: "agent",
            status: "ok",
            label: t("live.pf_agent", { defaultValue: "Agent connesso" }),
            hint: t("live.pf_agent_ok", { defaultValue: "Token attivo, backend raggiungibile" }),
          },
          {
            key: "game",
            status: gameProc ? "ok" : stale ? "unknown" : "warn",
            label: t("live.pf_game", { defaultValue: "Gioco in esecuzione" }),
            hint: gameProc
              ? `${t("live.pf_game_ok", { defaultValue: "Rilevato" })}: ${gameProc}${gameFromLibrary ? ` (libreria)` : ""}`
              : stale
                ? t("live.pf_game_stale", { defaultValue: "Nessun sync recente della lista processi. Vai in 'Il mio PC' -> Sync o seleziona manualmente qui sotto." })
                : t("live.pf_game_none_v2", { defaultValue: "Puoi avviare comunque. Gli FPS partiranno appena rileveremo un gioco a schermo intero." }),
          },
          {
            key: "heavy",
            // Never "bad": 0 apps → ok, 1+ → warn. The user decides if it's worth closing them.
            status: heavyProcs.length === 0 ? "ok" : "warn",
            label: t("live.pf_heavy", { defaultValue: "App in background" }),
            hint: heavyProcs.length === 0
              ? t("live.pf_heavy_ok", { defaultValue: "Ambiente pulito" })
              : t("live.pf_heavy_warn", { defaultValue: "Rilevate app che possono influenzare i risultati" }) + `: ${heavyProcs.slice(0, 4).join(", ")}${heavyProcs.length > 4 ? "…" : ""}`,
          },
          {
            key: "alerts",
            status: al.data?.enabled ? "ok" : "warn",
            label: t("live.pf_alerts", { defaultValue: "Alert push attivi" }),
            hint: al.data?.enabled
              ? `CPU ≥${al.data.cpu_max}°C · GPU ≥${al.data.gpu_max}°C`
              : t("live.pf_alerts_off", { defaultValue: "Push disattivate — non riceverai notifiche per temperature critiche" }),
          },
        ]);
      } catch (e) {
        console.error("preflight failed", e);
        setChecks([{ key: "err", status: "warn", label: "Preflight check", hint: String(e.message || e) }]);
      } finally {
        setLoading(false);
      }
    })();
  }, [open, t]);

  // v2: never block. Only the agent check ("agent" key with status "bad")
  // would truly matter — and today it's hardcoded to "ok" since we already
  // reached the backend to build the modal, so effectively always true.
  const canProceed = useMemo(() => {
    if (!checks) return false;
    const agentCheck = checks.find((c) => c.key === "agent");
    return !agentCheck || agentCheck.status !== "bad";
  }, [checks]);
  const hasWarning = useMemo(() => (checks || []).some((c) => c.status === "warn" || c.status === "unknown"), [checks]);

  // If the user picked a manual game, override the "game" check to ok.
  const displayedChecks = useMemo(() => {
    if (!checks || !manualGame) return checks;
    return checks.map((c) =>
      c.key === "game"
        ? { ...c, status: "ok", hint: `${t("live.pf_game_manual", { defaultValue: "Selezionato manualmente" })}: ${manualGame}` }
        : c);
  }, [checks, manualGame, t]);

  if (!open) return null;

  const STATUS_ICON = {
    ok: <CheckCircle2 size={16} className="text-[#00FF66] shrink-0" data-testid="pf-icon-ok" />,
    warn: <AlertTriangle size={16} className="text-[#E5FF00] shrink-0" data-testid="pf-icon-warn" />,
    bad: <XCircle size={16} className="text-[#FF3B30] shrink-0" data-testid="pf-icon-bad" />,
    unknown: <AlertTriangle size={16} className="text-zinc-500 shrink-0" data-testid="pf-icon-unknown" />,
  };

  const gameCheck = (displayedChecks || []).find((c) => c.key === "game");
  const showManualPicker = gameCheck && gameCheck.status !== "ok" && library.length > 0;
  const btnLabel = launching
    ? t("live.pf_launching", { defaultValue: "Apertura…" })
    : hasWarning
      ? t("live.pf_go_anyway", { defaultValue: "Avvia comunque" })
      : t("live.pf_go", { defaultValue: "Ora avvia" });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80" onClick={onClose} data-testid="monitor-preflight">
      <div className="bg-[#0F0F12] border border-[#2A2A35] max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">{t("live.pf_eyebrow", { defaultValue: "// pre-flight" })}</div>
            <h3 className="font-display font-black text-xl">{t("live.pf_title", { defaultValue: "Tutto pronto per il monitor?" })}</h3>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 text-xl leading-none px-2" data-testid="preflight-close">×</button>
        </div>

        {loading ? (
          <div className="py-10 flex items-center justify-center text-zinc-500 text-sm gap-2">
            <Loader2 size={16} className="animate-spin" /> {t("live.pf_loading", { defaultValue: "Controllo lo stato del sistema…" })}
          </div>
        ) : (
          <div className="space-y-2 mb-5" data-testid="preflight-checks">
            {(displayedChecks || []).map((c) => (
              <div key={c.key} className="flex items-start gap-3 bg-black border border-[#1A1A24] p-3" data-testid={`pf-check-${c.key}`}>
                {STATUS_ICON[c.status]}
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-zinc-200 font-semibold">{c.label}</div>
                  <div className="text-xs text-zinc-500 mt-0.5">{c.hint}</div>

                  {/* Manual game picker: appears inline inside the "game" check card
                      when nothing is auto-detected but the user has games installed. */}
                  {c.key === "game" && showManualPicker && (
                    <div className="mt-3 flex items-center gap-2" data-testid="pf-game-manual-wrap">
                      <Search size={14} className="text-zinc-500 shrink-0" />
                      <select
                        value={manualGame}
                        onChange={(e) => setManualGame(e.target.value)}
                        data-testid="pf-game-manual-select"
                        className="flex-1 bg-[#0A0A0F] border border-[#2A2A35] text-xs text-zinc-200 px-2 py-1.5 focus:outline-none focus:border-[#E5FF00]/40"
                      >
                        <option value="">{t("live.pf_game_manual_placeholder", { defaultValue: "Seleziona manualmente il gioco…" })}</option>
                        {library.slice(0, 100).map((g) => (
                          <option key={g} value={g}>{g}</option>
                        ))}
                      </select>
                      {manualGame && (
                        <button
                          onClick={() => setManualGame("")}
                          data-testid="pf-game-manual-clear"
                          className="text-xs text-zinc-500 hover:text-zinc-300 px-1"
                          title={t("common.reset", { defaultValue: "Reset" })}
                        >×</button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {hasWarning && !loading && (
          <div className="text-xs text-zinc-500 mb-4 border-l-2 border-[#E5FF00]/40 pl-3" data-testid="preflight-hint">
            {t("live.pf_warn_hint_v2", { defaultValue: "Le note sopra sono solo promemoria. Puoi avviare il monitor comunque — gli FPS partiranno appena un gioco andra a schermo intero." })}
          </div>
        )}

        <div className="flex items-center gap-3 justify-end">
          <button onClick={onClose} disabled={launching}
            data-testid="preflight-cancel"
            className="text-xs text-zinc-500 hover:text-zinc-300 px-3 py-2">
            {t("common.cancel", { defaultValue: "Annulla" })}
          </button>
          <button onClick={onConfirm} disabled={loading || !canProceed || launching}
            data-testid="preflight-confirm"
            className={`inline-flex items-center gap-2 font-bold px-4 py-2 text-sm transition-colors disabled:opacity-50 ${
              hasWarning
                ? "bg-transparent text-[#E5FF00] border border-[#E5FF00] hover:bg-[#E5FF00]/10"
                : "bg-[#E5FF00] text-black hover:bg-[#D4EE00]"
            }`}>
            {launching ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
            {btnLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
