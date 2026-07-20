// URL and SHA256 pubblicati alla GitHub Release del pacchetto onedir (forgefps-agent.zip).
// Da v0.6.7 distribuiamo uno ZIP (cartella onedir) invece di un .exe onefile per
// eliminare i falsi positivi euristici di Windows Defender sul bootloader PyInstaller.
//
// AGGIORNARE dopo ogni release: URL, SHA256, versione, data.
export const AGENT_EXE_URL = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.6.7/forgefps-agent.zip";
export const AGENT_EXE_SHA256 = "66be006b08e32ef85a6f68502d069095e068e8128c7cc16a5cc85a90df39235c";
export const AGENT_EXE_VERSION = "v0.6.7";
export const AGENT_EXE_DATE = "2026-07-20";
export const AGENT_EXE_FORMAT = "zip"; // "zip" (onedir) | legacy: "exe" (onefile)
export const AGENT_RELEASES_URL = "https://github.com/WjRKO/ForgeFPS/releases";
export const AGENT_REPO_URL = "https://github.com/WjRKO/ForgeFPS";
export const AGENT_DEFAULT_BACKEND = "https://forgefps.dev";
