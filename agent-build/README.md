# FrameForge — Build dell'app desktop (cartella + ZIP)

Questo kit produce **`forgefps-agent.zip`**: un archivio Windows contenente la cartella
`forgefps-agent/` con `forgefps-agent.exe` + le DLL affiancate. Il token non è incorporato
(si passa a runtime) e la cartella è verificabile via SHA256.

## Novità v0.6.7 — **build `--onedir`** (elimina i falsi positivi antivirus)
Da questa release **NON** usiamo più `--onefile`: PyInstaller onefile è un archivio
auto-estraente e Windows Defender lo classifica euristicamente come "dropper". Con
`--onedir` produciamo una cartella con `.exe` + DLL: nessun stub SFX, nessun unpacking a
runtime, **niente falsi positivi** anche senza firma Authenticode.

Se qualche vendor secondario dovesse ancora flaggarci, i testi pronti per la segnalazione
sono in [`VENDOR_FALSE_POSITIVE.md`](VENDOR_FALSE_POSITIVE.md) (Microsoft, Kaspersky,
Bitdefender, Norton, ESET).

## Novità v0.6 (Boost Adattivo + Benchmark v2)
- **Tweak adattivi**: l'agent rileva Laptop/Desktop, RAM totale e SSD/HDD e adatta le ottimizzazioni.
- **Nuovi tweak**: Fullscreen Optimizations OFF, Power Throttling OFF (solo desktop), Edge preload OFF.
- **Benchmark v2**: latenza DPC/scheduler (p95), 4K random IOPS, jitter ping, tempo di avvio Windows, SCORE 0-100.

## Novità v0.5 (GUI sicura)
L'agent apre una **GUI sicura** (opzione **G**, o `--mode securegui`): per **ogni** tweak
mostra **Problema trovato → Motivo → Modifica proposta → Impatto stimato** con un pulsante
**Applica** per singolo tweak. Backup automatico e "Ripristina tutto" sempre disponibili.
La GUI **non tocca MAI** Windows Defender, Firewall o servizi di sicurezza.

## Cosa contiene
- `forgefps_agent.py` — sorgente dell'agent (backend impostato su `https://forgefps.dev`)
- `build.bat` / `build.ps1` — script di build **`--onedir`** con PyInstaller + ZIP + SHA256
- `version_info.txt` — metadati versione dell'.exe (CompanyName, InternalName, OriginalFilename)
- `sign.bat` — firma locale dell'.exe con signtool
- `github-workflow-build-nosign.yml` — GitHub Actions per build **--onedir + ZIP** senza firma
- `github-workflow-build-sign.yml` — GitHub Actions per build + firma via SignPath (OSS)
- `SIGNING_AND_TRUST.md` — guida ai 3 percorsi per togliere gli avvisi (Microsoft / Certum / SignPath)
- `VENDOR_FALSE_POSITIVE.md` — **testi pronti** per segnalare falsi positivi ai principali AV
- `README.md` — questa guida

## Prerequisiti (una tantum)
1. Un PC **Windows 10/11**
2. **Python 3.10+** → https://www.python.org/downloads/ (spunta "Add Python to PATH")

## Build (2 minuti)
```
build.bat
```
(oppure `powershell -ExecutionPolicy Bypass -File build.ps1`)

Al termine trovi:
- **`dist\forgefps-agent\`** — cartella con l'.exe + DLL (installazione locale)
- **`dist\forgefps-agent.zip`** — archivio da caricare in Release (SHA256 stampato a video)

## Distribuzione
1. Crea una **GitHub Release** e allega `forgefps-agent.zip`.
2. Nella descrizione della release incolla il **checksum SHA256** del ZIP.
3. Aggiorna `frontend/src/config/agent.js` con URL + SHA256 + versione + data:
   ```js
   export const AGENT_EXE_URL = "https://github.com/<user>/ForgeFPS/releases/download/vX.Y.Z/forgefps-agent.zip";
   export const AGENT_EXE_SHA256 = "<sha256 del zip>";
   export const AGENT_EXE_VERSION = "vX.Y.Z";
   export const AGENT_EXE_DATE = "YYYY-MM-DD";
   ```

## Uso da parte dell'utente finale
```
# 1) Estrai forgefps-agent.zip (Explorer > Extract All)
# 2) Apri la cartella forgefps-agent
# 3) Doppio click su forgefps-agent.exe -> menu interattivo
#    oppure da PowerShell:
.\forgefps-agent.exe --token IL_TUO_TOKEN --mode optimize
```

Il token si trova nella pagina **Collega il PC** dell'account. Modalità: `optimize | sync |
benchmark | monitor | prematch | restore | securegui`.

## Avviso SmartScreen (atteso, senza firma)
Al primo avvio Windows mostra *"App non riconosciuta"* → **Ulteriori informazioni → Esegui comunque**.
Per rimuovere l'avviso serve la firma **Authenticode**:

### Firma digitale (opzionale, richiede certificato di code-signing)
```
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a dist\forgefps-agent\forgefps-agent.exe
```
Firma solo l'.exe interno alla cartella, poi ricomprimi in `.zip` prima di caricare sulla Release.

## Perché non `--onefile`?
- Onefile crea un archivio auto-estraente: al primo avvio l'.exe estrae DLL/pyd in `%TEMP%\_MEIxxxxxx\`.
- Questo pattern è **identico** a quello di alcuni dropper reali → Windows Defender lo flagga euristicamente
  con nomi come `Trojan:Win32/Wacatac.B!ml`, `Trojan:Script/Sabsik.FL.A!ml`, ecc.
- Onedir invece è una cartella normale con .exe + DLL affiancate: **zero heuristic hits** su Defender.
- Costo: l'utente deve estrarre uno ZIP prima di lanciare — pareggiato dal fatto che ORA il download non viene bloccato.
