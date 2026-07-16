# FrameForge — Build dell'app desktop (.exe)

Questo kit produce **`forgefps-agent.exe`**: un eseguibile Windows standalone, senza token
incorporato (il token si passa a runtime), così il file è generico, verificabile e firmabile.

## Cosa contiene
- `forgefps_agent.py` — sorgente dell'agent (backend già impostato su `https://forgefps.dev`)
- `build.bat` / `build.ps1` — script di build con PyInstaller + calcolo SHA256
- `README.md` — questa guida

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
