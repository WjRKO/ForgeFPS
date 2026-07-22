# Rebuild `.exe` v0.7.3 — Guida passo-passo

> **Obiettivo**: pubblicare il nuovo `.exe` FrameForge Agent con menu CLI rimosso
> + supporto "Cambia account" via GUI + tutta l'uniformità di terminologia
> P0+P1 del 2026-02-22.
>
> **Tempo stimato**: 10-15 minuti (di cui 5 di GitHub Actions build).
> **Cosa serve**: solo il tuo laptop con git installato + accesso al repo `WjRKO/ForgeFPS`.

---

## 📦 Cosa è già stato preparato per te (dal container Emergent)

Ho già aggiornato tutti i file necessari nella tua working copy `/app`. Li vedrai
apparire nel commit `Save to GitHub`:

- ✅ `agent-build/forgefps_agent.py` — menu CLI rimosso, `AGENT_VERSION="0.7.3"`, GUI-first
- ✅ `agent-build/version_info.txt` — bump 0.7.2 → **0.7.3.0** + `FileDescription` senza "Desktop"
- ✅ `backend/ps_agent.py` — bottone "Cambia account" nella GUI locale + endpoint `/api/logout`
- ✅ `backend/desktop_agent.py`, `backend/discord_bot.py`, `backend/helpers.py` — terminologia allineata
- ✅ `frontend/src/pages/MyPc.jsx` — fallback string aggiornato
- ✅ `memory/CHANGELOG.md`, `memory/PRD.md`, `memory/AGENT_UX_AUDIT.md` — documentazione

Ti mancano solo **3 azioni sul tuo lato**:
1. Push su GitHub
2. Creare il tag `v0.7.3` per triggerare la build automatica
3. Aggiornare `frontend/src/config/agent.js` con il nuovo SHA256

---

## 🚀 Step 1 — Salva il codice su GitHub (2 minuti)

**Nella chat Emergent**:
1. Guarda in alto a destra la barra della chat.
2. Clicca il pulsante **`Save to GitHub`** (icona GitHub o testo simile).
3. Nel messaggio di commit scrivi qualcosa tipo:
   ```
   v0.7.3: menu CLI rimosso, GUI-first, terminologia uniforme
   ```
4. Conferma e attendi il push (30-60 secondi).

> ℹ️ Se non trovi il pulsante o hai dubbi sul flusso GitHub, digita nella chat
> `come faccio il push su github?` e ti guido io.

**Verifica**: apri https://github.com/WjRKO/ForgeFPS/commits/main — deve
comparire il tuo commit con tutti i file modificati.

---

## 🏷 Step 2 — Crea il tag `v0.7.3` (1 minuto → build automatica 5 minuti)

Il workflow `agent-build/github-workflow-build-nosign.yml` è **già configurato**
per triggerare automaticamente su qualsiasi tag `v*`. Devi solo creare il tag.

### Opzione A — Da web (più semplice, consigliata)

1. Vai su https://github.com/WjRKO/ForgeFPS/releases
2. Clicca **`Draft a new release`** (bottone verde in alto a destra)
3. Nel campo **"Choose a tag"** scrivi: `v0.7.3` → clicca **"Create new tag: v0.7.3 on publish"**
4. **Target branch**: `main` (default)
5. **Release title**: `v0.7.3 — GUI-first, menu CLI rimosso`
6. **Description** (copia-incolla):
   ```markdown
   ## Novità v0.7.3

   ### 🎯 UX
   - **Menu CLI rimosso** — al doppio-click sull'`.exe` si apre subito la GUI sicura. Niente più prompt a tastiera.
   - **"Cambia account"** direttamente nella GUI (header, accanto a "Continua sul telefono"). Cancella `%APPDATA%\FrameForge\token.dat` e chiude la finestra.
   - **Terminologia unificata**: "Desktop Agent" → "FrameForge Agent" ovunque, prefissi console standardizzati (`[OK]`/`[STEP]`/`[INFO]`/`[WARN]`/`[ERR]`).

   ### 🔧 Backward-compat
   - Protocol handler `frameforge://` invariato — tutti i bottoni web funzionano come prima.
   - CLI flag `--mode sync|benchmark|restore|logout|securegui|optimize|gui` per power user.
   - Backup migrato da `boostpc_backup.json` → `forgefps_backup.json` con fallback lettura del vecchio nome: **nessuno perde i tweak attivi**.

   ### 📊 Benchmark
   - Il valore che il PowerShell chiamava `SCORE /100` ora si chiama esplicitamente `PERFORMANCE SCORE /100` con nota "Health Score globale su forgefps.dev".

   ---

   **Sicurezza**: build non firmata (SignPath in attesa). Verifica sempre lo SHA256 sotto prima di eseguire.
   ```
7. **Lascia** le checkbox `Set as pre-release` e `Set as latest release` come preferisci (default: latest).
8. **⚠️ NON allegare file manualmente** — il workflow genera e allega `forgefps-agent.zip` automaticamente.
9. Clicca **`Publish release`**.

### Opzione B — Da terminale locale (se hai già clonato il repo)

```bash
cd /path/to/ForgeFPS
git pull origin main
git tag -a v0.7.3 -m "GUI-first, menu CLI rimosso"
git push origin v0.7.3
```

Poi vai su https://github.com/WjRKO/ForgeFPS/releases per scrivere le release notes.

### ⏱ Attendere la build

Dopo il tag, vai su https://github.com/WjRKO/ForgeFPS/actions

- Cerca il workflow **`build`** con label **`v0.7.3`** (o timestamp recente)
- Aspetta ~5 minuti: passa da 🟡 (in corso) a 🟢 (successo)
- Se diventa 🔴 (fail): apri il run, guarda quale step è rosso, mandami lo screenshot dell'errore

Al successo, il file `forgefps-agent.zip` sarà **automaticamente** allegato alla release,
e nel log del run vedrai la riga:
```
SHA256 = <hash lungo 64 caratteri>
```

---

## 🔐 Step 3 — Aggiorna URL + SHA256 nella dashboard (2 minuti)

Servono per far scaricare agli utenti la nuova versione con verifica integrità.

1. Vai su https://github.com/WjRKO/ForgeFPS/releases/tag/v0.7.3
2. **Copia lo SHA256**: nella descrizione release c'è una riga tipo
   `**SHA256 (ZIP):** '<hash>'`  → copialo (64 caratteri esadecimali).
3. **Torna in chat Emergent e dimmi**:
   > "SHA256 v0.7.3: `<hash che hai copiato>`"

Io farò per te queste 2 modifiche + backup URL:

| File | Modifica |
|---|---|
| `frontend/src/config/agent.js` | `AGENT_EXE_URL`, `AGENT_EXE_SHA256`, `AGENT_EXE_VERSION`, `AGENT_EXE_DATE` |
| `backend/routers/pc.py` | `AGENT_ZIP_UPSTREAM` default (usato per il proxy cache lato server) |

Dopo di che ti dico "pronto per redeploy".

---

## 🌐 Step 4 — Redeploy produzione (5 minuti)

**Nella chat Emergent**:
1. Digita "**deploy**" o clicca il tuo bottone di deploy usuale (dipende dal tuo setup — se hai `forgefps.dev` su Emergent hosted, è il flusso Preview → Deploy).
2. Attendi il completamento del deploy.
3. **Verifica live**:
   - Apri https://forgefps.dev/app/desktop
   - Sotto "Scarica FrameForge Agent" deve comparire **"v0.7.3"** (invece dell'attuale v0.7.1)
   - Il pulsante di download deve puntare al nuovo ZIP.

---

## ✅ Step 5 — Test manuale sul tuo PC Windows (opzionale ma consigliato)

1. Scarica lo ZIP dalla nuova release (o dal bottone in dashboard)
2. Estrai `forgefps-agent/` in una cartella qualsiasi
3. **Doppio-click su `forgefps-agent.exe`** → deve aprirsi **direttamente la GUI sicura**, senza menu a tastiera
4. Nell'header della GUI cerca il bottone **`👤 Cambia account`** (a destra, accanto a "Continua sul telefono")
5. Clicca `Cambia account` → conferma → la GUI si chiude e il file `%APPDATA%\FrameForge\token.dat` sparisce
6. Riapri l'`.exe` → deve chiederti di nuovo il token (setup pulito)

Se tutto funziona → **v0.7.3 è live e coerente**. 🎉

---

## 🆘 Troubleshooting

### La build su GitHub Actions è rossa 🔴
- Apri il run, clicca lo step rosso, copia le ultime 20 righe di log e mandamele in chat.
- Cause tipiche:
  - Version file syntax error → verificato in questo container, non dovrebbe capitare
  - Timeout runner Windows → riprova con `Re-run failed jobs`
  - PyInstaller compat rotta con Python 3.12 → il workflow usa già 3.12 stabile

### Windows Defender segnala l'`.exe` come sospetto
- **Normale** per build non firmata (spiegato in `agent-build/VENDOR_FALSE_POSITIVE.md`).
- Il .exe è pulito, ma il bootloader PyInstaller genera falsi positivi.
- Sto già usando `--onedir --noupx` che riduce il problema al minimo.
- **Long-term fix**: firmare con SignPath (setup in `SIGNPATH_SETUP.md`) — quando avrai l'account approvato.

### Un utente v0.7.2 lamenta di "aver perso i tweak" dopo l'update
- **Non dovrebbe succedere**: il fallback `_LEGACY_BACKUP_FILE` legge il vecchio `boostpc_backup.json` al primo avvio v0.7.3.
- Se succede: apri `%TEMP%\` sul PC utente, cerca `boostpc_backup.json` — deve esserci ancora se non ha girato una `restore`. Rinominarlo a `forgefps_backup.json` sblocca tutto.

### La GUI si apre ma il bottone "Cambia account" non c'è
- La GUI è servita **dal backend cloud** (`/api/agent/script`), non è embedded nell'`.exe`. Quindi:
  - Se hai fatto **redeploy backend** → il bottone c'è per **tutti**, anche utenti con `.exe` vecchi
  - Se **NON** hai ancora fatto redeploy → il bottone non c'è ancora, ma l'`.exe` v0.7.3 funziona lo stesso
  - Consiglio: fai redeploy backend **prima** di annunciare la v0.7.3 agli utenti

---

## 📞 Bloccato? Chiedimi

Se ti perdi in qualsiasi step, scrivimi in chat cosa stai vedendo (o mandami
uno screenshot). Ti sblocco in 30 secondi.

Buon rilascio! 🚀
