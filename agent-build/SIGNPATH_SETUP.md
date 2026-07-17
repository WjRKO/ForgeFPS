# SignPath — Setup passo-passo (firma GRATIS per open source)

Obiettivo: pubblicare il sorgente + far firmare automaticamente l'.exe da SignPath ad ogni release,
così Windows Defender/antivirus non lo bloccano più.

## FASE 1 — Prepara il repo pubblico (5-10 min)
Il repo `WjRKO/ForgeFPS` è già pubblico. Aggiungi (commit) alla **root** del repo questi file:

| File (da questo kit `agent-build/`) | Dove va nel repo |
|---|---|
| `forgefps_agent.py` | root (sorgente dell'exe) |
| `version_info.txt` | root |
| `LICENSE` | root |
| `github-workflow-build-sign.yml` | rinominalo in `.github/workflows/build-sign.yml` |
| contenuto di `CODE_SIGNING_POLICY.md` | incollalo nel tuo `README.md` |

Come fare (via web GitHub, senza git):
1. Apri il repo → **Add file → Upload files** → trascina `forgefps_agent.py`, `version_info.txt`, `LICENSE` → Commit.
2. **Add file → Create new file** → nome: `.github/workflows/build-sign.yml` → incolla il contenuto di `github-workflow-build-sign.yml` → Commit.
3. Modifica il `README.md` → incolla in fondo la sezione **Code signing policy** (da `CODE_SIGNING_POLICY.md`) → Commit.

## FASE 2 — Fai domanda a SignPath Foundation (5 min)
1. Vai su **https://signpath.org/apply.html**
2. Compila con:
   - **Project/Repository URL:** `https://github.com/WjRKO/ForgeFPS`
   - **License:** `MIT`
   - **Download URL:** la tua pagina Releases GitHub
   - **Description:** "FrameForge Desktop Agent: open PC-optimization tool for gamers/streamers (PyInstaller .exe). Applies documented Windows tweaks with consent + backup, never touches Defender/Firewall."
3. Invia (o manda a **oss-support@signpath.org**). Attendi approvazione (giorni → qualche settimana).

## FASE 3 — Dopo l'approvazione (configurazione, 15 min)
SignPath ti guiderà; in sintesi:
1. Installa la **GitHub App di SignPath** sull'organizzazione/repo.
2. In SignPath crea un **Project** (annota il `project-slug`) e una **Signing policy** (es. `release-signing`).
3. In GitHub → **Settings → Secrets and variables → Actions**:
   - **Secret** `SIGNPATH_API_TOKEN` = token generato in SignPath
   - **Variable** `SIGNPATH_ORGANIZATION_ID` = il tuo Organization ID
4. Nel file `.github/workflows/build-sign.yml` aggiorna `project-slug` e `signing-policy-slug` con i tuoi valori.

## FASE 4 — Rilascia la v0.6.0 firmata
Dal repo:
```
git tag v0.6.0
git push origin v0.6.0
```
(oppure crea il tag/release dalla UI di GitHub). Il workflow:
- builda `forgefps-agent.exe` (con metadati + no UPX),
- lo **firma** con SignPath,
- crea la **Release** con l'exe firmato e stampa lo **SHA256** nel riepilogo del job.

## FASE 5 — Collega il download
Mandami **URL della release + SHA256** (lo trovi nel job "Compute SHA256" o con `Get-FileHash`):
aggiorno il pulsante e l'hash nella pagina "Collega il PC".

---
### Nel frattempo (subito, senza .exe)
Se non riesci a scaricare l'.exe, usa il **Metodo sicuro** nella pagina "Collega il PC":
scarichi lo `.ps1` (non viene bloccato), verifichi l'hash e lo esegui. Ottieni la **stessa GUI sicura**
dell'.exe con `-Mode optimize`.
