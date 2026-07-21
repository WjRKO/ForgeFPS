# Rebuild v0.6.0 — checklist (build `--onefile`, invariata)

Tutto è già pronto: sorgente aggiornato (`forgefps_agent.py` v0.6.0), metadati versione
(`version_info.txt` → 0.6.0.0) e docs allineate. Segui i passi in ordine.

## 1) Build sul tuo PC Windows
```bat
cd agent-build
build.bat
```
(oppure `powershell -ExecutionPolicy Bypass -File build.ps1`)

Alla fine ottieni `dist\forgefps-agent.exe` e lo **SHA256** stampato a schermo.
**Copia lo SHA256**: ti serve ai punti 3 e 4.

## 2) Test rapido sul tuo PC (5 minuti)
- `forgefps-agent.exe --token IL_TUO_TOKEN` → menu
- Verifica la riga `[*] Profilo hardware: Desktop/Laptop, RAM X GB, disco SSD/HDD` quando applichi i tweak
- Opzione benchmark → controlla che stampi DPC, 4K IOPS, jitter e `SCORE /100`
- Sul sito, "Il mio PC" deve mostrare le nuove metriche dopo il sync

## 3) Pubblica la release su GitHub
```bash
git tag v0.6.0
git push origin v0.6.0
```
- Se usi il workflow SignPath (`github-workflow-build-sign.yml`) la release viene creata e firmata da sola.
- Altrimenti: crea la Release `v0.6.0` a mano su GitHub e carica `forgefps-agent.exe`,
  incollando lo SHA256 nelle note di release.

## 4) Aggiorna il sito (1 file)
Modifica `frontend/src/config/agent.js`:
```js
export const AGENT_EXE_URL = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.6.0/forgefps-agent.exe";
export const AGENT_EXE_SHA256 = "<SHA256 del punto 1>";
export const AGENT_EXE_VERSION = "v0.6.0";
export const AGENT_EXE_DATE = "<data di oggi>";
```
Poi **Deploy** dalla piattaforma.

## 5) (Consigliato) Anti falso-positivo
- Carica l'exe su https://www.virustotal.com e salva il link del report
- Se Defender lo flagga: segnala il falso positivo → https://www.microsoft.com/wdsi/filesubmission

## Note
- La build resta `--onefile` come richiesto (nessun passaggio a `--onedir`).
- Lo **script PowerShell sicuro** NON richiede rebuild: è servito dal backend e si aggiorna col Deploy.
