// URL and SHA256 pubblicati alla GitHub Release del pacchetto onedir (forgefps-agent.zip).
// Da v0.6.7 distribuiamo uno ZIP (cartella onedir) invece di un .exe onefile per
// eliminare i falsi positivi euristici di Windows Defender sul bootloader PyInstaller.
// Da v0.6.8 l'.exe salva il token in %APPDATA%\FrameForge\token.dat: primo lancio
// chiede il token una volta, poi la GUI parte istantaneamente senza prompt.
// Da v0.7.0 l'.exe registra il protocollo `frameforge://` in HKCU al primo avvio:
// da lì in poi i bottoni della dashboard possono aprire la GUI senza download.
//
// AGGIORNARE dopo ogni release: URL, SHA256, versione, data.
export const AGENT_EXE_URL = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.7.3/forgefps-agent.zip";
export const AGENT_EXE_SHA256 = "4571ba466539d3a6bd552b40eadfe67948a33669b73f6410b689363588ed3600";
export const AGENT_EXE_VERSION = "v0.7.3";
export const AGENT_EXE_DATE = "2026-02-22";
export const AGENT_EXE_FORMAT = "zip"; // "zip" (onedir) | legacy: "exe" (onefile)
export const AGENT_RELEASES_URL = "https://github.com/WjRKO/ForgeFPS/releases";
export const AGENT_REPO_URL = "https://github.com/WjRKO/ForgeFPS";
export const AGENT_DEFAULT_BACKEND = "https://forgefps.dev";
