# FrameForge — Changelog

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
