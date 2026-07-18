# Changelog

Tutte le modifiche significative a **FrameForge** (agent + web app).
Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — Versioning: [SemVer](https://semver.org/lang/it/).

---

## [Unreleased] — 2026-07-18

### Added
- **Pagina Guida in-app (`/guida`, `/guide` → redirect)** — 5 walkthrough step-by-step con:
  - Primo boost in 3 minuti · Setup gaming competitivo · Setup streaming OBS · Leggere il benchmark 0-100 · Se qualcosa va storto
  - Ogni step marcato con badge "Sul sito" / "Sul PC" e comando PowerShell copiabile con feedback visivo
  - TOC iniziale, sezione Tips per guida, CTA finale verso login / download agent, tempo stimato in minuti
  - Bilingue IT/EN via i18n
  - Aggiunto link "Guida" nella `MarketingNav` e route lazy in `App.js`
- **Tour interattivo di onboarding (react-joyride v3.2.0)**:
  - 8 step: Il mio PC, Advisor, Rete, Agent desktop, Giochi, Notifiche, chiusura
  - Auto-start al primo atterraggio su `/app` (localStorage flag `ff_tour_done_v1`)
  - Skippabile, personalizzato con palette FrameForge (accent `#E5FF00`, tooltip dark `#0F0F12`)
  - Pulsante "Rifammi il tour" nella pagina Account (`data-testid="restart-tour-btn"`) che azzera il flag e dispatcha evento globale `ff:tour:start`
  - Stringhe i18n IT/EN dedicate (chiave `tour.*`)
- **GUI moderna via Edge WebView (Option C)** — nuovo pannello ottimizzazioni in HTML/CSS/JS servito localmente:
  - Server HTTP locale su `127.0.0.1` con **porta random** e **session token da 48 caratteri** per ogni request
  - Lancio di `msedge.exe --app=` in modalità chromeless (finestra pulita, no barra Edge)
  - UI dark responsive con animazioni CSS, ricerca tweak, categorie a tab
  - Card interattive con Problema/Motivo/Modifica/Impatto per ogni tweak
  - Bottone "Applica" singolo per ogni tweak + preset chip (Competitivo/Streaming/Completo/Nessuno)
  - Log console live via polling (400 ms), toast di conferma, indicatore backup real-time
  - Fallback automatico a **WinForms GUI** (legacy) se Edge non installato
  - Isolation: profilo Edge dedicato in `%TEMP%\forgefps-gui\edge-profile`
- **UX "GIÀ ATTIVO" per tweak già ottimizzati**:
  - Card con barra verde e opacità ridotta (72% → 100% al hover)
  - Pill outline verde "GIÀ ATTIVO" nell'header della card
  - Pulsante "Applica" sostituito da "*Nessuna azione necessaria*"
  - Tab counter mostra `da_fare/totali` (es. `Gaming 3/10`)
  - Preset (Competitivo/Streaming/Completo) saltano automaticamente i tweak già attivi
- Workflow GitHub Actions **senza SignPath** (`agent-build/github-workflow-build-nosign.yml`) — build + release automatica dell'exe unsigned finché SignPath Foundation non è approvata.

### Fixed
- **Edge process detection**: il launcher `msedge.exe` esce subito se c'è già un'istanza Edge attiva → `-PassThru` restituiva un process già terminato → listener chiuso prima che Edge caricasse la pagina (`ERR_CONNECTION_REFUSED`). Fix: recupero del process reale via WMI `Win32_Process` filtrando per `--user-data-dir` custom.
- **Safety net inactivity timeout**: se il process Edge non è rilevabile, uscita automatica dopo 30s di inattività.
- **URL locale stampato in console** prima di lanciare Edge: se la finestra non si apre l'utente può incollare l'URL in qualunque browser.
- **Regex `stateClass`**: aggiunto pattern "nessun" per riconoscere anche stati tipo "Nessuna app in avvio".

### Changed
- Landing page — KPI "tweak reali" allineato al catalogo effettivo: **26 → 35** (IT + EN).
- `frontend/src/config/agent.js` — puntamento a release **v0.6.0**:
  - URL: `https://github.com/WjRKO/ForgeFPS/releases/download/v0.6.0/forgefps-agent.exe`
  - SHA256: `18645e38ef463cb7a1e9afff40e2194416518589be080840654b4dc9aed45a1c`
  - Data: `2026-07-18`
- Branch `optimize` del PowerShell agent — prova prima `Show-WebGui`, poi fallback a `Show-Gui` (WinForms).

### Docs
- Aggiunta guida rapida push GitHub con branch dedicato (evita "Changes conflict detected" su `main`).

---

## [0.6.0] — 2026-07-17

### Added
- **Adaptive Boost Engine** — 35 tweak si adattano dinamicamente all'hardware rilevato:
  - Rilevamento laptop vs desktop (chassis type WMI), RAM installata, tipo disco (SSD/HDD/NVMe), GPU brand (NVIDIA/AMD/Intel)
  - Ogni tweak espone un `fit` block che decide `ok`/`warn`/`skip` in base al profilo hardware (es. `nvidia_tel` skippato su GPU AMD, `sysmain` disattivato solo su SSD, `paging_exec` solo con ≥16 GB RAM)
  - Preset "Competitivo", "Streaming", "Completo" ora rispettano i vincoli hardware
- **Game Booster (opt-in, real-time)**:
  - Il PS agent monitora l'avvio di processi gioco (whitelist configurabile)
  - Quando parte un gioco: **sospende** processi non essenziali in background (Chrome, Discord update, OneDrive, ecc.) tramite `NtSuspendProcess`
  - Alla chiusura del gioco: **riprende automaticamente** tutti i processi sospesi
  - Sempre opt-in: l'utente decide dalla pagina `/games` se attivarlo per titolo (nessun automatismo)
- **Benchmark Avanzato (0-100 score)**:
  - Misura **latenza DPC** (via performance counters + timer resolution sampling)
  - **Disk IOPS reali** (test 4K random R/W su file temp)
  - **Network jitter** (100 ping su target Cloudflare)
  - **CPU responsiveness** (context switch rate)
  - Punteggio composito 0-100 con formula ponderata
  - **Spiegazione AI** dei risultati via Claude Sonnet 4.5 (endpoint `POST /api/benchmark/explain`)
- Standalone Python `.exe` (PyInstaller) aggiornato a v0.6.0 con lo stesso Adaptive Boost + Game Booster + Benchmark del PS script.
- Metadati exe (`version_info.txt`) → riduce falsi positivi AV.
- Guide: `REBUILD_v0.6.0.md`, `SIGNING_AND_TRUST.md`, `SIGNPATH_SETUP.md`, `CODE_SIGNING_POLICY.md`.

### Changed
- Frontend: pagine `Games.jsx`, `MyPc.jsx`, `DesktopAgent.jsx` aggiornate per esporre le nuove feature.
- Backend DB schema: nuove collection `prematch_settings`, `benchmarks`, `benchmark_explanations`.

---

## [0.5.x] — precedenti

- AI Advisor (Claude) per ottimizzazioni PC context-aware
- Price Tracker multi-store (Amazon, Newegg, ecc.)
- Telemetria PC live (CPU/GPU/RAM/temp)
- Health Score storico
- MFA (TOTP), RBAC, rate limiting
- Landing page marketing, sistema profili per gioco
- Report PDF (base), Report BIOS-restore
