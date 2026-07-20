# FrameForge — Roadmap

> Priorità: **P0** = blocker/prossimo sprint · **P1** = alta · **P2** = media · **P3** = nice-to-have.
> Aggiornato al **2026-07-19** dopo release **v0.6.5** (AI Diagnostics + Learning Loop + Multi-modal Chat + Discord auto-sync).

---

## 🔴 P0 — Prossimo sprint (blocker)

### PyInstaller `--onedir` + testi vendor AV
- Motivazione: gli `.exe` PyInstaller `--onefile` sono cronicamente flaggati come "dropper" da Windows Defender/euristiche AV → conversione impatta trust del prodotto e conversion download.
- Migrazione build da `--onefile` → `--onedir` (cartella `forgefps-agent/` con `.exe` + DLL esterne).
- Aggiornare `agent-build/build.bat`, `build.ps1`, `github-workflow-build-nosign.yml`, `github-workflow-build-sign.yml`.
- Aggiornare `frontend/src/config/agent.js` per servire uno ZIP contenente la cartella.
- Testare download → unzip → esegui su Windows pulito senza flag Defender.
- Preparare testi standardizzati (email + form) per segnalare falsi positivi a: Microsoft (WDSI), Kaspersky, Bitdefender, Norton, ESET.
- **File toccati**: `agent-build/*`, `frontend/src/config/agent.js`, `frontend/src/pages/DesktopAgent.jsx` (UI zip vs exe).
- Deferred nella sessione precedente per priorità AI features → ora è top.

---

## 🟠 P1 — Alta

### Alert Storico Salute
- Notifica push (già configurato VAPID) quando l'Health Score PC scende sotto la sua **media rolling 30 giorni** con delta > X punti.
- Backend: cron/scheduler (APScheduler già in uso per price checks) su `db.health_history`.
- Frontend: preferenza opt-in in `/app/account` (soglia default -15 punti), toggle "Alert salute PC".
- Messaggio: "Il tuo Health Score è sceso da 87 a 62 (-25). Vuoi rifare un boost?" → CTA `/app/pc`.
- **File toccati**: `backend/scheduler.py` (nuovo o esteso), `backend/routers/pc.py`, `frontend/src/pages/Account.jsx`.

---

## 🟡 P2 — Media

### Report PDF completo
- Estendere `frontend/src/pages/Report.jsx` (che oggi esporta card semplice via `html-to-image` + `jspdf`).
- Aggiungere: **grafico storico Health Score** ultimi 90 giorni (recharts → canvas → PDF), **checklist tweak applicati** (dalla collezione `applied_tweaks`), **community insights** ("gli utenti come te hanno guadagnato +X FPS"), delta prima/dopo su ogni metrica del benchmark v2.
- Layout multipagina con branding FrameForge (logo + accent volt).
- Uso: creator che dimostrano il boost al cliente → forte value proposition.

### Condivisione SCORE benchmark
- Endpoint `/api/benchmark/share-image` che genera immagine social (1200×630 OG) con score + hardware + delta.
- Bottone "Condividi su Discord/Twitter/Reddit" nella card benchmark di `/app/pc`.
- Deep link a `/leaderboard` pubblico (una volta pubblicato).

---

## 🔵 P3 — Nice-to-have (monetization + growth)

### Modello SaaS Stripe Billing
- Attivare checkout Stripe per piani **Free** (attuale) / **Pro €9.99/mese** / **Creator €19.99/mese**.
- Pagina `/pricing` esiste già come informativa → collegare CTA a Stripe Checkout Session.
- Backend: `backend/routers/billing.py`, webhook Stripe per `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`.
- Aggiornare campo `user.plan` (già presente).
- **Note**: Stripe test key già in env preview; user dovrà configurare live key + product IDs in produzione.
- Chiamare `integration_playbook_expert_v2` per playbook aggiornato Stripe checkout.

### Conversioni avanzate Google Ads
- Implementare **email hashing SHA-256** (client-side + gtag `user_data`) per Enhanced Conversions.
- Migliora attribution matching → ROI campagne Google Ads.
- Modificare `frontend/src/lib/gtag.js` `trackConversion()` + Auth.jsx signup flow.

### Testimonianze + Contatore stelle GitHub
- Landing page: nuova sezione "Loved by 500+ gamers".
- 3-6 quote reali di utenti (raccogliere via Discord `#feedback` o form).
- Contatore live GitHub stars via `GET https://api.github.com/repos/WjRKO/ForgeFPS` (cache 1h backend).
- Social proof → boost conversion rate signup.

### Voice input AI Advisor
- Pulsante microfono nella chat `/app/advisor` accanto al paperclip immagine.
- Web Speech API (browser-native, gratis, no backend cost).
- Trascrizione live nella textarea, invio manuale.
- Bilingue IT/EN via `recognition.lang = i18n.resolvedLanguage`.
- Fallback: browser non supportati (Firefox) → nascondere il pulsante.

---

## 🧹 Refactoring / Tech debt

- **PRD.md è a ~700 righe** → considerare split PRD (statico) + CHANGELOG (già esistente) + ROADMAP (questo file).
- **Test coverage backend**: 162 test attuali, aggiungere copertura per `routers/advisor.py` (endpoints diagnose/feedback/outcome/applied-tweaks/followups) e `routers/discord.py`.
- **`backend/server.py`**: relativamente sottile grazie ai router → OK.
- **Immagini agent-preview.gif** (1.9 MB in public/assets): considerare compressione o CDN.

---

## ✅ Completati recentemente (v0.6.0 → v0.6.5)

Vedi `/app/CHANGELOG.md` per dettagli. Highlights:

- **v0.6.5** (2026-07-19): AI Diagnostics (JSON strutturato + persistence), Learning Loop (feedback thumbs, outcome tracking, community RAG-lite, "già attivo"), Multi-modal chat (image upload Claude Vision), Coach personas (5 modes), Follow-up chips, Message actions (copy/regenerate).
- **v0.6.4** (2026-07-19): Discord bot mini-guide (`/come-iniziare`, `/ruoli`, `/canali`), `/apply-creator` review flow con persistent views, sync auto ruolo Boosted, `/set-plan`, `/announce-release`, HOSTNAME-based env detection preview vs prod. Fix CORS wildcard, /api/stats query optimization.
- **v0.6.3** (2026-07-18): Footer landing esteso (Community column, Terms of Service, live Discord status badge), pagina `/terms` bilingue.
- **v0.6.2** (2026-07-18): Redesign `/app/dashboard` in Command Center (2-column sticky, Health Ring, Benchmark card con Discord share, Activity Feed, Onboarding checklist), preview GUI Edge card in `/app/desktop`.
- **v0.6.1** (2026-07-18): Redesign `/app/commands` e `/app/bios-restore`, integrazione Discord completa (bot + OAuth + webhooks), pagina `/guida`, tour react-joyride, GUI Edge WebView.
- **v0.6.0** (2026-07-17): Adaptive Boost Engine 35 tweak, Game Booster opt-in, Benchmark v2 (DPC/IOPS/jitter) con spiegazione AI Claude.
