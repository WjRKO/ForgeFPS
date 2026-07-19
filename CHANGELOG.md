# Changelog

Tutte le modifiche significative a **FrameForge** (agent + web app).
Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — Versioning: [SemVer](https://semver.org/lang/it/).

---

## [Unreleased] — 2026-07-19

### Added
- **AI Advisor "Diagnosi PC" (killer feature)**:
  - Nuovo endpoint `POST /api/advisor/diagnose` che chiama Claude Sonnet in modalità one-shot con schema JSON strutturato → ritorna `{summary, actions: [{title, description, impact, difficulty, kind, cta, priority}]}`.
  - Nuovo modulo `ai_engine.one_shot_advisor()` per invocazioni singole con context PC completo (no chat history).
  - Nuovo helper `_enrich_specs_for_ai()` in `routers/advisor.py`: arricchisce le specs con benchmark_history (ultimi 5) e tracker_summary (count + total_saved). Anche `advisor_chat` beneficia del context arricchito.
  - `pc_context_text()` in `helpers.py` estesa con sezioni `[TREND BENCH]` (delta % tra ultimo e primo benchmark degli ultimi 5) e `[TRACKER]` (numero prodotti + risparmio totale).
  - CRUD `/api/advisor/planned-actions` (GET list / POST create / POST done / DELETE) per la todo list "Salva per dopo".
  - Frontend: `<DiagnosePanel>` componente riutilizzabile in cima a `/app/advisor` con stati idle/loading/done/error, big button "Diagnosi PC AI", card risultati con azioni prioritizzate, badge difficoltà colorato (facile/medio/avanzato), impatto in verde, CTA "Apri agent"/"Pulisci disco ora" + "Salva per dopo" con toast conferma.
  - Empty state se PC non connesso → CTA "Connetti il PC →".
- **Discord — comandi mini-guida**:
  - `/help` completamente riscritto con embed rich (Onboarding · Gaming · Creator · Admin · Link utili).
  - Nuovi `/come-iniziare` (3 step onboarding), `/ruoli` (Boosted PC, Pro, Creator Verified, Staff), `/canali` (mappa canali).
- **Discord — flusso `/apply-creator`**:
  - Slash command con validazione URL (twitch.tv, youtube.com, youtu.be, kick.com).
  - View persistente `CreatorReviewView` con bottoni ✅ Approva / ❌ Rifiuta (custom_id fissi → sopravvive ai restart).
  - Cooldown 7 giorni dopo un rifiuto (configurabile via `DISCORD_CREATOR_REAPPLY_DAYS`).
  - Anti-doppio submit (max 1 pending per utente).
  - DM automatico all'utente con esito (approvazione: ruolo assegnato + link; rifiuto: cooldown days).
  - Embed originale aggiornato con colore verde/rosso e nota "APPROVATA/RIFIUTATA da @staff".
  - Nuove env: `DISCORD_ROLE_CREATOR_VERIFIED`, `DISCORD_CHANNEL_CREATOR_REVIEW`.
- **Sync automatico ruolo Boosted PC**:
  - Il periodic task nel bot Discord (già usato per Pro) ora sync anche il ruolo Boosted per tutti gli utenti con `discord_user_id` in DB → ruolo assegnato retroattivamente se OAuth flow ha fallito.
  - Refactor: nuovi helper `_sync_role()` (generico) + `_sync_all_roles_for_member()` (Boosted + Pro insieme).
- **`/set-plan` admin command** con `defer(ephemeral=True)` per evitare timeout Discord 3s.
- **`/announce-release <version> [force]`** admin command per forzare l'annuncio di una release. Nuovo helper `announce_release_by_version()` in `services/release_announcer.py`.
- **Auto-detect ambiente per release announcer**: check `HOSTNAME.startswith("agent-env-")` → in preview skippa automatico, in prod parte. Override manuale con `RELEASE_ANNOUNCER_ENABLED=true/false`.

### Fixed
- **CORS wildcard bloccante**: `settings.get_cors_origins()` filtrava `"*"` producendo lista vuota. Nuovo `get_cors_origin_regex()` usa `allow_origin_regex=".*"` compatibile con `allow_credentials=True`.
- **Email footer**: sostituita `hello@forgefps.dev` (non attiva) con `forgefps.support@gmail.com`. Al click ora copia negli appunti + toast Sonner "Email copiata".
- **Query non ottimizzate**: `/api/stats` ora fetcha solo 2 field da products; `/api/products/{id}` limita history a 200 record (era 1000).

### Changed
- Nuove collezioni Mongo: `diagnoses` (snapshot delle diagnosi AI), `planned_actions` (todo list utente), `creator_applications` (pipeline verifica creator).

## [0.6.3] — 2026-07-18
  - Nuovo componente riutilizzabile `FooterExtras.jsx` (`FooterCommunity` + `FooterLegal`) usato sia in `Landing.jsx` (5 colonne: Brand · Product · Community · Account · con legal row) sia in `MarketingChrome.jsx` (4 colonne).
  - **Discord** con badge live "🟢 XX online adesso" — dot verde pulsante — via `GET /api/discord/live-stats` (cache in-memory 5 min, fallback silenzioso se widget server non abilitato).
  - **GitHub** repo link + **Report a bug** (deep-link a `/issues/new/choose`) + email `hello@forgefps.dev`.
  - **Guida** aggiunta alla colonna Product (era invisibile).
- **Endpoint `GET /api/discord/live-stats` (pubblico, no auth)** in `backend/routers/discord.py`:
  - Chiama `https://discord.com/api/guilds/{DISCORD_GUILD_ID}/widget.json`.
  - Cache in-memory 5 min per limitare rate-limit.
  - Ritorna sempre 200: `{enabled, presence_count, invite_url, instant_invite, name}` — `enabled=false` se widget non attivo.
- **Nuova pagina `/terms`** (`Terms.jsx`): Termini di servizio con 9 sezioni bilingue IT/EN (Cos'è FrameForge, Account & sicurezza, Uso agent, Contenuti AI, Uso accettabile, Prezzi, Limitazione responsabilità, Modifiche termini, Contatti). Route lazy in `App.js`.
- **Legal row nel footer**:
  - Copyright "© 2026 FrameForge — Tutti i diritti riservati"
  - Link a Cookie policy (`/privacy-telemetry#cookies`), Terms of service (`/terms`), Privacy (`/privacy-telemetry`)
  - Firma discreta "Costruito con ❤️ da un gamer per gamer" (bilingue).
- **Env var `DISCORD_INVITE_URL`** letta da `/api/discord/status` e restituita al frontend → il bottone "Apri il server" nella Dashboard usa ora il link reale.
- **Feature flag `RELEASE_ANNOUNCER_ENABLED`** in `services/release_announcer.py`: default OFF in preview per evitare duplicati Discord tra preview e produzione. In prod si abilita via Custom Keys del pannello Deployments Emergent.
- **Chiave i18n `landing.nav_guide`** (IT: "Guida" / EN: "Guide") — mancava nonostante la route /guida esistesse.

### Fixed
- **Dashboard → "Apri il server" invito Discord non valido**: il link era hardcoded a `discord.gg/frameforge` (placeholder). Ora `Dashboard.jsx` legge `discord.invite_url` dallo status endpoint con fallback al vero invito permanente.
- **Duplicati changelog Discord**: preview e produzione avevano lo stesso `DISCORD_WEBHOOK_CHANGELOG` ma DB Mongo separati → l'idempotency `announced_releases` non copriva l'altro ambiente. Fix: flag `RELEASE_ANNOUNCER_ENABLED` con default OFF; solo la produzione (che imposta `=true` via Custom Keys) annuncerà.

### Changed
- **Rimozione hardcode `RELEASE_ANNOUNCER_ENABLED` dal `.env`**: il file `.env` è shared tra preview e prod, quindi il flag va gestito solo via Custom Keys del pannello Deployments (prod-only).

## [0.6.2] — 2026-07-18
  - Layout 2 colonne (main + sticky panel), coerente con `/app/desktop` e le altre tool pages.
  - **PC Hero card**: HealthRing grande con score 0-100 e grade colorato (verde/giallo/rosso), badge hardware CPU/GPU/RAM, contatori issue/warn, CTA "Ottimizza ora" con colore adattivo (rossa se score<55, gialla altrimenti). Se PC non connesso → empty state con CTA "Connetti il PC →".
  - **Benchmark card**: score latest, delta % vs precedente (verde/rosso), `Sparkline` degli ultimi 8 benchmark, bottone "Condividi su Discord" attivo solo se Discord linkato (chiama `POST /api/discord/share-score`).
  - **Activity Feed unificato**: merge cronologico di price drops (`/api/notifications`), ultimo benchmark, nuova release agent (mostrata solo se `localStorage.ff_agent_seen_v0.6.0` è false). Ordinato desc, top 6, con relative time.
  - **Recent Products** compatto con empty state migliorato.
  - **Sticky panel a destra**: `OnboardingChecklist` (5 step: Connect PC, First benchmark, Track a product, Link Discord, Enable 2FA — con checkmark verde, strikethrough, progress bar animata gradient volt→green; auto-hide a 5/5), `QuickActionsCard` (griglia 2×3 con Advisor/Agent/Games/Tracker/Builds/Network), `DiscordCard` (linked → avatar + username + link server; unlinked → CTA "Link account (30s)"), `AgentCard` (solo se nuova versione non ancora cliccata: badge NEW + CTA Download).
  - **Greeting contestuale**: "Ciao, {name} — Il tuo PC è a {score}/100" (se health disponibile), oppure "Hai risparmiato {saved}€" (se total_saved>0), oppure "Pronto a boostare il PC?" (fallback).
  - **Empty state hero**: `HeroEmpty` con 3 CTA giganti numerate (Fai il primo scan, Genera una build, Traccia un prodotto) mostrato solo se l'utente è brand new (no specs, no products, no builds, no chat sessions).
  - i18n: aggiunte ~45 chiavi sotto `dashboard.*` (IT + EN).
- **Preview GUI Edge nella sticky card `/app/desktop`**:
  - Nuovo componente `AgentPreview.jsx` con fallback a 3 livelli: `<video>` → `<img>` GIF → mock CSS animato.
  - Probe HEAD iniziale al `.mp4` per evitare flash: se non esiste va diretto al GIF.
  - GIF reale (1.9MB) caricata in `/app/frontend/public/assets/agent-preview.gif`.
  - Mock fallback CSS: finestra "FrameForge Agent" con title bar macOS-style, tab sidebar Gaming/Latenza/Rete/Sistema, 6 tweak con badge "GIÀ ATTIVO" a cascata, progress bar arcobaleno.
  - Badge overlay "LIVE GUI PREVIEW" con dot pulsante top-left, aspect 16:10.

### Changed
- **`/app/dashboard`**: layout completamente riprogettato (120 → 743 righe di codice). Le vecchie 4 stat card di base (tracked/builds/chats/saved) sono state sostituite dai widget dinamici sopra descritti.

## [0.6.1] — 2026-07-18
- **Redesign coerente `/app/commands` e `/app/bios-restore`** con lo stesso pattern sticky panel di DesktopAgent:
  - **Comandi Utili**: barra di ricerca fuzzy in tempo reale, filter chips (`Solo sicuri` / `Solo admin` / `Solo avanzati`), contatore "visibili/totali", hardware rilevato compact, jump-to categorie con badge count. Empty state se filtri non producono match.
  - **BIOS e Ripristino**: tabs BIOS/Restore spostati nel panel destro, hardware detected compatto, jump-to sezioni con pallino colorato + count, box "regola d'oro" compatto sempre visibile.
  - Layout `grid lg:grid-cols-[1fr_320px]`: contenuto scrollabile a sinistra, panel sticky a destra su desktop, stacking verticale su mobile.
- **Layout sticky action panel** in `/app/agent`: pannello destro con download button + versione + SHA256 + comando exe sempre visibili anche scrollando. Feature grid spostata in cima come value proposition. Metodo PowerShell ora in accordion collassato. Backend notice mostrato solo su preview (nascosto in prod). Su mobile il layout stacka in verticale (nessun impatto UX).
- **Integrazione Discord completa (A + B + C)**:
  - **A) Server community template**: `docs/DISCORD_SERVER_SETUP.md` con struttura 7 categorie/20 canali, 6 ruoli, testi regole/welcome, config bot moderazione (Dyno/YAGPDB), server onboarding con 3 domande, obiettivi Server Boost e Vanity URL.
  - **B) Bot Discord persistente (`discord.py 2.7.1`)**: worker `backend/discord_bot.py` gestito da supervisor come processo separato dal FastAPI. 5 slash commands sincronizzati nel guild: `/mypc` (Health Score), `/benchmark` (ultimo bench), `/leaderboard` (top 10), `/link` (istruzioni collegamento), `/help`. Handler `on_member_join` con welcome DM + auto-role Boosted PC.
  - **B2) OAuth2 account linking (`identify guilds.join`)**: `backend/routers/discord.py` con `/connect` (redirect Discord), `/callback` (state CSRF con TTL 10 min, exchange code, guilds.join, assign role opzionale), `/status`, `/disconnect`. Salva `discord_user_id`, `discord_username`, `discord_avatar`, `discord_linked_at` nel documento utente.
  - **C) Outbound webhooks**: `backend/services/discord_webhooks.py` con `post_release(version, notes_md)`, `post_price_drop(product, old, new)`, `post_milestone(text, subtitle)`, `post_raw()`. Colori brand FrameForge (`#E5FF00`, `#00E0FF`, `#00FF66`).
  - **Frontend**: nuova card "Discord" in `/app/account` con stato collegato/scollegato, avatar + username, pulsanti "Collega Discord" (colore Discord `#5865F2`) e "Scollega". Success banner al ritorno dal callback OAuth. Stringhe i18n IT/EN dedicate (chiave `account.discord_*`).
  - **Supervisor**: nuovo program `discord-bot` in `/etc/supervisor/conf.d/discord-bot.conf` (autostart, autorestart, log dedicati).
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
