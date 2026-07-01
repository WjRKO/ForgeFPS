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
- NEW: Rilevamento hardware reale del PC via desktop agent (opzione 7) → /api/agent/report-specs (auth token) → specs mostrate in "Il mio PC" e usate dall'AI Advisor per consigli su misura
- Tested: iteration_1 100%, iteration_2 100% (29/29 backend, frontend OK)

## Known Constraints
- Amazon blocca lo scraping HTTP (anti-bot) → fallback prezzo manuale (flusso principale)
- Desktop agent: script Python locale (azioni reali non possibili dal browser)

## Backlog / Next
- P1: Packaging desktop agent come .exe (PyInstaller) + auto-sync prodotti tracciati
- P1: Notifiche email/push quando prezzo scende
- P2: Rilevamento hardware PC reale via desktop agent (specs → consigli personalizzati)
- P2: Confronto prezzi multi-store (eBay, Amazon), storico più ricco
- P2: Export/condivisione build
