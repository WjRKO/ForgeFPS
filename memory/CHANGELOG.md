# FrameForge — Changelog

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
