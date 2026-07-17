# FrameForge — Build dell'app desktop (.exe)

Questo kit produce **`forgefps-agent.exe`**: un eseguibile Windows standalone, senza token
incorporato (il token si passa a runtime), così il file è generico, verificabile e firmabile.

## Novità v0.5 (GUI sicura)
L'agent ora apre una **GUI sicura** (opzione **G** nel menu, o `--mode securegui`): per **ogni** tweak
mostra **Problema trovato → Motivo → Modifica proposta → Impatto stimato** con un pulsante **Applica**
per singolo tweak. **Backup automatico** e **Ripristina tutto** sempre disponibili. La GUI **non tocca MAI**
Windows Defender, Firewall o servizi di sicurezza (guardrail integrati). Ricompila e ripubblica per aggiornare.


## Cosa contiene
- `forgefps_agent.py` — sorgente dell'agent (backend già impostato su `https://forgefps.dev`)
- `build.bat` / `build.ps1` — script di build con PyInstaller + calcolo SHA256
- `version_info.txt` — metadati versione dell'.exe (riducono i falsi positivi antivirus)
- `sign.bat` — firma locale dell'.exe con signtool (per Certum/SimplySign o .pfx)
- `github-workflow-build-sign.yml` — workflow GitHub Actions per build + firma gratuita via SignPath (OSS)
- `SIGNING_AND_TRUST.md` — **guida completa** ai 3 percorsi per togliere antivirus/SmartScreen (Microsoft / Certum / SignPath)
- `README.md` — questa guida

## ⚠️ L'antivirus segnala un virus? (FALSO POSITIVO)
Gli eseguibili creati con **PyInstaller** vengono **spessissimo** segnalati come malware da Windows Defender
e altri antivirus, anche quando sono puliti al 100%. È un **falso positivo euristico** (il bootloader di
PyInstaller è usato anche da malware reale, quindi i motori lo flaggano "per precauzione"). Il codice è
in chiaro in `forgefps_agent.py`: puoi leggerlo tutto.

**Cosa abbiamo già fatto per ridurlo:** `build.bat`/`build.ps1` ora aggiungono i **metadati versione**
(`version_info.txt`) e disattivano **UPX** (`--noupx`): due accorgimenti che abbassano molto le segnalazioni.

**Come eliminarlo del tutto (in ordine di efficacia):**
1. **Firma Authenticode** (soluzione definitiva): un `.exe` firmato non viene flaggato e sparisce anche SmartScreen.
   Certificati: DigiCert/Sectigo (a pagamento) oppure gratis per progetti open-source via **SignPath.io** o **Certum Open Source**.
2. **Segnala il falso positivo a Microsoft**: https://www.microsoft.com/wdsi/filesubmission
   (carichi l'.exe come "software non dannoso"; di solito lo mettono in whitelist in 1-3 giorni e Defender smette di bloccarlo per tutti).
3. **Verifica su VirusTotal**: https://www.virustotal.com — carichi l'.exe e vedi quali/quanti motori lo flaggano.
   Se sono pochi motori minori è quasi certamente un falso positivo.
4. **Alternativa immediata senza .exe**: usa il **Metodo sicuro** nella pagina *Collega il PC* (scarichi lo `.ps1`,
   verifichi l'hash, lo esegui): lo script PowerShell non viene flaggato come l'.exe e puoi leggerlo prima di eseguirlo.

## Prerequisiti (una tantum)
1. Un PC **Windows 10/11**
2. **Python 3.10+** → https://www.python.org/downloads/ (spunta "Add Python to PATH")

## Build (2 minuti)
Apri la cartella e lancia:
```
build.bat
```
(oppure `powershell -ExecutionPolicy Bypass -File build.ps1`)

Al termine trovi l'eseguibile in **`dist\forgefps-agent.exe`** e a schermo vedrai il suo **SHA256**.

## Distribuzione
1. Crea una **GitHub Release** e allega `forgefps-agent.exe`.
2. Nella descrizione della release incolla il **checksum SHA256** stampato dal build.
3. Comunicami l'URL del file (es. `https://github.com/<tuo-utente>/forgefps/releases/download/vX/forgefps-agent.exe`):
   collegherò il pulsante **"Scarica FrameForge"** nella pagina *Connect PC* a quel link e mostrerò il checksum.

## Uso da parte dell'utente finale
```
forgefps-agent.exe --token IL_TUO_TOKEN
```
Il token si trova nella pagina **Collega il PC** dell'account. Modalità opzionale: `--mode optimize|sync|benchmark|monitor|prematch|restore`.

## Avviso SmartScreen (atteso, senza firma)
Al primo avvio Windows mostra *"App non riconosciuta"* → **Ulteriori informazioni → Esegui comunque**.
Per rimuovere l'avviso serve la firma **Authenticode** (fase successiva):

### Firma digitale (opzionale, richiede certificato di code-signing)
```
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a dist\forgefps-agent.exe
```
Serve un certificato EV/OV da un'autorità (DigiCert, Sectigo, ...). Con la firma, lo SmartScreen sparisce.
