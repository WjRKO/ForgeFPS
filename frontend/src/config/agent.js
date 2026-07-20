// URL and SHA256 pubblicati alla GitHub Release del pacchetto onedir (forgefps-agent.zip).
// Da v0.6.7 distribuiamo uno ZIP (cartella onedir) invece di un .exe onefile per
// eliminare i falsi positivi euristici di Windows Defender sul bootloader PyInstaller.
// Da v0.6.8 l'.exe salva il token in %APPDATA%\FrameForge\token.dat: primo lancio
// chiede il token una volta, poi la GUI parte istantaneamente senza prompt.
//
// AGGIORNARE dopo ogni release: URL, SHA256, versione, data.
export const AGENT_EXE_URL = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.6.8/forgefps-agent.zip";
export const AGENT_EXE_SHA256 = "27e912ebb236ec4fed2f3453c763d6048105920200bfeec7768d9204bb0faf0c";
export const AGENT_EXE_VERSION = "v0.6.8";
export const AGENT_EXE_DATE = "2026-07-20";
export const AGENT_EXE_FORMAT = "zip"; // "zip" (onedir) | legacy: "exe" (onefile)
export const AGENT_RELEASES_URL = "https://github.com/WjRKO/ForgeFPS/releases";
export const AGENT_REPO_URL = "https://github.com/WjRKO/ForgeFPS";
export const AGENT_DEFAULT_BACKEND = "https://forgefps.dev";
