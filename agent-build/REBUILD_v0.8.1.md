# Rebuild v0.8.1 — Fix Auto-Pilot silent + Lab via URI

## Perché
L'exe v0.8.0 aveva due whitelist hardcoded che non conoscevano le modalità nuove:
1. `launch_silent_mode()`: mancava `autopilot` → il bottone "Avvia Auto-Pilot" della
   dashboard usciva in silenzio senza lanciare PowerShell (timeout "non risponde").
2. `_PS_UI_MODES`: mancavano `lab` e `autopilot` → il 1-click del Lab apriva la GUI
   optimize invece della console Lab.

## Cosa è cambiato in forgefps_agent.py
- `AGENT_VERSION = "0.8.1"`
- Whitelist silent: aggiunto `"autopilot"`
- `_PS_UI_MODES`: aggiunti `"lab"` e `"autopilot"`

## Workaround server-side attivo (nessuna fretta di rebuild)
Il backend ora firma gli URI Auto-Pilot con `mode=cleanup` (whitelistato anche
nell'exe 0.8.0) e lo script PowerShell mappa `cleanup` → autopilot. L'Auto-Pilot
quindi FUNZIONA anche con gli exe 0.8.0 già installati, dopo il redeploy.
Il rebuild 0.8.1 serve soprattutto per il 1-click del Lab.

## Procedura (identica a v0.8.0)
1. Push di `forgefps_agent.py` aggiornato nel repo GitHub WjRKO/ForgeFPS
2. Lancia il workflow GitHub Actions di build (vedi github-workflow-build-*.yml)
3. Crea la release con tag `v.0.8.1` e carica `forgefps-agent.zip`
4. Aggiorna `AGENT_ZIP_UPSTREAM` in `/app/backend/routers/pc.py` con il nuovo URL
   (la versione "latest" viene estratta da lì) e redeploy
5. Gli agent installati (>=0.7.9) si auto-aggiornano al prossimo lancio
