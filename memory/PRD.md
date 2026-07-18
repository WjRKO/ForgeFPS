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

