# FrameForge Agent — v0.7.9 Rebuild Guide

**Type:** Bug fix (auto-updater / UAC)
**Breaking:** No

## 🐛 Cosa cambia

Fix di 3 bug dell'auto-updater introdotto in v0.7.6:

1. **UAC dopo auto-update**: dopo un update, l'exe si riavviava SENZA argomenti
   → apriva la GUI optimize → self-elevation → popup UAC inatteso.
   Ora: se il lancio arriva da un bottone della dashboard (URI `frameforge://`),
   l'azione richiesta parte SUBITO e l'update viene applicato in background
   senza riavviare l'exe (`relaunch=False`).
2. **Update parziale (crash)**: `update.bat` copiava solo l'exe, non la cartella
   `_internal` → exe nuovo + librerie vecchie = crash al boot PyInstaller.
   Ora: `xcopy /E /Y` copia l'intera cartella onedir.
3. **Argomenti persi al relaunch**: nei lanci interattivi (doppio click) il
   relaunch post-update ora inoltra gli argomenti originali (es. `--token`).

## 🔨 Come rilasciare v0.7.9 (checklist)

1. Committa/pusha su GitHub i file aggiornati di `agent-build/`:
   - `forgefps_agent.py` (AGENT_VERSION = "0.7.9" + fix updater)
   - `version_info.txt` (0.7.9.0)
   - `forgefps-agent.manifest` (0.7.9.0)
   - `.github/workflows/build.yml` = copia di `github-workflow-build-nosign.yml`
     (ora include `--manifest` + safety check anti-requireAdministrator)
2. Crea il tag ESATTAMENTE `v0.7.9` (NO `v.0.7.9` col punto!) e pushalo:
   ```
   git tag v0.7.9 && git push origin v0.7.9
   ```
3. Attendi la GitHub Action verde → verrà creata la release con
   `forgefps-agent.zip` + SHA256.
4. Aggiorna `AGENT_ZIP_UPSTREAM` in `/app/backend/routers/pc.py` a
   `.../download/v0.7.9/forgefps-agent.zip`.
5. Redeploy su Emergent → gli agent v0.7.6+ si auto-aggiornano al prossimo
   lancio interattivo; i bottoni dashboard restano silenziosi durante l'update.

## ✅ Test manuale post-release

Su Windows, utente NON admin:

1. Con v0.7.8 installata, doppio click su `forgefps-agent.exe`
   → auto-update a 0.7.9 → la GUI si riapre da sola, NESSUN UAC.
2. Dashboard → "Sincronizza ora" / "Benchmark ora" / "Avvia monitor"
   → tutto silenzioso, nessuna finestra, nessun UAC.
3. Dashboard → "Applica ottimizzazioni" (mode=optimize)
   → UAC appare SOLO qui (comportamento voluto).

## 🩹 Fix per installazioni con UAC persistente (vecchio exe registrato)

Se l'UAC mostra "forgefps-agent.exe", il protocollo `frameforge://` punta
ancora a un VECCHIO exe (≤0.7.6 con --uac-admin). Procedura di riparazione:

1. Chiudi tutti i processi `forgefps-agent.exe` (Task Manager).
2. Elimina TUTTE le vecchie cartelle `forgefps-agent` (Downloads, Desktop, ecc.)
   lasciando solo quella nuova. Cerca `forgefps-agent.exe` con la ricerca di
   Windows per non perderne nessuna.
3. Apri il file `%APPDATA%\FrameForge\launcher.vbs` con Blocco Note e verifica
   il percorso exe: deve puntare alla cartella NUOVA.
4. Doppio click su `forgefps-agent.exe` (o `Avvia-FrameForge.bat`) della
   cartella nuova → rigenera `launcher.vbs` con il percorso corretto.
5. Testa un bottone della dashboard: deve partire senza UAC.
