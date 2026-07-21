# Rebuild v0.6.7 — Migrazione a `--onedir` (elimina falsi positivi AV)

## Perché
Le build `--onefile` di PyInstaller vengono cronicamente flaggate come *dropper*
euristico da Windows Defender e cloud AV secondari (Kaspersky, Bitdefender, ...).
Da v0.6.7 passiamo a `--onedir`: cartella con `.exe` + DLL affiancate, distribuita
come **ZIP**. Costo per l'utente: uno step di unzip. Beneficio: **niente più
bloccati al download**.

## Procedura di build (una volta sola su un PC Windows con Python 3.10+)

```powershell
cd agent-build
.\build.bat
```
oppure
```powershell
cd agent-build
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Alla fine ottieni **due** output in `dist\`:
- `forgefps-agent\` — cartella con l'.exe + DLL (per installazione locale)
- `forgefps-agent.zip` — **archivio da caricare in Release**
- e lo **SHA256** del ZIP stampato a video.

## Test funzionale (2 min, richiesto)
1. Estrai `dist\forgefps-agent.zip` in un percorso pulito (es. `%USERPROFILE%\Desktop\test-forge\`).
2. Apri la cartella `forgefps-agent\`.
3. Doppio click su `forgefps-agent.exe` → deve mostrare il menu interattivo.
   ```
   forgefps-agent.exe --token IL_TUO_TOKEN --mode sync
   ```
4. Su una VM Windows 11 pulita: **il download del ZIP deve completare** senza il popup rosso
   "Detected as unsafe" di Chrome/Edge, e **Windows Defender non deve lampeggiare**.

## Pubblicazione sulla GitHub Release
1. Push del tag `v0.6.7` sul repo pubblico ForgeFPS → parte automaticamente il workflow
   `github-workflow-build-nosign.yml` (o `build-sign.yml` se hai attivato SignPath).
2. La Release viene creata con il ZIP e lo SHA256 nel corpo.
3. Nel repo Emergent, aggiorna `frontend/src/config/agent.js`:
   ```js
   export const AGENT_EXE_URL    = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.6.7/forgefps-agent.zip";
   export const AGENT_EXE_SHA256 = "<sha256 del zip dalla release>";
   export const AGENT_EXE_VERSION = "v0.6.7";
   export const AGENT_EXE_DATE    = "YYYY-MM-DD";
   ```
4. Redeploy del frontend.

## Se un vendor secondario flagga ancora
Apri `VENDOR_FALSE_POSITIVE.md`: contiene testi pronti per Microsoft/Kaspersky/
Bitdefender/Norton/ESET. Timeline attesa 1-7 giorni.

## Nota importante
- La build **--onedir** *non* può essere `--onefile` mai più: se torniamo a onefile
  perdiamo il beneficio anti-AV.
- Se serve un singolo file self-contained per certi utenti, offri lo `.ps1`
  (già disponibile in `/api/agent/script`) come alternativa: è ispezionabile e non
  viene flaggato.
