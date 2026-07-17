# FrameForge — Firma dell'.exe & rimozione avvisi antivirus/SmartScreen

Questo documento spiega **3 percorsi** per far sparire l'avviso "virus" (falso positivo) e lo SmartScreen.
Riepilogo rapido:

| Percorso | Costo | Difficoltà | Elimina Antivirus | Elimina SmartScreen | Tempi |
|---|---|---|---|---|---|
| **A. Microsoft false positive** | Gratis | Bassa | Sì (solo Defender) | No | 1-3 giorni |
| **B. Certum Open Source (cloud)** | ~59 €/anno | Media | Sì | Sì (dopo reputazione) | 1-3 giorni verifica |
| **C. SignPath Foundation (OSS)** | Gratis | Alta (serve GitHub Actions) | Sì | Sì (dopo reputazione) | giorni/settimane approvazione |

> Nota: qualsiasi firma **cambia il file**, quindi lo **SHA256 cambia**: dopo aver firmato, ricalcola l'hash e mandamelo così aggiorno la pagina.

---

## A) Segnalazione falso positivo a Microsoft (fai SUBITO — gratis)
Rimuove la segnalazione di **Windows Defender** per tutti gli utenti, senza certificato.

1. Vai su **https://www.microsoft.com/wdsi/filesubmission**
2. Categoria: **"Software developer"** → tipo **"Incorrectly detected as malware/malicious" (false positive)**
3. Carica `forgefps-agent.exe` (o un link di download diretto alla release GitHub)
4. Nel campo **Additional information** (in inglese) scrivi qualcosa tipo:
   > "This is FrameForge Desktop Agent, an open PC-optimization tool for gamers/streamers built with PyInstaller. Source is public at https://github.com/WjRKO/ForgeFPS . It only applies documented Windows tweaks with user consent, creates a backup and never touches Windows Defender/Firewall. The detection is a PyInstaller false positive. Detection name: <quello mostrato da Defender>."
5. Prodotto: **Microsoft Defender Antivirus**
6. Invia. Di solito entro **1-3 giorni** Defender smette di bloccarlo.

Suggerimento: firmare l'exe (percorso B o C) **accelera** l'accettazione.

---

## B) Certum Open Source Code Signing (cloud / SimplySign) — ~59 €/anno, il più semplice per un singolo
È un certificato personale per sviluppatori open source. Firmi **in locale** con `signtool` (nessun GitHub Actions necessario).

### 1. Acquisto
- Vai su **sklep.certum.pl** (o partner) → prodotto **"Open Source Code Signing"** → versione **Cloud (SimplySign)** (~49 € + IVA).

### 2. Verifica identità (persona fisica, sviluppatore OSS)
Prepara:
- **Documento d'identità** (fronte/retro)
- **Prova di indirizzo** (bolletta recente)
- **URL del progetto open source** (es. https://github.com/WjRKO/ForgeFPS) con licenza OSI visibile
- Verifica **automatica**: ricevi un'email per fare la video-verifica (foto documento + volto).

### 3. Attivazione SimplySign (token virtuale, niente USB)
- App mobile **SimplySign** (Android/iOS) + **SimplySign Desktop** su Windows.
- Segui l'attivazione: email → codice segreto → scansione QR → login desktop con OTP.
- Il certificato compare come **smart card virtuale** in Windows.

### 4. Firma l'exe
Con SimplySign Desktop attivo (certificato nello store di Windows):
```
sign.bat
```
(usa `signtool sign /fd SHA256 /tr http://time.certum.pl /td SHA256 /a dist\forgefps-agent.exe`)

> ⚠️ Anche con firma valida, i certificati **OV/Open Source** costruiscono la reputazione SmartScreen col tempo/numero di download: all'inizio lo SmartScreen può ancora comparire, poi sparisce. La firma **EV** lo toglie subito ma costa molto di più e non è "open source".

---

## C) SignPath Foundation — firma GRATIS per progetti open source (la più "pulita", ma più impegnativa)
SignPath firma **solo artefatti costruiti automaticamente da GitHub Actions** dal sorgente pubblico (così garantiscono che il binario venga davvero dal codice). Quindi serve:
- Repo **pubblico** con il **sorgente** (`forgefps_agent.py` + `version_info.txt`)
- Una **licenza OSI** (MIT/Apache-2.0/GPL) nel repo
- Un **workflow GitHub Actions** che builda l'exe (te l'ho già preparato)
- Una **"Code signing policy"** pubblicata sulla home/README del progetto con la frase:
  *"Free code signing provided by SignPath.io, certificate by SignPath Foundation"*

### Passi
1. **Metti il sorgente nel repo pubblico** (non solo l'.exe): copia `forgefps_agent.py`, `version_info.txt` e aggiungi un file `LICENSE` (es. MIT).
2. **Copia il workflow**: prendi `github-workflow-build-sign.yml` di questo kit e mettilo in `.github/workflows/build-sign.yml`.
3. **Fai domanda** su **https://signpath.org/apply.html** (compila e invia a **oss-support@signpath.org**): indica repo URL, licenza, URL di download, descrizione.
4. Ad approvazione ottenuta:
   - Installa la **GitHub App di SignPath** sull'organizzazione.
   - Crea in SignPath un **progetto** (`project-slug`) e una **signing policy** (`release-signing`).
   - Aggiungi in GitHub: **Secret** `SIGNPATH_API_TOKEN` e **Variable** `SIGNPATH_ORGANIZATION_ID`.
   - Aggiorna nel workflow `project-slug`/`signing-policy-slug` con i tuoi valori.
5. **Rilascia**: fai `git tag v0.6.0 && git push --tags`. Il workflow builda, **firma** e crea la Release con l'.exe firmato.

---

## Dopo aver firmato / ripubblicato
1. Copia il **nuovo SHA256** dell'.exe firmato (lo stampa `sign.bat`, `certutil` o il workflow).
2. Mandami **URL della release + SHA256**: aggiorno il pulsante di download e l'hash nella pagina "Collega il PC".

## Consiglio pratico
- **Oggi**: fai la **segnalazione Microsoft (A)** — gratis, sblocca Defender in pochi giorni.
- **Questa settimana**: se vuoi la firma definitiva e sei un singolo dev, **Certum (B)** è la via più rapida (~59 €).
- **Se vuoi 100% gratis e sei disposto a rendere pubblico il sorgente + GitHub Actions**: **SignPath (C)**.
