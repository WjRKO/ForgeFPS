# REBUILD v0.8.0 — Stop definitivo UAC dai bottoni dashboard

## Cosa cambia (solo `forgefps_agent.py` + version bump)
1. **Niente elevazione per i lanci via URI** — `launch_secure_gui(mode, allow_elevation)`:
   quando il lancio arriva da `frameforge://` (bottoni dashboard) `allow_elevation=False`
   → nessun `ShellExecuteW("runas", ...)` in NESSUN caso, nemmeno come fallback con
   firma URI invalida/scaduta. La GUI si apre non-elevata ("Amministratore: NO").
2. **Anti-downgrade launcher** — `launcher.vbs` contiene il marker
   `' ## target=<path exe>|version=x.y.z`. Alla registrazione, se il launcher punta a
   un exe PIÙ NUOVO ancora esistente su disco, NON viene riscritto: un exe vecchio
   avviato per sbaglio non può più rubarsi il protocollo (causa dei UAC ricorrenti).
3. **Auto-riparazione RUNASADMIN** — all'avvio l'agent rimuove il flag
   "Esegui questo programma come amministratore" (HKCU `AppCompatFlags\Layers`)
   dal proprio path e dal target del launcher. Il flag sopravvive alla sostituzione
   del file ed è l'unica causa rimasta di UAC con manifest asInvoker.

## File toccati
- `forgefps_agent.py` → AGENT_VERSION = "0.8.0"
- `version_info.txt` → 0.8.0.0
- `forgefps-agent.manifest` → version 0.8.0.0 (resta **asInvoker**)
- `backend/data/changelog.json` → entry 0.8.0

## Checklist release (identica a v0.7.9)
1. Copia i file aggiornati nel repo GitHub dell'agent
2. Commit + tag **ESATTO** `v0.8.0` (NON `v.0.8.0`) + push tag
3. GitHub Actions (workflow build-nosign) builda `forgefps-agent.zip`
   - safety check anti-requireAdministrator già nel workflow
4. Scarica lo zip dalla release draft, calcola SHA256, passalo all'agente AI
5. L'agente AI verifica SHA + manifest, poi aggiorna:
   - `backend/routers/pc.py` → AGENT_ZIP_UPSTREAM → `.../v0.8.0/forgefps-agent.zip`
   - `frontend/src/config/agent.js` → URL/SHA/VERSION/DATE
6. **Redeploy produzione** (serve anche per GUI v3.1)
7. Sul PC: gli exe ≥0.7.9 si auto-aggiornano in background al prossimo lancio.
   Se il protocollo punta ancora a un exe VECCHIO (pre-0.7.6): eliminare le copie
   vecchie ed eseguire una volta il nuovo exe (o `forgefps-agent.exe --register-protocol`).
