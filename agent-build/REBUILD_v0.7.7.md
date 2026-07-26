# FrameForge Agent — v0.7.7 Rebuild Guide

**Ship date target:** 2026-07-26+
**Type:** Bug fix (UX regression)
**Breaking:** No

## 🐛 Cosa cambia

Rimuovo il flag `--uac-admin` dal build PyInstaller. Il manifest embedded nell'exe
ora e' `asInvoker`. Conseguenza pratica:

- **Nessun UAC prompt all'avvio dell'exe** (il caso comune: sync/monitor/benchmark
  triggerati dai bottoni della web dashboard tornano silenziosi come da UX
  originale pre-0.6.7).
- La logica di **self-elevation on-demand** e' gia' presente in
  `forgefps_agent.py:1127`: quando l'utente lancia `mode=optimize` (applicare
  tweak reali) e non e' admin, l'agent chiama
  `ShellExecuteW(None, "runas", "powershell.exe", ...)` e Windows chiede UAC
  **solo in quel momento**. Idem per il bottone "Riavvia come Amministratore"
  della GUI.
- **Retrocompatibile**: nessuna modifica al protocollo `frameforge://`, all'API
  o al formato dello ZIP.

## 📝 File modificati in questo commit

1. `agent-build/build.ps1` — rimosso `--uac-admin`, commento aggiornato
2. `agent-build/build.bat` — rimosso `--uac-admin`, commento aggiornato
3. `agent-build/forgefps_agent.py` — bumped `AGENT_VERSION = "0.7.7"`
4. `agent-build/version_info.txt` — bumped `filevers`/`prodvers`/StringStruct a `0.7.7.0`

## 🔨 Come rilasciare v0.7.7 (checklist)

Da una macchina **Windows** con Python 3.11+ e PyInstaller:

```powershell
cd agent-build
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Output atteso:
```
[3/5] Costruisco la cartella dist\forgefps-agent\ (onedir, metadati, no UPX, asInvoker manifest)...
...
[5/5] Checksum SHA256 del ZIP:
Algorithm : SHA256
Hash      : <NUOVO_HASH_SHA256>
Path      : <path>\dist\forgefps-agent.zip
```

Poi:

1. **Copia lo SHA256** dal terminale.
2. **Crea la GitHub release** `v0.7.7` su https://github.com/WjRKO/ForgeFPS/releases
   con `forgefps-agent.zip` allegato.
3. **Aggiorna `AGENT_ZIP_UPSTREAM`** in `/app/backend/routers/pc.py` da
   `.../v0.7.6/...` a `.../v0.7.7/...`.
4. **Aggiorna il changelog** in `/app/backend/services/release_announcer.py`
   (se applicabile) o `/app/frontend/src/pages/AppChangelog.jsx`.
5. **Redeploy** su Emergent → gli utenti riceveranno la notifica di update.

## ✅ Test manuale post-release

Su Windows, come utente NON admin:

1. Scarica lo ZIP v0.7.7, estrai, esegui `forgefps-agent.exe --token TOKEN`.
2. Verifica: **nessun popup UAC**.
3. Dashboard → "Launch monitor on your PC" → il monitor parte senza UAC.
4. Dashboard → "Applica ottimizzazioni" (mode=optimize) → **UAC appare qui
   solo** (comportamento voluto).

## 📊 Diagnostica utente-side che ha permesso di identificare il bug

- User: v0.7.6, UAC appare su Launch monitor / Sync / Live Monitoring.
- **Test bypass**: eseguire lo script `.ps1` direttamente in PowerShell (non via
  exe) → NON chiede UAC. Conferma isolata che il colpevole e' il manifest exe.
- Nessun Windows Update recente / policy locale — pulita responsabilita' del
  flag `--uac-admin` introdotto in v0.6.7 e sopravvissuto per errore fino a v0.7.6.

## 🔗 Ref

- Root cause: `agent-build/build.ps1` L21 (rimosso in questo commit)
- Self-elevation on-demand: `agent-build/forgefps_agent.py:1127`
- Release upstream: aggiornare `/app/backend/routers/pc.py:45`
