// URL and SHA256 pubblicati alla GitHub Release del pacchetto onedir (forgefps-agent.zip).
// Da v0.6.7 distribuiamo uno ZIP (cartella onedir) invece di un .exe onefile per
// eliminare i falsi positivi euristici di Windows Defender sul bootloader PyInstaller.
// Da v0.6.8 l'.exe salva il token in %APPDATA%\FrameForge\token.dat: primo lancio
// chiede il token una volta, poi la GUI parte istantaneamente senza prompt.
// Da v0.7.0 l'.exe registra il protocollo `frameforge://` in HKCU al primo avvio:
// da lì in poi i bottoni della dashboard possono aprire la GUI senza download.
//
// AGGIORNARE dopo ogni release: URL, SHA256, versione, data.
// Gli stessi tre valori vivono anche in backend/routers/pc.py (AGENT_ZIP_UPSTREAM,
// AGENT_ZIP_SHA256) e da li' vengono serviti al self-updater: tenerli allineati a
// mano e' gia' costato una versione di deriva (la dashboard offriva la v0.8.0
// mentre l'ultima release era la v0.8.1). Vanno cambiati insieme, finche' questa
// pagina non legge direttamente /api/agent/latest-version.
// L'hash va preso dall'allegato PUBBLICATO: il tag fa partire la CI, che
// riscrive l'allegato con la propria build. Vedi il commento piu' lungo
// sopra AGENT_ZIP_SHA256 in backend/routers/pc.py.
export const AGENT_EXE_URL = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.9.0/forgefps-agent.zip";
export const AGENT_EXE_SHA256 = "ee9131506b2b210b53feaa0e4b2b50a181e4ab1649edb7c1d63d0c47198c28e9";
export const AGENT_EXE_VERSION = "v0.9.0";
export const AGENT_EXE_DATE = "2026-08-22";
export const AGENT_EXE_FORMAT = "zip"; // "zip" (onedir) | legacy: "exe" (onefile)
export const AGENT_RELEASES_URL = "https://github.com/WjRKO/ForgeFPS/releases";
export const AGENT_REPO_URL = "https://github.com/WjRKO/ForgeFPS";
export const AGENT_DEFAULT_BACKEND = "https://forgefps.dev";
