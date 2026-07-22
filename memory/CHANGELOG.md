# FrameForge — Changelog


## Fase 3 + Fase 4 — 2026-02-22 · Benchmark contestuale & Storico visual
### Added (backend — `routers/pc.py`)
- **`GET /api/benchmarks/fleet-percentile`**: percentile del punteggio benchmark
  dell'utente vs. la flotta complessiva e vs. utenti con CPU/GPU della stessa
  famiglia. Include `delta` (before/after ultimi due run). Ritorna
  `available:false` se meno di 3 utenti nel fleet (evita percentili farlocchi).
  Helpers: `_cpu_family` / `_gpu_family` (parser euristici stringa CPU/GPU),
  `_percentile_rank`, `_bench_score`, `_bench_overall`.
- **`GET /api/benchmarks/guardrails`**: guardrail server-side (scelta utente A).
  Legge `running_apps` dall'ultimo sync e segnala giochi/streaming/recorder
  attivi che falserebbero il benchmark. Severità: `high` (blocking) per
  giochi (fortnite/valorant/cs2/…) e streaming (obs64/streamlabs/…),
  `medium` per recorder, `info` per snapshot stantìo (>10 min) o assente.
  Non blocca lato server: la UI decide se avvisare o meno.
- **`GET /api/benchmarks/history?days=30`**: serie temporale del benchmark
  (score/overall/cpu_score) capped 1..90 giorni, max 500 punti, con stats
  (min/max/avg/latest).
- **`GET /api/pc/sync-history?days=7`**: timeline di sync (fonte:
  `health_history` — ogni report hardware ne produce uno). Include
  aggregazione `by_day` per l'heatmap.
### Added (frontend)
- **`components/FleetPercentileCard.jsx`**: card con due barre — vs. tutti gli
  utenti e vs. hardware simile — e badge Δ before/after. Rende nulla se
  non ci sono abbastanza dati.
- **`components/BenchmarkSparkline.jsx`**: sparkline SVG 30gg del benchmark
  con gradient fill cyan, min/max/trend %. Fallback su `overall` per record
  vecchi che non hanno `score`.
- **`components/SyncTimeline.jsx`**: strip attività sync 7gg (heatmap
  intensità basata sul numero di sync/giorno). Tooltip con date localizzata.
- **`pages/Benchmark.jsx`**: integra i 3 nuovi componenti; `guardedLaunch`
  chiama `/benchmarks/guardrails` prima di lanciare l'agent — se rileva
  giochi/streaming mostra un `toast.warning` sonner con azione "Esegui
  comunque" (fail-open in caso di errore rete). Rimosso `ScoreSparkline`
  legacy (sostituito da `<BenchmarkSparkline>`).
- **`pages/MyPc.jsx`**: `<SyncTimeline days={7}>` sotto `<HealthHistoryCard>`.
### Tested
- Backend: 14/14 pytest passati (`test_phase34_benchmarks.py`) — auth guards,
  shape response, clamping giorni, blocking guardrail su valorant/obs64,
  running_apps injection via `/api/agent/report-specs`.
- Frontend: iteration_33 verificato — guardrail toast si mostra quando
  `running_apps=['valorant.exe']`, testid `bench-guardrail-toast` esposto.
### Design decisioni
- Scelta utente **A** — solo server-side guardrails (nessun rebuild `.exe`).
  Battery check rimandato (info non ancora catturata dall'agent).


## Fase 2 polish — 2026-02-21 · Hint browser popup one-shot
### Added
- **`<BrowserPopupHint>`** (`components/BrowserPopupHint.jsx`):
  - Piccolo banner cyan con icona info sotto i bottoni che triggerano
    `frameforge://` (Sync, Benchmark, Monitor).
  - Testo: "Prima volta? Chrome ti chiederà 'Aprire FrameForge?'. Spunta
    'Consenti sempre' e non lo vedrai più."
  - Bottone X per dismissare, stato persistito in localStorage
    (`ff_popup_hint_dismissed_v1`).
  - Traduzioni ITA/ENG via `defaultValue` (i18n keys `popup_hint.*`).
- Piazzato in `MyPc.jsx` (sotto last-sync-info), `Benchmark.jsx` (sotto
  PageHeader), `Live.jsx` (dentro pannello monitor sotto CTA).

### Verified
- Screenshot preview: hint visibile su Benchmark e Live, dismiss X funziona,
  localStorage persistente.

### Todo utente
- Redeploy per applicare a forgefps.dev (frontend-only, no rebuild).



## Fase 2 — Sync ambientale (~1.5h effort) — 2026-02-21
### Added
- **Hook `useAutoSync`** (`hooks/useAutoSync.js`):
  - Trigger 1: al primo carico, se `updated_at > 24h` -> silent sync auto
  - Trigger 2: `visibilitychange` listener, se tab torna dopo >1h idle -> silent sync
  - Cooldown 30 min tra un auto-sync e il successivo (via localStorage `ff_autosync_last_ts`)
  - Espone `{ ageSec, tier, forceSync, refresh, running }`
- **Componente `<FreshnessBadge>`** (`components/FreshnessBadge.jsx`):
  - Verde <10min, giallo 10min-24h, rosso >=24h
  - Click = force sync silent con `useAutoSync.forceSync()`
  - Piazzato nell'header globale di `Layout.jsx` -> visibile su ogni pagina
  - Format friendly: "or ora" / "45 min fa" / "21h fa" / "3gg fa"
- **Sync predittivo su hover AI Advisor** (`Layout.jsx`):
  - `onMouseEnter` sul NavLink `/app/advisor` -> se `ff_autosync_last_ts >5min`
    fa fetch `/api/agent/launch-uri?mode=sync&silent=1` + navigate URI
  - `advisorPreloaded` flag: max 1 trigger per sessione, evita spam su
    hover multipli

### Testato in preview
- Screenshot dashboard mostra badge "AGGIORNATI 21H FA" (tier warm, giallo)
- Zero console errors
- FreshnessBadge presente su tutte le rotte (Layout globale)

### Todo utente
- Redeploy produzione (solo web, no rebuild .exe)



## v0.7.1 (UX polish) — 2026-02-21 · Feedback visivo per Sincronizza ora
### Fixed
- **Utente segnalava "Sync completato ma dati non cambiano"**: il sync
  funzionava correttamente ma quando l'hardware/health erano identici al
  precedente non c'era feedback visivo tangibile, sembrava non fatto nulla.
- Aggiunto indicatore `<div data-testid="last-sync-info">` sotto il
  PageHeader con:
  - Pallino verde permanente + testo "Ultimo sync: X min fa"
  - Format friendly: "or ora" / "45s fa" / "3 min fa" / "2h fa" / data
  - **Pulse verde animato** (`animate-ping`) + testo bold "aggiornato!"
    per 5 secondi dopo un sync appena completato
- Se il sync riscrive dati identici ora l'utente vede comunque un cambio
  di UI: "21h fa" → "or ora · aggiornato!" → riflesso concreto dell'azione.
- Fix bonus preventivo in `forgefps_agent.py` v0.7.2:
  `register_frameforge_protocol` ora include `--backend "<URL>"` nel
  command del registry per preservare l'ambiente (preview vs prod). Non
  serve rilascio immediato: la produzione userebbe comunque default forgefps.dev.

### Todo utente
- Redeploy per applicare feedback visivo sul sync (frontend-only).
- v0.7.2 exe rebuild solo se in futuro vuoi testare i bottoni silent dalla
  preview URL (edge case).



## v0.7.1 (Hotfix) — 2026-02-21 · Sync silent polling: fix nome campo
### Fixed
- **Sincronizza ora non completava mai**: il polling in `MyPc.jsx` verificava
  `data.synced_at !== baseline` ma l'endpoint `/api/pc-specs` restituisce
  il campo con nome `updated_at`. Poll sempre falso → timeout dopo 60s con
  toast "app non risponde" anche quando la sync riusciva davvero.
- Fix: aggiornato `useSilentLaunch({ detectDone })` per confrontare
  `data.updated_at` (corretto) invece di `data.synced_at`.
- `baselineRef` rinominato coerentemente (`syncedAt` -> `updatedAt`).
- Verificato via screenshot: toast "Sincronizzazione in corso..." appare
  correttamente e il bottone mostra spinner. Il polling ora rileva il bump
  di `updated_at` non appena il Desktop Agent POSTa a `/api/agent/report-specs`.



## v0.7.1 (Fase 1 completa) — 2026-02-21 · Silent execution + Benchmark tab
### Added
- **Endpoint `/api/agent/launch-uri` con `silent=0|1`** — URI firmato HMAC
  retrocompatibile con v0.7.0 (firma solo `mode|ts`, silent viaggia come hint).
- **Python Agent v0.7.1** (`forgefps_agent.py`):
  - Nuova `launch_silent_mode(mode)`: PowerShell `-WindowStyle Hidden` +
    `CREATE_NO_WINDOW`. Whitelist: sync, benchmark, cleanup, optimize.
  - `parse_and_verify_uri` estrae `silent` dall'URI.
  - `__main__` intercetta `_SILENT_FROM_URI` e esce dopo lo spawn (no input()).
- **Frontend**:
  - Nuovo hook `useSilentLaunch({ mode, detectDone, ... })` con polling +
    toast + fallback "app non installata".
  - `MyPc.jsx`: bottone "Sincronizza ora" (ciano) nell'header.
  - `Live.jsx`: bottone "▶ Avvia monitor sul PC" sostituisce SecureRunBlock
    (che rimane in `<details>` come fallback power user).
- **Nuova tab "Benchmark"** (`pages/Benchmark.jsx`) affianco a Panoramica e
  Monitoraggio Live in `MyPcHub.jsx`. Route `/app/benchmark` in App.js.
  Header dedicato con bottone "Benchmark ora" (silent) + "Ricarica".
  Empty state con CTA "Esegui il primo benchmark".
- **Rilascio GitHub v0.7.1**: SHA `12ab8424e03da1fc06f1ebe37eca7d3e9f7878b0bcb759f24c0ac3b447d92e69`
  · PE FileVersion 0.7.1.0 · workflow ora usa `working-directory: agent-build`.

### Removed
- Card `BenchmarkCard` + helpers (`BENCH_METRICS`, `ScoreSparkline`) migrati
  in `pages/Benchmark.jsx` dedicato — pulita Panoramica da 300+ righe.

### Verified
- SHA download endpoint = SHA GitHub release ✅
- Bytecode compilato contiene: `AGENT_VERSION="0.7.1"`, `launch_silent_mode`,
  `Hidden`, `register_frameforge_protocol`, 11 occorrenze `silent` ✅
- Test frontend Playwright: tab Benchmark + bottoni silent presenti,
  BenchmarkCard rimossa da /app/pc, bottone Sync ancora presente ✅

### Todo utente
- Redeploy produzione (forgefps.dev) per aggiornare SHA + config frontend.



## v0.7.4 (UX cleanup) — 2026-02-21 · Consolidato Pre-match → Game Booster
### Removed
- **QuickStart hero** (2 CTA "Installa FrameForge" + "Dashboard web") sopra le
  Quick Actions in `/app/desktop`: ridondante coi bottoni sottostanti e col
  pannello sticky di destra. Ora la pagina apre direttamente sulla griglia
  6 (ora 5) di Quick Actions.
- **Bottone "Prima del match"** dalle Quick Actions: modalita' `prematch`
  faceva le stesse cose del `booster` (chiudi app, powercfg, priorita').
  Rimane come `mode` dietro le quinte per compat script Windows.
- **Wizard "auto vs manual"** e **card Pre-match** dalla pagina `/app/games`:
  eliminata la scelta perche' c'e' un solo path (Booster). Meno decisioni,
  meno frizione al primo utilizzo.
- Removed unused React state: `boostMode`, `chooseMode`, `resetMode`,
  `boostGroups`, `groups`, `showConfig`, `savingCfg`, `saveConfig`,
  `setPower`, `BOOST_MODE_KEY` (localStorage). Removed unused icons:
  `Rocket`, `Target`, `ChevronDown`, `ChevronUp`, `RotateCcw`.

### Changed — Game Booster "Personalizza cosa chiudere"
- **Prima**: 6 checkbox generiche (Browser, Chat, Media, Cloud, Launcher,
  Altro). L'utente selezionava categorie senza sapere cosa avesse in
  esecuzione davvero.
- **Adesso**: lista dinamica delle app effettivamente in esecuzione sul PC
  (da `pc_specs.running_apps` popolato dal Desktop Agent). Ogni app ha
  checkbox individuale + nome friendly (`APP_LABELS`: Chrome, Edge,
  Discord, Spotify, OneDrive, Epic Games Launcher, ecc.) + process name
  in monofont.
- Bottone "aggiorna" per rileggere lo state; placeholder se nessuna app
  rilevata ("Avvia Desktop Agent con Ottimizza o Sync per aggiornare").
- Salva su `close_apps` come lista piatta di process names (era: unione
  dei processi delle categorie ticked).
- Nuove chiavi i18n (IT/EN): `booster_no_running`, `booster_running_count`
  con plurali, `booster_will_close` con plurali, `refresh_short`.

### Files
- `frontend/src/pages/DesktopAgent.jsx`
- `frontend/src/pages/Games.jsx`
- `frontend/src/i18n.js`



## v0.7.3 (Rebuild fixed) — 2026-02-21 · Workflow CI ora usa `agent-build/`
### Fixed
- **Root cause definitivo**: `.github/workflows/build.yml` sul repo GitHub
  eseguiva PyInstaller dalla root del repo invece che da `agent-build/`.
  Il repo ha due copie storiche dei file (root + agent-build/): PyInstaller
  compilava le versioni OLD (v0.4.5.0 / v0.6.8) mentre agent-build/ conteneva
  le versioni nuove (v0.7.0).
- Fix workflow: aggiunto `working-directory: agent-build` a tutti gli step di
  build/zip/hash + path corretto `agent-build/dist/forgefps-agent.zip` nel
  release artifact.
- Aggiornato `AGENT_EXE_SHA256` in `agent.js` a
  `d524e50a323608f8994a0b1c23169c95df3079820cc5a4004350adf3011aea5c`.

### Verified (E2E)
- Estratto `forgefps_agent.pyc` dal ZIP servito da
  `/api/agent/download-zip`: contiene `AGENT_VERSION = "0.7.0"`,
  `register_frameforge_protocol`, `parse_and_verify_uri`, e le stringhe
  `frameforge://` (4 occ) + `--register-protocol`.
- PE metadata dell'exe = `FileVersion 0.7.0.0` (era 0.4.5.0).

### Todo utente
- Redeploy produzione (forgefps.dev) per aggiornare il SHA e il config.



## v0.7.2 (Backend hotfix) — 2026-02-21 · Endpoint download-zip -> v0.7.0
### Fixed
- **Root cause segnalato dall'utente**: `.\forgefps-agent.exe --register-protocol`
  apriva il menu interattivo invece di registrare il protocollo. Motivo:
  `/api/agent/download-zip` in `backend/routers/pc.py` (const `AGENT_ZIP_UPSTREAM`)
  scaricava ancora `v0.6.8`. La v0.6.8 non ha il flag `--register-protocol`
  quindi `parse_known_args` lo ignorava silenziosamente.
- Bumpato URL upstream a `v0.7.0`. Cache backend ricalcola l'hash del path
  automaticamente (nuovo file di cache, nessun cleanup manuale necessario).
- Verificato: `sha256sum(cache) == d1afd88b430427efd09064e570f7c53b196a713b768e046eb4b214f78685d898`
  (match esatto SHA della release GitHub v0.7.0).

### Fix secondario in `forgefps_agent.py`
- `--register-protocol` non deve mai bloccare sul prompt del token: se
  `token.dat` non esiste, salta il prompt e procede alla registrazione
  (scrivere in HKCU non richiede token).

### Todo utente
- Redeploy produzione (forgefps.dev) per pushare il fix upstream URL.



## v0.7.1 (Step 2 Frontend) — 2026-02-21 · Quick Actions con protocollo frameforge://
### Added
- **Griglia Quick Actions** in `DesktopAgent.jsx` con 6 bottoni colorati:
  Optimize, Live monitor, Benchmark, Pre-match, Game Booster, Restore.
- Ogni bottone chiama `GET /api/agent/launch-uri?mode=<mode>`, riceve un URI
  firmato HMAC e naviga a `window.location.href = uri` per aprire la GUI
  locale via protocollo custom `frameforge://` (v0.7.0+ dell'exe).
- Fallback UX: se la tab rimane visibile dopo 2s (`document.visibilityState`),
  toast "Non hai ancora l'app? Scarica FrameForge qui sotto" per ricordare
  di installare la v0.7.0 la prima volta.
- Anti-doppio-click: `launching` state con reset dopo 1s.
- Testid: `quick-actions`, `quick-action-{optimize,monitor,benchmark,prematch,booster,restore}`.

### Changed
- Il primo hero "Install FrameForge" ora ha copy piu' chiara ("Prima volta →
  Download the ZIP once. Registers frameforge:// on Windows") — separa il
  first-install dal daily-use.
- Hero secondario "Web dashboard" (era "Start monitoring") linka a `/app/live`
  per la telemetria via sito, distinguendo dal monitor via app locale.

### Verified
- Screenshot preview: griglia 3x2 con colori distintivi, hover states,
  responsive (2 col mobile, 3 col desktop).
- Chiamata reale HTTP 200 su `/api/agent/launch-uri?mode=optimize`
  osservata via Playwright.

### Note
- La v0.7.0 dell'exe deve essere installata dagli utenti (una tantum) prima
  che i bottoni possano aprire l'app. Se non installata, il click fallisce
  silenziosamente e appare il toast fallback.



## v0.7.0 (Frontend config) — 2026-02-21 · Bump versione + SHA256
### Changed
- `frontend/src/config/agent.js` aggiornato:
  - URL → `.../releases/download/v0.7.0/forgefps-agent.zip`
  - SHA256 → `d1afd88b430427efd09064e570f7c53b196a713b768e046eb4b214f78685d898`
  - VERSION → `v0.7.0`, DATE → `2026-02-21`
- `data/releases.json`: aggiunta entry v0.7.0 → verrà annunciata dal Discord
  release announcer al prossimo tick.
- Preview verificato via screenshot: sticky panel mostra versione, data e
  SHA corretti; il bottone "Download FrameForge" scarica dall'endpoint
  `/agent/download-zip` (che internamente pesca dal GitHub v0.7.0).

### To-do
- **Produzione**: click su "Redeploy" nella UI Emergent per pushare la
  nuova versione su forgefps.dev.
- Step 2 (frontend cleanup / nuovi bottoni "Ottimizza / Monitor / ...")
  disponibile subito dopo il redeploy.



## v0.7.0 — 2026-02-XX · Custom URL protocol `frameforge://` (Step 1)
### Added
- **Endpoint `GET /api/agent/launch-uri?mode=<mode>`** in `backend/routers/pc.py`:
  ritorna un URI firmato HMAC-SHA256 tipo `frameforge://launch?mode=optimize&ts=<epoch>&sig=<hex>`.
  Chiave HMAC = `agent_token` dell'utente (offline-verifiable dal client).
  Modes ammesse: optimize, sync, benchmark, monitor, prematch, booster, restore, gui.
  ts scade in 60s (anti-replay). Auth required (JWT cookie).
- **Registrazione protocollo Windows** in `agent-build/forgefps_agent.py` (bump v0.7.0):
  - `register_frameforge_protocol()` scrive in `HKCU\Software\Classes\frameforge`
    (no admin) e mappa a `"exe" --uri "%1"`. Idempotente.
  - Chiamata silenziosa best-effort ad ogni avvio; flag `--register-protocol`
    per repair manuale.
  - `parse_and_verify_uri()` valida HMAC + freshness locale col token in
    `%APPDATA%\FrameForge\token.dat`. Rifiuta URI di altri utenti (bad sig),
    URI vecchi (> 60s) e URI manomessi.
  - Nuovo flag `--uri "frameforge://..."`: quando il browser invoca il
    protocollo l'exe estrae la mode e apre direttamente la GUI sicura.
- **Test regressione**: `backend/tests/test_agent_launch_uri.py` (14 casi:
  auth, tutte le mode, mode invalida, verifica firma, rifiuto chiave sbagliata,
  freshness ts). Tutti PASSED.

### Notes
- Step 1 (backend + Python launcher) completo. Step 2 (frontend cleanup: nuovi
  bottoni Quick Actions + detection app installata + accordion Metodo Sicuro
  collassato) rimane da implementare dopo il rebuild dell'exe e la release GitHub.
- Version_info.txt bumpato a 0.7.0.0 per metadata dell'exe.



## v0.6.18 — 2026-02-XX · Quick Start hero su pagina Collega PC
### Added
- **Hero band con due CTA prominenti** in cima a `/app/desktop`
  (`DesktopAgent.jsx`): visibile al primo utente senza scroll o accordion:
  - **01 · Collega il tuo PC** (ciano): scarica lo ZIP personalizzato.
  - **02 · Avvia monitoraggio** (giallo): naviga a `/app/live` per la telemetria.
- Estratta la logica di download in `handleDownloadZip` per riuso tra hero
  e sticky panel di destra.
- Testid: `quickstart-hero`, `quickstart-connect-btn`, `quickstart-monitor-btn`.
- Verificato via screenshot preview: hero renderizza correttamente sopra il
  banner "Important: which server" senza rompere il layout esistente.



## v0.6.17 — 2026-02-XX · Fix caratteri glitchati nella GUI Desktop
### Fixed
- **UTF-8 BOM su `/api/agent/script`**: Windows PowerShell 5.1 (default su Win10/11)
  legge i file `.ps1` senza BOM usando il codepage ANSI di sistema (Windows-1252),
  causando mojibake per caratteri UTF-8 come `📚 👤 · …` presenti nella sezione
  Profili e nei toast Sync Cloud dell'Edge WebView GUI.
- Fix: prepend `\ufeff` (BOM UTF-8, bytes `EF BB BF`) alla `PlainTextResponse`
  di `/api/agent/script` + `media_type="text/plain; charset=utf-8"`.
- `/api/agent/script-info` allineato: SHA256 calcolato sui bytes BOM-inclusi
  per non rompere l'integrity check lato client.
- File: `backend/routers/pc.py` (agent_script + agent_script_info).
- Verificato via curl: risposta ora inizia con `EF BB BF` + 168288 byte di script.



## v0.6.16 — 2026-07-20 · Endpoint admin skip-annuncio release
### Added
- **`POST /api/admin/releases/mark-announced`** (auth admin): accetta
  `{"versions": ["x.y.z", ...]}` e inserisce le entries in `db.announced_releases`
  con `source: "admin_skip"` senza chiamare Discord. Idempotente: entries gia'
  presenti finiscono in `already_announced`. Uso: dopo aggiunta massiva di release
  al manifest, marchi le vecchie come "gia' annunciate" per evitare 6 embed in fila
  sul canale changelog al primo redeploy.
- Validazione: body vuoto o `versions` non-list ritorna 400. Entries non-string
  vengono ignorate (isinstance check).

### Verified
- iteration_32.json: 8/8 acceptance criteria PASS. Auth (401/403), idempotenza,
  validation, DB side-effect (source=admin_skip), integration con
  `announce_new_releases()` monkeypatched (dopo mark di 5 versioni, posta solo
  la 6a rimasta).
- Minor issue fixato post-test: isinstance(v, str) invece di str(v).strip() per
  evitare coercion di None/numeri a stringhe.

### Files touched
- `backend/routers/admin.py` (+ nuovo endpoint)

---

## v0.6.15 — 2026-07-20 · Fix Discord #changelog auto-announcer
### Fixed
- **`/app/data/releases.json`**: il manifest si fermava a v0.6.5. Aggiunte le 6 versioni
  user-facing pubblicate da allora: 0.6.6 (cross-device notifications), 0.6.7 (report PDF
  con grafico Health Score), 0.6.8 (build --onedir contro falsi positivi AV), 0.6.10 (ZIP
  personalizzato + token persistente), 0.6.13 (fix ZIP troncato), 0.6.14 (fix Coach EN +
  UX credito LLM).
- Il release_announcer al prossimo boot backend PROD posta i 6 embed mancanti sul canale
  Discord `#changelog-automatico` (idempotente via `db.announced_releases`).

### Verified
- iteration_31.json: 6/6 acceptance criteria. Manifest 12 versioni, announce_new_releases()
  posta 6 al primo run e 0 al secondo. announce_release_by_version force-re-announce OK.

### Files touched
- `/app/data/releases.json` (+6 entries)

---

## v0.6.14 — 2026-07-20 · Bug fixes multipli + UX budget LLM
### Fixed
- **QR Desktop GUI non si generava** (`ps_agent.py`): `Invoke-RestMethod` su
  Content-Type `image/svg+xml` auto-parsava il body come XML object perdendo il
  markup. Switch a `Invoke-WebRequest -UseBasicParsing` con `.RawContentStream.ToArray()`
  per proxare i bytes SVG intatti. **Richiede rebuild .exe v0.6.9** per l'utente finale.
- **AI Coach default rispondeva solo in italiano** (`ai_engine.stream_advisor`): il
  blocco `[CONTESTO PC DELL'UTENTE ...]` iniettato nel system prompt era hardcoded
  in italiano anche con `lang='en'`. Le istruzioni miste (system EN + contesto IT)
  confondevano Claude che fallback in italiano. Ora bilingue: `[USER PC CONTEXT ...]`
  in inglese quando `lang='en'`, headers 'User' / 'New message' bilingue.
- **UX budget LLM esaurito** (`routers/pc.py` fps_estimate + startup_analyze): quando
  il budget Emergent Universal Key e' scaduto, LiteLLM ritorna un errore tecnico che
  causava un Cloudflare 502 grezzo sulla pagina Gaming. Ora intercettiamo
  `"Budget ... exceeded"` e ritorniamo HTTP 402 con detail user-friendly
  "Credito LLM esaurito. Ricarica da Profilo -> Universal Key -> Add Balance."

### Verified
- Testing agent iteration_30.json: **7/7 PASS**.
- prompt bilingue verificato via monkeypatched build_chat.
- QR fix testabile solo su Windows (utente lo verifichera' dopo rebuild v0.6.9).

### Files touched
- `backend/ps_agent.py` (Invoke-WebRequest per SVG QR)
- `backend/ai_engine.py` (stream_advisor bilingue)
- `backend/routers/pc.py` (402 friendly per budget)

---

## v0.6.13 — 2026-07-20 · Fix ZIP troncato al download (Cloudflare/ingress)
### Fixed
- **`routers/pc.py:agent_download_zip`**: `StreamingResponse(BytesIO(...))` → `Response(content=payload,
  headers={"Content-Length": str(len(payload)), ...})`.
- **Root cause**: `StreamingResponse` con BytesIO senza `Content-Length` header esplicito veniva
  troncato dal reverse-proxy in mezzo (Cloudflare/ingress). L'utente riceveva ~2.8 MB dei 9.1 MB
  attesi e 7-Zip segnalava "Fine dei dati inattesa" con corruzione di `_ssl.pyd`.
- **Fix verificato dal testing agent** (iteration_29.json, 4/4 PASS): Content-Length header
  9128837 bytes esatti, `zipfile.testzip()` = None (integro), 60 entries + Avvia-FrameForge.bat,
  `_ssl.pyd` legge 179432 bytes puliti.

### Files touched
- `backend/routers/pc.py`

---

## v0.6.12 — 2026-07-20 · Backlog Code Quality (auth split + component split + hook cleanup)
### Backend
- **`auth.py` refactor** (474 → 363 righe, −23%). Estratti in file separati mantenendo API contract 100% identico (path, payload, cookies, status codes, rate-limits invariati):
  - **`auth_magic.py`** (nuovo, 101 righe): magic-link create/consume/status
  - **`auth_mfa.py`** (nuovo, 56 righe): mfa/status/setup/enable/disable
  - Router principale invariato (`build_auth_router(db)` è sempre l'entrypoint pubblico chiamato da server.py)
- **Fix pre-esistente: brute-force lockout via ingress** (auth.py:214-219). Login ora legge `X-Forwarded-For` prima di fallback a `request.client.host`, così replicas dietro ingress non hanno IP diversi che vanificano il lockout. Verificato: 5×401 → 6°=429.
- Testato via testing agent: 15/16 test PASS, l'unico "issue" era il lockout pre-esistente ora fixato.

### Frontend Hook Cleanup
- Analisi ESLint (`react-hooks/exhaustive-deps`) sull'intero `src/`: solo 6 warning reali (non 68 come reported). Fixati tutti:
  - `Account.jsx:214`: aggiunta eslint-disable comment esplicito con motivazione (mount-only redirect handler)
  - Rimosse 5 direttive `eslint-disable-next-line react-hooks/exhaustive-deps` OBSOLETE da `Dashboard.jsx:646`, `Games.jsx:89`, `Live.jsx:63,92`, `Profiles.jsx:46` (ESLint le segnalava come "unused" — il codice era già stato corretto in refactor precedenti)
- Build ora 0 warning React.

### Frontend Component Split
- **`DiagnosePanel.jsx` 503 → 295 righe (−41%)**. Estratti:
  - `DiagnoseHeader.jsx` (89 righe): header collapsible + timestamp + outcome badge + close button
  - `DiagnoseAction.jsx` (116 righe): singola action row con verify block + save + apply + feedback thumbs
- **`Games.jsx`** (434 righe) e **`MobileHandoffModal.jsx`** (177 righe): valutati, split ulteriore frammenterebbe logica coesa senza reale beneficio. Sub-componenti già in-file, entrambi sotto threshold critici.

### Verified
- Tutti gli endpoint auth rispondono identici al pre-refactor (login, /me, mfa/status, magic-link cycle, consume-magic con UA parsing, magic-status pre/post consume).
- Frontend build: `yarn build` completa senza warning.
- Smoke test Playwright: 7 pagine (Dashboard/Desktop/Games/MyPc/Advisor/Upgrade/Admin) caricano correttamente.

### Files touched
- `backend/auth.py` (refactor + brute-force fix)
- `backend/auth_magic.py` (nuovo)
- `backend/auth_mfa.py` (nuovo)
- `frontend/src/pages/Account.jsx` (eslint comment)
- `frontend/src/pages/Dashboard.jsx`, `Games.jsx`, `Live.jsx`, `Profiles.jsx` (removed unused eslint-disable)
- `frontend/src/components/DiagnosePanel.jsx` (slim)
- `frontend/src/components/DiagnoseHeader.jsx` (nuovo)
- `frontend/src/components/DiagnoseAction.jsx` (nuovo)

---

## v0.6.11 — 2026-07-20 · Code Quality Sweep
### Fixed
- **`routers/pc.py:43`**: `hashlib.md5(...)` → `hashlib.sha256(...)` per il nome del file di cache
  del ZIP agent. Non era usato in modo crypto-sensitive (solo naming determin.), ma migra a
  algoritmo moderno. Vecchia cache `/tmp/forgefps-agent-cache-*` invalidata al restart.
- **`agent-build/forgefps_agent.py:861`**: `os.system("cls")` → `subprocess.run(["cmd","/c","cls"])`.
  Zero rischio di shell injection nel caso originale (stringa statica), ma allinea a best practice.
- **`Advisor.jsx:83`, `Admin.jsx:29-30`, `BuildGenerator.jsx:70`**: aggiunti `console.warn` nei
  catch precedentemente vuoti dove il debug e' utile (load sessions/stats/users/builds).
- **React key stabili invece di array index**:
  - `Games.jsx:272,354,399`: session_id/game name/preset name
  - `MyPc.jsx:330,396`: check.id / startup.item.name
  - `Upgrade.jsx:93,142`: category-index composite / preset name
  Migliora riconciliazione React quando le liste cambiano ordine.

### Investigated as false positive (NO changes)
- `ps_agent.py:1878` "hardcoded secret" → e' il placeholder JS `const TOKEN = "__TOKEN__"` che
  PowerShell sostituisce a runtime con `$sessionToken` locale univoco per l'utente. Nessun
  segreto nel codice sorgente.
- `i18n.js:298, :846` "API keys" → traduzioni UI per il modulo auth (labels come "Password",
  "Email"). Il tool ha matchato le parole chiave "auth"/"password" nella stringa.
- `MyPc.jsx:84` SVG circles key={i} → lista fissa di N punti grafico che non si riordina mai;
  index e' il key semanticamente corretto.

### Skipped (require dedicated planning, on backlog)
- `auth.py:175` build_auth_router complexity 51: refactoring auth richiede
  `integration_playbook_expert_v2` per policy interna. Da fare in sprint dedicato.
- 68 hook dependencies missing: molti sono pattern intenzionali (api client stabile). Fix
  automatico rischia infinite render loops. Da valutare caso per caso.
- Component size (Games.jsx 415 righe, DiagnosePanel 244 righe): refactoring senza cambio
  funzionale, basso ROI in questa fase.
- Type hints backend: nice-to-have.

### Files touched
- `backend/routers/pc.py`
- `agent-build/forgefps_agent.py`
- `frontend/src/pages/Advisor.jsx`, `Admin.jsx`, `BuildGenerator.jsx`
- `frontend/src/pages/Games.jsx`, `MyPc.jsx`, `Upgrade.jsx`

---

## v0.6.10 — 2026-07-20 · ZIP personalizzato + token persistente (`.exe` v0.6.8)
### Added — Part A (backend + frontend, live subito)
- **Backend `routers/pc.py`**:
  - `_render_launcher_bat(token, backend, standalone)`: helper condiviso per generare
    launcher `.bat` con token pre-compilato.
  - `_ensure_agent_zip_cached()`: fetch una tantum del ZIP generico da GitHub, cache in
    `/tmp/forgefps-agent-cache-<hash>.zip` (invalidata se corrotta).
  - Nuovo endpoint `GET /api/agent/download-zip` (auth JWT): apre il ZIP cache in memoria,
    inietta `forgefps-agent/Avvia-FrameForge.bat` con token e backend URL dell'utente, e lo
    restituisce come `application/zip` (~9.1 MB). ~3s primo hit, ~2.8s cachato.
- **Frontend `DesktopAgent.jsx`**: bottone principale non punta più a GitHub, ma fa richiesta
  autenticata a `/agent/download-zip`. Rimosso il secondo bottone `.bat`. Nuovo copy:
  "ZIP has your token baked in: extract, open the folder and double-click Avvia-FrameForge.bat".
- **`Guide.jsx`**: primo step di quick-start aggiornato per riflettere il nuovo flusso "un
  download, un doppio-click" (niente più PowerShell manuale).

### Added — Part B (client-side .exe, richiede rebuild v0.6.8)
- **`agent-build/forgefps_agent.py` (v0.6.8)**:
  - Nuove funzioni `_token_store_path`, `_load_saved_token`, `_save_token`, `_forget_saved_token`.
  - Alla prima esecuzione senza `--token`, chiede il token una volta e lo salva in
    `%APPDATA%\FrameForge\token.dat` (per-utente NTFS, no ACL manuali).
  - Alle esecuzioni successive: token letto da disco, GUI parte istantaneamente.
  - Se il token viene passato via CLI e differisce da quello salvato, il file viene aggiornato:
    così anche il doppio-click diretto sull'.exe funziona subito dopo il primo lancio.

### UX flow
Prima: scarica → estrai → apri terminale → incolla comando con token.
Adesso: **scarica il ZIP dal tuo account → estrai → doppio-click su `Avvia-FrameForge.bat` → GUI parte**.

### Post-deploy TODO utente (per Part B)
Rebuild + release v0.6.8 su GitHub:
1. Copia il file aggiornato `forgefps_agent.py` in root del repo pubblico ForgeFPS
2. Bump `AGENT_VERSION = "0.6.8"` gia' presente
3. Crea tag `v0.6.8` (browser: https://github.com/WjRKO/ForgeFPS/releases/new)
4. Aspetta workflow build verde
5. Aggiorna `AGENT_ZIP_UPSTREAM` in backend/routers/pc.py + `AGENT_EXE_URL` e `AGENT_EXE_SHA256`
   in frontend/src/config/agent.js con la nuova versione.

### Files touched
- `backend/routers/pc.py` (+ ~85 righe: helpers + 2 nuovi endpoint)
- `frontend/src/pages/DesktopAgent.jsx` (refactor bottone download)
- `frontend/src/pages/Guide.jsx` (step 2-3 quick-start)
- `agent-build/forgefps_agent.py` (+ ~55 righe token storage, bump 0.6.0 -> 0.6.8)

---

## v0.6.9 — 2026-07-20 · Launcher `.bat` per-utente (GUI in un click)
### Added
- **Backend `routers/pc.py`**: nuovo endpoint `GET /api/agent/launcher-bat` (auth JWT cookie).
  Ritorna un piccolo file Windows batch con il token dell'utente pre-compilato e la logica
  di auto-lancio della GUI sicura dentro la cartella `forgefps-agent/` estratta.
  Content-Disposition: attachment con filename `forgefps-launcher.bat`.
- **`DesktopAgent.jsx`**: secondo bottone "SCARICA LAUNCHER (BAT)" sotto quello del ZIP,
  con etichetta "Doppio-click = GUI istantanea, zero token da incollare".

### Why
Il .exe distribuito sul repo pubblico GitHub è un binario **generico** condiviso da tutti gli
utenti: non può contenere il token privato di ciascuno. Prima l'utente doveva incollare il
token a mano ad ogni avvio. Ora scarica una-tantum un `.bat` da 200 byte con il proprio
token, lo mette accanto al ZIP estratto, e la GUI parte senza prompt.

### Sicurezza
- Il `.bat` è protetto dietro autenticazione (endpoint chiede JWT valido).
- Il token dentro il file coincide con quello mostrato in chiaro nella pagina "Collega il PC",
  quindi non aggiunge nuovi vettori di attacco.
- L'utente può revocare il token in qualsiasi momento dalle Impostazioni → il `.bat` scaricato
  smetterà di funzionare all'istante.

### Files touched
- `backend/routers/pc.py` (+ ~35 righe)
- `frontend/src/pages/DesktopAgent.jsx` (+ ~25 righe, nuovo bottone + label)

---

## v0.6.8 — 2026-07-20 · Build `--onedir` (fix falsi positivi AV)
### Changed
- **`agent-build/build.bat` + `build.ps1`**: PyInstaller `--onefile` → **`--onedir`**, poi
  `Compress-Archive` in `forgefps-agent.zip`. Output finale: cartella locale + ZIP + SHA256 stampato.
- **`agent-build/github-workflow-build-nosign.yml`**: build onedir + zip step + SHA256 sul ZIP.
- **`agent-build/github-workflow-build-sign.yml`**: firma solo `.exe` interno via SignPath, poi
  ricomprimi in ZIP e pubblica.
- **`frontend/src/config/agent.js`**: URL → `.../forgefps-agent.zip`, versione `v0.6.7`, campo
  `AGENT_EXE_FORMAT="zip"`.
- **`DesktopAgent.jsx`**: label bottone "Scarica FrameForge (ZIP)", istruzioni "estrai lo ZIP →
  entra nella cartella → doppio click", nota antivirus riscritta ("niente più falsi positivi
  euristici come nelle build --onefile precedenti").
- **`Guide.jsx`**: primo step di quick-start aggiornato con "estrai lo ZIP → apri PowerShell nella
  cartella".

### Added
- **`agent-build/VENDOR_FALSE_POSITIVE.md`**: testi standardizzati pronti da inviare per
  segnalare falsi positivi a Microsoft (WDSI), Kaspersky, Bitdefender, Norton, ESET. Include
  timeline attesa (1-7 giorni per vendor).
- **`agent-build/REBUILD_v0.6.7.md`**: procedura completa build + test + pubblicazione release.

### Verified
- Smoke test frontend `/app/desktop`: badge, URL, label bottone, istruzioni tutte aggiornate.

### Post-deploy TODO utente
Dopo aver eseguito la build su Windows e caricato il ZIP sulla GitHub Release v0.6.7:
1. Copia lo SHA256 stampato a video.
2. Aggiorna `AGENT_EXE_SHA256` in `/app/frontend/src/config/agent.js`.
3. Redeploy del frontend.

---

## v0.6.7 — 2026-07-20 · Report PDF con grafico Health Score
### Added
- **`Report.jsx` `exportPdf`**: fetch parallelo di `/api/health-history` insieme a `html-to-image` + `jspdf`.
- **Nuova funzione `renderHealthChart(points, {title, empty})`**: pure Canvas 2D (1400x520), disegna:
  - background nero con radial-glow accent giallo, titolo "Health Score — ultimi 90 giorni"
  - griglia orizzontale 0/20/40/60/80/100
  - area-fill sotto la linea (gradient giallo → trasparente)
  - linea principale gialla accent con punti evidenziati
  - box badge sull'ultimo punto con `{score}/100`
  - date labels (dd/mm) su asse X per primo/mid/ultimo punto
  - Fallback: se la history è vuota, mostra "Nessuno storico disponibile"
- **Layout PDF**: aggiunta pagina extra se il grafico non entra sotto la card; footer disegnato su ogni pagina.
- **i18n**: nuove chiavi `pdf_chart_title` e `pdf_chart_empty` per IT/EN.

### Tested
- Playwright end-to-end: seed 30 punti `health_history` → export PDF → renderizzato in PNG con PyMuPDF: chart presente con dati corretti, badge "88/100" sull'ultimo punto, date labels 21/06 → 20/07.
- Caso vuoto (0 punti): fallback empty renderizzato correttamente.

### Files touched
- `frontend/src/pages/Report.jsx` (+ ~110 righe)

---

## v0.6.6 — 2026-07-20 · Cross-device Magic Link Notification + Desktop GUI QR
### Added
- **Backend `auth.py`**
  - `_parse_device_label(ua)` helper: parsa User-Agent → label breve (Android/iPhone/iPad/Windows/Mac/Linux/Tablet Android).
  - `POST /api/auth/consume-magic`: ora salva `device_ua` e `device_label` sul record `magic_tokens`.
  - `GET /api/auth/magic-status/{token}` (pubblico, no auth): ritorna `{used, used_at, device_label, expired}`. Usato dal polling del web-modal e della GUI desktop per rilevare il consumo cross-device senza esporre l'identità utente.
- **Backend `routers/pc.py`**
  - `POST /api/agent/magic-link` (auth `X-Agent-Token`): la GUI desktop può generare un magic link senza cookie utente. Rate-limitato a 5/h per user (condivide contatore con endpoint web).
  - `GET /api/agent/magic-qr?token=X` (auth `X-Agent-Token`): ritorna SVG del QR generato server-side (evita di embeddare un QR generator in PowerShell).
- **Frontend `MobileHandoffModal.jsx`**
  - Polling ogni 2s su `magic-status`: appena `used=true` mostra pannello "Device connesso — <label>", toast `sonner` "Nuovo device connesso: <label>", e auto-chiude il modal dopo 2.2s.
  - Fix race-condition: l'auto-close vive in un `useEffect` separato keyed su `state === 'consumed'` (il vecchio setTimeout dentro il polling effect veniva cancellato dalla cleanup di React).
- **Desktop GUI `ps_agent.py`**
  - Nuovo bottone `[📞 Continua sul Telefono]` nell'header della GUI (colore accent, `data-testid="mobile-handoff-btn"`).
  - Nuovo modal HTML/CSS/JS in-page: overlay + QR SVG (fetched via `/api/mobile-handoff/qr`) + countdown 5:00 + Rigenera + stato "Device connesso" + auto-close.
  - 4 endpoint locali PowerShell proxied al cloud:
    - `POST /api/mobile-handoff/generate` → cloud `/api/agent/magic-link`
    - `GET  /api/mobile-handoff/qr` → cloud `/api/agent/magic-qr`
    - `GET  /api/mobile-handoff/status` → cloud `/api/auth/magic-status`
    - `POST /api/mobile-handoff/notify` → fire local `Show-DeviceToast`
  - Nuova funzione PowerShell `Show-DeviceToast($device)`: mostra una **notifica nativa Windows** (preferisce BurntToast, fallback `NotifyIcon` tray balloon). Gira in background job per non bloccare l'HTTP handler.

### Tested
- `iteration_26.json`: 17/17 backend tests PASS (serial). Rate-limit, auth, device parsing (Android/iPhone/Windows/Mac/vuoto), single-use enforcement, 401 su token cross-user o mancante.
- Frontend end-to-end via Playwright: apertura modal, QR render, polling detect, toast, pannello "consumed", auto-close entro 5s totali.

### Files touched
- `backend/auth.py`, `backend/routers/pc.py`, `backend/ps_agent.py` (~200 righe di HTML/CSS/JS/PowerShell aggiunte)
- `frontend/src/components/MobileHandoffModal.jsx`
- `backend/tests/test_magic_link_mobile_handoff.py` (nuovo, dal testing agent)

---

## Historical
Precedenti release documentate in `PRD.md`.

## Monitor lifecycle A+E — 2026-02-22 · Pre-flight & Live REC control
### Added
- **Backend** (`routers/pc.py`):
  - `POST /api/monitor/stop` (auth) — set stop_requested=true in db.monitor_control
  - `POST /api/monitor/reset` (auth) — clear stop flag before new session
  - `GET /api/monitor/state` (auth) — expose current flag + timestamps
  - Modified `POST /api/agent/telemetry` — now returns `{ok, stop}`; agent reads `stop` and breaks the monitor loop cleanly.
- **Agent** (`ps_agent.py`):
  - `Send-Telemetry` returns `$true` when backend signals stop
  - Monitor loop (`MODE=monitor`) checks the return value each tick and exits cleanly with a Say('Stop richiesto dal browser') message. **No .exe rebuild needed** — the .ps1 script is fetched fresh on every launch via `/api/agent/script`.
- **Frontend**:
  - `components/MonitorPreflight.jsx` — modal with 4 checks (agent, game detected, background apps, alerts enabled). Reads /prematch + /alerts. Non-blocking (bad→disable proceed, warn→proceed with note).
  - `components/MonitorLiveControl.jsx` — REC panel with pulsing badge, live duration, sample count, current game, Stop + Copia URI buttons. Hydrates stopPending from `/monitor/state` on mount.
  - `pages/Live.jsx` — replaces the launch button with preflight modal trigger + swap to LiveControl panel when data.live=true.
### Tested
- iteration_34.json — backend 9/9 pytest, frontend E2E happy path 100%.


## Cleanup — 2026-02-22 · Dead code removal
### Removed
- `frontend/src/hooks/use-toast.js` (shadcn toast, mai renderizzato — l'app usa `sonner`)
- `frontend/src/components/ui/toaster.jsx` (idem, componente non montato)
- `hud.jsx` exports inutilizzati: `StatCard`, `SkeletonRow`, `PageContainer`, `DataMetric` (160 → 118 LOC)
- `agent-build/REBUILD_v0.6.0.md`, `REBUILD_v0.6.7.md` → spostati in `agent-build/archive/`
### Moved
- `pages/SessionSummary.jsx` → `components/SessionSummary.jsx` (era un componente, non una pagina; importato da Live.jsx). Aggiornato l'import path.
### Verified
- Frontend compila pulito, 4 route (`/app`, `/app/live`, `/app/pc`, `/app/benchmark`) navigano senza errori console.


## Content refresh — 2026-02-22 · Testi & Changelog pubblico
### Changed
- `i18n.js` (IT+EN): `f_agent_long` — sostituito "pre-match mode" con "booster automatico che rileva i giochi in esecuzione" / "auto-booster that detects running games" (feature era stata rimossa nella scorsa iterazione).
- `DesktopAgent.jsx`: rimossa entry `prematch` da `RUN_MODES` (menu Quick Actions puntava a una modalità inesistente).
### Removed (dead i18n keys, mai renderizzate)
- `guide.prematch_title`, `guide.prematch_desc`, `guide.step_prematch`, `guide.python_title`, `guide.python_desc` (IT + EN)
### Added — pages/Changelog.jsx (contenuto pubblico)
- Nuove entry release: **v0.6.7** (bundle onedir), **v0.6.8** (token persistente), **v0.7.0** (protocollo frameforge://), **v0.7.1** (silent mode + --backend), **v0.7.2 web+agent** (Fase 3 percentile, Fase 4 storico, monitor lifecycle, guardrails, ambient sync v2, UTF-8 BOM fix).
- ROADMAP aggiornata: "--onedir build" spostata in Done, aggiunti "Bottleneck detector real-time" (in progress) e "Storico sessioni gaming" (planned).
### Verified
- Compile pulito, `/changelog` renderizza 6 versioni + roadmap; nessun console error.


## GUI locale v2.5 (P0+P1) — 2026-02-22 · Redesign completo
### Aggiunti (ps_agent.py, sezione HTML/CSS/JS)
- **A. Density toggle** Compatto/Dettagliato (persistente in localStorage, shortcut "D")
- **B. Impact meter** ●●●●● (5 step) parsando `+3-8% FPS`, `meno stutter`, ecc.
- **C. Preset preview** su hover: mostra "N tweak, +X% FPS, Y riavvii" ed evidenzia le card che verrebbero applicate
- **D. Icone al posto delle label** Problema/Motivo/Modifica/Impatto (⚠️/ℹ️/⚙️/📈)
- **E. Semaforo unico** = bordo card colorato (verde=applicato, giallo=consigliato, arancione=caution, grigio=skip)
- **F. Progress ring** SVG animato nell'header (%, "3/6 ottimizzato · Buona strada")
- **G. Search hero** larga con icona 🔍 e badge `Ctrl+K` shortcut
- **H. Filter chips**: Consigliati · No riavvio · Reversibili · Cautela · Da applicare (combinabili)
- **I. Sort dropdown**: Impatto | Categoria | Nome | Da fare per primi
- **J. Summary strip** in bottom bar: `5 selezionati · +12% FPS · 2 riavvii · Backup ON` + bottone Apply disabilitato quando 0
- **K. Big toast post-apply** con azione "Riavvia ora / Più tardi" + pulse verde sulla card applicata
- Bonus: **time pill** ⏱ ~2s / 🔄 riavvio su ogni card
- Bonus: keyboard shortcut `D` per toggle density
### Testato
- Smoke test HTML statico con dati mock in Playwright: tutti i data-testid resi, zero errori JS, preset preview funzionante.


## UX consistency P0+P1 — 2026-02-22 · Menu ristrutturato + terminologia
### Changed
- **Menu sidebar ristrutturato** (`components/Layout.jsx`):
  - PRIMARY (5 voci): Dashboard · Il mio PC · AI Advisor · Gaming · Prezzi & Tracker
  - Sezione **SHOPPING**: Consiglia Build · Upgrade & FPS
  - Sezione **STRUMENTI** (nuova): FrameForge Agent · Report PDF · Comandi · Rete · BIOS
  - Admin resta separato
- **Terminologia unificata** (`i18n.js`, IT+EN):
  - "Desktop Agent" → **"FrameForge Agent"** (32 occorrenze bulk replace)
  - "Collega il PC" (menu) → "FrameForge Agent"
  - "Prezzi" → "Prezzi & Tracker"
  - "Report Prima/Dopo" → "Report PDF"
  - "Rete & Bufferbloat" → "Rete"
  - "BIOS & Ripristino" → "BIOS"
  - "Comandi Utili" → "Comandi"
- **Landing**: `f_agent_t` "Desktop Agent" → "FrameForge Agent" (IT+EN)
### Added
- **3 bottoni canonici** in `components/hud.jsx`: `<PrimaryButton>`, `<SecondaryButton>`, `<GhostButton>` (per uniformare CTA in tutte le pagine)
- **Sezione "Strumenti"** in i18n con label `section.tools: Strumenti / Tools`
- **Bottone Mobile Handoff** persistente nell'header (`Layout.jsx`): icona telefono + label "Telefono" (nascosta su mobile). Al click apre il modal QR handoff su qualsiasi pagina, non solo Dashboard.
### Verified
- Compile pulito, menu renders correttamente, modal handoff si apre al click, terminologia unificata.
- OnboardingTour + FreshnessBadge già presenti nel Layout, non toccati.


## UX P1 batch — 2026-02-22 · Killer features + tooltip + banner contestuali
### Added
- **`components/BottleneckDetector.jsx`**: real-time bottleneck classifier che poll `/api/pc-telemetry` ogni 4s. Classifica: CPU-BOUND / GPU-BOUND / RAM SATURATED / BALANCED / IDLE / MIXED. Copy contestuale per ogni caso ("Chiudi Chrome/Discord per liberare thread"). **Chiude il gap della hero landing "trova i colli di bottiglia"**. Integrato in `Live.jsx` quando data.live=true.
- **`components/NextActionBanner.jsx`**: banner contestuale dopo azioni chiave. Presets: `no-hw` (no PC connesso → installa Agent), `post-sync` (sync OK → chiedi Advisor), `post-apply` (tweak applicati → fai benchmark), `post-benchmark` (bench OK → vedi confronto). Dismiss persistente 24h in localStorage. Integrato in Dashboard.jsx (no-hw / post-sync) e Benchmark.jsx (post-benchmark).
- **`components/TechTerm.jsx`**: tooltip glossario per termini tecnici. Dizionario IT+EN con 12 entry (bufferbloat, MPO, HAGS, MSI mode, MMCSS, ULPS, hiberfil, DPI, DWM, ping, jitter, frametime). Icona `HelpCircle` cyan + underline dashed. Usa shadcn Tooltip. Applicato a Network.jsx (bufferbloat + jitter).
- **i18n.js**: nuovi namespace `bottleneck.*` (14 chiavi) e `nba.*` (10 chiavi) in IT + EN, per evitare mixed-language UX.
### Fixed
- BottleneckDetector: rinominati testid dei chip interni da `bottleneck-{kind}` a `bottleneck-chip-{kind}` per eliminare collisione con il container (segnalato da testing agent iteration_35).
### Tested
- iteration_35: 80% pass, tutte le feature core verificate. Bottleneck detector switch CPU-BOUND ↔ GPU-BOUND in real-time confermato. Menu ristrutturato in IT verificato. Mobile handoff modal si apre. `nba-post-benchmark` renders correttamente sopra FleetPercentileCard.
### Deferred
- Migrazione bulk dei bottoni esistenti a `<PrimaryButton>/<SecondaryButton>/<GhostButton>` — troppo pervasiva (20+ pagine), farla iterativamente su nuovo lavoro.
- Fix i18n language init (bug pre-esistente: `localStorage.i18nextLng=it` non applicato al primo render).
- Route `/app/pc/live` → `/app/live` (già è `/app/live`, testing doc era outdated).


## Button migration P1 — 2026-02-22 · Dashboard + hud SSOT
### Added (hud.jsx)
- **`BTN_CLASSES`** exported constants — single source of truth per gli stili bottone:
  - `primary`, `secondary`, `ghost` (varianti size medium)
  - `primaryMono`, `secondaryMono`, `ghostMono` (HUD uppercase mono per header/eyebrow)
- `PrimaryButton`, `SecondaryButton` ora usano `BTN_CLASSES.primary/secondary` internamente (no duplicate strings).
### Refactored (pages/Dashboard.jsx)
- CTA "Collega il PC" empty state: da inline className a `BTN_CLASSES.primaryMono`
- CTA "Bench empty" da inline className a `BTN_CLASSES.secondaryMono`
- **Rimosso Mobile Handoff duplicato dal body** (era ridondante ora che il bottone è nell'header globale via `Layout.jsx`). Rimossi import `MobileHandoffModal`, `Smartphone`, state `mobileOpen`.
### Deferred
- Migrazione bottoni sulle altre pagine (Tracker, Games, Live, Advisor…) - approccio incrementale, page-by-page, per limitare superficie di rischio.


## UX polish batch — 2026-02-22 · i18n + Network glossary
### Fixed
- **i18n language detection**: precedentemente `localStorage.i18nextLng=it` non veniva onorato al primo login perché il detector cerca la chiave custom `boostpc_lang`. Aggiunto backfill al boot (`i18n.js`): se `i18nextLng` esiste e `boostpc_lang` no, lo copia. Aggiunto anche listener `languageChanged` che sincronizza `i18nextLng` all'evento switch — così tool esterni (testing agent, script) leggono sempre il valore corretto.
### Added
- **Network empty state**: nuova sezione "Cosa misureremo" con `<TechTerm>` tooltip per Bufferbloat, Ping, Jitter — il glossario è ora discoverable anche prima del primo test (feedback da iteration_35).
### Deferred (button migration)
- Migrazione bulk dei bottoni sulle pagine Tracker/Games/Live/Advisor/BIOS ecc.: sospesa dopo analisi. Le pagine usano ~5+ varianti di stile bottone (`btn-volt`, `bg-[#E5FF00] font-bold` con padding vario, `border-[#E5FF00]/50`, `text-[#5865F2]` per Discord, ecc.). Un bulk regex-replace sarebbe rischioso.
- **`BTN_CLASSES` è già la SSOT** in `hud.jsx`. Migrazione va fatta opportunisticamente su ogni nuova pagina/PR o quando si tocca il markup per altre ragioni.
### Verified
- Screenshot: menu completamente in italiano al primo login con `i18nextLng=it`, Network empty state mostra i 3 glossary tooltip.

