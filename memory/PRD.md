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
