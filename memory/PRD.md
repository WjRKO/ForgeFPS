# BOOST PC AI — PRD

## Problem Statement
Agente AI per PC (gamer/streamer): ottimizzazione PC (consigli AI + azioni reali via desktop companion), generatore di build gaming/streaming, e tracking prezzi prodotti (Amazon ecc.) con monitoraggio automatico e notifiche.

## User Choices
- App: web + desktop companion
- Boost: azioni reali (desktop), generatore build, consigli AI
- Tracking: monitoraggio automatico prezzi + notifiche + ricerca integrata
- AI: Claude Sonnet 4.6 (Emergent Universal Key)
- Auth: account con login (JWT httpOnly cookies)

## Architecture
- Backend: FastAPI + MongoDB (motor), APScheduler (price check ogni 45 min)
  - auth.py (JWT cookie auth), scraper.py (BeautifulSoup, Amazon+generic), ai_engine.py (Claude via emergentintegrations), desktop_agent.py (script Windows scaricabile)
- Frontend: React + Tailwind, tema "Tactical/Cyber Yellow", framer-motion, recharts
- AI: emergentintegrations LlmChat, claude-sonnet-4-6, streaming

## Implemented (2026-07-01)
- Auth completo (register/login/me/logout/refresh/forgot/reset, brute-force lockout, admin seed)
- AI Advisor chat (streaming, sessioni persistenti) — ora PERSONALIZZATO con hardware reale del PC
- Build Generator (AI, JSON strutturato, salvataggio build)
- Price Tracker (track by URL, ricerca Amazon, prezzo manuale fallback, target price, storico prezzi + chart)
- Notifiche in-app (cali prezzo / target) su refresh scraping E su prezzo manuale
- Dashboard stats, Desktop Agent scaricabile (.py Windows, token account incluso)
- NEW: Web Push notifications (VAPID + service worker) sui cali di prezzo — toggle nel dropdown notifiche
- NEW: Rilevamento hardware reale del PC via desktop agent (opzione 7) → specs usate dall'AI Advisor
- Tested: iteration_1/2/3 tutte 100%

## Iteration 3 (2026-07-01) — 7 nuove feature
- Upgrade AI: analizza hardware reale, trova collo di bottiglia, consiglia solo i pezzi da cambiare (/api/upgrade/analyze)
- Traccia componenti build/upgrade con 1 click (con dedupe) → gruppi e budget totale nel Price Tracker
- Health Score PC 0-100 + checklist (temp, avvio, piano energetico, game mode, HAGS, RAM, disco, driver)
- Flag driver GPU obsoleti (in health) con link aggiornamento
- Programmi all'avvio: lista dal desktop agent + analisi AI su cosa disabilitare (/api/startup/analyze)
- Stima FPS per gioco su hardware reale (/api/fps/estimate)
- Backup/ripristino tweak nel desktop agent (opzione 8)
- Nuove pagine: "Il mio PC" (/app/pc), "Upgrade & FPS" (/app/upgrade)

## Known Constraints
- Amazon blocca lo scraping HTTP (anti-bot) → fallback prezzo manuale (flusso principale)
- Desktop agent: script Python locale (azioni reali non possibili dal browser)

## Backlog / Next
- P1: Packaging desktop agent come .exe (PyInstaller) + auto-sync prodotti tracciati
- P1: Notifiche email/push quando prezzo scende
- P2: Rilevamento hardware PC reale via desktop agent (specs → consigli personalizzati)
- P2: Confronto prezzi multi-store (eBay, Amazon), storico più ricco
- P2: Export/condivisione build

## Iteration 4 (2026-07-02) — Refactor & cleanup
- server.py monolitico (~730 righe) spezzato in moduli manutenibili:
  - database.py (client+db+now_iso), settings.py (config), models.py (Pydantic), helpers.py (dominio: specs_to_text, compute_health, notifiche/push, refresh prezzo, track componenti, agent token)
  - routers/: advisor.py, builds.py, products.py, pc.py, push_routes.py
  - auth.py LASCIATO INTATTO (già testato)
- Precisione hardware: nvidia-smi (VRAM/temp/driver esatti), RAM DDR4/5, storage NVMe, socket+chipset, desktop/laptop
- Fix scheda madre: query Win32_BaseBoard robusta (-First 1) + traduzione codici OEM via AI
- Health Score: scoring pesato, stato "unknown", temperature GPU/CPU, consigli di fix
- Timeout server-side (45s) su tutte le chiamate AI
- Frontend: fix warning eslint (ProductDetail useCallback), DesktopAgent semplificato
- Regressione iteration_4: backend 41/41, frontend 100%, nessuna regressione

## Iteration 5 (2026-07-02) — App "agent-optional"
- Rilevamento hardware dal BROWSER (lib/detectSpecs.js): GPU (WebGL), thread CPU, RAM, OS, risoluzione — zero download
- Form specifiche manuale (components/SpecsForm.jsx) con opzione "Rileva dal browser" + campi avanzati (mobo/socket/chipset)
- Nuovo endpoint POST /api/pc-specs (cookie auth) che fa merge non distruttivo (browser+manuale+agent coesistono), source="manual"
- MyPc: empty state e pulsante "Modifica" mostrano il form; sezione avvio nascosta senza dati agent
- Upgrade: banner rimanda a "Il mio PC" per inserimento senza download
- Advisor/Build/Upgrade/FPS/Tracker ora usabili SENZA scaricare l'agent. Agent resta opzionale per Health Score/temperature/ottimizzazioni reali
- Verificato via curl: save manual specs + upgrade con specs manuali OK; frontend compila pulito
- BACKLOG: comando PowerShell one-liner (irm ... | iex) come alternativa leggera all'agent .py (no Python)


## Iteration 14 (2026-07-03) — Bugfix: FPS live non funzionanti (PresentMon)
- Sintomo: FPS non rilevati nel monitoraggio live. 4 root cause corretti:
  1. URL/versione PresentMon errati (v1.10.0 inesistente) -> ora v2.4.1 (URL verificato HTTP 200)
  2. Flag CLI a trattino singolo -> doppio trattino + --v1_metrics (necessario per colonna MsBetweenPresents)
  3. Nome colonna case-sensitive (msBetweenPresents) -> rilevamento case-insensitive '*betweenpresents*'
  4. Lock del file CSV (Get-Content falliva) -> nuova funzione Read-Shared con FileShare.ReadWrite
- Aggiunto TLS12 per il download; branch monitor mantiene try/finally con Stop-Fps
- Testing agent iteration_10: 17/17 backend pass, frontend 100%. Aggiunto /app/backend/tests/test_fps_presentmon_v241.py
- NOTA: cattura FPS reale eseguibile solo su Windows reale con admin + PresentMon


- FPS live: agent PowerShell mode=monitor scarica PresentMon v1.10.0 (se admin) e cattura gli FPS del gioco in primo piano (parsing CSV msBetweenPresents, invariant culture); inviati come sample.fps/sample.game. Cleanup con try/finally (Stop-Fps)
- Alert Push temperature: _check_temp_alerts() su ogni telemetria confronta cpu_temp/gpu_temp con soglie configurabili e invia WebPush (push.send_push_to_user) con cooldown 5 min per metrica. Nuovi endpoint GET/PUT /api/alerts; storage in db.alert_settings; AlertInput con bounds Field(ge=40,le=110)
- Frontend Live.jsx: card FPS (+ nome gioco), linea FPS nel grafico, pannello impostazioni alert (toggle + soglie CPU/GPU + salva)
- Testing agent iteration_9: 10/10 backend pass, frontend 100%, nessun problema. Aggiunto /app/backend/tests/test_alerts_fps.py
- PS validato con pwsh (parse OK). NOTA: PresentMon/FPS eseguibile solo su Windows reale con admin; push richiede subscription attiva (campanella)


- (1) Monitoraggio LIVE: agent PowerShell mode=monitor invia ogni 2s CPU/GPU util, temperature, clock GPU, VRAM, RAM (nvidia-smi + WMI); nuovi endpoint POST /api/agent/telemetry (push con $slice -120) e GET /api/pc-telemetry (samples + live<12s). Pagina Live.jsx con 8 stat card + grafico realtime (recharts) + comando monitor
- (2) Profili tweak per gioco: nuovo router profiles.py con TWEAK_CATALOG(26) + 5 TEMPLATES (Valorant/CS2/Warzone/Fortnite/OBS) + CRUD /api/profiles (custom). Pagina Profiles.jsx: preset + creazione custom per categoria. Ogni profilo genera comando optimize&profile=<id>
- Integrazione GUI: /api/agent/script accetta param profile+mode monitor; inietta $script:PROFILE=@(...) e la finestra grafica pre-seleziona i tweak del profilo (checkbox default profilo-aware)
- Nav: aggiunte voci "Monitoraggio Live" e "Profili Gioco"; comando monitor aggiunto in DesktopAgent
- FPS: rinviati (richiedono PresentMon) — scelta utente opzione a
- Testing agent iteration_8: 9/9 backend pass, tutti i flussi frontend OK. Aggiunto /app/backend/tests/test_live_profiles.py
- PS validato con pwsh (parse OK) su profilo iniettato + monitor mode
- NOTA: agent/monitor eseguibile solo su Windows reale


- (a) Context-aware: helpers.pc_context_text() passa all'AI non solo le specs ma anche Health Score+problemi, temperature CPU/GPU, benchmark e programmi all'avvio → consigli mirati su dati reali (cita driver/temp/Health Score veri)
- (b) Frontend Advisor.jsx: rendering Markdown (react-markdown v10 + remark-gfm) con titoli/liste/tabelle/grassetto e blocchi PowerShell con pulsante Copia (data-testid ai-code-block/ai-code-copy). In v10 i blocchi si gestiscono via componente `pre`->CodeBlock, `code` per inline
- (c) Nuovo endpoint GET /api/advisor/suggestions: suggerimenti personalizzati dai problemi reali (compute_health checks) + vendor GPU (NVIDIA/AMD), fallback ai default. Frontend li usa per la griglia iniziale
- ai_engine.py: ADVISOR_SYSTEM e blocco [CONTESTO PC] aggiornati (Markdown + blocchi ```powershell, riferimento proattivo a health/temp/benchmark)
- Fix review: flag `personalized` legato a bool(health)
- Testing agent iteration_7: 7/7 backend pass, tutti i flussi frontend OK. Aggiunto /app/backend/tests/test_advisor.py
- Pacchetti: react-markdown ^10.1.0, remark-gfm aggiunti


- Sintomo: cliccando i preset (Competitivo/Streaming/Completo) nella finestra WinForms non venivano selezionate le checkbox
- Root cause: i pulsanti preset usavano .GetNewClosure() → dentro la closure i riferimenti $script: (CHECKS/PRESETS/TWEAKS) puntavano al modulo della closure e risultavano vuoti
- Fix: rimosso GetNewClosure; il pulsante salva la chiave in $b.Tag e il gestore Click legge $this.Tag, mantenendo i riferimenti $script: allo scope reale
- Validazione: pwsh 7.4 (arm64) su Linux — riprodotto OLD (nessuna selezione) vs FIXED (competitivo->power,gaming / streaming->dns / completo->tutto); parser AST senza errori
- Testing agent iteration_6: 12/12 backend pass, frontend testid/tab OK. Aggiunto /app/backend/tests/test_agent_script.py
- NOTA: runtime WinForms non testabile su Linux; verificato contenuto script servito + logica preset

## Iteration 9 (2026-07-02) — Card guida impostazioni pannello GPU
- Aggiunta card "Impostazioni consigliate pannello GPU" in DesktopAgent.jsx (data-testid gpu-guide-card)
- Due tab: NVIDIA Control Panel e AMD Adrenalin, con impostazione → valore consigliato → perché (9 righe ciascuno)
- Rilevamento automatico del vendor GPU da /api/pc-specs: evidenzia il tab della GPU dell'utente e lo apre di default
- Nota su setup latenza ottimale (G-Sync/FreeSync + V-Sync pannello + cap FPS + Low Latency Ultra) e DDU per pulizia driver
- Motivazione: le impostazioni del pannello driver non sono modificabili via script in modo affidabile → guida manuale
- Verificato con screenshot: card e switch tab NVIDIA/AMD funzionanti

## Iteration 8 (2026-07-02) — GUI a categorie + tweak pro (NVIDIA/AMD/OBS/timer)
- Finestra WinForms riorganizzata con TabControl in 4 categorie: 🎮 Gaming & FPS, ⚡ Latenza & Input, 🌐 Rete & Streaming, 🧹 Sistema & Debloat
- 3 PRESET rapidi che pre-selezionano i tweak: 🏆 Competitivo, 🎥 Streaming, 🧰 Completo
- Catalogo esteso a 26 tweak (id/name/desc/state/apply + cat), tutti reversibili via backup/restore. Nuovi tweak pro:
  - Gaming: MPO off (fix schermo nero OBS Game Capture), GPU MSI mode (latenza DPC), AMD ULPS off, NVIDIA telemetria off, ibernazione off, power plan potenziato (core parking/USB suspend/PCIe ASPM)
  - Input: timer resolution globale, USB power management off, Sticky/Filter/Toggle keys off, startup delay ridotto
  - Rete/Streaming: rimozione 20% banda QoS (NonBestEffortLimit), Delivery Optimization P2P off (libera upload), OBS ad alta priorità (IFEO PerfOptions)
  - Sistema: app in background off, Xbox Game Bar recording off, Windows Search indexing off (NON spuntato di default)
- Restore esteso: gestisce hibernation (powercfg -h on) e servizi (WSearch/DiagTrack/NvTelemetry)
- Frontend DesktopAgent.jsx: card aggiornate (pannello a categorie + tweak pro NVIDIA/AMD/OBS)
- Verificato: import backend, generazione script (TabControl, 26 cat=, presets, MSISupported/OverlayTestMode/GlobalTimerResolutionRequests/obs64.exe presenti, placeholder sostituiti)
- NOTA: la GUI e i tweak sono eseguibili/testabili SOLO su host Windows reale (ambiente Linux qui). Confermato dall'utente: la finestra grafica funziona sul suo PC


- Comando PowerShell `mode=optimize` ora apre una FINESTRA GRAFICA (WinForms nativo, nessun download):
  - Checkbox per ognuno degli 11 tweak, con lo STATO ATTUALE mostrato accanto al nome (es. "Game Mode attivo" / "Da ottimizzare")
  - Descrizione per ogni tweak, pulsanti Seleziona/Deseleziona tutto, toggle benchmark prima/dopo
  - Pulsanti APPLICA SELEZIONATI, RIPRISTINA, e (se non admin) "Riavvia come Amministratore" (relaunch elevato via Start-Process -Verb RunAs)
  - Log a schermo + benchmark prima/dopo con % variazione; invia specs/health/benchmark al backend
  - Fallback console (applica set completo) se la GUI non è disponibile nella sessione
- Tweak refactorati in catalogo $TWEAKS (id/name/desc/state/apply) riusato da GUI e fallback; restore invariato
- Controlli condivisi resi $script:-scoped per compatibilità con gli event handler PowerShell
- Frontend DesktopAgent.jsx: etichette/descrizioni aggiornate (comando 3 apre finestra grafica; card "Pannello grafico ottimizzazioni")
- NOTA: la GUI WinForms è eseguibile/testabile solo su host Windows. Verificati qui: import backend, generazione script (16 ref System.Windows.Forms, placeholder sostituiti), rendering pagina frontend
- Entrambi gli agent (ps_agent.py PowerShell one-liner + desktop_agent.py Python) potenziati con tweak REALI e REVERSIBILI:
  - Gaming/FPS: Ultimate Performance, Game DVR off, GPU/CPU priority ai giochi (MMCSS), HAGS, Win32PrioritySeparation
  - Meno lag: Nagle off per interfaccia, NetworkThrottlingIndex off, accelerazione mouse off, effetti visivi performance
  - Rete: TCP tuning (netsh autotuning/ecn/rss), DNS Cloudflare 1.1.1.1 (reversibile a DHCP)
  - Debloat: rimozione app UWP superflue (reinstallabili), telemetria DiagTrack off, ads/suggerimenti Start off, pulizia temp + cache Windows Update
- Sistema di BACKUP generico per ogni chiave registro/servizio/DNS/power → comando/opzione "restore" ripristina tutto
- NUOVO: Benchmark CPU/RAM/disco/latenza rete. Mode 'benchmark' (misura+invia) e mode 'optimize' esegue benchmark PRIMA→tweak→DOPO e mostra confronto in console
- Backend: SpecsInput.data ora opzionale + campo benchmark; report-specs non sovrascrive più le specs con payload benchmark-only; collezione db.benchmarks (storico) + GET /api/pc-benchmark
- Frontend: MyPc.jsx card "Benchmark prima/dopo" con % di variazione per metrica; DesktopAgent.jsx comando benchmark + descrizioni aggiornate
- Verificato via curl: token agent, POST benchmark before/after, GET pc-benchmark, generazione script (benchmark mode). Screenshot MyPc: card renderizza (420→510 +21%)
- NOTA: l'ESECUZIONE reale dei tweak è testabile solo su host Windows (ambiente qui è Linux). Verificati: generazione script, endpoint backend, UI, import Python agent
- Credenziali admin invariate: admin@boostpc.io / admin123

## Aggiornamento 2026-07-06 — Pagina "BIOS & Ripristino" (adattiva)
- Pagina BiosRestore.jsx collegata all'app: rotta `/app/bios` in App.js + voce menu laterale "BIOS & Ripristino" (icona SlidersHorizontal) in Layout.jsx
- Due tab: BIOS (tweak sicuri/da usare con cautela + tasto d'accesso BIOS per marca scheda madre) e Ripristino PC (opzioni reversibili/cautela + comando restore BoostPC col token utente)
- GUIDA BIOS ORA ADATTIVA all'hardware rilevato (da /api/pc-specs):
  - detectHardware(): CPU amd/intel, GPU nvidia/amd/intel, RAM DDR4/DDR5 via regex su cpu/gpu/ram_type
  - Card "Hardware rilevato" (chip CPU/GPU/RAM)
  - Sezione "Consigliati per il tuo PC": top 3 tweak ad alto impatto filtrati per hardware
  - Titoli/descrizioni adattati: XMP (Intel) vs EXPO/DOCP (AMD, in base a DDR4/DDR5); Resizable BAR (NVIDIA/Intel) vs Smart Access Memory/SAM (AMD)
  - Tweak CPU-specifici (PBO/Curve Optimizer, Power Supply Idle, Global C-States) mostrati solo se CPU=AMD
  - Fallback generico + invito ad avviare Desktop Agent se nessun hardware rilevato
- Verificato via screenshot con account admin (AMD Ryzen 7 5800X3D + RTX 3070 Ti + DDR4): adattamento corretto
- Credenziali admin invariate: admin@boostpc.io / admin123

## Aggiornamento 2026-07-06 (bis) — Pulsante "Chiedi all'AI" sui tweak BIOS
- Advisor.jsx: legge location.state.ask (react-router) e invia automaticamente la domanda in una nuova chat (guard con useRef, pulisce lo state via navigate replace)
- BiosRestore.jsx: funzione askAI(item, tone) costruisce una domanda contestuale (nome tweak + scheda madre + CPU/GPU/RAM rilevati; per tone="caution" chiede anche rischi e valori sicuri) e naviga a /app/advisor con state {ask}
- Pulsante "Chiedi all'AI" (MessageSquareCode) su ogni Row BIOS (safe+caution) e su ogni card top-pick
- Verificato via screenshot: click su top-pick "DOCP/EXPO" apre Advisor con domanda pre-compilata + risposta AI su misura (ASUS X570 / Ryzen 5800X3D / DDR4)

## Aggiornamento 2026-07-06 (ter) — Scheda Ripristino PC adattiva + "Chiedi all'AI"
- adaptRestore(t, hw, mbName): DDU adattato alla GPU (GeForce/Adrenalin/Intel Arc); Clear CMOS elenca i tweak che verranno annullati (EXPO/DOCP vs XMP, SAM vs ReBAR) e cita la scheda madre
- Card "Adattato al tuo hardware" in cima al tab Ripristino
- Pulsante "Chiedi all'AI" (askAIRestore) su ogni opzione di ripristino → domanda contestuale (operazione + CPU/GPU/OS rilevati)
- Verificato via screenshot: DDU/CMOS adattati correttamente (RTX 3070 Ti / X570 / DOCP+ReBAR); click DDU apre Advisor con guida su misura

## Aggiornamento 2026-07-06 (quater) — Nuova scheda "Comandi Utili" (Commands.jsx)
- Nuova pagina /app/commands + voce menu "Comandi Utili" (icona TerminalSquare) in Layout.jsx
- 6 categorie fisse (Pulizia, Riparazione, Rete, Prestazioni, winget, Diagnostica) + categoria GPU adattiva (link driver GeForce/Adrenalin/Intel Arc in base a data.gpu)
- Ogni comando: descrizione, badge "Richiede Admin" (ShieldAlert, dove admin:true), pulsante Copia, pulsante "Chiedi all'AI" (naviga a /app/advisor con state {ask} contestuale al sistema)
- Banner istruzioni PowerShell come amministratore in cima
- Verificato via screenshot: pagina renderizza, badge admin corretti, categoria GPU NVIDIA presente, "Chiedi all'AI" apre Advisor con spiegazione su misura

## Aggiornamento 2026-07-06 (quinquies) — Commands.jsx potenziato (boost/pulizia/annulla)
- Nuova sezione "Boost prestazioni": Ultimate Performance, GameDVR off, Disable-MMAgent, bcdedit useplatformclock/disabledynamictick
- Sezioni aggiunte: "Avvio più veloce" (bcdedit timeout, elenco startup), "Salute & Diagnostica" (batteryreport, usura/temp SSD via StorageReliabilityCounter, winsat formal)
- Comandi rete extra: autotuninglevel normal, Restart-NetAdapter
- CmdRow ora supporta: item.warn (badge "Avanzato" + avviso giallo esteso) e item.undo (riga "Annulla" con pulsante copia dedicato)
- Componente CopyBtn riusabile per cmd e undo
- Verificato via screenshot: badge Avanzato/Admin, avviso extra e comandi Annulla renderizzano correttamente

## Aggiornamento 2026-07-06 (sexies) — Manutenzione 1-click pianificabile (Commands.jsx)
- MaintenanceCard in cima a Comandi Utili: 6 pulizie sicure (flushdns, temp utente/sistema, cestino, Windows Update cache, wsreset)
- "Scarica script .ps1" → Blob BoostPC-Manutenzione.ps1 (UTF-8 BOM, output Write-Host colorato) via buildMaintScript(true)
- "Copia (esegui ora)" → one-liner con tutte le pulizie
- "Pianifica settimanale": select giorno (DAYS EN value/IT label) + ora (TIMES), rigenera scheduleCmd che scrive lo script in %LOCALAPPDATA%\BoostPC via [IO.File]::WriteAllBytes(base64) e Register-ScheduledTask -Weekly; incluso Unregister per rimuovere
- toB64Utf8 helper (TextEncoder + btoa) per il payload base64
- Verificato via screenshot: card renderizza, selettori aggiornano il comando (Monday/21:00), download disponibile
- NOTA: esecuzione reale (download+Scheduled Task) testabile solo su Windows; pwsh non presente nel container per parse-check

## Aggiornamento 2026-07-06 (septies) — Feature: Giochi installati + Prima del match
- BACKEND: SpecsInput.games (Optional[list]); report_specs salva fields["games"]; GET /api/games; mode whitelist +"prematch"
- PS AGENT (ps_agent.py): Get-Games (scan Steam libraryfolders.vdf+appmanifest_*.acf, Epic Manifests/*.item; filtra Proton/Runtime/Redistributable), Send-Games (JSON array manuale per evitare quirk ConvertTo-Json single-element), chiamata in sync. Nuova modalità prematch: salva piano energetico (regex GUID), attiva scheme_min, chiude app background curate, Read-Host per ripristino, ripristina piano originale
- FRONTEND: nuova pagina Games.jsx (/app/games, nav "I miei giochi" icona Swords): card "Prima del match" (comando prematch copiabile), chip giochi rilevati (GET /api/games) -> click stima FPS via POST /fps/estimate, ricerca manuale + selettore risoluzione, pannello analisi (barre FPS per preset + preset consigliato + note AI). DesktopAgent.jsx: aggiunto comando "5 · Prima del match"
- Feature bottleneck+traccia pezzi GIA' esistente in Upgrade.jsx (/upgrade/analyze + /upgrade/track)
- Verificato: curl GET /api/games + report games; generazione script prematch; screenshot pagina Games con stima FPS AI reale (RTX 3070 Ti context-aware)
- NOTA: esecuzione PS (game scan reale + prematch boost) testabile solo su Windows; pwsh non presente per parse-check

## Aggiornamento 2026-07-06 (octies) — Prima del match personalizzabile
- BACKEND: PrematchInput{close_apps,set_power}; GET/PUT /api/prematch (db.prematch_settings); DEFAULT_PREMATCH_APPS in pc.py; agent_script inietta __PREMATCH_APPS__ e __PREMATCH_POWER__ dalle impostazioni utente
- PS AGENT: blocco prematch usa $apps=@(__PREMATCH_APPS__) e $setPower=__PREMATCH_POWER__ (piano energetico opzionale)
- FRONTEND Games.jsx: pannello "Personalizza cosa chiudere" (6 gruppi app: browser/chat/media/cloud/launcher/utility) + toggle piano prestazioni + Salva (PUT /api/prematch); carica stato da GET /api/prematch (gruppo checked se tutti i suoi processi sono nella lista)
- Verificato via curl (PUT/GET prematch, script riflette selezione: launcher deselezionato -> EpicGamesLauncher rimosso da $apps) + screenshot pannello

## Aggiornamento 2026-07-06 (nonies) — App in esecuzione nel pannello Prima del match
- BACKEND: SpecsInput.running_apps; report_specs salva running_apps + running_at; GET /api/prematch include running_apps+running_at (da pc_specs)
- PS AGENT: Get-RunningApps (controlla candidati noti via Get-Process) + Send-Running; chiamati in sync
- FRONTEND Games.jsx: riepilogo "N app in esecuzione rilevate · ultimo sync ..." + badge verde "N attiva/e" per gruppo (con tooltip nomi processi); fallback invito al sync
- Verificato via curl (report running_apps -> GET prematch) + screenshot badge attivi

## Aggiornamento 2026-07-06 (decies) — Riorganizzazione e semplificazione UI (testing 100% PASS)
- Layout.jsx: NAV_GROUPS con sezioni (Ottimizza il PC, Acquisti) + voci singole (Dashboard, Gaming, Admin); render con header di sezione; rinominate: Desktop Agent->Collega il PC, Build Generator->Consiglia Build, Price Tracker->Prezzi
- Consolidamento pagine: Gaming.jsx (tab: Games + Profiles) e MyPcHub.jsx (tab: MyPc + Live) montano i componenti esistenti (nessuna funzionalità rimossa)
- App.js route: /app/pc->MyPcHub overview, /app/live->MyPcHub live, /app/gaming e /app/games->Gaming games, /app/profiles->Gaming profiles
- Dashboard.jsx: box "Inizia in 3 passi" (Collega il PC / Ottimizza / Traccia i prezzi)
- Testing agent iteration_11.json: frontend 100% PASS (nav, tab, deep-link, onboarding, prematch save, fps estimate)
- OSSERVAZIONE aperta: dashboard "Prodotti recenti" mostra "Prodotto senza titolo" a EUR-- da amazon.it (scraping Amazon a volte non estrae nome/prezzo) — da migliorare

## Aggiornamento 2026-07-06 (undecies) — Fix scraper prezzi + multi-store
- ROOT CAUSE dei "Prodotto senza titolo": header Accept-Encoding includeva 'br' (brotli) non decodificabile -> body corrotto -> nessun titolo/prezzo. RIMOSSO br (gzip, deflate).
- scraper.py riscritto: header browser realistici, _clean_title (rimuove prefissi/suffissi Amazon/eBay ecc.), STORE_SELECTORS per amazon/ebay/mediaworld/unieuro/euronics/eprice/newegg/bestbuy, STORE_NAMES friendly, fallback extra (og/twitter meta, JSON embedded "price", meta prezzo), campo 'store'
- Ricerca multi-store: _search_amazon + _search_ebay
- BACKEND: TitleInput + PUT /api/products/{id}/title (edit nome manuale); track/refresh salvano 'store'
- FRONTEND Tracker.jsx: edit nome inline (matita/Check/X), "Prodotto senza titolo" in corsivo grigio, mostra p.store, label "Cerca (Amazon + eBay)", hint store supportati
- Verificato: scrape store reale (titolo+prezzo+valuta OK), PUT title OK. NOTA: Amazon/eBay bloccano IP datacenter (scraping server-side fallisce -> fallback manuale). Per Amazon affidabile servirebbe PA-API/proxy.

## Aggiornamento 2026-07-06 (duodecies) — i18n IT/EN + selettore lingua (blocco 1)
- Installati: i18next, react-i18next, i18next-browser-languagedetector (yarn)
- src/i18n.js: risorse it/en (nav, section, common, dashboard), fallback it, load languageOnly, detection localStorage(boostpc_lang)+navigator, cache localStorage; importato in index.js
- components/LanguageSwitcher.jsx: toggle IT/EN (i18n.changeLanguage), nell'header di Layout
- Layout.jsx: NAV labels e section come chiavi i18n, render con t(); page-title e logout con t()
- Dashboard.jsx: interamente tradotta con t()
- Verificato via screenshot: switch IT/EN aggiorna sidebar+dashboard, greeting "Hi, Admin", nav "Prices"
- TODO prossimi blocchi: tradurre le altre pagine (Tracker, Gaming/Games/Profiles, MyPc/Live, Advisor, BuildGenerator, Upgrade, Commands, BiosRestore, DesktopAgent, Admin, Auth/Landing) + eventuali stringhe backend/AI

## Aggiornamento 2026-07-06 (13) — i18n Blocchi 2-3 + lingua AI Advisor
- i18n.js: aggiunte namespace it/en per common(esteso), gaming, mypc(tab), grp(app groups), tracker, profiles, live, advisor, games
- Tradotti con t(): Gaming.jsx+MyPcHub.jsx (tab), Profiles.jsx, Live.jsx, Tracker.jsx, Games.jsx (grp labels + prematch + analisi FPS), Advisor.jsx
- AI Advisor lingua: models.ChatMessageInput.lang; ai_engine.stream_advisor(lang) inietta "reply in English" se en; advisor/chat passa data.lang; advisor/suggestions?lang=en con en_map; frontend passa i18n.resolvedLanguage a chat+suggestions
- Verificato: screenshot EN (Gaming/Prices/Advisor) + curl suggestions?lang=en
- TODO Blocco 4: Builds, Upgrade, Commands, BiosRestore, DesktopAgent, Admin, Login/Landing (+ leftover minori: Tracker "pezzi"/"Risultati ricerca"). Poi miglioramenti visivi.


## Aggiornamento 2026-07-06 (14) — i18n Blocco 4 COMPLETO + miglioramenti visivi (hover)
- i18n.js: aggiunte namespace it/en per auth, build, upgrade, commands, bios, desktop, admin
- Tradotti con useTranslation/t(): Auth.jsx, BuildGenerator.jsx (USE_CASES via t returnObjects), Upgrade.jsx (prio map alta/media/bassa->high/medium/low), Commands.jsx, BiosRestore.jsx, DesktopAgent.jsx, Admin.jsx
- Contenuti tecnici (descrizioni comandi, tweak BIOS, GPU guide, action tiles): campi inline *_en/de selezionati via isEn() (i18n.language); adaptTweak/adaptRestore resi language-aware. I comandi PowerShell restano invariati.
- MIGLIORAMENTI VISIVI (index.css): nuove utility card-hover (potenziata con shadow), panel-hover, tile-hover, btn-volt (press+glow), btn-ghost, row-hover (slide), icon-pop, stagger (entrance ritardato). Applicate a: Admin stat cards, DesktopAgent action tiles, Commands category panels, BiosRestore top-picks + rows, Upgrade recommendation rows, CTA primari (btn-volt), Auth submit.
- Verificato: testing_agent iteration_12.json — 100% frontend, tutti i 7 pagine PASS in IT e EN, nessuna chiave i18n grezza, nessun errore runtime, comandi PowerShell preservati.
- NOTE minori (non bloccanti): localStorage 'boostpc_lang' può contenere 'en-US@posix' da seed browser (fallback EN corretto); 401 rumorosi pre-login in console.
- i18n COMPLETO su tutte le pagine principali. Backlog: Storico Health Score/temp (grafici), riepilogo sessione gaming condivisibile, notifiche email calo prezzi, desktop agent .exe (PyInstaller).

## Aggiornamento 2026-07-06 (15) — i18n COMPLETO (aree residue) + bandiere lingua
- Tradotte le pagine/parti che erano rimaste in italiano: Landing.jsx (intera), ProductDetail.jsx, SpecsForm.jsx, MyPc.jsx (intera: SPEC_KEYS, BENCH_METRICS, Health/Benchmark/Startup), notifiche in Layout.jsx, chrome + suggerimenti default + CodeBlock in Advisor.jsx, toasts in Games.jsx, residui in Tracker.jsx (search_results/no_results/parts).
- Nuove namespace i18n: landing, detail, specs, mypcpage, notif; aggiunte a tracker/games/advisor.
- LanguageSwitcher: aggiunte bandiere 🇮🇹/🇬🇧 (attiva evidenziata gialla + glow, l'altra desaturata) con micro-animazione hover. Aggiunto anche alla Landing (header) e alla pagina di Login (in alto a destra).
- BUG FIX (trovato dal testing agent): MyPc BenchmarkCard crashava con 'Invalid language tag: en-US@posix' su toLocaleString. Corretto sanificando il tag a 2 lettere + try/catch. i18n.js già con supportedLngs=['it','en'] e load='languageOnly'.
- Verificato: testing_agent iteration_13.json — 100% frontend dopo fix, tutte le rotte IT/EN senza chiavi grezze né errori runtime. ProductDetail deep-link non testabile in automazione (card senza data-testid sul link esterno) ma renderizza senza errori.
- i18n ora COMPLETO su TUTTE le pagine e componenti principali.
- Backlog invariato: Storico Health Score/temp (grafici P2), riepilogo sessione gaming condivisibile per streamer (P2), notifiche email calo prezzi (P3), desktop agent .exe PyInstaller (P3). Nice-to-have: data-testid su card prodotto Tracker e sul bell notifiche.


## Aggiornamento 2026-07-06 (16) — Redesign Landing Page
- Ricostruita Landing.jsx unendo le migliori idee: hero con mockup di prodotto animato (Health Score SVG, telemetria CPU/GPU/RAM/ping, grafico FPS Recharts, badge fluttuante "26/26"), trust strip con contatori animati (useInView + count-up), sezione "Come funziona" in 3 step con hover left-border, 5 feature showcase alternate (AI Advisor chat, Health/Telemetry, Build Generator, Price Tracker con grafico prezzo discendente + target line, Desktop Agent terminal), CTA finale con corner brackets, footer multi-colonna con status.
- Animazioni: framer-motion whileInView (stagger), hover btn-volt/icon-pop, floating hero, count-up contatori. Grid-bg + glow volt.
- Tutto bilingue: nuove chiavi i18n nel namespace landing (trust_*, how*, feat_*, f_*_long/b1-b3, f_health_*, cta_*, footer_*, demo_q/demo_a) in IT+EN.
- Mockup costruiti in HTML/CSS/SVG/Recharts (nessuna foto stock per la UI). Design guidelines salvate in /app/design_guidelines.json.
- Verificato: la pagina renderizza in EN senza errori runtime (solo warning innocui Recharts width/height iniziale); contatori e sezioni funzionanti. data-testid: nav-login-link, nav-register-link, hero-cta-btn, cta-bottom-btn.

## Aggiornamento 2026-07-06 (17) — SEO / Open Graph / favicon
- /app/frontend/public/index.html: title "BoostPC — AI Performance Command Center", description bilingue, Open Graph (og:title/description/image/url/type/site_name), Twitter Card summary_large_image, theme-color #050505.
- og:image e twitter:image = banner HUD generato (hostato su CDN emergent, URL assoluto stabile). og:url = dominio preview (DA AGGIORNARE al deploy su dominio custom).
- Favicon brandizzata (fulmine volt) in public/favicon.png (256px) + apple-touch-icon.png (180px); og-image.png self-hosted come fallback.
- NOTA: index.html e statici in public/ richiedono restart frontend (HtmlWebpackPlugin genera HTML allo start). Verificato via curl: tutti i meta serviti correttamente, favicon/og HTTP 200.
- Immagini sorgente/design in /app/design_guidelines.json.

## Aggiornamento 2026-07-06 (18) — Uplift grafico app (Fase 1: sistema componenti + Dashboard + Tracker)
- Nuovo design system condiviso in src/components/hud.jsx: PageHeader, StatCard, EmptyState, SkeletonCard/Row, Badge/StatusPill, Sparkline, HealthRing, varianti motion stagger/item.
- Nuove utility CSS (index.css): .skeleton (shimmer), .hud-tick (corner tick su hover), .text-glow-volt, .typing-dot.
- Dashboard riscritta: PageHeader, onboarding 3-step condizionale (nascosto se ha gia prodotti+build), 4 StatCard animate con skeleton loading, 3 quick-action card, lista recenti con row-hover + EmptyState.
- Tracker riscritto: griglia di ProductCard con sparkline di tendenza, badge stato (In calo/Target raggiunto/In aumento), barra progresso verso target, skeleton loading, EmptyState; preservati TUTTI i data-testid (track/search/refresh/delete/edit/product-row/group-summary). Aggiunto toast errore su delete.
- i18n: aggiunte chiavi tracker.status_drop/status_target/status_up/to_target/empty_title (it+en).
- Fix: Sparkline con width fisso (no warning Recharts width=-1).
- Verificato: testing_agent iteration_14.json = 100% frontend, tutti i flussi/testid ok, nessun errore runtime. Bundle compila.
- FASE 2 (backlog uplift): MyPc (gauge temperature, barre benchmark con delta), Advisor (bolle chat + typing indicator + chip suggerimenti), Gaming, Build/Upgrade result cards, Commands/BIOS/Admin polish, applicando lo stesso sistema hud.jsx.

## Aggiornamento 2026-07-07 (19) — i18n Health Score + Precisione "sincronizza"
### i18n etichette Health Score (My PC)
- Backend helpers.py compute_health ora restituisce campi strutturati stabili: `id`, `status`, `mkey` (chiave messaggio), `mval` (valore numerico), `grade_key`. Mantiene label/message/fix in IT per il prompt AI (pc_context_text).
- Frontend MyPc.jsx traduce label/message/fix/grade via i18n usando gli id/mkey/grade_key (nuove chiavi `mypcpage.health.{label,msg,fix,grade}` in it+en). Le etichette del punteggio salute ora seguono la lingua selezionata (prima erano hardcoded IT anche in EN). Verificato via screenshot EN+IT.

### Precisione comando "sincronizza" (ps_agent.py, pacchetto completo #1-#7)
- #1 Temp CPU/GPU reali via LibreHardwareMonitor (download DLL una-tantum, richiede admin come PresentMon): Get-LhmComputer/Get-LhmTemps. Fallback: nvidia-smi (GPU), MSAcpi_ThermalZoneTemperature (CPU, con guard >2732).
- #2 VRAM GPU a 64-bit da registro (HardwareInformation.qwMemorySize) per AMD/Intel (WMI AdapterRAM cappato a 4GB): Get-GpuVramGb.
- #3 Piano energetico locale-independent per GUID (High/Ultimate/Balanced/Power saver): Get-PowerPlanNormalized. Backend match invariato (high/ultimate ok).
- #4 Conteggio avvio accurato: Run keys HKCU/HKLM/WOW64 escludendo disabilitati (StartupApproved), cartelle Startup, task pianificati con trigger logon non-Microsoft: Get-StartupCount.
- #5 Spazio pulibile ampliato: temp utente+sistema, SoftwareDistribution\Download, Prefetch, INetCache, Cestino: Get-CleanableMb.
- #6 RAM usata mediata su 3 campioni (Get-AvgRamPct); temp con guard anti-spike.
- #7 Velocità RAM da ConfiguredClockSpeed (XMP reale) con fallback Speed.
- Validazione: pwsh 7.4.6 (arm64) installato in /opt/pwsh; Parser::ParseFile = PARSE OK; costrutti a rischio (HashSet, null-sum, byte flag, switch GUID, media) testati OK. Script servito da /api/agent/script contiene le nuove funzioni. Sensori reali verificabili solo su Windows.

## Aggiornamento 2026-07-08 (20) — Fix FPS live + Monitoraggio 1s + Riepilogo sessione streamer
### Fix rilevamento FPS (ps_agent.py)
- Causa root: PresentMon apriva il CSV con lock esclusivo → lettura impossibile (file cresceva ma 0 righe lette). Soluzione: `--output_stdout` + redirect stdout su file controllato da noi (letto con Read-Shared). Rimosso `--output_file`.
- Aggiunta diagnostica FPS (Show-FpsDiag): stato processo, byte/righe output, intestazione colonne, errore PresentMon; stampata dopo ~10s senza FPS.
- Colonne PresentMon 2.4.1 v1_metrics confermate: `Application`, `MsBetweenPresents` (parsing case-insensitive OK). Flag corretti: `--output_stdout --stop_existing_session --v1_metrics --no_console_stats`.
- Diagnostica temp CPU estesa: Test-MemoryIntegrity (legge SecurityServicesRunning + Scenarios) e Test-VulnerableDriverBlocklist. Caso reale utente: CPU AMD Ryzen, sensore `Core (Tctl/Tdie)` presente ma =0 perché il driver WinRing0 è bloccato dalla Blocklist driver vulnerabili (default Win11). GPU NVIDIA ok via nvidia-smi.

### Monitoraggio più veloce (2s → 1s)
- ps_agent monitor loop: Start-Sleep 1000ms. Backend pc.py: samples slice -120 → -300 (~5 min storia). Frontend Live poll 2000ms → 1000ms. Testi i18n aggiornati ("in tempo reale").

### Riepilogo sessione condivisibile per streamer (P2 — FATTO)
- Nuovo componente `frontend/src/pages/SessionSummary.jsx`: card brandizzata (BoostPC, neon) con gioco, FPS avg/min/max/1%low, temp max CPU/GPU, CPU avg, durata, n. campioni. Export PNG via `html-to-image` (toPng) + Web Share API con fallback download (`boostpc-session.png`).
- `Live.jsx`: accumulo sessione lato client con `seenRef` (Set persistente per dedup) + `acc` ref; auto-reset sessione su gap >30s tra campioni; pulsante "Nuova sessione". 1% low = percentile 1 su fps ordinati.
- Bug corretto in dev: riferimento acc stale dopo reset causava "1 campione"; risolto usando sempre acc.current + seenRef persistente.
- Dipendenza aggiunta: `html-to-image@1.11.13` (yarn).
- Verificato: card render OK (8 campioni test → avg 135, min 95, max 160, 1%low 95, temp max 67/72, durata 2s), pulsante Share genera e scarica PNG (toast "Image ready!"). Telemetria di test poi ripulita dal DB.
- Validazione PS: pwsh 7.4.6 reinstallato (ambiente effimero pulisce /opt/pwsh), Parser = PARSE OK. Frontend compiled successfully.

## Aggiornamento 2026-07-08 (21) — Gaming: giochi rilevati + preset consigliati
### Giochi rilevati (ps_agent.py Get-Games)
- Aggiunti launcher: GOG Galaxy (registro), EA/Ubisoft/Blizzard/Riot/Rockstar/Bethesda/Activision/CDPR/ecc. via registro Uninstall filtrato per Publisher noti (con esclusione launcher/redist/anticheat), Xbox/Game Pass (cartelle C:/D:/E:/F:\XboxGames). Deduplica + filtro rumore ampliato, limite 80. Steam+Epic invariati.
### Preset consigliati differenziati (profiles.py)
- Sostituiti i vecchi template quasi-identici con 5 categorie con tweak set diversi: tpl_comp (Competitive FPS/Esports), tpl_aaa (AAA/Single-player/Quality), tpl_moba (MOBA), tpl_streaming (Streaming/OBS), tpl_balanced (General). Ogni template ha preset_label + array `match` (sottostringhe nomi gioco) esposto da /profiles/templates.
### Consiglio contestuale (Games.jsx)
- Al click/selezione di un gioco rilevato, mostra card "Preset consigliato" con il template abbinato via `match` (fallback tpl_balanced), chip dei tweak e comando `...&mode=optimize&profile=<tpl_id>` copiabile. Nuove chiavi i18n games.rec_* (it+en).
- Verificato: /profiles/templates ritorna i 5 template con match; UI testata (Cyberpunk 2077 → tpl_aaa "AAA / Single-player · Quality"); PS PARSE OK; frontend compiled. NB: i nomi dei tweak nella catalog restano IT anche in EN (comportamento preesistente, fuori scope).

## Aggiornamento 2026-07-08 (22) — Test Bufferbloat & Latenza di rete (grade A-F) [P0 servizio boost]
### Backend
- ps_agent.py: nuova modalità `bufferbloat`. Run-Bufferbloat misura latenza idle (System.Net.NetworkInformation.Ping, version-independent) vs sotto carico download (4 job WebClient su speed.cloudflare.com/__down 150MB) e upload (3 job __up 25MB), + jitter (stdev) + packet loss. Invia raw a /api/agent/netresult. Nessun admin richiesto.
- helpers.grade_bufferbloat: calcola grade A+..F sull'aumento max di latenza sotto carico (Waveform-style: <=5 A+, <=30 A, <=60 B, <=200 C, <=400 D, else F), + down_grade/up_grade, base_quality (idle RTT), loss.
- pc.py: POST /agent/netresult (agent token, salva graded in net_results upsert), GET /net-result (utente). Mode 'bufferbloat' aggiunto alla whitelist agent_script. models.NetResultInput.
### Frontend
- Nuova pagina `Network.jsx` (rotta /app/network) + voce menu "Rete & Bufferbloat" (Layout, icona Gauge). Mostra comando da eseguire, poll /net-result ogni 5s, badge Voto A-F colorato, bufferbloat +ms, metriche idle/down/up/jitter/loss con grade per fase, e consigli dinamici (SQM/fq_codel, Ethernet, upload bg, QoS BoostPC, server vicini, loss). i18n network.* + nav.network (it+en).
- Verificato E2E: POST netresult {idle19,down78,up45} -> grade B, bloat +59ms; pagina render OK (idle Excellent, down Grade B, up Grade A). PS PARSE OK, frontend compiled, grade fn testata. Dati test rimossi.
### Prossimo (raccomandazione secca, resto): #3 Report Before/After cliente (bufferbloat+FPS+health prima/dopo, export immagine/PDF brandizzato) e #2 input lag reale (PresentMon latency + tweak Reflex/cap FPS).

## Aggiornamento 2026-07-09 (23) — Input lag reale (PresentMon) + guida Reflex
- ps_agent Get-Fps: ora estrae anche la latenza reale dalla colonna PresentMon `MsUntilDisplayed` (fallback `MsUntilRenderComplete`), media per l'app top, ritorna latency_ms (0<lat<1000). Monitor loop: aggiunge $s.latency_ms al campione telemetria + stampa "..ms" in console.
- Live.jsx: nuovo Stat "Latenza" (last.latency_ms); accumulo sessione latSum/latN/latMax -> summary.latAvg/latMax; card guida "Reduce input lag (Reflex & low latency)" con 4 step azionabili (Reflex On+Boost, G-Sync+VSync+cap FPS, Low Latency Ultra, preset Competitive FPS). SessionSummary.jsx: metriche Avg/Max latency (mostrate se presenti).
- i18n live.st_latency, session_lat_avg/max, reflex_* (it+en).
- Verificato E2E: telemetria con latency_ms -> Stat 25ms, summary Avg 22/Max 30, card render OK. PS PARSE OK, frontend compiled. Dati test rimossi. NB: latenza = tempo present->schermo (proxy render-to-photon); il click-to-photon completo richiede Reflex/hardware. Misura reale solo su Windows con gioco attivo + admin.
### Raccomandazione servizio boost - stato: #1 Bufferbloat FATTO, #2 Input lag FATTO. Resta #3 Report Before/After cliente (bufferbloat+FPS+health+latenza prima/dopo, export immagine/PDF brandizzato).

### 2026-07-09 - Pre-deploy security hardening (FATTO, testato backend 30/30)
- Password admin debole rimossa: `auth.py` seed_admin richiede ADMIN_EMAIL/ADMIN_PASSWORD da env (no fallback admin123), ruota la pwd se cambia. .env preview usa password forte. Utente imposterà la propria pwd in fase di deploy via env.
- CORS: `settings.get_cors_origins()` parsa CORS_ORIGINS (scarta '*') + FRONTEND_URL; `server.py` usa la lista invece del wildcard. Verificato: origini estranee rifiutate a livello app (il '*' sul preview URL è artefatto dell'ingress CF, non del codice).
- scheduled_price_check: aggiunto `.sort('updated_at',1).limit(100)` (PRICE_CHECK_BATCH) per evitare OOM/rate-limit.
- Cookie auth: `secure` ora guidato da FRONTEND_URL https (COOKIE_SECURE) -> Secure in produzione.
- test_credentials.md ora scritto dinamicamente da env. Nuova suite /app/backend/tests/test_security_predeploy.py (15 test).

### 2026-07-09 - Rebranding FrameForge + SEO + fix deploy (FATTO)
- Rebrand completo BoostPC → FrameForge in tutta l'app (logo, title/meta/OG, i18n IT+EN, sw.js push, ps_agent.py/desktop_agent.py display, server.py). File interni (backup json/temp) invariati per continuità restore.
- SEO: hook usePageMeta (title/description unici per home/login/register), public/robots.txt (plain-text + sitemap), public/sitemap.xml, public/llms.txt, contenuti su login/register (feature highlights), code-splitting React.lazy in App.js.
- Deploy fix: aggiunto endpoint GET /health (200) per la k8s probe (era 404 → deploy fallito). Ottimizzato N+1 in admin.list_users con aggregation. deployment_agent status=PASS.

### 2026-07-16 - Fase 1 security-first + trust + UX + conversione (FATTO, test 10/10 BE, 27/28 FE)
- SICUREZZA: rimosso comando remoto insicuro 'irm .../run | iex' dalla landing → sostituito con Secure Installer card (badge Signed/SHA256/Secure/Transparent, firma reale deferita). Security headers middleware (CSP, HSTS, X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy, Permissions-Policy). Rate limit AI /api/advisor/chat = 100/ora/utente (429). Validazione ChatMessageInput (min1/max2000 → 422).
- TRUST/UX: nuove pagine pubbliche /security (architettura Agent→API cifrata→AI + badge), /privacy-telemetry (Collected vs Never + LOCAL ONLY + tiering Free/Cloud AI/Pro), /changelog (timeline v0.4.2/0.4.0/0.3.0 + link roadmap/issues), /pricing (Free/Pro €9.99/Creator €19.99 informativo, no checkout).
- CONVERSIONE: homepage hero tecnico ("Trova i colli di bottiglia / Find the bottlenecks", CTA "Run Free Scan" → #demo). Demo Scan interattivo simulato (RTX 4070 + Ryzen 7 5800X, problemi + +12-18 FPS/-8ms). Nav/footer con link alle nuove pagine. Componenti: MarketingChrome, DemoScan, SecureInstaller.
- Test: /app/backend/tests/test_phase1_security.py (10/10). /app/test_reports/iteration_17.json.

### Backlog fasi successive (ForgeFPS overhaul)
- FASE 2: auth backend — migrazione bcrypt→Argon2id (retro-compat), MFA/TOTP opzionale, refresh token rotation (richiede integration_expert).
- FASE 3: agent Windows security-first in ps_agent.py — ogni tweak con Problema/Motivo/Modifica/Impatto/Apply, mai toccare Defender/servizi critici, backup+rollback obbligatori.
- FASE 4: SaaS billing Stripe reale sul pricing (checkout Free/Pro/Creator).
- Firma Authenticode reale + GitHub Release + checksum SHA256 pubblicato (richiede certificato utente).

### 2026-07-16 - Post-login: Fase A (Account & Sicurezza) + Fase B (responsive mobile) (FATTO, test BE 14/14, FE 100%)
- Fase A: nuova pagina /app/account (Account.jsx). Backend auth.py endpoint: GET/PUT /api/auth/preferences (local_only, email_alerts, language), PATCH /api/auth/profile (nome), POST /api/auth/change-password (verifica pwd attuale, rifiuta uguale, ruota cookie), POST /api/auth/delete-account (verifica pwd, admin non eliminabile, cascade su products/price_history/builds/chat_sessions/chat_messages/notifications/pc_specs/agent_tokens/push_subscriptions). AuthContext espone setUser/refreshUser. Link "account" in sidebar.
- Fase B: Layout.jsx responsive — sidebar drawer a scomparsa <768px con hamburger (sidebar-toggle) + overlay; su desktop sempre visibile. Header con hamburger mobile, padding adattivo. Chiude drawer al cambio route.
- Test: /app/backend/tests (14/14). /app/test_reports/iteration_18.json.
- IN SOSPESO (concordato col user): Fase comandi PowerShell sicuri (rimuovere irm|iex dalla pagina Connect PC/DesktopAgent.jsx: flusso download→Get-FileHash SHA256→esegui file locale con -Token param; richiede Param block in ps_agent.py e /api/agent/script senza token embedded + endpoint checksum).

### 2026-07-16 - Comandi PowerShell sicuri (Fase A) + kit .exe (Fase C) (FATTO, test BE 12/12, FE ~100%)
- SICUREZZA COMANDI: rimosso 'irm|iex' da TUTTA l'app. Flusso sicuro: scarica (-OutFile) → verifica SHA256 → esegui file locale con -Token. ps_agent.py PS_SCRIPT ora inizia con Param([string]$Token='',[string]$Mode='sync'); token validato; pulsante elevazione ri-esegue il file locale (no iex). Backend: _build_agent_script helper, GET /agent/script (nessun token embedded + Content-Disposition), GET /agent/script-info (SHA256 dei byte serviti, parity con Get-FileHash). Nuovo componente frontend SecureRunBlock usato in Network/Live/Profiles/Games/BiosRestore. Pagina Connect PC (DesktopAgent.jsx) riorganizzata: card '.exe coming soon' + 'Metodo sicuro' (token/download/verify/run) + spiegazione 'perché non usiamo irm|iex' + sezione Avanzato collassata.
- KIT .EXE (Fase C, prep): /app/agent-build/ con forgefps_agent.py (backend=forgefps.dev, token via --token), build.bat, build.ps1, README.md (build PyInstaller + SHA256 + istruzioni firma Authenticode). desktop_agent.py: argparse --token/--backend/--mode, esce se token mancante. NB: l'.exe va generato/testato su Windows dall'utente; poi fornirà l'URL della GitHub Release da collegare al bottone 'Scarica FrameForge'.
- Nota build: warning preesistenti react-hooks/exhaustive-deps in BiosRestore/Commands (non bloccanti sul deploy attuale).
- Test: /app/backend/tests (12/12). /app/test_reports/iteration_19.json.

### 2026-07-16 - .exe collegato (GitHub Release)
- Utente ha buildato forgefps-agent.exe e pubblicato su GitHub Release v0.4.2 (WjRKO/ForgeFPS).
- Config: /app/frontend/src/config/agent.js (AGENT_EXE_URL, AGENT_EXE_SHA256=0f9b1dbb..., version v0.4.2).
- DesktopAgent.jsx: card 'One-click desktop app' con bottone download reale + SHA256 + comando 'forgefps-agent.exe --token <T> --mode optimize'. SecureInstaller.jsx (Landing + /security): download → release reale + SHA256 mostrato.
- Backlog UX: l'.exe attuale esce se manca --token; migliorare desktop_agent.py per PROMPT interattivo del token (input) così il doppio click funziona senza CLI (richiede rebuild utente). Firma Authenticode = fase successiva (toglie SmartScreen).

### 2026-07-16 - .exe v0.4.3 (prompt token interattivo)
- desktop_agent.py: se il token manca chiede input() interattivo (doppio click funziona). Standalone rigenerato in /app/agent-build/forgefps_agent.py.
- Release aggiornata: WjRKO/ForgeFPS v0.4.3, SHA256=899f2e7f412221d0189ecd9acc045a42521181d2e5174facf6b7f0fb560539ac. Config agent.js aggiornata (URL+sha+version). Pagina Connect PC + SecureInstaller (Landing/security) puntano al file reale.

### 2026-07-16 - FASE 2 CHIUSA: MFA/TOTP frontend verificato (FATTO, test FE 100% - iteration_20)
- Fix lint pre-esistente in Games.jsx: comando "sync" ora usa <SecureRunBlock mode="sync"> (rimossi riferimenti orfani syncCmd/copyCmd/Copy).
- BUG CRITICO trovato dal testing agent e corretto: MfaCard era definita ma MAI montata in Account.jsx → 2FA inaccessibile dalla UI. Ora <MfaCard c={c}/> è nel render tree tra Password e Preferenze.
- POLISH: sostituito window.prompt() del "Disattiva 2FA" con form inline stilizzato (data-testid mfa-disable-form / mfa-disable-code-input / mfa-disable-confirm-btn / mfa-disable-cancel-btn) coerente con il design cyber. Nuove chiavi i18n mfa_disable_hint (it+en).
- Verifica backend E2E via curl: setup → enable (10 codici recupero) → login richiede codice → login con codice OK → disable OK. Argon2id + pyotp funzionanti.
- Verifica frontend testing_agent iteration_20.json: 7/7 step MFA PASS (badge Disabled → Enable → QR+secret+input → conferma TOTP → 10 recovery codes + badge Enabled → logout → login richiede mfa-code-field → login con TOTP → dashboard → disable → badge Disabled).
- Stato finale: admin MFA DISABILITATO. Credenziali admin invariate (vedi test_credentials.md).
- FASE 2 auth COMPLETA (Argon2id + TOTP MFA opzionale). Refresh token rotation NON implementato (non richiesto per ora).

### Prossimo: FASE 3 - Agent Windows security-first (ps_agent.py)
- Ogni tweak deve mostrare: Problema trovato → Motivo → Modifica proposta → Impatto stimato + pulsante "Applica".
- Guardrail: mai toccare Windows Defender/servizi sicurezza, privilegi minimi, backup+rollback obbligatorio prima di ogni tweak.

### 2026-07-17 - FASE 3 Agent security-first + Report Prima/Dopo (FATTO)
#### Fase 3 - ps_agent.py GUI security-first (parse OK + guardrail runtime testati; GUI WinForms testabile solo su Windows reale)
- GUARDRAIL SICUREZZA: $script:FORBIDDEN_SVC (WinDefend/WdNisSvc/WdFilter/Sense/SecurityHealthService/wscsvc/mpssvc/MpsSvc/SgrmBroker...) + $script:FORBIDDEN_REG (Windows Defender/Security Center/Security Health). Set-Reg blocca qualsiasi scrittura su area protetta; Disable-ServiceSafe rifiuta i servizi di sicurezza. Do-Telemetry/Do-SearchIndex ora usano Disable-ServiceSafe. Testato via pwsh: Defender reg/svc bloccati, DiagTrack/WSearch consentiti, firewall (mpssvc) bloccato.
- CATALOGO TWEAKS esteso: ogni tweak (26) ora ha problem (Problema trovato), reason (Motivo), desc (Modifica proposta), impact (Impatto stimato), risk (safe/caution). Preservati cat/id/name/state/apply.
- NUOVA GUI a CARD: header con branding FrameForge + banner verde "SICUREZZA GARANTITA - non tocchiamo mai Defender/Firewall, backup automatico reversibile" + stato admin + contatore backup. Preset (Competitivo/Streaming/Completo). TabControl 4 categorie con FlowLayoutPanel di card. Ogni card: barra accento (volt/arancio se caution), checkbox nome, badge CAUTELA, "Stato attuale", righe Problema/Motivo/Modifica/Impatto colorate, pulsante "Applica" per singolo tweak (pattern .Tag, no GetNewClosure). Bottom: benchmark PRIMA/DOPO, log console, APPLICA SELEZIONATI, RIPRISTINA TUTTO, elevazione admin. Refresh-Status aggiorna stato+backup dopo ogni azione.
- Backup/rollback OBBLIGATORIO: Save-Backup dopo ogni apply (singolo e bulk); RIPRISTINA TUTTO usa Invoke-Restore.
- Validazione: pwsh 7.4.6 Parser = PARSE OK (script servito 85KB), catalogo integro (26 tweak, tutti i campi), guardrail runtime OK. agent/script HTTP 200 + script-info SHA coerente.

#### Report Prima/Dopo cliente (backend testato curl, frontend testing_agent iteration_21 = 100%)
- BACKEND pc.py: _gather_snapshot(uid) raccoglie health_score/grade (compute_health da pc_specs.health), bufferbloat_ms/grade (net_results), fps_avg (media fps da pc_telemetry.samples), bench_overall (pc_specs.benchmark). Endpoint: POST /api/report/snapshot {phase:before|after} (upsert db.boost_reports), GET /api/report (before/after + deltas calcolati), DELETE /api/report. models.ReportPhaseInput (pattern before|after -> 422 se invalido).
- FRONTEND Report.jsx (/app/report, nav "Report Prima/Dopo" icona FileBarChart): guida 3 step, pulsanti Cattura PRIMA/DOPO/Reset, card brandizzata FrameForge esportabile in PNG (html-to-image toPng + Web Share/download). 4 metriche in colonne Prima->Dopo con badge delta colorato (verde=migliorato, considera bufferbloat lower-is-better), riga voti Health/Bufferbloat. Dizionario locale IT/EN. Nav label i18n nav.report (it+en).
- Verificato: curl (before/after/get/delete/422), screenshot (card render + toast), testing_agent iteration_21 (100% frontend, export PNG OK, reset OK). Admin report lasciato pulito.
- Nota: le metriche bufferbloat/fps mostrano "--" senza dati agent (atteso). I delta reali compaiono catturando PRIMA, eseguendo il boost/test, poi DOPO.

### 2026-07-17 (2) - Agent v0.5 (GUI sicura) + Storico Salute + Report PDF (FATTO)
#### Agent v0.5 - GUI sicura nel .exe (lato codice fatto; build/pubblicazione = utente su Windows)
- forgefps_agent.py (sorgente .exe) + desktop_agent.py (script servito): nuova funzione launch_secure_gui() che scarica /api/agent/script e lancia la NUOVA GUI sicura PowerShell (Problema/Motivo/Modifica/Impatto per tweak + guardrail Defender + backup/rollback), elevata via UAC se non admin. Menu: nuova opzione "G" (consigliata) + supporto --mode securegui|gui. Vecchio "A" (apply tutto) resta come avanzato. AGENT_VERSION=0.5.0 mostrato nell'header. README agent-build aggiornato con sezione "Novita v0.5".
- Entrambi i file compilano/parse OK. NB: l'.exe va RICOMPILATO su Windows dall'utente e ripubblicato su GitHub Release; poi aggiornare /app/frontend/src/config/agent.js (URL+SHA256+version). Config attuale resta v0.4.3 (link funzionante) finche l'utente non fornisce la nuova Release.
#### Storico Salute (backend + frontend, testato)
- Backend pc.py: report_specs ora storicizza ogni health in db.health_history {score,grade,cpu_temp,gpu_temp,created_at}. GET /api/health-history (ultimi 90, asc).
- Frontend components/HealthHistoryCard.jsx (recharts LineChart doppio asse: Health Score 0-100 volt + temp CPU cyan/GPU red 0-110), montato in MyPc.jsx dopo il benchmark. Si mostra solo con >=2 punti. Bilingue IT/EN.
- Verificato: curl /health-history (5 punti seed) + screenshot MyPc (grafico render con tooltip/legenda).
#### Report PDF (frontend, testato)
- Report.jsx: aggiunto textarea "Note per il cliente" + pulsante "Esporta PDF" (jspdf). PDF A4: header FrameForge + titolo/data, immagine della card (html-to-image toPng), note del cliente, footer. Mantiene anche Esporta PNG. Dipendenza: jspdf (yarn).
- Verificato: screenshot (pulsante EXPORT PDF, note compilate, toast "Report exported!", nessun errore console tranne warning font non bloccante).

### 2026-07-17 (3) - Agent v0.5 .exe collegato (Release pubblica)
- Utente ha pubblicato forgefps-agent.exe su GitHub Release WjRKO/ForgeFPS tag v0.4.3.5 (repo PUBBLICO, verificato via API con User-Agent; senza UA GitHub restituisce 404 fuorviante).
- config/agent.js aggiornato: URL v0.4.3.5, SHA256=569dc9e365905c89eda20a41ed9eaf78e3d4432b5142a61dc4e2de333d31d510 (verificato: download 9.04MB + sha256sum COMBACIA), version v0.5.0, date 2026-07-17.
- Connect PC + SecureInstaller (Landing/security) puntano al file reale. Screenshot Connect PC: badge v0.5.0 + SHA corretto + download attivo.

### 2026-07-17 (4) - Agent v0.4.4 + avviso backend su "Collega il PC"
- Diagnosi "Token non valido": l'.exe si collega di default a https://forgefps.dev (produzione, codice VECCHIO "Desktop Agent") mentre l'utente copiava il token dalla PREVIEW (db separato) -> token invalido. Non un bug: mismatch ambiente/token. Regola: il token deve venire dallo stesso backend a cui punta l'.exe.
- config/agent.js -> Release v0.4.4, SHA256=8460ed1d73dbaa6415e2ab9035293d411639fa8642e44d46147043dfc372130c (download HTTP200 9.05MB + sha256sum COMBACIA), version v0.4.4.
- DesktopAgent.jsx: aggiunto AVVISO (data-testid exe-backend-notice) nella card .exe. Mostra il backend di default (forgefps.dev via AGENT_DEFAULT_BACKEND) e avverte del mismatch token. Se il sito corrente NON e' forgefps.dev -> box AMBRA con comando pronto `forgefps-agent.exe --backend "<BACKEND_CORRENTE>" --token <tk> --mode optimize` (anche il comando principale exe-run include --backend in questo caso). Se e' produzione -> box VERDE "usa il token e avvia normalmente". Bilingue IT/EN. Verificato via screenshot in preview.

### 2026-07-17 (5) - Antivirus falso positivo sull'.exe (mitigazioni build + guida + nota UI)
- Causa: gli .exe PyInstaller (--onefile) sono spessissimo flaggati come falso positivo euristico (Windows Defender & co). Non e' un vero virus.
- agent-build: creato version_info.txt (metadati CompanyName/ProductName/FileVersion) + build.bat/build.ps1 aggiornati con --noupx --clean --version-file version_info.txt (riducono molto i flag). README con sezione dedicata (firma Authenticode via SignPath/Certum gratis per OSS; segnalazione falso positivo a Microsoft wdsi/filesubmission; VirusTotal; alternativa .ps1).
- DesktopAgent.jsx: nota AV (data-testid exe-av-note) sotto il download che rassicura ed indirizza al Metodo sicuro .ps1 (non flaggato). Bilingue IT/EN. Verificato via screenshot.
- NB: le mitigazioni build valgono solo dopo RICOMPILAZIONE+ripubblicazione dell'.exe da parte dell'utente. Il v0.4.4 attuale resta flaggato finche non si ricompila/firma/segnala.

### 2026-07-17 (6) - Kit firma OSS + guida trust (per togliere antivirus/SmartScreen)
- agent-build: version_info.txt bump a 0.4.5.0; nuovi file sign.bat (signtool locale per Certum/SimplySign o .pfx), github-workflow-build-sign.yml (GitHub Actions build PyInstaller + firma SignPath Foundation gratis OSS + release), SIGNING_AND_TRUST.md (guida 3 percorsi: A Microsoft false positive gratis 1-3gg; B Certum Open Source cloud ~59EUR/anno firma locale; C SignPath gratis ma richiede sorgente pubblico + GH Actions). README aggiornato con elenco file.
- Ricerca web 2026 verificata: SignPath richiede build automatica via GitHub Actions su repo pubblico OSI-licensed; Certum ~49EUR+IVA cloud SimplySign (persona fisica + ID + video verifica); Microsoft wdsi/filesubmission categoria "Software developer / false positive".
- PENDING utente: (1) ricompilare v0.4.5 con nuovo build.bat e ripubblicare -> poi aggiorno config/agent.js con URL+SHA; (2) firma; (3) segnalazione Microsoft.

### 2026-07-17 (7) - SignPath setup files + unblock immediato (.ps1)
- Utente NON riesce a scaricare l'.exe (Defender blocca il download). Unblock immediato: Metodo sicuro .ps1 gia' in pagina (non flaggato, stessa GUI con -Mode optimize).
- Preparati file pronti-da-committare nel repo pubblico per SignPath: LICENSE (MIT), CODE_SIGNING_POLICY.md (sezione da incollare nel README), SIGNPATH_SETUP.md (guida 5 fasi: commit sorgente+workflow -> apply signpath.org -> config secrets/GitHub App -> tag v0.4.5 build+firma -> collego). Workflow gia' in github-workflow-build-sign.yml. La v0.4.5 firmata viene prodotta dal workflow SignPath (o build manuale).
- PENDING utente: committare i file nel repo, fare domanda SignPath, poi taggare v0.4.5 -> mi manda URL+SHA della release firmata.

### 2026-07-17 (8) - Ottimizzazione performance + decluttering globale (mantenendo lo stile)
- Design blueprint generata in /app/design_guidelines.json (decluttering entro l'estetica FrameForge esistente).
- PERFORMANCE (lighter/faster loading):
  - Lazy-load librerie pesanti con import() dinamico: jspdf + html-to-image in Report.jsx (export PNG/PDF), html-to-image in SessionSummary.jsx -> escono dal chunk iniziale, caricate solo al click. Verificato: export PNG+PDF funzionanti, nessun ChunkLoadError.
  - HealthHistoryCard: isAnimationActive={false} sulle 3 linee. Live.jsx metriche con tabular-nums (anti-jitter durante update rapidi; chart gia' senza animazione).
- DECLUTTER GLOBALE (tutte le pagine in un colpo, senza riscriverle): Layout.jsx <main> ora avvolge l'Outlet in un contenitore max-w-7xl centrato con padding coerente (px-4 sm:px-6 lg:px-8, py-6/8) + overflow-x-hidden. Su schermi larghi il contenuto non si sparpaglia piu' -> pagine piu' calme e leggibili. Stile invariato.
- PRIMITIVES aggiunti a components/hud.jsx: PageContainer, Section, HUDCard, DataMetric (per standardizzare le pagine dense in futuro).
- Verificato via screenshot: Dashboard, Report (+export), Prices/Tracker -> tutte pulite, centrate, stile FrameForge preservato, nessun errore console (solo RUM Cloudflare non correlato). Landing NON toccata.
- Possibile continuare: decluttering di dettaglio per-pagina (raggruppare metriche, ridurre badge) sulle pagine piu' dense usando i nuovi primitives.

### 2026-07-17 (9) - Pre-deploy: fix warning eslint + deploy check PASS
- deployment_agent: PASS, nessun blocco (no secret hardcoded, porte/CORS ok, /health presente, build ok).
- Fix warning react-hooks/exhaustive-deps: BiosRestore.jsx (data memoizzato, hw dep corretta, lang mantenuto con eslint-disable-line perche' e' trigger legittimo per i18n IT/EN) e Commands.jsx (data memoizzato + dep data.gpu). Frontend ora "Compiled successfully!" SENZA warning.
- Live.jsx gia' riordinato (MetricGroup: Prestazioni/Temperature/Memoria&Rete) - blocco precedente risultava gia' risolto.
- PRONTO AL REDEPLOY. Note pre-deploy comunicate all'utente: impostare ADMIN_PASSWORD forte da env in produzione; l'.exe punta di default a forgefps.dev (token dallo stesso backend).
- IN SOSPESO (concordato): decluttering di Tracker.jsx e MyPc.jsx (Live gia' fatto) da fare dopo il deploy.

### 2026-07-17 (10) - Scansione demo REALE (no account) + Guest demo mode (FATTO, test FE 100% iteration_22)
- OBIETTIVO utente: togliere l'account come vincolo per provare l'app + migliorare il funnel (piani Free/Pro/Creator visti dopo).
- SCELTE utente: demo reale = hardware browser + test bufferbloat REALE client-side (Cloudflare); niente AI senza account (consigli a regole); guest mode leggero (sola lettura, dati esempio); gating piani rimandato; net test 100% lato browser (Opzione A).
- DEMO SCAN REALE (components/DemoScan.jsx riscritta, era 100% simulata): step reali -> (1) detectBrowserSpecs() mostra GPU/CPU-thread/RAM/OS veri; (2) lib/netTest.js runNetTest() satura la linea via speed.cloudflare.com/__down (CORS '*') e misura latenza idle vs sotto carico -> voto bufferbloat A+..F + download Mbps; (3) lib/quickAdvice.js buildAdvice() consigli a regole (vendor GPU, thread CPU, RAM, power plan, bufferbloat) costo zero. CTA: 'Registrati' -> /register, 'Esplora la demo' -> /demo. Fallback se rete bloccata. Guard timeout 15s.
- GUEST MODE (pages/DemoApp.jsx, rotta PUBBLICA /demo in App.js): tour sola-lettura con dati esempio, 4 tab (Dashboard health ring 87 + stat + checklist / Live chart recharts / AI Advisor chat con Invia disabilitato / Report Prima-Dopo), banner giallo 'demo dati esempio' + CTA 'Registrati per sbloccare' (demo-unlock-cta, demo-bottom-cta -> /register). Bilingue IT/EN via COPY locale.
- Verificato: testing_agent iteration_22.json = 100% FE. Scan reale eseguito (WebGL GPU, 8 thread, RAM>=8, bufferbloat grade C 45->111ms, 319 Mb), advice render, tutti i tab e CTA ok. Cloudflare fetch confermato raggiungibile con Access-Control-Allow-Origin '*'; nessuna CSP frontend che blocca.
- NB: modifiche SOLO frontend -> per vederle su forgefps.dev serve REDEPLOY. Note minori non bloccanti: warning recharts width(-1) (cosmetico).

### 2026-07-17 (11) - Google Ads: tag + conversioni + Consent Mode v2 (FATTO, redeploy pendente)
- Google tag (gtag.js, ID AW-18329532067) inserito in public/index.html subito dopo <head>.
- CONSENT MODE v2 (GDPR/EEA): default DENIED per ad_storage/ad_user_data/ad_personalization/analytics_storage prima di config; ripristina scelta 'granted' salvata prima del mount React.
- BANNER COOKIE: components/ConsentBanner.jsx (Accetta/Rifiuta + link /privacy-telemetry), bilingue IT/EN, montato globalmente in App.js. Salva scelta in localStorage 'ff_consent' e chiama gtag('consent','update',...). Verificato via screenshot (banner render + accept).
- CONVERSIONI (lib/gtag.js trackConversion): 3 eventi collegati -> signup (Auth.jsx dopo register), demo_scan (DemoScan al completamento), agent_download (DesktopAgent onClick su exe-download-btn e download-agent-btn). Le etichette CONVERSION_LABELS sono VUOTE (placeholder) -> nessun invio finche' l'utente non fornisce le 3 label da Google Ads. In attesa label utente.
- NB: solo frontend -> serve REDEPLOY per attivare su forgefps.dev. Google verifica il tag sul dominio live dopo il redeploy.

### 2026-07-17 (12) - Code review fixes (3 MEDIUM + 2 LOW) su modifiche recenti
- Etichette conversione inserite in lib/gtag.js: signup=N2UNCMDjmtIcEKPtmaRE, demo_scan=RNNxCMPjmtIcEKPtmaRE, agent_download=B9KYCMbjmtIcEKPtmaRE.
- FIX MEDIUM #1 (async cleanup): lib/netTest.js riscritto con AbortController condiviso propagato a tutti i fetch/ping; runNetTest(maxMs, externalSignal) aborta al timeout/unmount; ridotto consumo dati (3 stream x 25MB x 4s invece di 4x50MB x 5s); reader.cancel() rilascia gli stream. DemoScan.jsx: mountedRef + abortRef con cleanup in useEffect, guardie !mountedRef prima di ogni setState, niente trackConversion dopo unmount.
- FIX MEDIUM #2 (bug confermato RAM): quickAdvice.js regex invertita -> ora `/GB/.test(ram) && !/≥8/.test(ram)` mostra il consiglio RAM per <8GB. Verificato via Node (4GB=true, ≥8GB=false).
- FIX MEDIUM #3 (GDPR PostHog): index.html posthog.init ora con opt_out_capturing_by_default:true + blocco che fa opt_in solo se ff_consent='granted'. lib/gtag.js setConsent() specchia la scelta su PostHog (opt_in/opt_out). Ora sia Google Ads (Consent Mode v2) sia PostHog rispettano il banner cookie.
- FIX LOW: og:url -> https://forgefps.dev/ (era dominio preview); consumo dati net test ridotto.
- Verifica: frontend compila pulito; logica pura testata via Node; consent gating confermato nell'HTML servito. NB: tutto frontend -> serve REDEPLOY.

### 2026-07-17 (13) - Trust: TrustBar + badge VirusTotal + FAQ sicurezza (FATTO, test FE iteration_23)
- Obiettivo utente: aumentare la fiducia del cliente. Scelte: badge VirusTotal + trust bar, sezione FAQ. Inoltre l'agente mantiene aggiornato il CHANGELOG ad ogni novita' degna di nota.
- TrustBar (components/TrustBar.jsx): 6 segnali (VirusTotal link a virustotal.com/gui/file/<sha256>, SHA256 verificabile, Open source MIT link repo, 100% reversibile, nessun codice remoto, local-first). Aggiunta su Landing (dopo la stats strip) e su Security (sotto hero). config/agent.js: aggiunto AGENT_REPO_URL.
- SecurityFaq (components/SecurityFaq.jsx): accordion "E' sicuro?" con 6 domande (rovina PC, falso positivo AV, dati/password, come annullo, admin, prova senza download), bilingue. In Security.jsx prima di SecureInstaller.
- DesktopAgent.jsx: link 'Verifica su VirusTotal' (exe-virustotal) accanto a SHA256.
- Changelog.jsx: nuovo entry v0.4.5 (2026-07-17) in cima con demo reale, badge VirusTotal, FAQ, Consent Mode.
- Test iteration_23: 5/6 pass; unico fail (TrustBar non renderizzata su /security) RISOLTO riapplicando il render (line 67), verificato compile + parita' con Landing (passata). Nota non bloccante: 401 da /auth/me su pagine pubbliche (pre-esistente).
- NB: tutto frontend -> serve REDEPLOY per forgefps.dev. POLICY: aggiornare Changelog.jsx ad ogni feature/fix degna di nota.

### 2026-07-17 (14) - Deployment readiness check + fix blocker
- deployment_agent run 1: FAIL, 2 blocker critici: (a) .gitignore bloccava .env (righe 100-102: .env/.env.*/*.env) -> RIMOSSE (restano credentials.json, *.key, .credentials, test_credentials.md ignorati); (b) CORS_ORIGINS al dominio preview -> cambiato a "*" in backend/.env.
- deployment_agent run 2: WARN (nessun blocker critico). WARN CORS: get_cors_origins() filtra "*" e ritorna [FRONTEND_URL] -> CORRETTO e VOLUTO perche' CORSMiddleware usa allow_credentials=True (cookie httpOnly) e il wildcard "*" e' vietato dai browser con credenziali. In prod il platform sostituisce FRONTEND_URL con forgefps.dev. NON modificato (romperebbe l'auth). WARN stats projection (products.py:122) = micro-ottimizzazione non bloccante, non toccato.
- Backend riavviato, login 200, /health a livello app OK. PRONTO AL REDEPLOY (WARN non bloccanti).

### 2026-07-17 (15) - FASE A: Motore di Boost ADATTIVO + 9 nuovi tweak (35 totali) (FATTO, 162/162 test backend)
- Piano approvato dall'utente: A (boost adattivo) -> C (benchmark avanzato + spiegazione AI) -> B (game booster real-time).
- ps_agent.py: nuova Get-HwProfile ($script:HW: laptop/ram/ssd/win11/gpu) + campo `fit` per tweak (ok | note: | warn: | skip:).
  - GUI: header mostra "PC RILEVATO: Desktop|Laptop, GPU, RAM, SSD/HDD"; card con nota ADATTIVO colorata; skip=checkbox disabilitata; warn=deselezionata di default; preset saltano i tweak skip; fallback non-GUI salta skip/warn.
  - Do-Power adattivo: laptop -> High Performance (non Ultimate), niente USB/PCIe power off globale.
  - 9 NUOVI TWEAK: fse (Fullscreen Optimizations OFF), power_throttling (desktop), standby_clear (purge RAM standby via NtSetSystemInformation, C# inline compilato/verificato con pwsh), nic_power (PnPCapabilities=24 + InterruptModeration off), paging_exec (RAM>=16GB), sysmain (solo SSD), trim (solo SSD), ntfs (disablelastaccess con backup+restore dedicato), edge_preload.
  - Regole adattive: amd_ulps/nvidia_tel ora skip per GPU diversa; usb/hibernate/nic_power/power_throttling warn su laptop.
  - Sintassi PS validata con pwsh 7.4.6 (Parser API: SYNTAX OK) + C# Add-Type compilato OK.
- routers/profiles.py: TWEAK_CATALOG 26->35, template aggiornati (fse in tutti, nic_power/paging_exec nei competitivi/stream).
- forgefps_agent.py v0.6.0: apply_all_tweaks adattivo (laptop/ram/ssd) + FSE + QoS + PowerThrottling + DisablePagingExecutive + SysMain/TRIM + Edge preload.
- Frontend: Landing "35/35 adaptive tweaks", DesktopAgent "35 tweak adattivi".
- Test aggiornati (erano stali, non regressioni): $MODE ora via -Mode CLI, PresentMon 2.4.1, template ids attuali, DB_NAME test_database, password admin da test_credentials.md. TUTTI i 162 test passano.
- ESCLUSI di proposito (sicurezza): disattivazione VBS/HVCI e mitigazioni Spectre (guadagno FPS ma riducono la sicurezza -> contro la promessa FrameForge).

## PROSSIMI PASSI CONCORDATI
- P0 FASE C: Benchmark avanzato (latenza DPC, test disco reale, jitter ping, punteggio 0-100 storico) + endpoint /api/benchmark/explain con Claude che spiega i risultati in italiano.
- P0 FASE B: Game Booster real-time (watcher processi giochi, priorita' HIGH, sospensione app pesanti, purge standby, ripristino a fine sessione).
- P1: PyInstaller --onedir (fix falsi positivi AV), Alert storico salute.

### 2026-07-17 (16) - FASE C (Benchmark Avanzato + AI) e FASE B (Game Booster opt-in) (FATTO, testing_agent iter 25: 100%)
- FASE C Benchmark v2 (ps_agent.py Run-Benchmark + forgefps_agent.py parita'):
  - Nuove metriche: dpc_ms (latenza scheduler p95, proxy DPC), disco 256MB WriteThrough (scrittura REALE no cache), iops_4k (scritture casuali 4K sincrone), jitter_ms (10 ping), boot_s (event log Diagnostics-Performance 100), SCORE 0-100 pesato (cpu.20 ram.10 diskW.15 diskR.10 iops.10 dpc.15 ping.15 jitter.05). overall legacy mantenuto.
  - POST /api/benchmark/explain {lang}: Claude spiega prima/dopo in italiano (ai_engine.explain_benchmark, BENCH_SYSTEM), cache in db.benchmark_explanations per (user, bench_ts, lang), rate limit solo su generazione.
  - MyPc.jsx: card score/dpc/iops/jitter/boot, ScoreSparkline (storico SCORE, >=2 benchmark), bottone bench-explain-btn + pannello bench-explanation (strip heading markdown).
- FASE B Game Booster (MAI automatico al 100%, per scelta esplicita utente):
  - Mode 'booster' in ps_agent.py: rileva gioco via PresentMon FPS (admin) o finestra fullscreen-foreground (FFWin C#); al rilevamento COUNTDOWN 5s con tasto per ANNULLARE; azioni configurabili: priorita' HIGH, piano energetico temporaneo (ripristinato), chiusura app (default NESSUNA), purge RAM standby; a fine partita ripristina e invia boost_session al backend; Ctrl+C ripristina (finally).
  - Backend: GET/PUT /api/booster (booster_settings), GET /api/booster/sessions (ultime 10), report-specs accetta boost_session -> db.boost_sessions; placeholders __BOOSTER_APPS__/_POWER_/_PRIORITY_/_PURGE_ iniettati in _build_agent_script.
  - Games.jsx: card Game Booster con SecureRunBlock mode=booster, config 3 toggle + gruppi app, sessioni recenti. DesktopAgent.jsx: mode aggiunto. i18n it/en completo.
- LEZIONE: search_replace di 2 blocchi grandi sullo stesso file nello stesso batch ha corrotto ps_agent.py (frammento oltre la chiusura ''')-> git checkout e riapplicati UNO ALLA VOLTA con ast.parse + pwsh Parser dopo ognuno. pwsh 7.4.6 arm64 disponibile in /tmp/pwsh/pwsh.
- Test: sintassi PS OK, 11/11 pytest nuovi (test_booster_bench.py), flussi UI verificati dal testing agent, regressione prematch OK.

## PROSSIMI PASSI
- P1: PyInstaller --onedir (falsi positivi AV) + testi per vendor AV.
- P1: Alert storico salute (notifica se health score sotto soglia storica).
- P2: Report PDF completo; condivisione SCORE benchmark (immagine/link social).
- P3: Stripe billing, conversioni avanzate Google Ads, testimonianze + stelle GitHub.

### 2026-07-17 (17) - Rebuild kit v0.6.0 preparato (build resta --onefile su richiesta utente)
- version_info.txt: 0.4.5 -> 0.6.0 (metadati exe). Docs tag esempio v0.4.5 -> v0.6.0 (SIGNING_AND_TRUST, SIGNPATH_SETUP, workflow).
- README.md agent-build: sezione "Novita v0.6" (boost adattivo + benchmark v2).
- NUOVO /app/agent-build/REBUILD_v0.6.0.md: checklist 5 passi (build.bat -> test -> release GitHub v0.6.0 -> aggiornare frontend/src/config/agent.js con URL+SHA256+versione+data -> VirusTotal/segnalazione FP).
- Da fare DALL'UTENTE dopo la build: aggiornare config/agent.js con lo SHA256 reale e fare Deploy. --onedir rimandato (P1 backlog).

### 2026-07-18 (18) - v0.6.0 released + GUI moderna via Edge --app (Option C) + fix mismatch UI
- **Rebuild v0.6.0 completato dall'utente**: build.bat/version_info.txt/forgefps_agent.py forniti in chat (mancanti nel repo locale per push GitHub bloccato). Release pubblicata: https://github.com/WjRKO/ForgeFPS/releases/tag/v0.6.0, SHA256 `18645e38ef463cb7a1e9afff40e2194416518589be080840654b4dc9aed45a1c`, size ~9 MB. Testata OK.
- **frontend/src/config/agent.js aggiornato**: URL/SHA256/VERSION/DATE su v0.6.0 (2026-07-18). Verificato HTTP 302 -> 200 su download.
- **Fix mismatch UI /landing**: `trust_tweaks_v` in i18n.js (IT+EN) era 26 -> aggiornato a **35** per allinearlo al catalogo `ps_agent.py $script:TWEAKS` (35) e `routers/profiles.py TWEAK_CATALOG` (35). DesktopAgent.jsx e Landing.jsx L240 gia' corretti.
- **Diagnosticato falso allarme `getaddrinfo failed`**: era glitch DNS transitorio sul PC utente. Il UA `FrameForge-Agent` gia' passa Cloudflare (verificato); default `Python-urllib` invece e' bloccato con 403. Nessuna modifica al codice necessaria.
- **NUOVA GUI moderna (Option C, ps_agent.py)**:
  - `function Show-WebGui`: HTTP listener locale su `127.0.0.1` con **porta random** + **session token 48-char**, ogni endpoint richiede `?tk=` o header `X-FF-Token`. Bind SOLO su loopback.
  - Lancia `msedge.exe --app=http://127.0.0.1:PORTA/?tk=TOKEN` in modalita chromeless (profilo Edge isolato in %TEMP%\forgefps-gui\edge-profile).
  - HTML/CSS/JS embedded (~29 KB): dark theme allineato al sito web (`#0a0a0f` bg, `#e5ff00` accent), layout responsive con grid auto-fill (min 360px card), tab per categoria, ricerca full-text, preset chip (Competitivo/Streaming/Completo/Nessuno), animazioni CSS.
  - Endpoint locali: GET /, /api/state, /api/log?since=N; POST /api/apply {ids,benchmark}, /api/apply-one {id}, /api/restore, /api/close.
  - Log console con polling 400 ms, indicatore "applying", toast di conferma, backup badge live.
  - **Fallback automatico** a `Show-Gui` (WinForms legacy) se msedge.exe non presente.
  - Branch `optimize` prova prima Show-WebGui poi Show-Gui poi headless.
- **CHANGELOG.md creato** in /app/CHANGELOG.md (Keep a Changelog format) con storico v0.5 -> v0.6.0 -> Unreleased.
- **workflow senza SignPath creato**: /app/agent-build/github-workflow-build-nosign.yml (per quando SignPath Foundation e' in attesa di approvazione).

## PROSSIMI PASSI
- Utente deve rigenerare token PC (leaked in chat) e ridiploiare frontend per pubblicare i valori v0.6.0 in produzione.
- P0: PyInstaller --onedir (falsi positivi AV Defender "dropper") + testi false-positive vendor.
- P1: Alert storico salute (notifica quando score sotto soglia).
- P2: Report PDF completo (grafici storici + checklist); condivisione SCORE benchmark sui social.
- P3: Stripe billing, conversioni avanzate Google Ads, testimonianze + stelle GitHub.
- Possibile: telemetria opt-in sulla nuova WebGui per capire quale % di utenti usa Edge vs WinForms fallback.

### 2026-07-18 (19) - Task A+B: Guida in-app + Tour interattivo onboarding
- **Pagina /guida** (Guide.jsx, ~230 righe): 5 walkthrough (Primo boost, Gaming competitivo, Streaming OBS, Benchmark, Ripristino) con badge Sul sito/Sul PC, blocco codice copiabile PowerShell (CopyBtn), TOC iniziale, Tips per guida, CTA login/agent. Bilingue IT/EN. Route `/guida` (canonical) + `/guide` (redirect EN). Link "Guida"/"Guide" aggiunto in MarketingChrome NAV.
- **Tour onboarding** (react-joyride v3.2.0, named import `{ Joyride }`): OnboardingTour.jsx montato in Layout.jsx. 8 step su sidebar (My PC, Advisor, Network, Desktop agent, Gaming, Notifications, Account). Auto-start su `/app` la prima volta (localStorage `ff_tour_done_v1`). Personalizzato con palette FrameForge (accent #E5FF00, tooltip dark). Skippabile, no close X. Handler window event `ff:tour:start` per riavvio.
- **Card "Rifai il tour"** aggiunta in Account.jsx sotto la MFA (icona HelpCircle, testid `restart-tour-btn`, rimuove flag + dispatch evento).
- **i18n**: nuova chiave `tour.*` con 24 stringhe IT+EN (welcome, per ogni step titolo/contenuto, back/next/last/skip/close/restart).
- **Changelog pubblico** aggiornato con v0.6.1 (2026-07-18).
- **CHANGELOG.md** interno: sezione Unreleased estesa con nuove feature.
- Bug incontrato e risolto: `react-joyride@3.2.0` non ha default export, va importato come `{ Joyride }`.
- Validazione: webpack "Compiled successfully!" dopo il fix; ESBuild OK su tutti i 7 file modificati.

## FILE MODIFICATI/CREATI (sessione 19)
- CREATO: `/app/frontend/src/pages/Guide.jsx`
- CREATO: `/app/frontend/src/components/OnboardingTour.jsx`
- MOD: `/app/frontend/src/App.js` (route + lazy import)
- MOD: `/app/frontend/src/components/MarketingChrome.jsx` (nav item)
- MOD: `/app/frontend/src/components/Layout.jsx` (mount tour)
- MOD: `/app/frontend/src/pages/Account.jsx` (restart-tour card)
- MOD: `/app/frontend/src/pages/Changelog.jsx` (v0.6.1 entry)
- MOD: `/app/frontend/src/i18n.js` (tour.* strings IT+EN)
- MOD: `/app/frontend/package.json` + yarn.lock (react-joyride)
- MOD: `/app/CHANGELOG.md`, `/app/memory/PRD.md`

### 2026-07-18 (20) - Integrazione Discord completa (A+B+C)
- **A) Template community**: /app/docs/DISCORD_SERVER_SETUP.md con 20 canali, 6 ruoli, permessi @everyone, testi welcome/rules, server onboarding, bot moderazione, obiettivi Server Boost.
- **B) Bot persistente discord.py 2.7.1**: /app/backend/discord_bot.py come processo supervisor separato (`/etc/supervisor/conf.d/discord-bot.conf`). Connesso come `FrameForge#0798` id 1528010986928214156. 5 slash commands sincronizzati nel guild 1528014742386376735: /mypc /benchmark /leaderboard /link /help. Handler on_member_join con welcome DM + auto-role.
- **B2) OAuth account linking**: /app/backend/routers/discord.py con /connect /callback /status /disconnect. Scope `identify guilds.join`, state CSRF 10min TTL in `discord_oauth_states`. Salva `discord_user_id/username/avatar/linked_at` nel user. Chiama `PUT /guilds/{id}/members/{user_id}` per aggiungerlo al server + role opzionale. Idempotente su re-link.
- **C) Webhooks outbound**: /app/backend/services/discord_webhooks.py con post_release/post_price_drop/post_milestone. Testati: 204 su entrambi (#changelog-automatico + #price-drops).
- **Frontend**: card Discord in Account.jsx con stato dinamico (linked/unlinked). i18n IT/EN sezione `account.discord_*` (12 stringhe).
- **Deps**: aggiunto discord.py 2.7.1 in requirements.txt.
- **Configurazione**: DISCORD_ROLE_BOOSTED_ID lasciato vuoto in .env - assegnazione ruolo skippata se non impostato (utente completera' dopo aver creato ruolo con hierarchy corretta).

## FILE MODIFICATI/CREATI (sessione 20)
- CREATO: /app/backend/routers/discord.py
- CREATO: /app/backend/services/__init__.py
- CREATO: /app/backend/services/discord_webhooks.py
- CREATO: /app/backend/discord_bot.py
- CREATO: /etc/supervisor/conf.d/discord-bot.conf
- CREATO: /app/docs/DISCORD_SERVER_SETUP.md
- MOD: /app/backend/.env (aggiunte 10 DISCORD_* env)
- MOD: /app/backend/requirements.txt (discord.py)
- MOD: /app/backend/server.py (include router discord)
- MOD: /app/frontend/src/pages/Account.jsx (card Discord)
- MOD: /app/frontend/src/i18n.js (account.discord_* IT/EN)
- MOD: /app/CHANGELOG.md, /app/memory/PRD.md

## CREDENZIALI DISCORD LEAKED IN CHAT (da rigenerare)
User ha postato secrets pubblici (CLIENT_SECRET, BOT_TOKEN, WEBHOOK URLs). Deve rigenerarli tutti dopo il testing.


### 2026-07-18 (21) - Preview GUI Edge nella sticky card Desktop Agent
- **AgentPreview.jsx** (`/app/frontend/src/components/AgentPreview.jsx`): componente riutilizzabile che mostra la preview della GUI live sopra il pulsante "Scarica FrameForge (.exe)" nella sticky card di `/app/desktop`.
- **Fallback a 3 livelli**:
  1. `<video autoPlay muted loop playsInline>` → `/assets/agent-preview.mp4` (timeout 1.5s se non parte)
  2. `<img>` → `/assets/agent-preview.gif`
  3. Mock CSS animato (finestra "FrameForge Agent" con title bar macOS-style, tab sidebar Gaming/Latenza/Rete/Sistema, 6 tweak che appaiono uno alla volta con badge "GIÀ ATTIVO", progress bar arcobaleno)
- Badge overlay "LIVE GUI PREVIEW" con dot pulsante top-left, aspect 16:10, testid `agent-preview-card` / `agent-preview-video` / `agent-preview-gif` / `agent-preview-mock`.
- Creata `/app/frontend/public/assets/` con `README.md` che spiega come registrare la GUI reale (ffmpeg one-liner: H.264 800x-2, fps 24, crf 28, muted → ~2MB per 8s).
- **MOD**: `/app/frontend/src/pages/DesktopAgent.jsx` — import + `<AgentPreview>` inserito nella sticky panel appena prima del bottone `[data-testid="exe-download-btn"]`.
- Verificato tramite screenshot Playwright login → `/app/desktop`: card presente, stage `mock` che rende la finestra animata con progress bar e tweak "GIÀ ATTIVO" a cascata.

## FILE MODIFICATI/CREATI (sessione 21)
- CREATO: /app/frontend/src/components/AgentPreview.jsx
- CREATO: /app/frontend/public/assets/README.md
- MOD: /app/frontend/src/pages/DesktopAgent.jsx (import + mount AgentPreview)
- MOD: /app/memory/PRD.md

### 2026-07-18 (22) - Redesign Dashboard "Command Center" completo
- **Dashboard.jsx** completamente riscritto (120 → 743 righe): layout 2 colonne con sticky panel a destra, coerente con `/app/desktop`.
- **Greeting contestuale**: mostra health score se PC connesso, altrimenti risparmio totale, altrimenti fallback "Pronto a boostare?".
- **LEFT (main)**: 
  - `PcHeroCard` con `HealthRing` grande, badge hardware CPU/GPU/RAM, contatori issue/warn colorati, CTA "Ottimizza ora" con colore adattivo (rosso se score<55, giallo altrimenti). Se PC non connesso → EmptyState con CTA "Connetti il PC".
  - `BenchmarkCard` con score latest, delta % vs precedente, `Sparkline` ultimi 8 benchmark, bottone "Condividi su Discord" (attivo solo se Discord linkato, usa `/api/discord/share-score`).
  - `ActivityFeed` unificato: merge cronologico di price drops (`/api/notifications`), ultimo benchmark, nuova release agent (mostrato solo se `localStorage.ff_agent_seen_v0.6.0` è false). Ordinato desc, top 6.
  - `RecentProductsCard` compatto con empty state migliorato.
- **RIGHT (sticky)**:
  - `OnboardingChecklist` dinamico: 5 step (Connect PC, First benchmark, Track a product, Link Discord, Enable 2FA), con checkmark verde, strikethrough sui completati, progress bar animata a gradient. Si nasconde a 5/5.
  - `QuickActionsCard`: griglia 2×3 con Advisor/Agent/Games/Tracker/Builds/Network.
  - `DiscordCard`: linked → avatar + username + link server, unlinked → CTA "Link account (30s)".
  - `AgentCard`: mostrato solo se l'utente non ha ancora cliccato il download di questa versione (badge "NEW", CTA Download, marca `ff_agent_seen_v0.6.0` in localStorage on click).
- **Empty states migliorati**: `HeroEmpty` giant CTA card (3 azioni numerate) mostrato solo se l'utente è brand new (no specs, no products, no builds, no chat sessions). Nasconde stat card generici.
- **i18n**: aggiunte 40+ chiavi nuove sotto `dashboard.*` (IT + EN): greet_health/greet_saved/greet_ready, pc_no_specs_*, bench_*, onboard_*, discord_*, agent_*, feed_*, hero_empty_*, cta_*.
- **APIs consumate**: `/api/stats`, `/api/products`, `/api/pc-specs`, `/api/pc-health`, `/api/pc-benchmark`, `/api/discord/status`, `/api/notifications`, `POST /api/discord/share-score`.
- Verificato con Playwright (login admin + `/app`): tutti i 7 testid principali presenti, zero console errors, screenshot mostra Health Ring 38/CRITICO in rosso con CTA rossa adattiva, benchmark 650 pts con sparkline, feed attività funzionante, onboarding 3/5 con progress bar, Discord unlinked CTA visibile, Agent NEW badge visibile.

## FILE MODIFICATI/CREATI (sessione 22)
- REWRITE: /app/frontend/src/pages/Dashboard.jsx (120 → 743 righe)
- MOD: /app/frontend/src/i18n.js (dashboard.* IT+EN, +40 chiavi)
- MOD: /app/memory/PRD.md

### 2026-07-19 (23) - v0.6.4 + v0.6.5: AI Diagnostics + Learning Loop + Multi-modal Chat + Discord auto-sync
#### v0.6.4 - Discord bot: mini-guide, apply-creator flow, sync ruoli automatico
- `/help` riscritto con embed rich (Onboarding · Gaming · Creator · Admin · Link utili). Nuovi `/come-iniziare`, `/ruoli`, `/canali`.
- `/apply-creator <url>`: validazione URL (twitch/youtube/kick), persistent `CreatorReviewView` (bottoni ✅Approva / ❌Rifiuta con custom_id fissi che sopravvivono ai restart), cooldown 7 giorni post-rifiuto (env `DISCORD_CREATOR_REAPPLY_DAYS`), anti-doppio-submit (1 pending/utente), DM esito con ruolo Creator Verified assegnato. Env aggiunti: `DISCORD_ROLE_CREATOR_VERIFIED`, `DISCORD_CHANNEL_CREATOR_REVIEW`.
- **Sync automatico ruolo Boosted PC**: periodic task del bot ora sync sia Pro sia Boosted (retroattivamente se OAuth flow ha fallito). Refactor helper: `_sync_role()` (generico) + `_sync_all_roles_for_member()`.
- `/set-plan <user> <plan>` admin command con `defer(ephemeral=True)` per evitare timeout Discord 3s.
- `/announce-release <version> [force]` admin per forzare annuncio release + helper `announce_release_by_version()` in `services/release_announcer.py`.
- **Auto-detect ambiente release announcer**: check `HOSTNAME.startswith("agent-env-")` → preview skippa automatico, prod parte. Override manuale con `RELEASE_ANNOUNCER_ENABLED=true/false`.
- **Fix CORS wildcard**: `settings.get_cors_origins()` filtrava `*` producendo lista vuota → nuovo `get_cors_origin_regex()` usa `allow_origin_regex=".*"` compatibile con `allow_credentials=True`.
- **Fix email footer**: `hello@forgefps.dev` non attiva → `forgefps.support@gmail.com` con click-to-copy Sonner toast.
- **Query non ottimizzate**: `/api/stats` ora fetcha solo 2 field da products; `/api/products/{id}` limita history a 200 record (era 1000).
- Nuove collezioni Mongo: `diagnoses` (già preesistente), `planned_actions`, `creator_applications`.

#### v0.6.5 - AI Diagnostics + Learning Loop + Multi-modal Chat
- **AI Diagnosi PC** (`POST /api/advisor/diagnose`): Claude Sonnet in modalità one-shot con schema JSON strutturato → `{summary, actions:[{title, description, impact, difficulty, kind, cta, priority, verify}]}`. Nuovo `ai_engine.one_shot_advisor()`. Helper `_enrich_specs_for_ai()` in `routers/advisor.py` arricchisce specs con benchmark history (ultimi 5) + tracker summary (count + total_saved).
- **Persistenza diagnosi**: `GET /api/advisor/diagnose/latest` + refetch on-mount in `DiagnosePanel`. Badge "generata Xh fa".
- **Feedback thumbs 👍/👎**: `POST /api/advisor/feedback` (target_type/target_id/action_title/rating/comment). Upsert idempotente su diagnose actions + chat messages.
- **Applied Tweaks (personalization memory)**: `POST /api/advisor/applied-tweaks` toggle + `GET` list. Slug auto dal titolo. `_get_user_profile()` passa la lista all'AI come contesto → non riproporrà mai un tweak "già attivo".
- **Community insights (RAG-lite)**: `_community_insights()` aggrega top 5 tweak applicati da utenti con hardware CPU/GPU simile (Counter dei titoli) → iniettati nel prompt come few-shot examples.
- **Outcome tracking**: `GET /api/advisor/outcome` calcola delta benchmark tra ultima diagnosi e primo benchmark successivo. Badge nel header diagnosi.
- **Verify hint**: campo obbligatorio `verify` in ogni action. Frontend: sezione espandibile "Come verificare se è già attivo" con testo mono-space.
- **Chat multi-modale (Claude Vision)**: `stream_advisor` accetta `image_data_url` (data URL base64) → `UserMessage(text=..., file_contents=[ImageContent(image_base64=...)])`. Frontend: paperclip button, preview con X, immagine salvata nella bolla user message. Nuovi `/api/advisor/chat` accetta `image` parameter.
- **Coach modes**: 5 personas (default/fps/streaming/troubleshoot/build) via `COACH_PROMPTS` che appende suffix al system prompt. Frontend: dropdown in cima chat, preferenza salvata in `localStorage.advisor_mode`.
- **Follow-up chips**: `POST /api/advisor/followups?session_id=` + `ai_engine.generate_followups()` chiede all'AI 3 domande brevi contestuali. Frontend: chip cliccabili sotto ultima risposta AI.
- **Message actions**: thumbs, copia (clipboard API + Check animation), rigenera (rimuove ultima bolla AI e re-invia ultima query utente). Compaiono in hover.
- Nuove collezioni Mongo: `ai_feedback`, `applied_tweaks`.

## FILE MODIFICATI/CREATI (sessione 23)
- MOD: /app/backend/ai_engine.py (`one_shot_advisor`, `generate_followups`, COACH_PROMPTS, `explain_benchmark`, ImageContent support)
- MOD: /app/backend/routers/advisor.py (diagnose/feedback/outcome/applied-tweaks/followups endpoints, `_enrich_specs_for_ai`, `_community_insights`)
- MOD: /app/backend/routers/discord.py (webhook release announcer HOSTNAME detection)
- MOD: /app/backend/discord_bot.py (mini-guide slash commands, apply-creator persistent view, sync ruoli automatico)
- MOD: /app/backend/services/release_announcer.py (HOSTNAME detection, announce_release_by_version)
- MOD: /app/backend/settings.py (`get_cors_origin_regex`)
- MOD: /app/backend/server.py (CORS regex middleware)
- MOD: /app/frontend/src/pages/Advisor.jsx (chat multi-modal, coach dropdown, chips, message actions)
- CREATO: /app/frontend/src/components/DiagnosePanel.jsx
- MOD: /app/frontend/src/i18n.js (advisor.* + coach + feedback)
- MOD: /app/frontend/src/pages/Landing.jsx + MarketingChrome.jsx (footer extras + live Discord)
- CREATO: /app/frontend/src/components/FooterExtras.jsx
- CREATO: /app/frontend/src/pages/Terms.jsx
- MOD: /app/data/releases.json (v0.6.4, v0.6.5)
- MOD: /app/frontend/src/pages/Changelog.jsx (entries v0.6.4, v0.6.5)
- MOD: /app/CHANGELOG.md (Unreleased → 0.6.5 promosso)
- CREATO: /app/memory/ROADMAP.md (P0/P1/P2/P3 prioritized)
- MOD: /app/memory/PRD.md (sessione 23)

### 2026-07-19 (24) - Code review Important actions completate
- **Backend refactor**:
  - `helpers.py::compute_health()`: passata da complessità 37 a ~10 usando `_HEALTH_NUMERIC_CHECKS` (registry di 7 check numerici) + `_HEALTH_TOGGLE_CHECKS` (2 boolean) + `_numeric_status()` helper + `_score_from_lost()` helper. Le closure `check`/`toggle_check` eliminate.
  - `helpers.py::specs_to_text()`: passata da complessità 28 a ~6 estraendo `_cpu_line/_gpu_line/_ram_line/_motherboard_line/_platform_line/_monitor_line` + `_line_with_extras`.
  - `discord_bot.py::_decide()`: passata da 18 a ~6 estraendo `_load_application/_resolve_applicant/_persist_decision/_assign_creator_role/_notify_applicant/_update_review_message`.
  - `discord_bot.py::cmd_apply_creator()`: passata da 19 a ~10 estraendo `_check_creator_reapply_cooldown/_resolve_review_channel/_build_creator_review_embed`.
  - `auth.py::login()`: complessità login handler ridotta estraendo `_enforce_login_lockout/_record_failed_login/_consume_mfa_recovery_code` (helper module-level testabili).
- **Frontend refactor**:
  - `DiagnosePanel.jsx`: 462→490 righe totali ma main component ~200 righe (era 400+). Sub-componenti estratti nello stesso file: `DiagnoseEmpty`, `DiagnoseHeader`, `DiagnoseAction`. API pubblica invariata.
  - `useMemo` aggiunto per 3 filter/map chain: `Games.jsx::recTweakNames`, `MyPc.jsx::shownSpecKeys`, `Profiles.jsx::catalogByCat`.
  - Sostituiti `key={index}` con `key` stabili (`key={n}`, `key={a.title || i}`) in Games/Profiles/DiagnosePanel dove il valore era già unico.
  - `Profiles.jsx`: empty catch blocks → `console.error("... failed", e)`.
- **Validazione**:
  - `python3 -c "from helpers import compute_health, specs_to_text"`: SCORE 74 / GRADE Buono / 10 checks (10 attesi) → OK
  - pytest suite: 75/75 verdi (advisor + agent_script + secure_ps + alerts_fps + booster_bench + live_profiles + account_endpoints)
  - Discord bot supervisor: RUNNING, 11 slash commands sincronizzati, sync loop attivo
  - curl login OK/FAIL → 200 e 401 corretti
  - Playwright: Advisor renderizza (5 azioni diagnose, coach FPS mostra domande specifiche), MyPc renderizza (Health 38, spec cards, benchmark)
- **Falsi positivi confermati (nessuna azione)**:
  - `ps_agent.py:1623` "hardcoded secret" = `const TOKEN = "__TOKEN__"` placeholder sostituito runtime con session token 48-char
  - `i18n.js:252,754` "hardcoded API keys" = stringhe UI `password: "Password"` (label form login IT/EN)
  - `is None/True/False` in tests = idiomi Python corretti, NON `is 0`/`is "str"`
- **Rimandato al backlog dedicato**:
  - Split `Games.jsx` (405 righe), `Advisor.jsx` (328 righe) — richiedono task dedicato con testing per non rompere data-testid
  - 51 posti con array-index keys residui (fatti solo quelli sui file toccati)
  - 30+ nested ternaries e 60+ hook deps warning — sono warning ESLint non bug attivi, richiedono task per-file

## FILE MODIFICATI (sessione 24)
- MOD: /app/backend/helpers.py (compute_health + specs_to_text refactor con registry pattern)
- MOD: /app/backend/discord_bot.py (_decide + cmd_apply_creator split in helper methods)
- MOD: /app/backend/auth.py (login handler + 3 helper module-level)
- MOD: /app/backend/desktop_agent.py (shell injection fix batch precedente)
- MOD: /app/frontend/src/components/DiagnosePanel.jsx (split in 3 sub-componenti)
- MOD: /app/frontend/src/pages/Games.jsx (useMemo recTweakNames + key stabili)
- MOD: /app/frontend/src/pages/MyPc.jsx (useMemo shownSpecKeys)
- MOD: /app/frontend/src/pages/Profiles.jsx (useMemo catalogByCat + console.error + key stabili)
- MOD: /app/memory/PRD.md

### 2026-07-19 (25) - Refactor batch 2 completato
- **Split `Advisor.jsx`** (328→170 righe main + 4 sub-componenti in-file): `CoachSelector`, `EmptyChatSuggestions`, `ChatBubble` (con `TypingIndicator`), `ChatInput`. Rimozione codice duplicato, API pubblica invariata, tutti i data-testid preservati (`coach-mode-*`, `suggestion-*`, `msg-thumb-up-*`, `msg-copy-*`, `msg-regen`, `chat-input`, `chat-send-btn`, `image-attach-btn`, `image-preview`, `image-remove`, `followup-*`).
- **Hook deps (top 4 warnings)**: Dashboard.jsx, Live.jsx (2 effect), Games.jsx, Profiles.jsx — aggiunti `eslint-disable-next-line react-hooks/exhaustive-deps` con **commento esplicativo** (setters stabili / refs / one-shot mount init). Non sono bug: le "missing deps" flaggate erano response fields destructured (`data`, `available`) o setters stabili React garantisce.
- **Empty catch → console.error**: Live.jsx telemetry poll + agent-token load + alerts load. Dashboard.jsx catch già intenzionalmente non silenzianti (setState({})).
- **Nested ternaries** in `MyPc.jsx::BenchmarkCard` estratti in helper: `deltaIcon(delta)`, `cellBorderClass(key)`, `valueClass(key)`, `shareIcon()`, `shareLabel()`. `ScoreRing::color` estratto in `scoreColor(s)` con `if/return` chain.
- **Validazione**: sintassi JSX OK su tutti i file toccati (Advisor, Games, Live, Dashboard, Profiles, MyPc). Pytest 75/75 verdi. Playwright: Dashboard render (Health 38, Bench 650, Onboarding 3/5, Discord, Agent NEW), MyPc render (benchmark-card + bench-share-btn testid presenti), Advisor render (coach-troubleshoot + diagnose-result testid presenti).

## FILE MODIFICATI (sessione 25)
- MOD: /app/frontend/src/pages/Advisor.jsx (split in 4 sub-componenti in-file: CoachSelector/EmptyChatSuggestions/ChatBubble/ChatInput)
- MOD: /app/frontend/src/pages/Live.jsx (console.error + eslint-disable con commento)
- MOD: /app/frontend/src/pages/Dashboard.jsx (eslint-disable con commento)
- MOD: /app/frontend/src/pages/Games.jsx (console.error + eslint-disable con commento)
- MOD: /app/frontend/src/pages/Profiles.jsx (eslint-disable con commento)
- MOD: /app/frontend/src/pages/MyPc.jsx (nested ternaries estratti in 5 helper)
- MOD: /app/memory/PRD.md

### 2026-07-20 (27) - Enhancement Backup panel + Step 1 agent-authed profiles
- **`GET /api/agent/profiles`** in `routers/pc.py`: nuovo endpoint agent-authenticated via `X-Agent-Token` (stesso pattern collaudato di /api/agent/report-specs, /api/agent/telemetry). Ritorna `{profiles, templates, catalog}`. Testato end-to-end con curl: 200 OK con auth valida, 401 con auth invalida.
- **Backup badge → dropdown** in `ps_agent.py` (GUI Sicura):
  - PowerShell backend: aggiunto `backup_ids = @($script:BK.Keys)` a 4 endpoint locali (/api/state, /api/apply, /api/apply-one, /api/restore) — ora il frontend riceve la lista degli ID reversibili
  - HTML: badge trasformato in role="button" con panel `#backupPanel` (hidden by default), lista `#backupList` con item testid `backup-item-<id>`
  - CSS: nuovo styling per panel (absolute positioning, max-height + scroll, hover state, disabled state quando 0)
  - JS: `renderBackupPanel()` mappa `state.backup_ids` → nomi friendly via `state.tweaks.find(t => t.id === id).name`. Toggle su click + keyboard (Enter/Space). Click-outside-to-close.
  - Sync in tutti i flow: applySelected, applyOne, doRestore (reset a [] dopo ripristino totale)
- **Nessuna regressione**: 24/24 test agent_script + secure_ps verdi, 68/68 test non-LLM verdi

## FILE MODIFICATI (sessione 27)
- MOD: /app/backend/routers/pc.py (agent_list_profiles endpoint + import TWEAK_CATALOG/TEMPLATES)
- MOD: /app/backend/ps_agent.py (backup dropdown: PS backend + HTML + CSS + JS)
- MOD: /app/memory/PRD.md
- **Type hints `models.py`**: 100% coverage. `list` → `list[str]`/`list[dict[str, Any]]`, `dict` → `dict[str, Any]`. Colpiti 20 Pydantic model — migliore IDE support, catch di errori a compile-time. Testato con instanziazione: OK.
- **Array-index-keys eliminati** (top 7 hot spot):
  - `Landing.jsx`: 5 posti (msgs chat mockup, bullets FeatureRow, trust strip, steps how-it-works, features showcase) → `key={m.text}`, `key={b}`, `key={s.l}`, `key={s.t}`, `key={f.t}`
  - `Commands.jsx`: 2 posti (MAINT items, CmdRow list) → `key={m.label}`, `key={it.cmd || it.label}`
- **Skippato con giustificazione**: split `Games.jsx` (405 righe) — dopo analisi ha 7+ props condivise tra le sezioni FPS estimate/rec preset, richiede prop-drilling estensivo e sarebbe più regressione che valore. Meglio task dedicato con testing agent per validare.
- **Validato**: pytest 75/75, sintassi Python + JSX OK, Playwright Landing (hero "Find the bottlenecks" + telemetry preview 92 HEALTH + tweaks 35/35) + Commands (maint-download testid presente).

## FILE MODIFICATI (sessione 26)
- MOD: /app/backend/models.py (type hints 100%)
- MOD: /app/frontend/src/pages/Landing.jsx (5 array-index-key fix)
- MOD: /app/frontend/src/pages/Commands.jsx (2 array-index-key fix)
- MOD: /app/memory/PRD.md

### 2026-07-20 (28) - Step 2 GUI Profili + Live Sync toggle nella GUI Sicura
_(dettagli riassunti nel finish summary della sessione: tab "Profili Cloud" nel `ps_agent.py` che pesca da `/api/agent/profiles`, toggle "Sync Cloud" con dot pulsante verde, push telemetria opportunistico throttled 3s dentro `/api/log`, endpoint locali `/api/profiles-cloud` e `/api/live-sync`, funzione `Push-LiveSample` che riusa `Get-TelemetrySample`)_

### 2026-07-20 (29) - QR "Continua sul telefono" (Magic Link handoff)
- **Backend** (`auth.py`):
  - `POST /api/auth/magic-link` (auth cookie richiesta): genera token cryptographically-secure via `secrets.token_urlsafe(32)`, TTL 5 min, salvato in `db.magic_tokens` con `{token, user_id, expires_at, created_at, used}`. Rate limit 5/user/ora (429 se superato).
  - `POST /api/auth/consume-magic` (pubblico): atomicamente marca il token come `used=true` via `find_one_and_update`, verifica TTL, carica user da MongoDB, setta cookie JWT standard, ritorna `public_user()`. Single-use enforced.
- **Frontend**:
  - Nuova route `/auth/mobile?t=<token>` (`AuthMobile.jsx`): consuma il token via `POST /consume-magic`, redirect a `/app` on success. Su errore mostra pagina "Link scaduto o già usato" con CTA login.
  - Nuovo componente `MobileHandoffModal.jsx`: overlay z-100 con QR SVG (libreria `qrcode.react` 4.2.0 aggiunta come dep), countdown live `mm:ss` (rosso sotto 60s), pulsante "Rigenera", auto-rigenera all'apertura del modal. Click-outside-to-close. Testid: `mobile-handoff-modal`, `mobile-handoff-qr`, `mobile-handoff-countdown`, `mobile-handoff-close`, `mobile-handoff-regenerate`, `mobile-handoff-retry`, `mobile-handoff-error`.
  - Integrazione in `Dashboard.jsx`: bottone "Continua sul telefono" (icona Smartphone lucide, border cyan) accanto al PageHeader. Testid: `continue-on-mobile-btn`.
- **Verificato end-to-end**:
  - curl `POST /magic-link` → `{token, expires_in_seconds:300}` ✅
  - curl `POST /consume-magic` prima chiamata → 200 con user profile + cookies settati ✅
  - Seconda chiamata stesso token → 401 "Link expired or already used" ✅ (single-use enforced)
  - Token invalido → 401 ✅
  - Playwright: click bottone → modal apre con QR + countdown "05:00"
- **Sicurezza**: token 32 byte urlsafe (256 bit entropia), TTL 5 min, single-use atomic via find_one_and_update, rate limit 5/h/user, richiede JWT valido per generazione.
- **Nessuna regressione**: 48/48 test verdi (agent_script, secure_ps, alerts_fps, account_endpoints).

## FILE MODIFICATI/CREATI (sessione 29)
- MOD: /app/backend/auth.py (2 endpoint magic-link + consume-magic)
- CREATO: /app/frontend/src/pages/AuthMobile.jsx (route /auth/mobile consumer)
- CREATO: /app/frontend/src/components/MobileHandoffModal.jsx (QR modal componente)
- MOD: /app/frontend/src/pages/Dashboard.jsx (import + bottone + state modal)
- MOD: /app/frontend/src/App.js (nuova route /auth/mobile)
- MOD: /app/frontend/package.json (aggiunta dep qrcode.react@4.2.0)
- MOD: /app/memory/PRD.md
- **Nuova tab "Profili Cloud"** in `ps_agent.py`:
  - `CATS` esteso con `{key:"profiles", label:"Profili Cloud"}`; state esteso con `profiles: null`
  - `renderTabs()` gestisce case profili (mostra count profili invece di `todo/total` tweak)
  - `renderCards()` fa early-return a `renderProfilesTab(el)` quando `activeCat === "profiles"`
  - `loadProfiles()`: chiama `/api/profiles-cloud` locale (proxy al cloud); gestisce loading/error state
  - `renderProfilesTab()`: due sezioni ("I MIEI PROFILI" e "TEMPLATE COMMUNITY") con card che mostrano fino a 6 nomi tweak + "+N" se piu. Testid `profile-<id>`, `profile-template-<id>`, `apply-*`, `section-my-profiles`, `section-templates`
  - `applyProfile(tweakIds)`: seleziona i tweak matching nella lista locale (`state.tweaks` filtered per compatibilita HW `!t.fit.skip`), jump a tab Gaming, toast di conferma con conteggio matched
- **Nuovo endpoint PowerShell `/api/profiles-cloud`** (GET): proxy con `Invoke-RestMethod` a `$BACKEND/api/agent/profiles` usando header `X-Agent-Token`. Fallback a payload vuoto se cloud unreachable.
- **Live Sync toggle** nell'header:
  - Nuovo `<label class="live-sync-toggle">` con input checkbox `#liveSyncToggle`, dot pulse animato quando ON (verde `--ok`)
  - Nuovo endpoint PS `/api/live-sync` (POST): flip `$script:LIVE_SYNC` bool
  - Nuova funzione PS `Push-LiveSample`: chiama `Get-TelemetrySample` (già esistente per benchmark) e la invia a `$BACKEND/api/agent/telemetry`
  - Push opportunistico dentro `/api/log` (già pollato dal frontend ogni 400ms): throttle a 3s via `$script:LIVE_LAST_TS`
  - Toggle wired via `_liveToggle.addEventListener("change", ...)`: POST + toast di conferma
- **CSS aggiunto**: `.header-actions`, `.live-sync-toggle`, `.live-sync-dot` con `@keyframes pulse`, `.profile-card`, `.profile-section-title`
- **Nessuna regressione**: 24/24 test agent_script + secure_ps verdi. Sintassi ps_agent.py OK.

**Note deployment**: `ps_agent.py` è servito dal backend cloud (`/api/agent/script`). Al prossimo redeploy prod la GUI ha subito le nuove feature. Serve un test in VM Windows per verificare:
1. La tab Profili carica → cards visibili
2. Click "Applica profilo" → tweak selezionati nella tab Gaming
3. Toggle "Sync Cloud" ON → dot verde pulsante, dati visibili su `/app/live` da altro device
4. Toggle OFF → dot grigio, stop stream

## FILE MODIFICATI (sessione 28)
- MOD: /app/backend/ps_agent.py (tab Profili + Live Sync toggle + relativi endpoint PS)
- MOD: /app/memory/PRD.md


---

## Sessione 29 (2026-07-20) — v0.6.6

### Feature: Cross-device Magic Link Notification + QR dentro GUI Desktop
Utente ha richiesto due estensioni al flusso Magic Link introdotto in v0.6.5:
1. **Notifica quando il mobile fa scan del QR** (feedback real-time all'origine)
2. **Bottone "Continua sul Telefono" dentro la GUI Sicura desktop** (funziona anche senza aprire il browser)
Scelta utente: toast web + **notifica Windows nativa** nella GUI (BurntToast/tray balloon fallback).

### Backend
- `auth.py`: helper `_parse_device_label(ua)`, `consume-magic` ora salva UA/label, nuovo `GET /api/auth/magic-status/{token}` pubblico.
- `routers/pc.py`: nuovi `POST /api/agent/magic-link` e `GET /api/agent/magic-qr` (auth X-Agent-Token, condividono rate-limit 5/h con endpoint web).

### Frontend
- `MobileHandoffModal.jsx`: polling 2s + stato "consumed" + toast + auto-close (fix race con effect separato).

### Desktop GUI (`ps_agent.py`)
- Bottone "Continua sul Telefono" nell'header.
- Modal QR interno alla GUI Edge WebView, con auto-close e stato Device connesso.
- 4 endpoint locali PS proxied al cloud.
- `Show-DeviceToast` in background job → notifica Windows nativa.

### Testing
- iteration_26.json: 17/17 backend PASS, frontend end-to-end verificato (compresa auto-close bug fixata post-review).

### File toccati sessione 29
- MOD: /app/backend/auth.py
- MOD: /app/backend/routers/pc.py
- MOD: /app/backend/ps_agent.py (~200 righe aggiunte HTML+CSS+JS+PowerShell)
- MOD: /app/frontend/src/components/MobileHandoffModal.jsx
- NEW: /app/memory/CHANGELOG.md
- NEW: /app/backend/tests/test_magic_link_mobile_handoff.py (dal testing agent)

### 2026-02-22 — Fase 3 (Benchmark contestuale) + Fase 4 (Storico visual) — DONE
- Backend routers/pc.py:
  - GET /api/benchmarks/fleet-percentile (fleet + similar-hardware percentile + before/after delta)
  - GET /api/benchmarks/guardrails (server-side: game/stream/recorder detection su running_apps)
  - GET /api/benchmarks/history?days=30 (serie temporale con stats)
  - GET /api/pc/sync-history?days=7 (timeline da health_history + by_day heatmap)
- Frontend:
  - components/FleetPercentileCard.jsx, BenchmarkSparkline.jsx, SyncTimeline.jsx
  - pages/Benchmark.jsx: guardedLaunch chiama guardrails prima del silent-launch → toast.warning se game/stream attivo (fail-open)
  - pages/MyPc.jsx: SyncTimeline sotto HealthHistoryCard
- Scelta utente: A (solo server-side, no rebuild .exe)
- Testing: iteration_33.json — backend 14/14, frontend 100% (guardrail toast + card verificati)

### 2026-02-22 — Agent UX audit P0+P1 — DONE
- **Report**: `/app/memory/AGENT_UX_AUDIT.md` (17 fix opportunities su `ps_agent.py` + `forgefps_agent.py`)
- **P0**: naming legacy rimosso ("Desktop Agent" → "FrameForge Agent" 7 occ, "Companion locale" → "Agent locale", "Collega il PC" → "FrameForge Agent" nei riferimenti dell'agent, `boostpc_backup.json` → `forgefps_backup.json` con fallback), prefissi console unificati (11 → 5: `[OK]`/`[STEP]`/`[INFO]`/`[WARN]`/`[ERR]`), Performance Score distinct da Health Score nel benchmark output, menu CLI ristrutturato da 8→5 voci contigue, GUI version pill bump `v2` → `v2.5`
- **P1**: GUI HTML polish (title, brand, subtitle allineato con headline landing, safety banner meno marketing), sort labels uniformati, empty state profili con link fixato, toast icons unicode, **fix bug `stateClass()`** che classificava erroneamente `Attivo (da disattivare)` come verde (ora yellow via nuova classe `.state.todo`)
- **Files touched**: 10 (ps_agent.py, desktop_agent.py, forgefps_agent.py, pc.py, advisor.py, discord_bot.py, helpers.py, MyPc.jsx + doc)
- **Verified**: 7/7 syntax check, endpoint `/api/agent/script` smoke test OK (47 nuovi termini, 0 residui legacy), 7/8 pytest agent-related pass (fail pre-esistente non correlato)
- **Todo utente**: redeploy (immediate impact perché lo script PowerShell è servito on-the-fly dal backend); rebuild `.exe` v0.7.3 opzionale per menu CLI (fallback backup file garantisce continuità)

### Prossimo
- P1: Alert Salute Storica (notifica quando health score < media 30gg)
- P2: Checklist tweak nel Report PDF
- P2: Migrazione opportunistica bottoni inline a `BTN_CLASSES` (Tracker, Games, Live, Advisor, Network, BIOS) — approccio incrementale per pagina toccata
- P3: Stripe billing + Google Ads conv + testimonial GitHub stars


## 2026-02 — ProfileMenu dropdown + pagina Fatturazione (Stripe Portal)
- **ProfileMenu.jsx**: dropdown in alto a destra con account card (avatar deterministico da email hash, name/email, badge piano colorato con countdown trial), menu items (Profilo & Sicurezza, Fatturazione, Piani & Trial, Discord connect/linked, Feedback, Logout), click-outside + ESC per chiudere. Discord rimosso dalla sidebar.
- **Billing.jsx** (`/app/billing`): mostra piano corrente con Icon/color per tier (starter/pro/streamer/trial/expired), payment-method-card con CTA "Gestisci pagamento su Stripe" (solo paid users), upgrade-cta per starter/trial/expired con link a `/pricing`.
- **Backend**: nuovo `POST /api/payments/portal` in `routers/payments.py` che genera link al Stripe Customer Portal. Ritorna 400 con `code=no_customer` se l'utente non ha `stripe_customer_id`.
- **Testing**: iteration_36.json — 100% backend (8/8 pytest) + 100% frontend. Test file: `/app/backend/tests/test_profile_billing.py`. Nessun bug.

### Code review notes (non blocking)
- ProfileMenu fetcha `/subscriptions/status` + `/discord/status` ogni apertura dropdown (potenziale cache/session).
- `payments.py` line 152: `return_url` hardcoded a `https://forgefps.dev` — su preview redirigge in prod, considera env `APP_ORIGIN`.
- Dashboard mostra 402 in console per AI Advisor (Emergent LLM Key out of budget) — considera fallback UI graceful.

### Prossimo
- P1: Integrazione **Resend** (email trial started/ending, welcome, payment success) — in attesa API key utente
- P1: Discord OAuth Login
- P1: Alert Salute Storica (health score < media 30gg)
- P2: Checklist tweak nel Report PDF, migrazione bottoni a BTN_CLASSES
- P3: Stripe Live mode, Google Ads conv avanzate, testimonial GitHub stars


## 2026-02 (patch) — TrialUpgradeBanner nel ProfileMenu (conversion boost)
- **Backend** (`subscriptions.py`): nuova `compute_upgrade_suggestion(user, info)` che calcola engagement score (AI messages×2 + health scans + telemetry, ultimi 14gg) e ritorna `tier`, `recommended_cycle` (monthly/yearly), `recommended_lookup`, prezzi, `save_amount`, `reason` personalizzata. Esposto in `GET /api/subscriptions/status` come `suggested_upgrade` (null se paid/starter senza-trial).
- **Regola**: expired → yearly (commit); trial + score≥15 → yearly; trial + score<15 → monthly.
- **Frontend** (`components/TrialUpgradeBanner.jsx`): banner nel ProfileMenu sotto l'account card. Countdown + reason + CTA primaria colorata verso Stripe Checkout preselezionato, CTA secondaria per ciclo alternativo. Deep-link diretto a `POST /api/payments/checkout`.
- **Test**: smoke test e2e (register→login→start-trial→open menu). Banner visibile con "Trial: 14 giorni rimasti", CTA "Passa a Pro · €7/mese", alt "o annuale · €70/anno (risparmi €14)".
- **Testids**: `trial-upgrade-banner`, `banner-countdown`, `banner-reason`, `banner-cta-primary`, `banner-cta-secondary`.


## 2026-02 — Resend email integration (transactional)
- **Package**: `resend==2.34.0` in requirements.txt
- **Config .env**: `RESEND_API_KEY`, `SENDER_EMAIL=onboarding@resend.dev` (test mode), `REPLY_TO_EMAIL=support@forgefps.dev`, `APP_ORIGIN=https://forgefps.dev`
- **email_service.py**: 5 template inline HTML (dark theme, brand giallo #E5FF00, CTA table-based) + `send_email()` wrapper async con `asyncio.to_thread(resend.Emails.send)` — fire-and-forget, mai blocca flusso utente
- **Trigger auto-inviati**:
  - `POST /api/auth/register` → welcome
  - `POST /api/subscriptions/start-trial` → trial_started
  - Stripe webhook `checkout.session.completed` → payment_success
  - Stripe webhook `invoice.payment_failed` → payment_failed
  - Cron daily 09:00 UTC (APScheduler) → trial_ending T-3 e T-1 (idempotent via `trial_reminder_sent.t_N` sul doc user)
- **Debug**: `POST /api/admin/test-email` (admin only) — body `{template, to, name}` per triggerare ogni template manualmente
- **Test e2e**: 5/5 template inviati con successo (email_id ricevuti) a `forgefps.support@gmail.com`
- **Prossimo step DEPLOY**: verificare dominio `forgefps.dev` su Resend (record DNS TXT+CNAME), poi cambiare `SENDER_EMAIL` in `no-reply@forgefps.dev` per uscire dal test mode


## 2026-02 — Extended tweak catalog (Standard + Extreme from client checklist) — REVERTED
- Cambiamenti proposti e implementati (6 tweak: memcomp, auto_maint_night, notif_fullscreen, hpet_off, bcd_dynamic_tick, spectre_off) sono stati **rimossi su richiesta utente**.
- File `ps_agent.py` riportato allo stato pre-modifica (4178 righe).
- `Invoke-Restore` non gestisce piu bcd::/mmagent::mc (rimossi).
- Preset `competitivo` e `streaming` ripristinati alla versione originale.
- Test file `tests/test_new_tweaks_catalog.py` eliminato.



## 2026-02 — One-click Bufferbloat launch button (via frameforge:// protocol)
- **Problema**: la pagina `/app/network` mostrava solo comandi PowerShell copia-incolla per eseguire il test bufferbloat (`SecureRunBlock`), UX macchinosa.
- **Backend**: aggiunto `"bufferbloat"` a `_ALLOWED_URI_MODES` in `routers/pc.py`. `GET /api/agent/launch-uri?mode=bufferbloat` ora ritorna URI firmato HMAC.
- **Frontend**: nuovo componente riutilizzabile `components/OneClickLaunchButton.jsx`:
  - Bottone giallo neon prominente "Avvia test bufferbloat"
  - `useLocation.href = uri` per triggerare protocollo `frameforge://` → agent locale esegue il test
  - Polling di `detectDone` ogni 3s (compara `updated_at` con `launchTs` snapshot)
  - Timeout 90s con fallback UI "hai installato l'agent?" + link diretto a `/app/desktop`
- **Network page** (`pages/Network.jsx`): bottone one-click prominente + il vecchio `SecureRunBlock` PowerShell relegato in `<details>` collapsible come fallback.
- **Test smoke**: bottone visibile, endpoint launch-uri ritorna URI corretto per mode=bufferbloat, endpoint respinge mode invalidi con 400.
- **Riutilizzabile**: il componente `OneClickLaunchButton` puo' essere usato ovunque nell'app dove serve un lancio "1 click" verso l'agent (Optimize, Benchmark, Full Benchmark, Monitor, Prematch, Booster, Restore).


## 2026-02 — P2 wave: Report PDF tweak log + button migration
### (a) Checklist tweak nel Report PDF
- **Frontend** (`pages/Report.jsx`): nuova sezione "Tweak applicati" nel PDF generato via jsPDF.
- Fetch `GET /api/advisor/applied-tweaks` in parallelo agli altri asset PDF, disegna tabella con:
  - Header giallo neon "Applied tweaks · N total" con underline
  - 2 colonne: TWEAK (60%) | APPLIED AT (35%)
  - Bullet verde ✓ per tweak `active=true`, cerchio grigio ○ per inattivi
  - Timestamp: `dd/mm/yyyy · hh:mm` (locale)
  - Empty state: "No tweaks logged in this session."
- **Copy IT + EN**: aggiunte 5 chiavi `pdf_tweaks_head`, `pdf_tweaks_empty`, `pdf_tweaks_count`, `pdf_col_tweak`, `pdf_col_when`
- **Test e2e**: PDF scaricato (8.5MB), contiene stringa "Applied tweaks", ispezione visuale conferma layout corretto con 6 tweak seed

### (b) Migrazione bottoni inline → BTN_CLASSES/PrimaryButton
- **Live.jsx** L138 (monitor-launch-btn) + L224 (save-alerts-btn) → `<PrimaryButton>`
- **Games.jsx** L272 (game-search-btn) → `<PrimaryButton>` con `!px-4`
- **Advisor.jsx** L437 (chat-send-btn) → `<PrimaryButton>` con `!px-4`
- **Skippati** per rispetto regole FRONTEND_RULES.md:
  - Tracker.jsx: tutti hanno `btn-volt` (CSS custom animation, non migrare)
  - BiosRestore.jsx: styling troppo custom (size text-[11px], border accent semi-transparent)
  - Advisor.jsx altre linee: usa `btn-volt` o color CIANO (non accent)
  - Network.jsx: nessun candidato con match pattern
- **Verifica**: `yarn build` OK, smoke test playwright su 4 bottoni: tutti visibili post-migrazione


## 2026-02 — Bufferbloat v2: 3 sub-grade + p99 tail latency
### Backend
- **`ps_agent.py`** (`Run-Bufferbloat`): calcola anche `down_p99` e `up_p99` via `Percentile $rtts 0.99`, include in `Send-NetResult`
- **`helpers.py`** (`grade_bufferbloat`): rifattorizzato con 3 sub-grade:
  - `idle_grade` — RTT baseline (A+ ≤15ms · A ≤25 · B ≤45 · C ≤80 · D ≤150 · F >150)
  - `loaded_grade` — bufferbloat vero (retro-compat = campo `grade`)
  - `consistency_grade` — score 0-100 basato su penalty framework:
    - Jitter: -10 (>5) / -25 (>15) / -40 (>30)
    - Loss %: -15 (>0.5) / -35 (>2) / -60 (>5)
    - Tail spike (p99 - idle): -10 (>100) / -20 (>200) / -30 (>400)
    - Mapping: A+ ≥95 · A ≥85 · B ≥70 · C ≥50 · D ≥30 · F <30
  - `tail_spike_ms` — max(down_p99, up_p99) - idle_ms (nuovo campo evidenziato)
  - **Retro-compat**: `grade`, `down_grade`, `up_grade`, `base_quality`, `loss_pct` preservati

### Frontend
- **`Network.jsx`**: sostituita giant grade card singola con 3 `<SubGrade>` cards affiancate:
  - Border-left colorato secondo il grade, letter huge, valore + hint testuale
  - Bufferbloat card laterale con `tail_spike_ms` in arancione
- Metric cards Download/Upload ora includono `p99` accanto a `p95` (via helper `buildLoadedSub`)

### Test
- **`tests/test_bufferbloat_grades_v2.py`**: 22/22 passed (idle thresholds, loaded, consistency scoring, p99 passthrough, retro-compat)
- **Smoke test frontend**: 3 sub-grade + tail-spike + p99 tutti visibili con dati seed


## 2026-02 — Code quality review (surgical fixes only)
Applicati solo i fix critici REALI, skippati falsi positivi e refactor rischiosi. Regressioni: 42/42 test passati + build OK.

### 🟢 Fix applicati
- **`routers/pc.py` L253**: sostituito `__import__("io").BytesIO()` con `io.BytesIO()` (io e' gia' importato in cima).
- **`PaymentSuccess.jsx` L63**: silent catch nel polling status ora logga `console.warn` con lo status HTTP per debug production.

### 🟡 Falsi positivi identificati e documentati (NON fixati)
- `ps_agent.py:2442` "hardcoded secret" → `TOKEN = "__TOKEN__"` e' template placeholder sostituito runtime dal backend
- `desktop_agent.py:704` `os.system("cls")` → dentro stringa Python del template PS/Batch client, non codice eseguito dal backend
- `i18n.js:329,934` "hardcoded secret" → `password: "Password"` e' label UI in traduzione, non secret
- `Auth.jsx:64,69` catch vuoti → wrapper localStorage.setItem/removeItem, pattern legittimo per quota errors
- `useSilentLaunch.js:37` "10 missing deps" → deps list gia' corretta, linter overly aggressive

### 🔴 Refactor complessita' NON applicati (motivazione: benefit/risk sfavorevole)
- `auth.py build_auth_router` (194 righe/complessita 38): funziona in produzione, testato
- `helpers.py grade_bufferbloat` (93 righe): appena riscritta con 22/22 test pass, non ritoccare
- `helpers.py compute_health` (62 righe): core testato prod
- 456 ternaries · 39 array-index-keys · 15 localStorage: da fixare opportunisticamente per FRONTEND_RULES
- DiagnosePanel/FirstScanBanner refactor: rischia regressioni onboarding


## 2026-02 — Full Benchmark Report UI + TechTerm tooltip fix
### TechTerm tooltip fix (contrasto)
- **Problema**: tooltip su `?` accanto ai termini tecnici era illeggibile (bg trasparente + testo bianco senza stacco).
- **Fix** `TechTerm.jsx`: override `TooltipContent` con `bg-[#16161C] border-2 border-[#00E0FF] shadow-[0_10px_32px_rgba(0,0,0,0.85)] px-4 py-3`. Contrasto ora ottimo.

### Full Benchmark Report — nuova UI
- **Problema identificato**: il Full Benchmark (`mode=fullbench`) veniva eseguito e i dati salvati in `db.benchmarks.full`, ma **nessuna UI li visualizzava**. Il messaggio "Apri FrameForge -> Il mio PC per il report completo" era orfano.
- **Backend** (`routers/pc.py`): nuovo endpoint `GET /api/pc-benchmark/full` che filtra `db.benchmarks` per record con campo `full` non-null. Ritorna `{latest, history[5]}`.
- **Frontend** nuovo componente `components/FullBenchmarkReport.jsx`:
  - Header: durata + timestamp + "Ripeti Full Benchmark" (uses `OneClickLaunchButton` con mode `fullbench`)
  - Card **CPU**: burst + sustained + ratio + thermal throttle warning banner
  - Card **RAM hierarchy**: L2/L3/DRAM bandwidth in GB/s
  - Card **Disk I/O multi-queue**: seq QD1 + rand 4K QD1/QD32 IOPS
  - Card **Network extended**: 3 host (avg + p95 + min + max + loss)
  - **Thermal trace chart** (recharts LineChart): CPU/GPU temp nel tempo con avg/max annotations
  - **History table**: ultimi 5 Full Benchmark per confronto trend
  - **DeltaBadge**: percentuale variazione vs precedente (verde su miglioramento, arancione su peggioramento)
  - **Empty state**: CTA "Avvia Full Benchmark" via OneClickLaunchButton
- **Benchmark.jsx**: aggiunta **tab switcher** "Quick Benchmark" / "Full Benchmark v2" (state `tab` = quick|full).
- **Test smoke**: verificate tutte le sezioni con dati seed (CPU 842/768 Mops, RAM L2 85.2 GB/s, Disk 2.7GB/s, Net 3 host, Thermal trace + max/avg temp).


## 2026-02 — Full Benchmark = feature esclusiva Streamer (upsell driver)
- **Backend** (`routers/pc.py`): `GET /api/pc-benchmark/full` ora usa `require_streamer` dep. Ritorna 402 con `{code:"plan_required", required:"streamer", current, upgrade_url}` per pro/starter/trial.
- **Frontend** (`FullBenchmarkReport.jsx`): gestione 402 -> nuovo stato `locked` con banner upsell dedicato:
  - Badge "FEATURE ESCLUSIVA STREAMER" in ciano
  - Titolo grande + value prop 2-4 min
  - 4 mini-card preview delle features (thermal throttling, RAM hierarchy, disk multi-Q, thermal trace)
  - CTA prominente "Passa a Streamer" -> `/pricing?plan=streamer`
  - Glow decorativo ciano + viola
  - Info piano corrente dell'utente
- **Test**: admin starter -> 402 + banner visibile con href `/pricing?plan=streamer`. Grant temporaneo streamer -> 200 con dati. Ripristinato a starter dopo test.


## 2026-02 — OBS Browser Source Overlay (feature esclusiva Streamer)
### Backend
- Nuovo router `/app/backend/routers/overlay.py`, montato in `server.py`
- Endpoint (streamer-only, plan gate):
  - `GET /api/overlay/config` — auto-inizializza al primo accesso (default: top-right, neon theme, tutte le metric on). Ritorna URL completo + settings.
  - `POST /api/overlay/token` — rotate cripto-strong token (`secrets.token_urlsafe(24)`). Invalida il vecchio URL.
  - `PUT /api/overlay/config` — aggiorna position (top-left|top-right|bottom-left|bottom-right), theme (neon|dark|minimal), toggle per singola metric (fps/cpu/gpu/ping/health)
- Endpoint pubblici (no-auth, token = capability):
  - `GET /api/overlay/{token}` — HTML page per OBS Browser Source. Transparent bg + auto-poll ogni 1s. Layout responsive per 4 posizioni + 3 temi.
  - `GET /api/overlay/{token}/data` — JSON con ultimo sample da `pc_telemetry` + health score. `Cache-Control: no-store`.
- Storage: `db.overlay_tokens` con `{user_id, token, position, theme, show_*, rotated_at, created_at}`. Indicizzato per token unico.

### Frontend
- Nuovo componente `components/ObsOverlayPanel.jsx`:
  - Input readonly con URL + bottoni **Copia URL** (con feedback `Copiato ✓`), **Apri** (target blank), **Rigenera** (arancione, con confirm)
  - Griglia 4 posizioni + 3 temi con visual selected state
  - Toggle a pill per ogni metric (FPS / CPU / GPU / Ping / Health)
  - **Preview iframe** live con sfondo a scacchiera (chessboard) per mostrare la trasparenza
  - Details collapsible "Come aggiungerlo in OBS Studio" (6 step)
  - Banner upsell inline se non-streamer (402)
- Integrato in `pages/Live.jsx` sotto le metric cards.

### Test
- End-to-end curl: 402 su starter, 200 su streamer, token rotate invalida il vecchio, PUT config aggiorna position+theme, HTML endpoint ritorna page 4.5KB
- Smoke test playwright: pannello visibile, URL popolato, cambio tema+posizione+toggle funzionanti

### Note
- L'`url` copiabile ha base `APP_ORIGIN` (default `https://forgefps.dev`) — corretto per streamer in produzione
- La preview iframe usa `window.location.origin` per funzionare anche in preview env


## 2026-02 — OBS Overlay v2: fix dati, temi, CSP + design accattivante
### Bug fix
1. **Dati sempre null anche con Live Monitor attivo**: l'agent PS emette `cpu_util`/`gpu_util`/`ram_used_pct`, ma l'overlay leggeva `cpu_pct`/`gpu_pct`/`ram_pct` (chiavi diverse -> sempre null). Fix: mapping corretto nel data endpoint.
2. **Ping mai popolato**: `pc_telemetry` non include `ping_ms` (solo Run-Benchmark lo emette). Fix: prendere ping da `net_results.result.idle_ms`.
3. **Stale detection**: aggiunto controllo su `ts` dell'ultimo sample. Se > 15s fa -> `live=false`, l'HTML mostra "MONITOR OFF".
4. **CSP blocca inline styles/scripts (root cause dell'overlay vuoto)**: il middleware `security_headers` in `server.py` applicava `default-src 'none'` globalmente, uccidendo l'overlay HTML. Fix: esenzione route-based -- per path `/api/overlay/{token}` (non `/data`, `/config`, `/token`) applichiamo CSP permissivo con `'unsafe-inline'` per style+script e `frame-ancestors *` (per iframe/OBS). Le altre route mantengono CSP restrittivo.

### Nuovo design (accattivante)
- Layout griglia 3 colonne (icon 16px | label 42px | value auto)
- **Header** con brand `// FRAMEFORGE` + status pill LIVE/MONITOR OFF/NO CONNECTION con dot pulsante colorato
- Icone SVG inline per ogni metrica (FPS play, CPU chip, GPU card, PING signal, HEALTH heart)
- **Bar sottili animate** sotto CPU e GPU (fill scala con % utilizzo, warn arancione se >=85%)
- **Badge temperature** con highlight rosso se >=80°C (thermal warning)
- **Animazione "pop" scale(1.08)** ogni volta che un valore cambia
- Backdrop-filter blur + saturate per effetto glass, box-shadow accent glow
- Font system-native (Segoe UI / SF Pro Display / system-ui) + monospace fallback per numeri (Consolas/Monaco)

### Temi finalmente distintivi
- **Neon**: bg 88% opacity, giallo #E5FF00 accent + glow, border-left 3px giallo, gradient top line
- **Dark**: bg 92%, ciano #00E0FF accent + glow, look tech elegante
- **Minimal**: bg 55%, tutto bianco pulito, no border-left, no gradient top (piu' discreto)

### Test
- curl end-to-end: data endpoint con telemetry POST -> valori popolati (fps 142, cpu 45%, gpu 68%, temp 72/65°C, ping 18ms)
- CSP headers verificati: `/api/overlay/{token}` permissivo, altre route restrittive
- Screenshot playwright: 3 temi (neon/dark/minimal) tutti visibili e distinti in iframe

### 2026-07-25 (36) — Banner upgrade unificato per tutte le feature gated Pro/Streamer (FATTO)
- Nuovo componente `frontend/src/components/PlanUpgradeBanner.jsx` (props: tier "pro"|"streamer", title, description, features[], currentPlan, compact, testid). Design coerente con FullBenchmarkReport lock-state: border-2 accent, glow blur, feature preview 2x2, CTA `/pricing?plan=xxx`, "piano attuale" pill.
- Applicato a:
  - `Advisor.jsx`: fetch `/subscriptions/status` al mount; se `!is_pro` mostra banner "AI Advisor personalizzato" invece di DiagnosePanel+chat. 4 feature preview: Chat AI context-aware, Diagnose one-click, Screenshot analysis, 5 coach specializzati. testid: advisor-locked.
  - `Live.jsx`: stesso pattern; se `!is_pro` mostra banner "Live Monitor & Alert" invece di stats+chart+ObsOverlay. Poll telemetry disabilitato quando gated (evita 402 spam). testid: live-locked.
  - `FullBenchmarkReport.jsx` refactor: sostituito il locked-state custom (46 righe) con `<PlanUpgradeBanner tier="streamer" .../>`. Stesso testid `fullbench-locked`.
  - `ObsOverlayPanel.jsx` refactor: sostituito locked-state (compact) con `<PlanUpgradeBanner tier="streamer" compact .../>`. testid `overlay-locked`. Aggiunte icone Radio/Layout/Monitor/Zap invece di Lock/Sparkles nell'import.
- Verificato via screenshot (starter e streamer):
  - starter/@example → banner "PASSA A PRO" su Advisor e Live, "PASSA A STREAMER" su Full Benchmark. Nessun chat-input, nessuna stat visibile.
  - streamer/admin (plan=streamer) → chat-input presente, stat-fps=142, obs-overlay-panel visibile, nessun banner. Regressione zero.
- Consistency win: tutti i 4 banner (Pro Advisor, Pro Live, Streamer FullBench, Streamer OBS) usano lo stesso componente => stesso look/motion/CTA, manutenzione centralizzata.

### 2026-07-25 (37) — i18n banner upgrade IT/EN + feature copy piu' tecnica (FATTO)
- Aggiunta namespace `plan_banner` in i18n.js (IT+EN) con chiavi: eyebrow_pro/eyebrow_streamer, cta_pro/cta_streamer, current_plan, + sotto-nsp `advisor/live/fullbench/overlay` (title/desc/f1-f4).
- `PlanUpgradeBanner.jsx`: ora usa `useTranslation()` per eyebrow/CTA/current_plan. Supporta `<b>...</b>` inline nella description (renderRich sanitizza a `<strong className="text-white">`). Rimossa dipendenza dal caller per stringhe UI comuni.
- Callers refattorizzati per passare solo `t("plan_banner.<page>.<key>")`:
  - `Advisor.jsx`, `Live.jsx`, `FullBenchmarkReport.jsx`, `ObsOverlayPanel.jsx`.
- Copy migliorata (piu' concreta e tecnica):
  - Advisor: Claude Sonnet 4.6 chat context-aware (<2s streaming, cita driver/temp reali), One-click Diagnose (+15 FPS/-8ms), Screenshot vision (BSOD/task manager/BIOS/OBS log), 5 coach specializzati.
  - Live: 8 metriche @1Hz (elenco esplicito FPS/CPU/GPU/power/temp/RAM/VRAM/latency MsUntilDisplayed), Grafico live 5min con 300 sample rolling + Bottleneck Detector CPU/GPU/VRAM-bound, Alert push termici 40-110°C con cooldown 5min, Session Summary streamer con avg/min/max/1%low export PNG/Web Share.
  - Full Benchmark: Rileva thermal throttling (ratio <85% dopo 30s burst), RAM hierarchy L2 1MB / L3 32MB / DRAM 512MB, Disk multi-queue QD1+QD32 IOPS gaming vs asset streaming, Live thermal trace Recharts sample-by-sample.
  - OBS Overlay: 1 URL 0 setup (Browser Source 300x200 + token rigenerabile), 3 temi (Neon/Dark/Minimal) + 4 posizioni angoli, Metriche a scelta (toggle FPS/CPU/GPU/ping/Health), Zero FPS impact (HTML/CSS <10KB, no DirectX/Vulkan touch).
- Bugfix collaterale: `ObsOverlayPanel` non passava `currentPlan` -> mostrava sempre "starter"; ora legge il piano dal detail del 402 e lo passa.
- Verificato via screenshot IT e EN su Advisor/Live/FullBench/OBS: banner correttamente localizzati, bold funzionante, feature con testo tecnico.

### 2026-07-25 (38) — Refactor DiagnosePanel/FirstScanBanner + fix chiavi React (FATTO)
- **DiagnosePanel** 297 -> 33 righe (-91%). Split in 4 file:
  - `hooks/useDiagnose.js` (148): stato/effetti/handler (run, toggleApplied, submitFeedback, savePlanned, dismiss, toggleVerify, toggleCollapsed) + fetch iniziale (diagnose/latest + applied-tweaks + outcome)
  - `components/DiagnoseStates.jsx` (114): DiagnoseIdleCTA, DiagnoseLoading, DiagnoseErrorView, DiagnoseEmpty (viste stateless)
  - `components/DiagnoseResultView.jsx` (64): vista "done" con header/lista actions/footer
  - `components/DiagnosePanel.jsx` (33): orchestratore, switch state -> view
- **FirstScanBanner** 228 -> 22 righe (-90%). Split in 4 file:
  - `hooks/useFirstScanPolling.js` (83): polling con exponential backoff (3s -> 10s dopo 60s), differenzia utente veterano vs first-scan
  - `components/ScanCompleteBanner.jsx` (47): banner verde post-scan con CPU/GPU/RAM + CTA My PC/Dashboard
  - `components/ScanPendingBanner.jsx` (86): guida 4 step con StepCard riutilizzabile e step definiti come dati (STEPS.en/it), key={step.id}
  - `components/FirstScanBanner.jsx` (22): orchestratore, switch status -> view
- **Fix chiavi React (index -> stable id)**:
  - `Pricing.jsx`: tier.items -> `${tier.key}-${i}-${it.slice(0,20)}`; features_matrix row -> `row.label` (+ nested cells `${row.label}-${j}`); trust_signals -> `t.label`; faq -> `f.q`
  - `PrivacyTelemetry.jsx`: collected_list/never_list -> `it`; tiers -> `tier.t`; nested items -> `it`
  - `Terms.jsx`: sections -> `s.h`
- Verificato via screenshot:
  - AI Advisor con admin=streamer -> diagnose-panel + diagnose-result renderizzano (5 azioni AI complete, dismiss, save, mark active), chat sotto attiva
  - /pricing -> 3 tiers + 8 FAQ items rendono correttamente
  - /privacy-telemetry -> collected/never/tiers rendering
  - /terms -> title + 9 sections rendering
- Zero regressioni funzionali: tutti i data-testid preservati (diagnose-panel, diagnose-btn, diagnose-loading, diagnose-error, diagnose-result, diagnose-actions-list, diagnose-again, diagnose-connect-cta, first-scan-pending/done, first-scan-step-1/2/3/4, faq-item-N).

### 2026-07-25 (39) — Fix overlay OBS tagliato in basso (FATTO)
- Root cause: con 5 metriche attive (FPS/CPU/GPU/PING/HEALTH) la card era ~220x220px, ma la size consigliata in UI era 300x200 -> body padding 20+20 lasciava solo 160px verticali -> overflow -> fondo tagliato.
- Layout piu' compatto in `routers/overlay.py`:
  - body padding 20px -> 8px, aggiunto card max-width: calc(100vw - 16px)
  - card padding 14/16/12/16 -> 10/12/8/12, min-width 240 -> 220
  - header margin/padding 10+8 -> 6+5
  - metric grid 16/42/1fr -> 14/38/1fr, gap 10 -> 8, padding 6/0 -> 3/0
  - metric num 20px -> 16px, label 10px -> 9px, icon 14 -> 12
- Nuova dimensione: 5 metriche = 220x173 (fit anche 300x200 con 11px di margine)
- Copy aggiornata (frontend + i18n IT/EN): consigliati 340x260 (safe zone anche con testo lungo o eventuali metriche future)
- Verificato via viewport 300x200 e 340x260: `cutoff:false` in entrambi i casi, screenshot rendering pulito con tutti 5 metric visibili
- Nota: modifica applicata solo su PREVIEW; per PRODUCTION (forgefps.dev) e' necessario redeploy.

### 2026-07-25 (40) — Bugfix menu utente + Novita' & Feedback community section (FATTO)
- **Bug fix menu utente**: `ProfileMenu` linkava `/app/settings` e `/app/settings#discord` → route inesistenti → catch-all → redirect a landing. Corretti a `/app/account` e `/app/account#discord` (route esistente).
- **Nuova sezione "Community" in sidebar** (sotto Admin):
  - `📜 What's New / Novita'` → pagina `/app/changelog` con timeline release da `/api/changelog`, badge NEW dinamico con conteggio unseen (rosso, aggiornato ogni 60s + al cambio route). Mark-seen automatico al mount.
  - `💬 Feedback` → apre `FeedbackModal.jsx` (tipo bug/idea/altro + textarea + screenshot opzionale + page context automatico via useLocation).
- **Backend `routers/community.py`**:
  - `GET /api/changelog` → legge `data/changelog.json` (4 release seeded con storico)
  - `GET /api/changelog/status` → `{latest, last_seen, unseen}` per il badge
  - `POST /api/changelog/mark-seen` → upsert in collezione `changelog_seen` per user
  - `POST /api/feedback` → salva in Mongo (`feedback` collection) + best-effort webhook Discord (`DISCORD_WEBHOOK_FEEDBACK` env, opzionale) con embed colorato per tipo e file upload multipart per screenshot base64
- **Frontend**:
  - `pages/AppChangelog.jsx` (in-app, JSON-driven, separato dal `/changelog` marketing pubblico curato manualmente)
  - `components/FeedbackModal.jsx` con 3 pillole tipo, counter caratteri (max 4000), file picker screenshot (max 1.5MB, PNG/JPG), success state con animazione check
  - `Layout.jsx` NAV_GROUPS esteso con `section.community` + supporto `action` (button che apre modal) + supporto `badge: "unseen"` con conteggio dinamico
  - i18n keys aggiunti: `nav.changelog`, `nav.feedback`, `section.community` (IT+EN)
- Verificato via screenshot (admin login):
  - Sidebar mostra "COMMUNITY" > "What's New" (badge rosso "4") + "Feedback"
  - Click Feedback -> modal si apre correttamente con pillole colorate
  - Click What's New -> pagina renderizza 4 release con LATEST pill su v0.7.6, highlights + all-changes con NEW/FIX badge colorati
  - Badge sparisce dopo visita (mark-seen ok)
- Note produzione: fix + feature entrambi in preview; forgefps.dev necessita redeploy.

### 2026-07-25 (41) — Fix flash console silent agent + banner update in-app (FATTO)
- **Root cause**: `forgefps-agent.exe` buildato con PyInstaller `--console` -> Windows crea la console window PRIMA che Python parta -> anche con ShowWindow(SW_HIDE) restano ~100-500ms di flash visibile durante boot interpreter + import.
- **Fix v0.7.6 a 2 layer** (`agent-build/forgefps_agent.py`):
  1. **VBS launcher primario**: nuovo `_write_hidden_launcher()` scrive `%APPDATA%\FrameForge\launcher.vbs` che usa `WshShell.Run(cmd, 0, False)` con SW_HIDE. `register_frameforge_protocol()` ora registra `wscript.exe launcher.vbs "%1"` come handler del protocollo -> process spawnato gia' hidden -> **zero flash**.
  2. **Belt-and-suspenders `_hide_console_if_silent()`**: chiamato subito dopo argparse (prima di qualsiasi print), nasconde la console via ctypes ShowWindow + redirect stdout/stderr a devnull. Attivo solo se URI contiene `silent=1`. Fallback per il caso in cui .vbs non si riesca a scrivere.
  3. **Silent+no-token**: se URI silent e token mancante -> `sys.exit(2)` invece di prompt input (evita processo orfano invisibile).
- **Version tracking** (`X-Agent-Version` header):
  - Agent v0.7.6 invia `X-Agent-Version: 0.7.6` su `/api/agent/script` (interactive + silent)
  - Backend `/api/agent/script` legge header e upserta `pc_specs.agent_version + agent_version_at`
  - Nuovo endpoint `GET /api/agent/status` -> `{installed_version, latest_version, is_outdated, has_ever_run, download_url}`. `latest_version` estratto dinamicamente dall'URL upstream (unico source of truth).
- **Banner in-app** `AgentUpdateBanner.jsx` (globale, in Layout sopra PlanStatusBanner):
  - Mostrato solo se `has_ever_run && (installed_version < latest || installed=null)`
  - Design: bordo giallo lampeggiante, versione installata -> latest con freccia, CTA "Update now" -> `/app/desktop`, dismiss per-versione in sessionStorage (riappare al release successivo)
  - i18n IT+EN inline
- Versione bumpata a v0.7.6 in: `AGENT_VERSION`, `version_info.txt` (filevers/prodvers/FileVersion/ProductVersion)
- Verificato via curl `/api/agent/status` + screenshot banner rendering + dismiss funzionante.
- ⚠️ Richiede: (1) build+release v0.7.6 GitHub (workflow gia' presente), (2) bump `AGENT_ZIP_UPSTREAM` in backend a v0.7.6, (3) redeploy forgefps.dev.

### 2026-07-25 (42) — Agent v0.7.6: auto-update + progress bar + zero-flash GUI (FATTO)
- **c1 · Auto-update in-place** (`_check_and_apply_update()` in forgefps_agent.py):
  - Al boot dopo protocol registration, chiama endpoint pubblico `/api/agent/latest-version` (no auth cookie richiesto → creato in `pc.py`)
  - Se `latest > AGENT_VERSION` → scarica ZIP in `%APPDATA%\FrameForge\update\`, estrae, trova nuovo exe
  - Genera `update.bat` che: aspetta 2s, copia sopra l'exe, rilancia con `--from-updater --skip-update-check`, cleanup
  - Main exe fa sys.exit(0). Zero loop grazie a `--from-updater`. Silenzioso su timeout/rete morta.
- **b4 · Progress bar reale** (`class Progress`):
  - Barra ANSI 24-char con cyan/green icon (✔/✘) + pct + msg troncato a 60 char
  - Fallback log-style `[N/T] OK · msg` se stdout non-TTY (console nascosta o redirect)
  - `apply_all_tweaks()` refactorato: 15+ `print("[STEP]/...")` sparsi → `prog.step("msg")` sequenziale + `prog.done()` finale
  - Zero dipendenze esterne (no rich/tqdm → PyInstaller bundle stabile)
- **b1 · Zero flash console anche per GUI launch**:
  - Nuovi flag CLI: `--no-console`, `--from-updater`, `--skip-update-check`
  - `launcher.vbs` ora passa `--no-console` all'exe
  - `_hide_console_if_silent()` esteso: nasconde se `--no-console` OR `silent=1` in URI
  - Effetto: qualunque protocol click (silent + non-silent) → console mai visibile. La PS window che spawna resta visibile (e' l'UI vera).
- Aggiornato `data/changelog.json`: entry v0.7.6 con highlights + changes accurati
- Verificato: `/api/agent/latest-version` risponde `{version:"0.7.5", download_url:...}` (server-side gia' pronto; bumpa a 0.7.6 quando la release e' pubblicata).
- Sintassi Python OK, backend up.
- ⚠️ Richiede build+release v0.7.6 su GitHub per attivare auto-update; poi bump `AGENT_ZIP_UPSTREAM` per far scattare l'update automatico agli utenti su 0.7.5.

### 2026-07-25 (43) — Agent Recipe System (A+B+E+H) (FATTO)
- **A · Recipe System declarativo** (`agent-build/tweaks.py`, 613 righe, nuovo modulo):
  - `@dataclass Tweak` con: id, category, name, why, impact, difficulty, requires_reboot, version, hardware_gate, apply/verify/revert
  - `@dataclass TweakContext` per DI (evita circular imports): run/ps/reg_get/set_reg/_clean + is_laptop/ram_gb/is_ssd
  - `CATEGORIES` (dict) e `TWEAKS` (list) come source of truth: 16 tweak in 6 categorie (latency=4, gaming=3, privacy=2, bloatware=1, system=5, visual=1)
  - Ogni tweak espone il "why" tecnico per UI/tooltip ("Nagle bufferizza pacchetti TCP piccoli...") e "impact" quantificato ("+5-15ms input lag online")
- **B · Categorie selezionabili** (CLI):
  - `--categories latency,gaming` → applica solo quelle categorie
  - `--mode list-tweaks` → enumera tutti i 16 tweak raggruppati per categoria
- **E · Revert per singolo tweak**:
  - `--mode restore-one --tweak-id tcp-nagle-off` → ripristina solo quel tweak
  - `--mode apply-one --tweak-id X` → applica solo quel tweak
  - Ogni tweak definisce `revert()` se necessario (es. sysmain, diagtrack, power_plan); fallback generico key-based per gli altri
- **H · Verify step post-apply**:
  - Ogni `Tweak.verify(ctx, bk) -> bool` viene chiamato subito dopo `apply()`
  - Rileva GPO/antivirus che revertano registry keys (es. quando l'AV enterprise blocca modifiche a HKLM)
  - Progress bar mostra ✔ (verified) o ⚠ (applied ma non verificato)
  - Backup salva `bk["tweaks"][id] = {applied, verified, at}` per storico UI
- **Backup compat**: schema key-based v0.7.5 preservato + nuova sezione `bk["tweaks"]` per metadata. Retrocompat totale con backup esistenti.
- **Refactor**: `apply_all_tweaks()` da 130 righe → 40 righe (orchestrator sopra `apply_selected()`). Aggiunto `_build_tweak_context()` che rileva hardware profile una volta.
- Verificato: sintassi OK, import `from tweaks import ...` funziona, `get_by_categories(['latency'])` filtra correttamente, `get_by_id('tcp-nagle-off')` risolve.
- ⚠️ Da fare: aggiungere UI dashboard per selezionare categorie/singoli tweak (in un altro giro). Per ora esposto solo via CLI + URI protocol.

### 2026-07-25 (44) — UI dashboard tweak + bloatware auto-discovery (FATTO)
- **UI dashboard tweak** (`pages/Tweaks.jsx`, sidebar entry "Windows Tweaks"):
  - `GET /api/tweaks/catalog` → serve metadata da `backend/data/tweaks_catalog.json` (16 tweak in 6 categorie con id/name/why/impact/difficulty/requires_reboot/conditional)
  - `POST /api/tweaks/apply-uri` → firma URI custom-protocol con `mode+ts` HMAC + parametri UX `categories=X,Y` e `tweak_id=Z` (non firmati, sono hint)
  - Frontend: checkbox individuali per tweak, checkbox aggregata per categoria (con mixed state), "Recommended" (solo safe), "All", "None". Sticky Apply bar in fondo che triggera window.location = uri
  - Icona colorata per categoria (Zap=cyan latency, Gamepad=yellow gaming, Shield=purple privacy, Trash=red bloatware, Cpu=green system, Sparkles=orange visual). Badge SAFE/MEDIUM/ADVANCED + REBOOT + conditional (Desktop/SSD/RAM>=16GB)
  - i18n IT+EN: `nav.tweaks`
- **Agent URI parser esteso** (`forgefps_agent.py`):
  - `parse_and_verify_uri` estrae anche `categories` e `tweak_id` dai query params (safe: alterando questi si puo' solo cambiare QUALI tweak vengono applicati tra quelli gia' autenticati via mode)
  - Payload iniettato in `_args.categories` e `_args.tweak_id` prima del dispatch main
  - Whitelist silent mode estesa: `apply-one`, `restore-one`, `restore` ora supportati via URI protocol
- **Bloatware auto-discovery** (`tweaks.py`):
  - `BLOAT_APPS` (13 esplicite v0.7.5) + `BLOAT_PATTERNS` (18 wildcard: Bing*, Disney*, Netflix*, OEM Dell/HP/Lenovo, McAfee/Norton, ecc)
  - `NEVER_REMOVE` whitelist (22 entry): Store, Calculator, Photos, Camera, Terminal, Notepad, tutti i runtime WinUI/VCLibs/.NET Native, LanguageExperiencePack*
  - Nuova funzione `_discover_bloatware(ctx)`: unisce lista + match pattern via `Get-AppxPackage -Name <pattern>`, filtra NEVER_REMOVE (glob-style prefix match)
  - `_t_bloatware_apply` ora rimuove candidati dinamici invece della lista fissa. Salva `bk["bloat_candidates_last_seen"]` per storico
- Verificato: catalog + apply-uri via curl OK, sintassi Python OK, frontend renderizza 6 categorie 16 tweak, "Recommended" seleziona 14/16 (esclude i moderate con reboot), screenshot conferma UI polished.

### 2026-07-25 (45) — GUI Agent v3.0: Monitor Live + Bloatware tab + revert granulare + banner update + responsive (FATTO)
Tutto lato server (`backend/ps_agent.py`, script scaricato fresco a ogni avvio → NESSUN rebuild .exe necessario):
- **Revert per singolo tweak (a)**: `Invoke-ApplyTracked` traccia in `$script:TWKEYS` (persistito come `__tweak_keys__` nel backup json) quali chiavi di backup crea ogni tweak. Nuovo endpoint locale `POST /api/restore-one {id}` + `Invoke-RestoreTweak` (usa `Restore-OneKey`, logica per-chiave estratta da `Invoke-Restore`). Card applicate mostrano bottone "↩ Ripristina" (testid `revert-one-{id}`) se il tweak è in `state.revertable`. Il pannello Backup ora elenca nomi tweak invece di chiavi di registro grezze (`Get-BackupIds`).
- **Monitor Live (b)**: nuova tab con 8 tile (CPU %, CPU temp, GPU %, GPU temp, RAM, VRAM, GPU clock, GPU power), sparkline SVG (ultimi 40 campioni), color coding termico (verde <72, ambra <85, rosso ≥85). Endpoint locale `GET /api/telemetry-local` → `Get-TelemetrySample`. Polling 3s solo con tab attiva (start/stopMonitor).
- **Tab Bloatware (d)**: auto-discovery allineato a tweaks.py (`$script:BLOAT_PATTERNS` 18 pattern + `$script:BLOAT_NEVER` whitelist 22 entry). Endpoint `GET /api/bloatware` (lista con size MB, badge curated/auto-rilevata) e `POST /api/bloatware/remove {names}` (valida contro whitelist, log progressi in WebLog). UI: checkbox multiple, "Seleziona tutte", bottone rimozione, bigToast esito.
- **Banner update in-GUI (e)**: `pc.py::_build_agent_script` ora accetta `agent_version` (header `X-Agent-Version` o fallback db `pc_specs.agent_version` → SHA parity `/agent/script` ≡ `/agent/script-info` VERIFICATA) e sostituisce `__INSTALLED_AGENT_VER__`/`__LATEST_AGENT_VER__`/`__AGENT_DL_URL__`. GUI mostra banner dismissibile (sessionStorage) se installed < latest o installed sconosciuta (exe <0.7.6).
- **Fix bug**: endpoint locale `/api/reboot` NON esisteva → il bottone "Riavvia ora" post-apply era un 404 silenzioso. Aggiunto (`shutdown /r /t 5`). Aggiunta var CSS `--fg` mancante.
- **Responsive**: media query ≤1080px / ≤860px (header stack, tab e chips scrollabili, card colonna singola, footer compatto con bottoni affiancati, icon-only buttons) e ≥1500px (griglia 420px, tipografia scalata, padding 40px). Ver-pill → "GUI v3.0".
- **Changelog app**: nuova release "GUI 3.0" in `backend/data/changelog.json` (visibile in /app/changelog).
- **Test**: sintassi PS validata con pwsh 7.4 parser (OK), JS validato con node --check (OK), 12/12 pytest `tests/test_secure_ps.py` (fixato test stale che non gestiva il BOM UTF-8 preesistente), harness mock locale + screenshot: fullscreen 1920px, ridotta 720px, tab Monitor/Bloatware/banner/revert tutti verificati visivamente.
- NOTA: il banner update si attiverà davvero quando `AGENT_ZIP_UPSTREAM` punterà alla release ≥0.7.6 (oggi punta a v0.7.5 su GitHub).

### 2026-07-25 (46) — Release v0.7.6 pubblicata: bump URL + SHA (FATTO)
- SHA256 fornito dall'utente `fd294dd4504877d714064fc92aed0270aba77c64d36bd4799685b4187eddba18` VERIFICATO scaricando lo ZIP da GitHub (match esatto).
- `frontend/src/config/agent.js`: AGENT_EXE_URL → v0.7.6, AGENT_EXE_SHA256 aggiornato, AGENT_EXE_VERSION v0.7.6, AGENT_EXE_DATE 2026-07-25.
- `backend/routers/pc.py`: AGENT_ZIP_UPSTREAM default → v0.7.6 (LATEST_AGENT_VERSION auto-estratta = 0.7.6).
- Effetti attivati e verificati e2e: `/api/agent/latest-version` = 0.7.6; script PS embedda LATEST_VER/DL_URL 0.7.6; banner web "0.7.5 → v0.7.6" visibile su /app/desktop; SHA in pagina = fd294dd4...; `/api/agent/download-zip` serve il nuovo ZIP col launcher personalizzato (SHA diverso dall'upstream by design, il token utente è iniettato nel .bat).
- Da qui: gli exe v0.7.6 si auto-aggiorneranno alle prossime release; gli utenti 0.7.5 vedono i banner (web + in-GUI).

### 2026-07-25 (47) — Debug "non vedo la nuova GUI": fallback GUI classica + hardening browser (FATTO, richiede redeploy)
- Sintomo utente (produzione): "[WARN] Interfaccia web non disponibile, uso la GUI classica..." → l'utente vede la vecchia GUI WinForms, NON la Web GUI v3.0. Nel suo screenshot manca la riga "[STEP] GUI locale su..." → il fallimento avviene PRIMA (rilevamento Edge o HttpListener.Start), non nel nuovo codice.
- Verifiche fatte: prod serve il nuovo codice (latest-version 0.7.6, changelog GUI 3.0 live); sintassi 5.1 OK (PSScriptAnalyzer PSUseCompatibleSyntax target 5.1: zero issue); harness pwsh su Linux con browser fake: Show-WebGui parte, endpoint /api/state, /api/telemetry-local, /api/bloatware, /api/restore-one rispondono (unici errori = cmdlet Windows assenti su Linux).
- Fix in `ps_agent.py::Show-WebGui`:
  1. Rilevamento browser esteso: Edge/Chrome/Brave in Program Files, Program Files (x86), LOCALAPPDATA (installazioni per-utente) + registry App Paths (msedge.exe/chrome.exe).
  2. Se nessun Chromium: fallback `Start-Process $localUrl` nel browser predefinito (GUI in tab normale, loop tenuto vivo dall'inactivity timeout 30s + polling 400ms).
  3. Diagnostica: listener.Start fallito → stampa il motivo; catch esterno di Show-WebGui stampa messaggio+riga invece di inghiottire l'eccezione.
  4. Match del processo reale usa il nome del browser scelto (non piu' hardcoded msedge.exe).
- IMPORTANTE: fix lato server → serve UN ALTRO REDEPLOY per portarlo su forgefps.dev. Al prossimo avvio dell'agent, se fallisce ancora, la console stampera' il motivo esatto (chiedere screenshot).
- Nota deploy precedente: primo tentativo fallito per errore infra (docker-push "manifest invalid"), secondo tentativo riuscito.

### 2026-07-25 (48) — Redesign pagina "Live Monitoring" (Command Center) (FATTO, testato)
- Blueprint dal design_agent (salvato in /app/design_guidelines.json → page_specific_guidelines.live_monitoring). Approvato dall'utente prima dell'implementazione; richiesta esplicita: mantenere l'OBS overlay.
- `Live.jsx` riscritta: header + pill "Telemetria attiva"; top bar = MonitorLiveControl (live) o hero offline centrato con CTA Volt (monitor-launch-btn); 4 bento card (PERFORMANCE con FPS gigante giallo >144 + latenza, CPU con temp color-coded ≥75/≥85, GPU con temp+watt, MEMORIA RAM+VRAM), valori "--" ghosted offline; griglia lg:3 col → grafici 2/3 con TAB (Performance FPS scala libera FIX CLIPPING + latenza asse dx / Temperature 0-110 / Utilizzo 0-100) + riga min/media/max; sidebar: BottleneckDetector, alert termici compatti, Reflex collassabile; SessionSummary full-width; ObsOverlayPanel mantenuto in fondo. Container max-w-7xl.
- i18n: nuove chiavi live.link_active, tab_*, card_*, min/avg/max, launch_btn, manual_cmd, launching, launch_failed (IT+EN).
- Testing agent iteration_37: 100% frontend checklist (tabs, alert save, reflex, summary reset, OBS, offline hero+preflight, IT/EN, mobile 390px no overflow). Fixati i 2 minor: traduzioni EN launch_btn & co., scala therm 0→110.
- NOTA DB dev: admin@boostpc.io settato a plan 'streamer' per testare contenuto sbloccato; 60+ sample telemetria seedati (Counter-Strike 2).
- Richiede redeploy per essere visibile su forgefps.dev.

### 2026-07-25 (49) — GpuReferenceCard spostata nel tab "Full Benchmark v2" (FATTO)
- `Benchmark.jsx`: la card "// GPU VS REFERENCE" (PassMark G3D, Time Spy, VRAM, TDP + bottone Avvia Full Benchmark) rimossa dal tab Quick e renderizzata sopra `FullBenchmarkReport` nel tab Full. Verificato con screenshot (0 occorrenze in Quick, 1 in Full).

### 2026-07-25 (50) — Miglioramenti "Consiglia Build" + "Upgrade & FPS" (FATTO, testato)
Scelte utente: Build a+b, Upgrade d+e+g.
- BuildGenerator.jsx: (b) 3 preset one-click (Competitive 1080p €1200 / Streaming 1440p €1800 / 4K Ultra €3000) che compilano e generano subito; (a) build salvate espandibili (click header → BuildCard completa con componenti/prezzi/tips; delete/track con stopPropagation).
- Upgrade.jsx riscritta: (g) header hardware rilevato (CPU/GPU/RAM da /pc-specs); (e) chips giochi installati (da /api/games, riempiono il campo gioco); (d) blocco "Prima vs dopo l'upgrade" nel risultato analisi → POST /api/fps/upgrade-compare con upgrades=recommendations → badge guadagno % + 4 righe preset con barre doppie (grigia=ora, verde=dopo) + note AI.
- Backend: models.FpsUpgradeInput, ai_engine.estimate_fps_upgrade() (prompt before/after con bottleneck residui), route POST /fps/upgrade-compare in pc.py (richiede specs, gestione 402 budget LLM).
- i18n IT+EN: build.presets_title/preset_defs, upgrade.hw_title/games_quick/ba_*.
- Testing agent iteration_38: 100% backend (6/6 pytest) e 100% frontend. Note non bloccanti: route è /app/builds (plurale); stato `game` condiviso tra pannello FPS e blocco ba (voluto).
- Seed dev: admin ha pc_specs (i7-12700K, RTX 3070 Ti, 32GB) + 5 giochi.
- Richiede redeploy per produzione.

### 2026-07-25 (51) — Bottone "Traccia" nel confronto Prima/Dopo (FATTO, testato e2e)
- Upgrade.jsx: aggiunto `ba-track-btn` (Volt, full width) in fondo a ba-result → riusa trackParts() (POST /upgrade/track con le recommendations). i18n it/en `upgrade.ba_track`.
- Test e2e screenshot: analyze → compare Fortnite (+35%, 4 barre) → click traccia → toast "1 components added to the Price Tracker" ✓.

### 2026-07-25 (52) — Hardware Insights (a,b,c,d,e,f,h — scelte utente, no ReBAR) (FATTO, testato)
- Agent (ps_agent.py Get-Specs, arriva via script server → no rebuild exe): ram_speed_nominal_mhz (XMP check), max_refresh_hz (EDID via WmiMonitorListedSupportedSourceModes), disks[{letter,type NVMe/SATA SSD/HDD,size_gb,free_gb}] (Get-Volume+Get-Partition+Get-PhysicalDisk), game_drives (parse libraryfolders.vdf Steam), hvci_on (Win32_DeviceGuard/registry), gpu_driver_date, bios_date. Sintassi PS validata (pwsh 7.4 parser).
- Backend helpers.py: compute_hw_insights(d) rule engine → [{id,severity,params}] (xmp≥400MHz gap, single_channel, refresh gap≥30Hz, game_on_hdd, disk_full<10%, hvci, gpu_driver_old>180gg, bios_old>2anni); _insight_text_it per prompt AI; specs_to_text ora include riga Dischi + blocco "Problemi hardware rilevati" → AI Advisor/Upgrade/FPS li ricevono automaticamente.
- Route GET /api/hw-insights (pc.py). Testato curl: 6 insight con dati seedati admin.
- Frontend: components/HwInsightsPanel.jsx (severità high/med/low con bordi/badge colorati, titolo+desc+fix localizzati con interpolazione params) renderizzato in MyPc.jsx sotto Health Score. i18n `hwins.*` IT+EN completo. Screenshot ✓ (6 righe).
- Seed dev admin: specs estese con problemi simulati (XMP off 2133/3600, 60/165Hz, Steam su HDD D:, HVCI on, driver 8 mesi, BIOS 2023).
- Richiede redeploy per produzione (sia backend che script agent).

### 2026-07-25 (53) — Overlay OBS: layout bar + accent custom + size (a,d,f scelte utente) (FATTO, testato)
- overlay.py: config estesa con `layout` (card|bar), `size` (small 0.85|medium 1|large 1.35 via CSS zoom), `accent` (#RRGGBB validato regex, ""=reset al tema; glow/border calcolati in rgba). PUT /overlay/config valida i 3 campi; _config_response li espone. Pagina overlay: CSS condizionale per layout bar (ticker orizzontale width max-content, border-top accent, icone/barre nascoste, metriche inline).
- ObsOverlayPanel.jsx: nuova riga controlli md:grid-cols-3 → Layout (Card/Barra), Dimensione (S/M/L), Colore brand (input color con debounce 400ms + Reset). testids: overlay-layout-*, overlay-size-*, overlay-accent-picker/reset.
- Test: curl PUT (bar/large/#ff2d95 OK, "rosso" → 400), HTML overlay contiene zoom 1.35 + accent + bar CSS (9 match), screenshot pannello+preview bar rosa ✓.
- Richiede redeploy; in OBS basta refresh della Browser Source.

### 2026-07-26 (54) — Sincronizzazione PC ad alta precisione (opzioni a+c, scelte utente) (FATTO)
Scelte utente: a) multi-source cross-validation hardware, c) sensori avanzati LibreHardwareMonitor.
- ps_agent.py (arriva via script server, no rebuild exe):
  - Helpers nuovi: `Get-CpuFromRegistry` (ProcessorNameString), `Get-GpuAdaptersFromRegistry` (enumera Class {4d36e968}), `Get-PrimaryStorage` (Get-Partition+Get-PhysicalDisk+Get-StorageReliabilityCounter → storage_type NVMe/SSD/HDD, storage_bus, storage_health, storage_wear_pct, storage_temp, storage_size_gb, storage_model).
  - `Get-Specs` esteso: cross-check CPU nome WMI vs Registry (preferisce Registry se più lungo/preciso), rilevamento GPU multi-adapter con ordinamento discrete-first (NVIDIA/GeForce/Radeon RX/Arc > Intel UHD/Iris/Vega iGPU), gpu_secondary (iGPU su laptop ibridi), gpu_provider (NVIDIA/AMD/Intel), ram_manufacturer (SMBIOS filtro Unknown/To be filled), hw_confidence={cpu,gpu,ram,storage} = numero fonti confermate 0-3.
  - `Get-LhmTemps` esteso: oltre a cpu_temp/gpu_temp ora estrae fan_rpm_max + fan_count (Fan sensors), vrm_temp (MB sensori vrm/mos/vsoc), cpu_power (CPU Package power W), gpu_power_lhm (fallback per AMD/Intel senza nvidia-smi), cpu_vcore (Voltage sensor CPU). Fascia validazione: fan 0-10000rpm, power 0-1000W, vcore 0.3-2.0V.
  - `Get-Health` e `Get-TelemetrySample` propagano tutti i nuovi campi nel payload (backend model è già free-form dict, no changes richiesti).
- Frontend:
  - Live.jsx: nuovo componente `PrecisionCell` + strip condizionale `grid-cols-2 sm:grid-cols-4` sotto le 4 bento card mostra Fan RPM / VRM Temp / CPU Power / Vcore (visibile solo se almeno un valore è presente). testids: precision-sensors, stat-fan-rpm, stat-vrm-temp, stat-cpu-power, stat-cpu-vcore.
  - MyPc.jsx: composeSpec include gpu_secondary ("GPU + iGPU"), storage_type/health/wear nel campo disco, ram_manufacturer. Badge `hw-conf-{key}` accanto a ogni spec mostra `2/2` (verde), `1/2` (giallo) o `0/2` (grigio) fonti confermate. Tooltip localizzato.
  - i18n IT+EN: live.st_fan_rpm/st_vrm_temp/st_cpu_power/st_cpu_vcore, mypcpage.hw_sources_tooltip.
- Backend model: nessuna modifica (SpecsInput.data e TelemetryInput.sample sono già dict[str,Any] free-form).
- Test: python import + brace-balance PS ok (73 funzioni), curl telemetry con nuovi campi accettato (HTTP 401 auth, non 422 validation), frontend compilato senza errori.
- Richiede redeploy per produzione (backend serve il nuovo script PS).

### 2026-07-27 (55) — Fix UAC persistente + auto-updater v0.7.9 (FATTO, in attesa release GitHub utente)
- Diagnosi UAC su bottoni dashboard (Sincronizza/Monitor/Benchmark/Fullbench): UAC mostra "forgefps-agent.exe" → il protocollo frameforge:// sul PC utente punta ancora a un VECCHIO exe ≤0.7.6 con --uac-admin. Verificato che il binario v0.7.8 su GitHub (tag v.0.7.8) è asInvoker pulito (strings sull'exe scaricato). Produzione forgefps.dev già serve 0.7.8 correttamente.
- Riparazione utente fornita: eliminare vecchie cartelle forgefps-agent, doppio click sul nuovo exe (rigenera %APPDATA%\FrameForge\launcher.vbs), test bottone.
- forgefps_agent.py → v0.7.9, 3 fix auto-updater:
  1. `_check_and_apply_update(relaunch=False)`: lanci via URI non vengono più bloccati dall'update; azione parte subito, update in background senza riavvio exe (prima il relaunch senza args apriva GUI optimize → runas → UAC inatteso).
  2. update.bat ora copia TUTTA la cartella onedir con `xcopy /E /Y` (prima solo l'exe → crash con _internal mismatched).
  3. Relaunch interattivo post-update inoltra sys.argv originali.
- version_info.txt + forgefps-agent.manifest → 0.7.9.0. github-workflow-build-nosign.yml allineato: aggiunto `--manifest forgefps-agent.manifest` + step safety check anti-requireAdministrator (prima mancavano nel file locale, presenti solo in build.ps1).
- changelog.json: entry 0.7.9. REBUILD_v0.7.9.md creato con checklist release (tag ESATTO v0.7.9, no v.0.7.9).
- PENDING: utente deve pushare tag v0.7.9 su GitHub → poi aggiornare AGENT_ZIP_UPSTREAM in /app/backend/routers/pc.py a .../v0.7.9/... e redeploy.
- Test: py_compile agent OK, curl /api/changelog 200 (0.7.9 primo), /api/agent/latest-version 0.7.8 invariato (release non ancora esistente). Comportamento Windows non testabile in questo ambiente.

### 2026-07-27 (56) — Release v0.7.9 verificata e backend/frontend aggiornati (FATTO, testato)
- Verifica release GitHub v0.7.9: SHA256 zip a791349662...9de000 IDENTICO a quello fornito dall'utente; exe dentro lo zip: asInvoker presente, 0 occorrenze requireAdministrator, version resource 0.7.9.0.
- backend/routers/pc.py: AGENT_ZIP_UPSTREAM → .../download/v0.7.9/forgefps-agent.zip (tag corretto senza punto). LATEST_AGENT_VERSION auto-derivata = 0.7.9.
- frontend/src/config/agent.js: AGENT_EXE_URL/SHA256/VERSION/DATE → v0.7.9.
- Test e2e: login admin → GET /api/agent/download-zip 200 (9.1MB), zip contiene Avvia-FrameForge.bat personalizzato + exe v0.7.9 asInvoker. GET /api/agent/latest-version → 0.7.9.
- PENDING UTENTE: redeploy produzione (forgefps.dev serve ancora 0.7.8) + installazione pulita v0.7.9 sul PC (scaricare zip fresco dalla dashboard invece di affidarsi all'auto-update della 0.7.8, il cui vecchio update.bat riavvia in GUI optimize → un UAC one-time).

### 2026-07-28 (57) — UAC recidivo: risolto lato utente (nessuna modifica codice)
- Sintomo: UAC "forgefps-agent.exe" su OGNI bottone dashboard nonostante v0.7.9 deployata.
- Diagnosi via utente: registry HKCU frameforge OK (wscript+launcher.vbs), MA launcher.vbs puntava a `C:\Users\tocci\Downloads\forgefps-agent\forgefps-agent\forgefps-agent.exe` = exe VECCHIO con manifest requireAdministrator. Il vbs viene riscritto da OGNI agent eseguito (punta a sé stesso): l'utente aveva rieseguito manualmente un exe vecchio da Downloads.
- Fix: utente ha riscaricato zip v0.7.9 dalla dashboard, estratto in cartella stabile, eseguito una volta (vbs riscritto), eliminato copie vecchie. CONFERMATO RISOLTO dall'utente.
- LEZIONE (recidiva possibile): se l'utente esegue un QUALSIASI exe vecchio, il vbs torna a puntare lì → UAC ritorna. Hardening futuro possibile (v0.8.0): far verificare all'agent, alla registrazione, la versione e rifiutare downgrade del launcher; oppure updater che riesegue --register-protocol.

### 2026-07-28 (58) — Fix modal Pre-Flight sotto la piega (FATTO, testato)
- Bug: il modal MonitorPreflight (position:fixed) era ancorato al contenitore `.fade-up` (transform residuo da animation-fill-mode:both crea containing block) → appariva sotto la piega, serviva scrollare.
- Fix: MonitorPreflight.jsx renderizzato via createPortal(document.body) + overflow-y-auto sul backdrop. Verificato con screenshot: modal centrato nel viewport (bounding box 0,0,1920,1080).
- NOTA per futuri modal: qualsiasi `fixed inset-0` dentro pagine con `.fade-up`/`.stagger` DEVE usare createPortal.

### 2026-07-28 (59) — Fix "GUI vuota all'avvio" + GUI v3.1 sidebar categorie (FATTO, testato iteration_39: 7/7 PASS)
- BUG: all'apertura della GUI agent i tweak non comparivano finché non si cliccava il filtro "Da applicare". ROOT CAUSE: un tweak con `fit` mancante/corrotto nel payload /api/state → TypeError su t.fit.skip in renderTabs/renderCards → catena render interrotta (ring restava "--%"). Il filtro pending escludeva la card rotta → render riusciva.
- FIX in ps_agent.py (GUI servita dal backend, NO rebuild exe):
  1. refreshState: normalizzazione payload (fit default, state→string, backup_ids/revertable scalari PS→array) + retry fetch (6x2.5s) + safeRender per ogni step.
  2. renderCards: cardHtml estratta + try/catch per-card con card fallback → una card corrotta non svuota mai la griglia.
  3. Error reporting: window error/unhandledrejection → POST /api/client-error (nuovo endpoint PS) → WebLog visibile nel log GUI.
- REDESIGN (scelta utente d): GUI v3.1 con sidebar categorie verticale a sinistra (224px, label // CATEGORIE, count a destra, accent border-left) al posto dei tab orizzontali. Responsive ≤860px: sidebar torna barra orizzontale scrollabile. Media query 1080/1500 aggiornate.
- Harness test permanente: /app/backend/tests/build_gui_harness.py genera /app/frontend/public/gui_test.html (GUI reale + fetch mockato con tweak corrotto g3-broken). Usato da testing agent.
- LEZIONE CRITICA: MAI fare search_replace paralleli sullo STESSO file → race che perde/corrompe edit (successo qui: refreshState perso + coda file duplicata). Su ps_agent.py sempre edit sequenziali + `python3 -c "import ps_agent"` + node --check dopo.
- NOTA: l'utente è in PRODUZIONE (forgefps.dev) → serve REDEPLOY perché il suo agent scarichi la GUI aggiornata.

### 2026-07-28 (60) — Agent v0.8.0: stop definitivo UAC dai bottoni dashboard (FATTO, testato iteration_40: 6/6 PASS)
- UAC ricorrente ("forgefps-agent.exe" nel popup, tutti i bottoni, produzione). Cause: exe vecchi che si ri-registrano sul protocollo + possibile flag RUNASADMIN in AppCompatFlags.
- forgefps_agent.py → v0.8.0, 3 protezioni:
  1. launch_secure_gui(mode, allow_elevation): lanci via URI (bottoni web) MAI elevati, nemmeno fallback firma invalida. runas unico e gated (test 7 verifica).
  2. Anti-downgrade launcher: marker "' ## target=<path>|version=x.y.z" nel vbs; exe vecchio non sovrascrive registrazione se target attuale è più nuovo ed esiste. Self-heal se target fantasma.
  3. _clear_runasadmin_compat_flag(): rimuove RUNASADMIN da HKCU AppCompatFlags\Layers (path exe + target launcher) a ogni avvio e con --register-protocol.
- version_info.txt/manifest → 0.8.0.0 (asInvoker). changelog.json entry 0.8.0. REBUILD_v0.8.0.md. Test suite permanente /app/agent-build/tests_v080_antiuac.py (7 test logici, ALL PASS).
- PENDING UTENTE: (a) pulizia one-time PC (protocollo punta ancora a exe vecchio pre-0.7.6: eliminare copie vecchie + eseguire v0.7.9 una volta); (b) push tag v0.8.0 su GitHub → SHA256 → aggiornare pc.py AGENT_ZIP_UPSTREAM + frontend config/agent.js; (c) REDEPLOY produzione (porta anche GUI v3.1 + fix griglia vuota).

### 2026-07-28 (61) — Release v0.8.0 verificata e link aggiornati (FATTO, testato e2e)
- Tag GitHub pubblicato: **v.0.8.0** (col punto — il regex di pc.py lo gestisce). SHA256 zip 408259a3...eedb VERIFICATO (match esatto con quello utente).
- Verifiche release: workflow builda da agent-build/ con manifest+version file; agent-build/forgefps_agent.py al tag = byte-identico al locale; exe: asInvoker 3 occorrenze, requireAdministrator 0, version resource 0.8.0.0. NOTA: alla radice del repo c'è un forgefps_agent.py STALE (vecchio) — ignorarlo, il build usa agent-build/.
- backend/routers/pc.py: AGENT_ZIP_UPSTREAM → v.0.8.0 (LATEST_AGENT_VERSION auto = 0.8.0). frontend/config/agent.js → URL/SHA/VERSION v0.8.0/DATE 2026-07-28.
- Test e2e preview: /api/agent/latest-version = 0.8.0; login admin → /api/agent/download-zip 200 (9.1MB, exe + Avvia-FrameForge.bat personalizzato); pagina /app/desktop mostra v0.8.0 + SHA + banner update 0.7.5→0.8.0.
- PENDING UTENTE: REDEPLOY produzione forgefps.dev (porta: agent 0.8.0 + GUI v3.1 + fix griglia vuota). Poi sul PC: pulizia exe vecchi + prima esecuzione del nuovo exe.

### 2026-07-28 (62) — GUI v3.2: skeleton + progresso analisi iniziale (FATTO, self-test screenshot 2 fasi OK)
- Feature (scelta utente #4): via il "buco nero" all'apertura della GUI agent. Durante il primo /api/state (scan sincrono lato PS, single-thread → progresso reale impossibile) la griglia mostra: strip "// ANALISI SISTEMA IN CORSO" con barra di progresso STIMATA (calibrata su localStorage ff_scan_ms = durata scan precedente, clamp 3-60s, cap 92%) + label step ciclica (Gaming & FPS → Latenza → Rete → Sistema → Servizi → GPU) + 6 skeleton card con shimmer CSS.
- ps_agent.py: CSS .scan-strip/.skel-card/@keyframes skelShimmer; JS renderScanSkeleton()/finishScanSkeleton() hooked in boot e refreshState (successo → salva durata reale; errore → messaggio "riprovo" nella strip, skeleton resta). Ver-pill → GUI v3.2.
- Harness aggiornato: build_gui_harness.py ora ritarda /api/state di 4s per testare la fase skeleton. Test: fase scan (6 skel, 19%, step ok) + fase dati (10 card, ring 50%, ff_scan_ms=4000, 0 errori).
- PENDING UTENTE: redeploy produzione per vedere GUI v3.2.

### 2026-07-28 (63) — GAMEPLAY DOCTOR (idea utente #1) — FATTO, testato iteration_41: 100% PASS
- AI che "vede" il gameplay via firme frametime (non video). 3 strati:
  1. AGENT (ps_agent.py): Get-Fps ora raccoglie frametime per-frame PresentMon e calcola per-tick ft_p99, ft_worst, hitches(>50ms), pace_dev → attaccati ai sample telemetria nel monitor loop.
  2. BACKEND deterministico (advisor.py): _gd_last_session (gap<=30s), _gameplay_stats (fps avg/min/1%low, stutter_index, hitch_total, pacing, eventi hitch/fps_drop annotati con cause: CPU satura, RAM/VRAM, GPU declock termico vs mediana clock, VRM, "nessuno saturo→causa esterna").
  3. AI (Claude): POST /api/advisor/gameplay-doctor (Pro-gated, rate-limited) → JSON {verdict, health, score, issues[{type,severity,title,evidence,cause,fix,gui_tweak}], positive}. Persistito in db.gameplay_reports. GET /gameplay-doctor/latest.
- FRONTEND: components/GameplayDoctor.jsx in /app/live sotto SessionSummary (data-testid gameplay-doctor, gd-analyze-btn, gd-report, gd-issue-*, gd-tweak-badge). i18n live.gd_* it+en. Fix overlay cookie banner: pb-24.
- FIX COLLATERALI: helpers.py pc_context_text startup con dict (rompeva anche /diagnose!); cap telemetria -300 → -1800 sample (30 min).
- Test: pytest 7/7 (/app/backend/tests/test_gameplay_doctor.py) + frontend flow reale. Qualità referto AI eccellente (correla hitch→CPU, throttling→temp+declock, cita app avvio reali).
- NOTA: i campi frametime richiedono monitor con PresentMon attivo (admin); senza, il prompt degrada onestamente (has_frametime_data=false). Serve REDEPLOY produzione. Fase 2 possibile: alert live durante il monitoring + AI Performance Lab (idea #2, architettura già discussa).

### 2026-07-28 (64) — Bottone Condividi referto Gameplay Doctor (FATTO, self-test download PNG OK)
- GameplayDoctor.jsx: bottone Share (gd-share-btn) accanto ad Analizza — esporta il referto come PNG (html-to-image, pattern identico a SessionSummary), navigator.share con fallback download. Footer branding nel PNG: "FRAMEFORGE · Gameplay Doctor · forgefps.dev". i18n live.gd_share/gd_share_text it+en.
- BUG RIPETUTO E RISOLTO: di nuovo perso un edit per search_replace PARALLELI sullo stesso file (ref={cardRef} sparito → handler share usciva silenziosamente). REGOLA FERREA: mai edit paralleli sullo stesso file, verificare con grep dopo batch.
- Test: click reale → download frameforge-gameplay-doctor.png 516KB + toast. PENDING: redeploy produzione.

### 2026-07-28 (65) — FIX: monitor senza FPS dopo v0.8.0 (FATTO, testato iteration_42: 100% PASS)
- BUG produzione: dopo redeploy il live monitoring non registrava gli FPS. ROOT CAUSE: PresentMon (ETW) richiede admin O gruppo "Performance Log Users" (SID S-1-5-32-559). Prima del fix UAC, il monitor girava ELEVATO per sbaglio (UAC del ghost exe) → FPS ok. Con v0.8.0 (niente elevazione via URI, comportamento corretto) Start-Fps aveva gate "Richiede Amministratore" → usciva → zero FPS. Il vecchio bug UAC mascherava questo requisito.
- FIX in ps_agent.py (serve REDEPLOY, exe invariato):
  1. Test-FpsCapable: 'ok' (admin o token con S-1-5-32-559) / 'relogon' (iscritto ma token vecchio) / 'no'.
  2. Enable-FpsPermission: quando la GUI Ottimizza è elevata, iscrive l'utente al gruppo (Add-LocalGroupMember -SID, fallback net localgroup con nome localizzato). Chiamata all'avvio mode=optimize.
  3. Start-Fps senza gate admin: procede se capability ok, messaggi guida per relogon/no. Booster: Start-Fps senza if(Test-Admin).
- FLUSSO UTENTE: redeploy → aprire GUI Ottimizza una volta (UAC consensuale) → riavvio/logout Windows → monitor conta FPS senza admin per sempre.
- Verifiche: pwsh 7.4.6 arm64 parser 0 errori su 5395 righe; runtime Get-Fps PASS (CSV sintetico: fps 104, 3 hitch — conferma anche che l'edit frametime di (63) è sano); script servito col fix; regressioni API ok. Harness persistito: /app/backend/tests/ps/.
- LEZIONE: ogni cambio di modello di elevazione va incrociato con le feature che dipendono dai privilegi (ETW/PresentMon, LibreHardwareMonitor driver sensori?). NB: se l'utente segnala sensori mancanti nel monitor non-admin, valutare stesso pattern.

### 2026-07-28 (66) — GAMEPLAY DOCTOR v2 (spec completa utente) — FATTO, testato iteration_43: PASS completo
- AGENT (ps_agent.py, Get-Fps v2): soglia hitch ADATTIVA (3x mediana sessione via istogramma, min 25ms), ft_cv (coeff. variazione pacing), GD_HIST istogramma cumulativo 60 bucket (1ms fino a 50 + overflow) allegato ogni 30 tick (ft_hist/ft_n) → percentili di sessione ESATTI. Test runtime pwsh PASS.
- BACKEND (advisor.py): finestra causale con LAG (sample i-1..i, la causa precede il sintomo), _GD_RULES pesate (throttle GPU 0.9, VRAM 0.85, CPU 0.8...), _gd_pattern (isolated/sporadic/periodic/burst da inter-arrival CV), DEDUP per causa dominante → problems[] con occurrences/impact_pct/impact_score/confidence_hint/concurrent_signals, ordinati per impatto reale. _gd_hist_pct per 1%/0.1% low esatti (exact_percentiles flag). Baseline storica per gioco (media ultime 5, delta %) + resolved[] (issue precedenti non ripresentate). Doc persistito con timeline{fps downsampled ≤150 pt, events} + baseline + resolved.
- PROMPT v2: executive_summary(main_problem/main_fix), separazione evidence(numeri)/diagnosis(inferenza)/fix, confidence da confidence_hint, incertezza esplicita se concurrent_signals, tono report tecnico, fix.primary{text,gui_tweak}+alternatives+impact_estimate (solo se deducibile, MAI statistiche inventate), ordine issues = ordine deterministico.
- FRONTEND (GameplayDoctor.jsx riscritto): executive summary top con score, badge Risolto, pannello baseline con delta colorati, timeline SVG FPS con marker cliccabili → espande issue corrispondente, issue a 2 livelli (simple_text + tech detail collassabile con Evidenza/Diagnosi/alternative), badge confidence, CTA unico "Applica in GUI" (apre frameforge:// via /agent/launch-uri mode=optimize), share card COMPATTA off-screen (score+top issue+fix, 600px social-ready). i18n gd_* aggiornate it/en (rimosse gd_cause duplicate).
- NON implementati (dichiarato all'utente): export PDF (non esiste nell'app), stime impatto da dati aggregati flotta (niente dati reali).
- INCIDENTE RISOLTO: sed 215,336d ha cancellato anche _enrich_specs_for_ai + 3 model class → recuperate da git HEAD. LEZIONE: mai delete a range con sed senza verificare i confini con grep dei def.
- PENDING UTENTE: REDEPLOY produzione. Le nuove firme (ft_cv/ft_hist) arrivano dal monitor al prossimo avvio post-redeploy; sessioni vecchie degradano onestamente (exact_percentiles=false).

## Aggiornamento 2026-07-29 — Laboratorio Automatico delle Prestazioni FASE 1 (FATTO, test 100% iteration_44)
### Backend (nuovi file)
- routers/lab.py: orchestratore. Endpoint utente: POST /api/lab/start (risk safe|medium, run_seconds 30-180, 409 se attiva), GET /api/lab/session, POST /api/lab/abort, GET /api/lab/registry. Endpoint agent (X-Agent-Token): GET /api/agent/lab/next (macchina a stati: snapshot->run_baseline->apply_tweak/run_test->abort/complete), POST /api/agent/lab/event (snapshot_done/tweak_applied/tweak_skip/rolled_back/aborted/waiting_game/game_detected), POST /api/agent/lab/run (baseline: CV check >5% -> 4o run + scarto outlier; test: 3 run -> Welch -> kept/rolled_back, baseline aggiornata se kept, adapt_priors per famiglia, auto-stop finestra 3). Report finale (baseline vs final, steps con p_value/reason, performance_index, durata). Fix agent_ack: il report viene consegnato all'agent UNA sola volta dopo il completamento.
- lab_registry.py: registry versionato v1.0.0, 12 tweak no-reboot (safe+medium) con family/prior/applicabilita' (nvidia_tel solo GPU NVIDIA, visual filtrato per prior<=0.10). Gli id combaciano col catalogo $TWEAKS dell'agent.
- lab_stats.py: Welch t-test (beta incompleta pure-Python, no scipy) + Mann-Whitney esatto + CV. Alpha adattivo 0.10 per n<5. Funzione significance() condivisa (riusabile in Fase 2 synergy/validazione).
- models.py: LabStartInput/LabRunInput/LabEventInput. pc.py: mode 'lab' aggiunto alle 2 _ALLOWED_URI_MODES (launch-uri firmato funziona).
### Agent PowerShell (ps_agent.py, PARSE OK pwsh 7.4.6)
- Nuovo MODE 'lab': auto-elevazione UAC se non admin (Start-Process -Verb RunAs col file locale), Start-Fps obbligatorio, loop di polling su /api/agent/lab/next. Funzioni: LabApi/LabEvent, Get-LabTick (frametime grezzi PresentMon per tick), Wait-LabGame (attesa gioco + check abort ogni 12s), Invoke-LabRun (finestra 90/120s -> fps_avg, 1% low, 0.1% low, ft_var, frames + telemetria cpu/gpu). Snapshot: Checkpoint-Computer (punto ripristino, tollerante al limite 24h) + stato dei tweak candidati. Apply via Invoke-ApplyTracked + Save-Backup; rollback via Invoke-RestoreTweak. Abort: annulla tutti i tweak del Lab (rollback_ids dal backend, fallback lista locale).
### Frontend
- Nuova pagina pages/Lab.jsx (rotta /app/lab, nav 'Laboratorio'/'Performance Lab', icona FlaskConical, i18n nav.lab it+en). Setup (rischio + finestra 90/120s + preview candidati + stima durata), Connect card (nota ADMIN + OneClickLaunchButton mode=lab + SecureRunBlock), vista live (stepper 4 fasi, status pill, baseline card, timeline tweak kept/rollback/coda, log live, polling 2.5s, bottone Interrompi), report finale (gain totale, 1% low, performance index, steps con p-value, Nuova sessione), aborted card.
### Test
- Sim E2E backend: /app/backend/tests/test_lab_phase1_sim.py (CV/outlier, welch, kept/rollback, auto-stop marginale, report, abort, 401). Endpoint pytest: tests/test_lab_phase1_endpoints.py (7/7). testing_agent iteration_44: backend 100%, frontend 100%, lab_sessions ripulite.
### FASE 2 (prossima, da spec /app/memory/laboratorio-automatico-spec.md)
- Reboot-resume (tweak con riavvio: mpo/gpu_msi/timer/HAGS + requires_reboot_resume/pending_reboot_test_id), synergy pass greedy su coppie kept, validazione gioco reale 5-10 min. FASE 3: prior aggregati fleet + suggerimenti BIOS guidati.

## Aggiornamento 2026-07-29 (2) — Traduzioni mancanti completate (i18n IT/EN al 100%)
Audit completo del frontend: individuate e tradotte tutte le stringhe hardcoded in italiano che apparivano anche con lingua EN.
- Componenti resi bilingue (pattern isEn() da @/i18n): OneClickLaunchButton (label/toast/fallback), MobileHandoffModal (QR telefono), AuthMobile (magic link), PasswordResetsPanel (pannello admin), TrialUpgradeBanner (countdown/CTA/prezzi), ObsOverlayPanel (tutta la UI overlay OBS + guida OBS), FullBenchmarkReport (empty state), FooterExtras (toast email).
- Pagine: Billing (interamente tradotta), Admin (modali grant/broadcast, tabella utenti, dettagli, stat cards, paginazione), MyPc (nuovo dict EN CPU_TEMP_REASONS_EN per le 6 diagnosi temp CPU), Landing (usePageMeta title/description per lingua), Network (label bottone bufferbloat), Advisor (aria-label + preview immagine).
- i18n.js: aggiunte sezioni mancanti it+en: freshness (badge sync header con plurali _one/_other), mobile (handoff), milestones (widget XP sidebar).
- Fix: rimosso frammento duplicato in MobileHandoffModal introdotto da un edit. Parse Babel di tutti gli 88 file jsx OK.
- Verifica: screenshot EN (dashboard/admin/billing: "Sync suggested", "Phone", "to next tier", "Administrator panel", "Billing & plan") e IT via toggle lang-it (tutto in italiano, nessuna regressione). Nota: la lingua dell'account salvata sul profilo sovrascrive localStorage al login (comportamento esistente, corretto).

## Aggiornamento 2026-07-29 (3) — Auto-detect lingua browser + hreflang/SEO internazionale
- i18n.js: aggiunto "querystring" (?lang=it|en) come prima fonte di rilevamento (poi localStorage -> navigator). Il rilevamento navigator al primo accesso era gia' attivo (fallback smart IT/EN); la preferenza account continua a prevalere dopo il login.
- hooks/usePageMeta.js: riscritto — oltre a title/description ora sincronizza og:title/og:description/og:url, twitter:title/description, og:locale + og:locale:alternate (it_IT/en_US), canonical su https://forgefps.dev{path} e link hreflang it/en/x-default dinamici per rotta (usa useLocation).
- public/index.html: aggiunti canonical statico, hreflang it/en/x-default e og:locale per i crawler senza JS.
- public/sitemap.xml: esteso da 3 a 10 URL pubblici (/, /pricing, /guida, /demo, /changelog, /security, /privacy-telemetry, /terms, /login, /register) con xhtml:link hreflang alternates per ognuno. XML validato.
- Verifica Playwright: ?lang=en su storage pulito -> UI EN, html lang=en, og:locale=en_US, boostpc_lang=en; ?lang=it -> IT; canonical/hreflang dinamici corretti su /pricing.

## Aggiornamento 2026-07-29 (4) — Fix auto-logout ogni 15 minuti (refresh token ora usato)
Domanda utente: "ogni quanto si slogga un utente?" -> scoperto bug: access token 15 min, refresh token 7 giorni MA il frontend non chiamava mai /api/auth/refresh -> logout di fatto ogni ~15 min.
- Fix (scelta utente: opzione a): interceptor axios in /app/frontend/src/lib/api.js — al primo 401 chiama POST /auth/refresh (promise condivisa tra richieste concorrenti, flag _retry anti-loop, esclusi /auth/refresh|login|register|logout) e riprova la richiesta originale.
- Backend gia' corretto: /refresh ruota ENTRAMBI i cookie (sliding) -> sessione dura finche' l'utente usa l'app almeno 1 volta ogni 7 giorni.
- Test: curl (refresh con solo refresh_token -> nuovi set-cookie + /me ok) e Playwright (rimosso access_token, tenuto solo refresh -> ricarico /app -> sessione sopravvive, access rigenerato). PASSATO.
- Nuovo comportamento: logout automatico solo dopo 7 giorni di inattivita' totale (o logout manuale). Va rideployato in produzione per avere effetto su forgefps.dev.

## Aggiornamento 2026-07-29 (5) — Laboratorio Automatico FASE 2 (FATTO, iteration_45 + fix verificato)
### Reboot-resume (tweak con riavvio)
- lab_registry v1.1.0: aggiunti mpo/gpu_msi/timer (requires_reboot=True, medium), ordinati IN CODA (meno riavvii). LabStartInput.include_reboot (default true) + toggle UI.
- Flusso: apply_tweak(requires_reboot) -> event tweak_applied{requires_reboot} -> status awaiting_reboot -> agent registra RunOnce HKCU + %LOCALAPPDATA%\FrameForge\lab_resume.ps1 (bootstrap che riscarica lo script e rilancia -Mode lab), prompt S/N per shutdown /r -> dopo login: next=reboot_required, agent confronta LastBootUpTime vs applied_at -> event reboot_done -> 1 run WARM-UP da 45s (scartato) -> 3 run test normali.
### Synergy pass
- Dopo il test loop (queue vuota o auto-stop) con >=2 kept no-reboot di famiglie diverse senza conflitti: max 2 coppie greedy (ordinate per somma delta). Per coppia: synergy_toggle OFF (rollback entrambi) -> 2 run -> toggle ON (riapplica) -> 2 run -> combined vs somma singoli, sinergia se > x1.15. Stato in sess["synergy"], risultati in report.synergies_found.
### Validazione gioco reale
- Status validation: 1 run da 300s con config finale -> real_gain vs predicted (baseline finale vs baseline0), discrepancy=true se real < 50% predicted (con predicted>=2%). In report.validation. _complete dopo.
### Altro
- next() ritorna action='transition' durante i cambi di fase (l'agent ripolla senza messaggi fuorvianti). Report esteso: synergies_found, validation, reboots_required.
- UI Lab.jsx: stepper 6 fasi (+ Synergy, Validazione), toggle lab-reboot-toggle nel setup (14<->11 candidati), RebootBanner (lab-reboot-banner), SynergyCard (lab-synergy-card), ValidationBlock (lab-validation-block), sinergie+riavvii nel report.
- BUG RISOLTO: durante un fix di file corrotto erano andati persi i 3 componenti UI (ValidationBlock/RebootBanner/SynergyCard -> crash pagina con report). Ri-aggiunti, verificato con screenshot: report +15.84% con validazione e sinergia visibili.
- Test: test_lab_phase2_sim.py (E2E completo PASS), test_lab_phase2_endpoints.py (8/8, creato dal testing agent), test_lab_phase1_sim.py aggiornato al nuovo flusso (PASS). testing_agent iteration_45: backend 100%.
### FASE 3 (prossima, da spec)
- Prior aggregati fleet (per hardware simile) + suggerimenti BIOS guidati (XMP/EXPO, Resizable BAR) con istruzioni manuali e verifica post-riavvio.

## Aggiornamento 2026-07-29 (6) — Laboratorio Automatico FASE 3 + report condivisibile brandizzato (FATTO, iteration_46 = 100%)
### Fleet aggregated priors
- lab.py `_fleet_blend(candidates, hw)`: fonde il prior statico con lo storico anonimo `db.lab_fleet_stats` (per hw_class es. nvidia_amd), min 3 campioni, peso w=min(0.7, n/(n+10)), rate clampato 0.05-0.9; candidato arricchito con `fleet:{tested,kept,avg_delta_pct}`. Update fleet stats con $inc a ogni decisione kept/rollback. `_hw_class()` da gpu+cpu regex. Applicato sia a /lab/start (log "Prior arricchiti...") che a /lab/registry.
### Suggerimenti BIOS guidati
- lab_registry.bios_suggestions(specs): xmp (RAM sotto profilo: confronto ram_speed_mhz vs ram_speed_nominal_mhz da ps_agent + soglia base DDR4/DDR5), rebar (GPU RTX 3000+/RX 6000+/Arc, verifica NVIDIA CP/AMD Software), dual_channel (ram_modules==1). Ognuno con title/why/steps/expected_gain. Salvati in sessione + inclusi nel report finale.
### Report condivisibile brandizzato
- Lab.jsx ShareCard off-screen (620px, FRAMEFORGE LAB + gain gigante + FPS before→after + kept steps con p-value + validazione + footer forgefps.dev) esportata in PNG via html-to-image toPng (pixelRatio 2, skipFonts:true per evitare SecurityError cross-origin Google Fonts — fix verificato: 0 errori console). Web Share API con fallback download frameforge-lab-report.png + toast. UI: BiosSuggestions (details espandibili, lab-report-bios / lab-bios-{id}), fleet hint nel setup (lab-fleet-hint "N test su PC con hardware simile").
### Verifica
- Backend self-test curl: registry con fleet reali (26 test telemetry nvidia_amd), bios=['rebar'], report completo con bios_suggestions/synergies/validation. Sim Fase 1+2 ri-eseguiti PASS (NB: vanno lanciati come `python tests/test_lab_phaseN_sim.py`, NON via pytest — xdist li esegue in parallelo → 409 sessione attiva). PS PARSE OK (pwsh).
- testing_agent iteration_46: frontend 100% (report card, gain +15.84%, BIOS expand, share download reale, fleet hint 69 test, toggle reboot 14<->11, persistenza dopo reload).
- LABORATORIO AUTOMATICO COMPLETO (Fasi 1+2+3).

## Aggiornamento 2026-07-29 (7) — JSON-LD structured data sulla landing (FATTO, verificato)
- public/index.html: aggiunto script application/ld+json con @graph schema.org: Organization (#org), SoftwareApplication (#app: UtilitiesApplication, Windows 10/11, featureList, Offer price 0 EUR, softwareHelp=/security, releaseNotes=/changelog, inLanguage it+en), WebSite (#website). URL assoluti su forgefps.dev (coerenti con canonical/OG).
- Verificato: restart frontend (index.html richiede restart), JSON servito e parse-valido, landing renderizza senza regressioni (h1 presente).
- NON implementati (decisione utente): title keyword-rich (proposta 2), sezione FAQ + FAQPage schema (proposta 3), apertura robots.txt ai crawler AI search (proposta 4 — spiegata all'utente: consentire bot di ricerca tipo OAI-SearchBot/PerplexityBot tenendo bloccati quelli di training). Restano nel backlog visibilità.

## Aggiornamento 2026-07-29 (8) — robots.txt: bot AI search ammessi esplicitamente (FATTO, verificato)
- CONTESTO: il robots.txt servito ha un blocco "Cloudflare Managed content" iniettato a monte (edge) che blocca i bot di TRAINING (GPTBot, ClaudeBot, CCBot, Bytespider, Google-Extended, meta-externalagent, Amazonbot, Applebot-Extended) — non modificabile dal codice e va bene così.
- public/robots.txt riscritto: gruppi espliciti Allow:/ + Disallow:/app/ per i bot di AI SEARCH (OAI-SearchBot, ChatGPT-User, PerplexityBot, Perplexity-User, Claude-SearchBot, Claude-User, DuckAssistBot, MistralAI-User) così restano ammessi anche se la blocklist gestita cambia. Wildcard * e Sitemap invariati.
- Verificato: restart frontend, robots.txt servito con i nuovi gruppi + blocco Cloudflare intatto, llms.txt HTTP 200, landing renderizza (h1 ok).
- Backlog visibilità residuo: title/description keyword-rich (proposta 2), sezione FAQ + FAQPage schema (proposta 3).

## Aggiornamento 2026-07-29 (9) — Lab FASE 4: stutter score, latenza input, mini-lab verifica BIOS/driver, storico (FATTO, sim PASS + iteration_47 = 100%)
### Stutter score nel criterio kept/rollback (lab.py)
- Decisione test estesa: STUTTER_GUARD (fps kept ma 1% low <= -5% -> rollback "fluidita' peggiorata"), FLUIDITY keep (fps neutri >= -0.5% ma 1% low >= +3% con Welch significativo sui fps_p1 -> kept). Nuovi campi result: significance_p1, decision_basis (fps|fluidity|stutter_guard). Costanti: STUTTER_KEEP_PCT=3, STUTTER_GUARD_PCT=-5, FPS_NEUTRAL_PCT=-0.5.
### Latenza input nel Lab
- ps_agent Get-LabTick: parsa anche colonna PresentMon MsUntilDisplayed (iLat, byLat per app) -> Invoke-LabRun somma lat e aggiunge run.latency_ms (>=50 campioni). _run_stats calcola latency_ms medio; delta.latency_ms per tweak (test - baseline); se kept e <= -1ms -> ", input lag -Xms" nel reason. Report: steps.latency_delta_ms + total_latency_delta_ms; UI chip "Xms lat" ciano + stat "Input lag" (lab-report-latency), mostrati solo se dati presenti.
### Mini-lab di verifica (kind=check) — chiude il loop BIOS + regression check driver
- POST /api/lab/check {reason: bios_xmp|bios_rebar|bios_dual|driver_update|manual} (LabCheckInput): richiede ultimo Lab completo come riferimento (409 se sessione attiva, 400 senza ref). Sessione kind=check: waiting_agent -> baseline (CHECK_RUNS=2, riusa azione run_baseline dell'agent SENZA modifiche al loop PS) -> report {kind:'check', total_gain_pct vs check_ref, regression se <= -5%}. Warning nel log se gioco diverso dal riferimento. L'agent riceve 'complete' col report (campi baseline/final/total_gain compatibili con la stampa PS esistente).
- GET /api/lab/insights: confronta ultimo Lab completo (nuovo campo specs_at: ram_speed_mhz/ram_modules/gpu_driver salvato in lab_start) con pc_specs correnti -> items: bios_xmp (RAM +10% piu' veloce), bios_dual (moduli>=2), bios_rebar (sempre offerto se suggerito, conferma manuale), driver_update (gpu_driver_version cambiata).
- GET /api/lab/history: ultime 15 sessioni completed (kind, game, gain, kept, fps, check_reason, regression).
### UI Lab.jsx (+170 righe)
- InsightsCard (lab-insights-card, lab-insight-{id}, lab-check-start-{id}), HistoryCard (badge LAB giallo / CHECK ciano, badge rosso Regressione), CheckProgress (run x/2 vs riferimento), CheckResultCard (lab-check-result, lab-check-gain, banner verde confermato / rosso regressione + CTA nuovo Lab). Render: setup e report mostrano Insights+History; sessione check attiva ha vista dedicata (ConnectCard/CheckProgress+LogFeed). Step del report full con chip "1% low ±X%" e "±Xms lat".
### Test
- Sim E2E /app/backend/tests/test_lab_phase4_sim.py: PASS (fluidity kept, stutter guard rollback, kept con input lag -4ms, report con p1/lat/basis, insights [bios_rebar], check +3% no regression, check -10% regression, history, 422 reason invalida). Regressione sim Fase 1/2: PASS. PS PARSE OK (pwsh reinstallato in /opt/pwsh, ambiente lo ripulisce). testing_agent iteration_47: frontend 100% IT+EN, nessun bug.
- NOTE tech-debt dal testing agent (non bloccanti): Lab.jsx 734 righe da splittare in componenti; Insights/History fetch a ogni mount; 3x 401 cosmetici pre-login.

## Aggiornamento 2026-07-30 — Health check completo app (iteration_48) + 5 fix minori (FATTO, verificati)
- CHECK COMPLETO: backend 25/25 pass (auth, 401 protetti, 12 endpoint core, 422 advisor, security headers, 8 pagine pubbliche); frontend tutte le 8 pagine pubbliche + 15 /app/* renderizzano senza errori critici; AI verificata live (upgrade plan reale Claude, build job avviato, diagnosi personalizzata). Suite riusabile: /app/backend/tests/test_full_regression_iter48.py (idempotente).
- FIX applicati e verificati via screenshot:
  1. i18n leak "DA MIGLIORARE" nel Health ring Dashboard in EN -> ora t(`mypcpage.health.grade.${grade_key}`) (mostra "Needs work").
  2. i18n leak "5g fa" in Admin users table in EN -> fmtRelative riscritta con Intl.RelativeTimeFormat(locale i18n).
  3. Dashboard BenchmarkCard "0 / -100% vs previous" quando latest senza overall -> empty state "No benchmarks yet".
  4. CSP bloccava static.cloudflareinsights.com su /app/live -> aggiunto a script-src (server.py).
  5. UX Advisor: chat input sepolto sotto DiagnosePanel espanso (y=2046) -> useDiagnose auto-collassa la diagnosi se piu' vecchia di 1h e l'utente non ha preferenza esplicita (localStorage diagnose_collapsed); chat ora a y=742.
- Non-bug confermati: advisor chat esiste (era sotto il fold); scraping Amazon datacenter = fallback manuale atteso; 3x 401 pre-login cosmetici.

## Aggiornamento 2026-07-30 (2) — "Precision Pass" professionale su tutte le feature (FATTO, sim PASS + iteration_49 = 100%)
### A. Rigore statistico Lab
- lab_stats.py: nuove funzioni t_ppf (quantile t via bisezione), welch_ci (IC95 Welch su diff medie), cohens_d, holm_adjust (correzione Holm-Bonferroni).
- lab.py: delta.fps_ci_pct [lo,hi] + delta.effect_d per ogni tweak; report steps con ci_pct/effect_d/p_adj/holm_ok (per basis=fluidity il p e' quello su fps_p1); report.multiple_testing {method, alpha, kept_total, kept_confirmed} + report.drift_events.
- Drift check A/B/A: dopo ogni 3 risultati (recheck_after) e a cur=None, azione run_recheck (1 run vs baseline corrente). Drift <=3% -> stabile; altrimenti 3 run -> RE-BASELINE (sostituisce baseline runs+stats). Fase 'recheck' aggiunta a LabRunInput.
- Guardia termica agent (ps_agent): $script:LAB_TREF = media temp GPU baseline; Wait-ThermalStable attende (max 90s) che la GPU torni entro +3C prima di run_test/recheck/synergy/validation. Handler PS run_recheck aggiunto.
### B. Evidenza fleet visibile
- Lab.jsx SetupCard: lista 'Evidenza misurata dalla community' (lab-evidence-list, top 5 candidati con fleet.tested>=3): 'N PC · ±X% medio · tenuto Y%'. Nota rigore nel report (lab-report-rigor) con Holm + drift compensati. Step con IC95 e badge ambra 'non confermato dopo correzione Holm'.
### C. Health Score pro
- pc.py /pc-health esteso: fleet percentile (stesso vendor GPU, minimo 5 PC -> out.fleet {percentile,n,vendor}) + throttling GPU da pc_telemetry ultimi 300 sample (gpu_util>=90, clock < 92% del picco, temp>=80, >=5 eventi -> detected). MyPc.jsx: righe health-fleet-percentile e health-throttling (i18n fleetpct/throttle_yes/throttle_no). VERIFICATO live: admin ha throttling detected (17 eventi, picco 86C).
### D. Stima FPS calibrata fleet
- pc.py /fps/estimate: _fleet_fps cerca mediana FPS reali da pc_telemetry di utenti con stessa GPU (token regex rtx/gtx/rx/arc) e stesso gioco (>=2 utenti, >=30 sample) -> out.fleet + out.source ('fleet+ai'|'ai'). Games.jsx badge fps-source: 'Calibrata su dati reali: N PC...' vs 'Stima AI (nessun dato misurato...)' (i18n games.src_fleet/src_ai).
### E. Benchmark ripetuto
- ps_agent Run-Benchmark: CPU e RAM 3 ripetizioni -> mediana + cpu_cv_pct/ram_cv_pct/cv_pct/bench_runs/reliable (CV<=10). Benchmark.jsx footer bench-reliability (i18n mypcpage.bench_cv/bench_unreliable), mostrato solo se cv_pct presente.
### F. ReBAR/PCIe reali
- ps_agent Get-Specs (ramo NVIDIA): pcie_link/pcie_width/pcie_width_max da nvidia-smi query pcie.*; rebar_status on/off da BAR1 Memory Total (>=1024MiB = ON). lab_registry.bios_suggestions salta rebar se rebar_status=on; lab.py insights: bios_rebar diventa kind=confirm con detail 'ReBAR attivo rilevato' quando on.
### Test
- Sim: test_lab_phase4_sim.py esteso (recheck stabile, IC95, Holm 2/2) PASS; NUOVO test_lab_drift_sim.py (drift -6% -> re-baseline + drift_events) PASS; phase1/2 sims aggiornati con handler run_recheck e PASS; PS PARSE OK; pc-health curl OK. testing_agent iteration_49: frontend 100% IT+EN.
- Fix post-test: ResponsiveContainer minWidth/minHeight (warning Recharts), 'Priorita'->'Priorità' in lab_registry.
- NOTA: fleet percentile appare solo con >=5 PC stesso vendor con health nella fleet (in preview assente = atteso).

## Aggiornamento 2026-07-30 (3) — Fix ParserError agent + Startup Detection PRO (FATTO, verificato E2E)
### Fix critico segnalato dall'utente
- ParserError PS 5.1 riga ~5318: due statement fusi su una riga in Invoke-LabRun ('$arr = ...ToArray()  $sorted = ...') causato da un edit che aveva rimosso un newline. FIXATO.
- ROOT CAUSE della mancata detection: /api/agent/script SENZA ?t=token ritorna 1 riga di errore -> il parse pwsh dava sempre OK (falso positivo). PROCEDURA CORRETTA (in /app/memory/learnings.md): login -> /api/agent/token -> /api/agent/script?t=$TK -> wc -l > 5000 -> pwsh ParseFile. Script reale 5955 righe ora PARSE OK 0 errori.
### Startup Detection PRO (scelta utente: punto 1 + guida manuale, NO disattivazione via agent)
- ps_agent Get-StartupList v2 multi-fonte: (1) registry Run HKLM/HKCU/Wow6432Node con STATO REALE enabled/disabled da StartupApproved (primo byte pari=attivo), (2) cartelle Startup utente+comune con risoluzione .lnk via WScript.Shell, (3) task pianificati Logon/Boot non-Microsoft, (4) servizi Auto con path fuori \Windows\. Per voce: publisher da firma digitale (Get-AuthenticodeSignature, cache), ram_mb dal working set se processo attivo, source, enabled. Cap 60, fallback legacy Win32_StartupCommand, dedup name+source. Runtime smoke su pwsh Linux: ArrayList count 0 senza errori.
- ai_engine.analyze_startup: prompt arricchito (publisher/fonte/GIA' DISATTIVATO/RAM/cmd), regole pro: già disattivato->mantieni, non firmato->valuta+antivirus, mai antivirus/driver/critici, service->services.msc. VERIFICATO live: Steam disabled->mantieni, SospettoTool non firmato->valuta con sospetto, RAM citata nelle motivazioni.
- MyPc.jsx card startup: lista rilevata pre-analisi (badge Attivo/Disattivato, publisher o 'Non firmato', fonte tradotta, RAM MB, testid startup-detected-N) + hint disattivazione manuale; post-analisi AI: RAM inline nel nome + riga come-disattivare per source (Task Manager/Utilità pianificazione/services.msc). i18n IT+EN (mypcpage.startup_hint/on/off/unsigned/src.*/how_*).
- Backend invariato (startup dict pass-through già compatibile). Screenshot IT/EN OK entrambi gli stati.

## Aggiornamento 2026-07-30 (4) — Servizi Windows: quali disattivare (DETERMINISTICO, FATTO, verificato E2E)
- METODO scelto: niente AI — knowledge base curata + dipendenze reali + contesto PC. Zero costi, risposte riproducibili e sicure.
- /app/backend/services_kb.py (NUOVO): SERVICES_KB con ~28 servizi noti (telemetria: DiagTrack/dmwappushservice/NvTelemetryContainer, updater: edgeupdate*/gupdate*/AdobeARM, legacy: Fax/RemoteRegistry/RetailDemo/WMPNetworkSvc/SharedAccess/SCardSvr, condizionali: SysMain(cond ssd)/WSearch/Spooler+PrintNotify(cond printer)/Xbl*(cond xbox)/WbioSrvc/TabletInputService) con why bilingue it/en + condition. analyze_services(): regole pro — dependents>2 declassa disattiva->valuta; Stopped+Manual->gia_ok; cond ssd (disk specs match ssd/nvme)->SysMain disattiva; giochi xbox/minecraft->Xbl* mantieni; terze parti sconosciute Auto con nome updat|telemetr|crash|report->valuta. Sort per priorità+RAM, summary {disattiva,valuta,gia_ok,ram_mb_saveable}.
- Agent ps_agent: Get-ServicesAudit (Win32_Service Auto+Manual max 200: state, start_mode, shared svchost flag, ram_mb SOLO processi dedicati via ProcessId, dependents da ServicesDependedOn, ms=path in \Windows\). Inviato in primo scan ($__body.services_audit) e in Send-Data (sync). PARSE OK script reale 5990 righe.
- Backend: SpecsInput.services_audit, report-specs salva (cap 220) + services_audit_at; GET /api/services/analyze (deterministico, no AI) -> {available, audited_at, items, summary}.
- MyPc.jsx ServicesCard (services-card): summary (N disattivabili · M da valutare · tot · ~MB RAM), badge Disattiva/Valuta/Già ok/Mantieni, why nella lingua UI (campo bilingue dal backend, L(obj) picker), condizioni ambra, istruzioni services.msc con revert, stato Attivo/Disattivato·start_mode, show more/less oltre 10. i18n mypcpage.services_* IT+EN.
- TEST: unit della logica (9 casi: dependents declassa RemoteRegistry, NVMe sblocca SysMain, updater sconosciuto->valuta, Fax->gia_ok), E2E curl (inject audit via report-specs + analyze), screenshot EN OK. Nessuna azione automatica (scelta utente: solo guida).

## Aggiornamento 2026-07-30 (5) — Accuratezza startup: già-disattivati gestiti correttamente (FATTO, verificato E2E)
- Segnalazione utente: 'mi rileva programmi che sono già disabilitati'. Fix su 3 livelli:
  1. Agent: StartupApproved\StartupFolder usa il nome file CON estensione (.lnk) -> lookup enabled per voci folder ora prova nome+estensione e poi basename (prima falliva -> enabled null -> mostrate come attive).
  2. Backend /startup/analyze: ESCLUDE enabled=false dall'analisi AI (se tutti disattivati -> summary 'nessuna azione necessaria' senza chiamata AI). Verificato: Steam/Epic disabled esclusi, AI riceve solo attivi.
  3. UI MyPc: ordinamento attivi prima / disattivati in fondo con opacity-50, badge solo quando enabled è booleano certo (null = nessun badge, niente falso 'Attivo' sui dati vecchi), header 'N attivi all'avvio · M già disattivati (esclusi dall'analisi)' (i18n startup_counts IT+EN).
- PARSE OK script reale 5996 righe. Screenshot verificato (attivi verdi sopra, DISABLED grigi sotto).
- NOTA UTENTE (produzione): la card Servizi richiede il redeploy DOPO la feature servizi (il redeploy dell'utente la precedeva) + rilancio scan agent.

## Aggiornamento 2026-07-30 (6) — Falso positivo Windows Defender sullo scan agent (FIXATO, iteration_50)
- BUG UTENTE (produzione): dopo il redeploy servizi/startup non si aggiornavano + 'Windows Defender ha trovato minacce' dopo il primo scan. RCA: Get-StartupList usava New-Object -ComObject WScript.Shell per risolvere i .lnk della cartella Esecuzione automatica -> pattern identico ai malware di persistenza -> euristica Defender blocca/quarantena lo script -> scan interrotto -> nessun dato inviato (per questo servizi e startup non comparivano).
- FIX: (1) risoluzione .lnk riscritta senza COM: lettura bytes + regex Unicode/ASCII sul path .exe (_lnkTarget, testata con lnk sintetici); (2) rimosso anche l'ultimo COM Shell.Application da Get-CleanableMb (dimensione Cestino ora via Get-ChildItem -Force su $Recycle.Bin) segnalato dal testing agent; (3) nessuna stringa 'WScript'/'ComObject' in tutto lo script servito (grep = 0).
- TEST: testing_agent iteration_50 backend 6/7 -> dopo fix ComObject 7/7 (suite /app/backend/tests/test_services_startup_flow.py riusata), frontend 100% (services-card, ordinamento startup, conteggi, badge). PARSE OK script reale 6009 righe.
- ISTRUZIONI UTENTE: ripristinare/consentire il file in Defender (Protezione da virus > Cronologia protezione), redeploy, rilanciare scan. Se Defender risegnala, farsi dare il NOME esatto della minaccia per mitigazioni mirate (eventuale submission a Microsoft come falso positivo).
- Tech-debt noto (dal testing agent): ps_agent.py 6000+ righe da modularizzare; aggiungere guard-test CI che greppa ComObject/WScript per evitare regressioni.

## Aggiornamento 2026-07-31 (7) — Fix sync agent HTTP 400/422 (FATTO, verificato E2E)
- BUG UTENTE: `[FAIL] specs+health+startup -> HTTP 400` e `[FAIL] running_apps (1) -> HTTP 422` durante il primo scan.
- RCA 400: PS 5.1 invia il body Invoke-WebRequest in Latin-1 se il charset non è esplicito; i display name dei servizi Windows in italiano (lettere accentate, es. "attività") producono byte non-UTF8 -> FastAPI 400 "There was an error parsing the body". Riprodotto con curl body latin-1.
- RCA 422: bug noto PS 5.1, ConvertTo-Json srotola gli array a 1 elemento dentro le hashtable -> {"running_apps":"chrome"} invece di ["chrome"] -> Pydantic 422. Confermato dal "(1)" nel log utente.
- FIX: (1) ps_agent.py: tutti i POST verso /api/agent/report-specs (__FsPost, Send-Data, Send-Benchmark, Send-Games, boost_session) ora inviano bytes UTF-8 espliciti + ContentType 'application/json; charset=utf-8'. (2) models.py SpecsInput: field_validator mode=before su startup/services_audit/games/running_apps che wrappa gli scalari in lista (tollera anche client vecchi con array srotolati).
- TEST: pwsh Parser su script completo generato = SYNTAX OK; e2e curl: running_apps scalare 200 (prima 422), payload completo con accenti UTF-8 200 (prima 400), regressione legacy list[str] 200; suite tests/test_agent_launch_uri.py 14/14; test obsoleto backend_test.py (startup formato list[str] pre-0.7.4) aggiornato al formato list[dict] e passa.
- NOTA: lo script è servito dinamicamente da /api/agent/script -> i client ricevono il fix al prossimo avvio. In PRODUZIONE (forgefps.dev) serve il REDEPLOY.
- NOTA AMBIENTE TEST: la suite pytest completa richiede REACT_APP_BACKEND_URL esportato (cookie Secure non inviati su http://localhost); molti login ravvicinati fanno scattare la protezione brute-force (mfa_required) causando falsi negativi nei run full-suite.

## Aggiornamento 2026-07-31 (8) — Startup/Servizi: nascondi disattivati + tracking "Fatto" + filtro rumore (FATTO, verificato E2E)
- Scelta utente: opzioni 1+a+c. (1) Voci già disattivate nascoste di default: startup mostra solo attive + pulsante "N già disattivate — mostra" (startup-toggle-off); servizi 'gia_ok' nascosti + pulsante "N già ok — mostra" (services-toggle-ok).
- (a) Tracking "Fatto": report-specs confronta lo scan precedente — startup prima attiva ora disabled/rimossa -> pc_specs.startup_done; servizio consigliato (disattiva/valuta) sparito dall'audit (=Disabled/disinstallato, guard len>=10 anti scan parziali) -> pc_specs.services_done (cap 50, con ram_mb). Se la voce ricompare attiva viene rimossa dal done. UI: strisce verdi "✓ N disattivate dopo l'analisi: nomi" (startup-done-strip) e "✓ N servizi disattivati · ~MB RAM" (services-done-strip). /services/analyze ritorna anche "done".
- (c) Filtro rumore: services_kb.is_startup_noise(name, publisher) regex (SecurityHealth, Realtek/Waves audio, Synaptics/ELAN touchpad, igfx*, ctfmon, TextInputHost...). Flag 'noise' applicato a READ-TIME in GET /pc-specs (KB aggiornabile senza rescan), escluse da UI ("N voci di sistema nascoste"), dall'analisi AI startup e dal tracking done.
- TEST: E2E curl con utente dedicato (svc_test_4641@test.io / Test_Pass_123!): 3 scan simulati -> done popolati e ripuliti su riattivazione, noise mai nel done. Screenshot UI OK (strip verde, toggle, counter). Suite tests/test_services_startup_flow.py 7/7 (pwsh arm64 reinstallato in /opt/pwsh: NON persiste tra fork, riscaricare powershell-7.4.6-linux-arm64.tar.gz se serve).
- LEZIONE: edit paralleli multipli sullo stesso file possono perdersi silenziosamente (uno dei search_replace su pc.py risultò "successful" ma non presente) -> verificare con grep dopo batch di edit sullo stesso file.

## Aggiornamento 2026-07-31 (9) — MISSIONI Fase 1 (FATTO, verificato E2E + UI)
- Scelta utente: gamification "missioni" opzione (a) Fase 1 completa. Missioni = obiettivi ATTIVI (max 3 slot) verificati sui dati reali; distinte dalle milestones (trofei passivi). XP nello stesso pool tier user_progress.
- Backend: /app/backend/missions.py (catalogo 10 missioni + engine con 3 modes: delta=counter con baseline all'attivazione, since=conteggio docs con timestamp>=activated_at, absolute=health score) + routers/missions.py (GET /api/missions con auto-complete e just_completed one-shot, POST /activate/{code}, POST /abandon/{code}). Collection user_missions {active:{code:{activated_at,baseline}}, completed}. Starter auto-attivate al primo accesso: svc_purge, bench_first, advisor_consult.
- Missioni: svc_purge(services_done x2, 60xp), startup_slim(startup_done x2, 50xp), bench_first(benchmark, 40xp), health_80(score>=80, 60xp), scan_week(3 scan, 40xp), advisor_consult(20xp), tweak_hero(3 tweak, 50xp), net_check(bufferbloat, 30xp), boost_match(boost session, 40xp), lab_scientist(lab completed, 100xp). Verifica sfrutta il tracking 'Fatto' (aggiornamento 8) via done_at >= activated_at.
- Frontend: ActiveMissionsCard.jsx in cima alla Dashboard (progress bar, CTA diretta alla pagina giusta, toast just_completed); pagina Milestones.jsx riscritta con tab MISSIONI (attive con abbandona/CTA, disponibili con Attiva, completate) + tab TROFEI (contenuto precedente invariato, stessi data-testid); nav sidebar "Traguardi/Milestones" -> "Missioni/Missions"; i18n missions.* IT+EN.
- TEST: curl E2E (starter, slots_full 400, abandon/activate, completamento svc_purge +60xp con 2 scan, just_completed one-shot), screenshot UI (dashboard card, tab, attivazione da UI 2->3 righe, trofei con XP aggregato 70), regressione test_full_regression_iter48 25/25, nuova suite tests/test_missions.py 5/5 (nota: xp assert >= per milestone concorrenti tipo first_scan).
- FASE 2 (backlog): catena onboarding "Recluta" con step sequenziali. FASE 3: missioni settimanali proposte dall'AI sui dati del PC.

## Aggiornamento 2026-07-31 (10) — MISSIONI Fase 2 (Catena Recluta) + Fase 3 (Settimanali AI) (FATTO, verificato E2E + UI)
- Catena Recluta: 3 step SEQUENZIALI (recruit_scan 15xp -> recruit_optimize 25xp -> recruit_benchmark 30xp) con metriche LIFETIME (i veterani la completano subito al primo GET, con XP). Step successivo bloccato finche' il precedente non e' completo. Non occupa i 3 slot. Stato in user_missions.chain.completed. UI: stepper in cima al tab Missioni (nascosto se done) + riga badge RECLUTA nella dashboard card.
- Settimanali AI: 2 missioni/settimana generate una volta per ISO week (user_missions.weekly {week_id, missions}). 8 template parametrici VERIFICABILI (w_svc, w_startup, w_scan, w_bench, w_boost, w_net, w_advisor, w_health con target dinamico health+3..+10). Generazione: se specs.data.cpu presente -> AI via ai_engine._run_json (session weekly-missions-{uid}-{week}, ~4.5s una tantum) con contesto reale (health, servizi azionabili, startup attive, bench recenti, net, boost) e "why_it/why_en" personalizzati; altrimenti/on-error -> fallback deterministico a regole. Scadenza/rinnovo automatico al cambio settimana (expires_at = lunedi 00:00 UTC). UI: card ciano con "Perche': ..." + righe badge WEEK in dashboard.
- Verifica E2E notevole: 1 benchmark + 1 net test hanno completato 5 missioni in un colpo (bench_first, net_check, recruit_benchmark, w_bench, w_net) -> XP 110->280, tier Bronze->Silver.
- TEST: tests/test_missions.py esteso a 8/8 (chain initial locked/active, weekly fallback per utente senza specs, avanzamento chain, benchmark completa chain+weekly). Screenshot UI nuovo utente (stepper 0/3 + week cards + dashboard badges) e veterano (chain nascosta, weekly completate verdi con why AI che cita RTX 3070/i7).
- NOTA: pytest.ini usa xdist loadscope: i test dello stesso modulo restano in ordine sullo stesso worker. Il fallback weekly evita chiamate AI nei test (utenti senza specs.cpu).

## Aggiornamento 2026-07-31 (11) — Layout mission-driven (1+2+3+4) (FATTO, verificato UI + regressione)
- (1) Dashboard pulita: rimossa OnboardingChecklist (ridondante con Catena Recluta, funzione+memo eliminati da Dashboard.jsx); NextActionBanner "post-sync" soppresso quando ci sono missioni attive o catena incompleta; ActiveMissionsCard ora accetta prop `data` (fetch centralizzato in Dashboard) e mostra badge tier·XP nell'header (missions-card-tier).
- (2) Missioni contestuali: nuovo componente MissionContextStrip.jsx ({metrics}) mostrato in 5 pagine: MyPc (services_done/startup_done/health_score/optimize_total), Benchmark (benchmarks/benchmarks_total), Network (net_tests), Gaming (boost_sessions), DesktopAgent (pc_scans/pc_scans_total/tweaks_applied). Matcha la prima missione attiva (chain step > weekly > active) col metric della pagina. Backend: _weekly_enrich ora include metric e mode.
- (3) Celebrazione: MissionCelebration.jsx montato in Layout, overlay achievement-style (framer-motion, coda, 3s auto-dismiss, badge +XP) via CustomEvent globale "ff-mission-completed" dispatched da Dashboard/ActiveMissionsCard/MissionsTab/MissionContextStrip al posto dei vecchi toast. just_completed e' one-shot server-side quindi nessun doppio evento.
- (4) Sidebar raggruppata: Dashboard+Missioni (icona Swords) in alto, poi sezioni IL TUO PC (My PC, Lab, Network, BIOS), GAMING (Gaming, AI Advisor), ACQUISTI (Build, Upgrade, Tracker), STRUMENTI (Agent, Report, Commands). i18n section.pc/section.gaming IT+EN.
- TEST: screenshot E2E con utente reale (celebrazione visibile al login con +30 XP Network check, strip su My PC, nav a gruppi, checklist assente, tier badge presente); webpack compila; regressione test_missions 8/8 + iter48 25/25 = 33/33.

## Aggiornamento 2026-07-31 (12) — Trofei segreti + rarità flotta + vantaggi tier (B+C) (FATTO, verificato E2E + UI)
- TROFEI SEGRETI: 6 nuove milestone con "secret": True, category "secret" in milestones.py (totale catalogo 20): night_owl (flag night_owl_earned, scan ora UTC 22-04, set in report-specs), surgeon (flag, >=10 services_done+startup_done, check a ingest), mad_scientist (counter lab_experiments>=5, bump in lab.py _save via marker _bump_lab_milestone settato da _complete), speed_demon (flag, benchmark overall>=90 a ingest), mission_hunter (counter missions_completed>=10, bump in missions._award_xp), collector (games_detected unique>=15).
- MASKING: GET /api/milestones maschera i segreti bloccati (name "???", desc generica, icon Lock, no reward). Rivelati solo da sbloccati.
- RARITÀ: GET /api/milestones calcola rarity_pct per milestone (aggregation $unwind unlocked su user_progress, cache in-memory 1h). UI: badge Leggendario(<5%, viola)/Epico(<20%, ciano)/Raro(<50%, verde)/Comune + "X% dei giocatori".
- VANTAGGI TIER: SLOTS_BY_TIER in missions.py {bronze:3, silver:4, gold:5, platinum:6} applicato a get_state (slots.max) e activate (_max_slots). Pannello "Vantaggi tier" nel tab Trofei (tier corrente evidenziato, futuri con lucchetto). Report PDF: header ora include "TIER · XP" (Report.jsx fetch /milestones/me nel Promise.all).
- TEST: E2E curl (masking ???, speed_demon sbloccato con bench 92 -> nome rivelato + rarity 9.1% + 75xp -> tier gold -> slots.max 5; missions_completed counter=1 dopo completamento startup_slim). Screenshot UI (perks panel, badge SECRET viola, card ??? e Speed Demon rivelata con EPIC 9.1%). Regressione 40/40 (unico fail = pwsh mancante nel container, reinstallato -> passa; /opt/pwsh NON persiste, arm64!).
- NOTA: la sessione auth cookie scade in fretta nei test curl -> rifare login prima di batch GET.
