# FrameForge — Segnalazioni Falsi Positivi (Vendor AV)

Da v0.6.7 la build usa `--onedir` invece di `--onefile`: questo tipicamente **azzera** i falsi
positivi euristici di Windows Defender sul bootloader PyInstaller. Se un vendor secondario
dovesse ancora flaggarci, usa i testi qui sotto (pronti da incollare).

Prima di inviare qualsiasi segnalazione:
1. Vai su https://www.virustotal.com/gui/file/<SHA256> e verifica quanti/quali motori flaggano il ZIP.
2. Segna il vendor esatto (nome motore + nome minaccia).
3. Prendi lo SHA256 dallo screenshot delle GitHub Releases o dal build log.

Dati fissi (riutilizzabili in tutti i moduli):

```
Vendor / Publisher : FrameForge (open source project)
Product name       : forgefps-agent
File name          : forgefps-agent.zip (contiene forgefps-agent/ con forgefps-agent.exe)
File type          : Windows console application, PyInstaller onedir bundle
Website            : https://forgefps.dev
Source code        : https://github.com/WjRKO/ForgeFPS
Purpose            : Diagnostica hardware PC, applicazione tweak reversibili di Windows,
                     bufferbloat test, benchmark. Nessuna comunicazione con C2, nessun payload,
                     tutte le modifiche di sistema hanno backup automatico in
                     %TEMP%\boostpc_backup.json e sono ripristinabili con `--mode restore`.
Signing            : (compila) Not signed / Signed by SignPath Foundation on <data> serial <s/n>
False positive     : Yes — heuristic detection on PyInstaller bootloader (common FP).
```

---

## 1) Microsoft (Windows Defender / Microsoft Defender SmartScreen)

Portal: **https://www.microsoft.com/en-us/wdsi/filesubmission**
Categoria: `Software developer` → `I believe this file has been incorrectly detected as malware`.

**Testo per il campo "Additional information":**

```
forgefps-agent is an open-source Windows PC optimization tool (source code available at
https://github.com/WjRKO/ForgeFPS). It is a Python application packaged with PyInstaller
--onedir (bundle folder with .exe + DLLs, no self-extracting stub). No obfuscation, no
packing, no UPX. The .exe embeds a version_info resource (CompanyName=FrameForge,
FileDescription=FrameForge Agent, InternalName=forgefps-agent).

The application applies documented Windows registry/service/DNS/power tweaks with a
mandatory before/after backup written to %TEMP%\boostpc_backup.json. Every change can be
reverted with `forgefps-agent.exe --mode restore`. The app never touches Windows Defender,
Windows Firewall or Windows Update.

Runtime behavior that may trigger heuristics:
- Reads system inventory (WMI Win32_Processor, VideoController, PhysicalMemory).
- Writes reversible entries under HKCU\...\SystemProfile\GameConfigStore, HKCU\Control
  Panel\Mouse, HKLM\...\Priority Control (with UAC prompt when required).
- Downloads a signed PowerShell tweak script from https://forgefps.dev/api/agent/script
  ONLY when the user picks the "sync" or "optimize" mode from the local GUI.

Please whitelist the SHA256 <INSERISCI SHA256 DEL ZIP QUI> and the InternalName
"forgefps-agent" for cloud AV heuristics.

Contact: security@forgefps.dev
```

---

## 2) Kaspersky

Portal: **https://opentip.kaspersky.com/** (upload file) e/o https://newvirus.kaspersky.com (email).

**Oggetto email:**  `False positive — forgefps-agent.zip (open-source PyInstaller onedir)`

**Corpo:**

```
Dear Kaspersky team,

your engine is flagging forgefps-agent.exe (SHA256 <SHA256>) as <NAME_OF_DETECTION>.
The file is the console entry point of an open-source Windows optimizer whose complete
source code is published under MIT license at https://github.com/WjRKO/ForgeFPS.

The executable is built with PyInstaller --onedir, no UPX, no obfuscation, and embeds
standard version metadata (CompanyName=FrameForge, FileDescription=FrameForge Agent,
OriginalFilename=forgefps-agent.exe). It never modifies Kaspersky-related components
and never disables real-time protection. All Windows tweaks are backed up before
being applied and can be reverted via the `--mode restore` flag.

Please review as a false positive and update your signature database.

Thanks,
FrameForge team — security@forgefps.dev
```

---

## 3) Bitdefender

Portal: **https://www.bitdefender.com/consumer/support/answer/29358/** (form "Report a false positive").

**Testo per "Description":**

```
forgefps-agent.exe (SHA256 <SHA256>) is flagged as <DETECTION_NAME> by Bitdefender.
This is the entry point of FrameForge, an open-source PC optimizer released at
https://github.com/WjRKO/ForgeFPS under MIT license.

Build: PyInstaller --onedir, no UPX, version_info.txt with CompanyName=FrameForge and
InternalName=forgefps-agent. The .exe reads local hardware inventory via WMI and applies
reversible Windows tweaks with a mandatory backup at %TEMP%\boostpc_backup.json. No
network calls apart from HTTPS to https://forgefps.dev (whitelist-friendly).

Kindly whitelist this SHA256 and the InternalName "forgefps-agent" as a false positive.
```

---

## 4) Norton (Gen Digital / NortonLifeLock)

Portal: **https://submit.norton.com/**  → `Dispute a detection`.

**Campi:**
- Product: Norton 360 / Norton Security
- Category: `Suspicious`, `PUP` or the one shown in your VT screenshot
- Detection name: <NAME_OF_DETECTION>
- File SHA256: `<SHA256>`

**Notes:**

```
Open-source Windows PC optimizer (FrameForge). Source at
https://github.com/WjRKO/ForgeFPS. Built with PyInstaller --onedir (no UPX, no
packer). The executable embeds standard version metadata and only performs
reversible Windows tweaks with automatic backups. Please review as a false
positive and whitelist the SHA256 in your cloud definitions.
```

---

## 5) ESET (NOD32 / Endpoint Security)

Portal: **https://support.eset.com/en/kb141** → email `samples@eset.com` con lo ZIP + password
di archivio `infected`.

**Oggetto:**  `False positive — forgefps-agent.zip (open-source, PyInstaller onedir)`

**Corpo:**

```
Hello ESET,

please review the attached forgefps-agent.zip (unpacked SHA256 of .exe: <SHA256>)
which ESET flags as <DETECTION_NAME>. This is the entry point of FrameForge, an
open-source Windows optimizer whose full source code is available at
https://github.com/WjRKO/ForgeFPS (MIT license).

The .exe is produced by PyInstaller --onedir, no UPX, no obfuscation. Version
metadata embedded (CompanyName=FrameForge, InternalName=forgefps-agent). All
Windows tweaks are logged in %TEMP%\boostpc_backup.json and can be reverted with
`forgefps-agent.exe --mode restore`.

Please whitelist this SHA256 and add "forgefps-agent" to your allowlist for future
builds.

Best regards,
FrameForge — security@forgefps.dev
```

---

## Timeline atteso
- **Microsoft**: 1–3 giorni, poi Defender smette di flaggare per tutti gli utenti.
- **Kaspersky/ESET**: 1–2 giorni, risposta via email con link update database.
- **Bitdefender**: 2–5 giorni.
- **Norton**: 3–7 giorni.

Se dopo 7 giorni un vendor non ha risposto:
1. Ricarica il file su VirusTotal (spesso i motori aggiornano da soli).
2. Apri un ticket di follow-up allegando il case ID della prima segnalazione.
