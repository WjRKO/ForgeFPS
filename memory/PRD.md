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
