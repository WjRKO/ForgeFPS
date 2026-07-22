# Rebuild `.exe` v0.7.4 — Guida passo-passo

> **Obiettivo**: pubblicare `.exe` v0.7.4 con il fix del **monitor mode routing**
> (URI `mode=monitor/fullbench/booster/prematch/bufferbloat` non collassano più
> silenziosamente su `optimize`) + l'uscita silenziosa quando firma URI ko + silent hint.
>
> **Tempo stimato**: 10-15 min (5 di build su GitHub Actions).
> **Cosa serve**: chat Emergent + accesso al repo `WjRKO/ForgeFPS`.

---

## 📦 Modifiche già preparate (nel container Emergent)

Sono già nel tuo working tree `/app`, verranno pushate con "Save to GitHub":

- ✅ `agent-build/forgefps_agent.py`
  - `AGENT_VERSION = "0.7.4"`
  - `launch_secure_gui(mode="optimize")` — ora accetta la mode
  - `parse_and_verify_uri` — su firma invalida ritorna `{invalid_reason, silent_hint}` invece di `None`
  - Main dispatcher — nuove handler per `monitor / fullbench / prematch / booster / bufferbloat`
  - Main dispatcher — uscita silenziosa (`sys.exit(2)`) se firma URI ko + `silent=1`
- ✅ `backend/ps_agent.py` — primo scan condizionale (skip se sync < 15 min)
- ✅ `backend/routers/pc.py` — nuovo endpoint `GET /api/pc-specs-agent`
- ✅ `frontend/src/hooks/useAutoSync.js` — auto-launch disabilitato
- ✅ `frontend/src/components/Layout.jsx` — `prefetchAdvisorSync` rimosso
- ✅ `frontend/src/components/TokenMismatchHint.jsx` — nuovo componente (v0.7.4a)
- ✅ `frontend/src/pages/Benchmark.jsx` — `GpuReferenceCard` spostata qui
- ✅ `memory/CHANGELOG.md` — righe v0.7.4a e v0.7.4b

Ti restano **3 azioni**:
1. Push su GitHub
2. Bumpare `version_info.txt` (facoltativo ma consigliato — vedi sotto)
3. Creare il tag `v0.7.4` → build automatica

---

## 🔢 Step 0 — Bump di `version_info.txt` (30 secondi, opzionale)

Nel file `agent-build/version_info.txt` c'è `0.7.3.0` come version tuple. Se
vuoi mostrare `0.7.4.0` nelle proprietà del file `.exe` (tasto destro →
Proprietà → Dettagli su Windows), aggiornalo. **Se lo salti**, il .exe funziona
comunque — solo la stringa nelle proprietà resta v0.7.3.

Cerca queste righe e sostituisci:

```
filevers=(0, 7, 3, 0),
prodvers=(0, 7, 3, 0),
...
StringStruct('FileVersion', '0.7.3.0'),
StringStruct('ProductVersion', '0.7.3.0'),
```

→ con `0, 7, 4, 0` e `0.7.4.0`.

Se vuoi che lo faccia io, dimmelo: **"Bumpa version_info.txt a 0.7.4"** e lo
faccio in 5 secondi prima del push.

---

## 🚀 Step 1 — Salva il codice su GitHub (2 minuti)

**Nella chat Emergent**:

1. In alto a destra della chat, clicca **`Save to GitHub`**.
2. Messaggio di commit consigliato:
   ```
   v0.7.4: monitor routing + primo scan condizionale + no auto-sync
   ```
3. Conferma e attendi il push (30-60 s).

**Verifica**: apri https://github.com/WjRKO/ForgeFPS/commits/main — deve
comparire il nuovo commit con tutti i file toccati (dovresti vedere le
modifiche in `agent-build/forgefps_agent.py`, `backend/`, `frontend/src/`).

> Se non trovi il bottone o hai dubbi, scrivimi **"come faccio il push su
> github?"** e ti guido.

---

## 🏷 Step 2 — Crea il tag `v0.7.4` → build automatica (~5 min)

Il workflow `agent-build/github-workflow-build-nosign.yml` triggera su
qualsiasi tag `v*`.

### Opzione A — Da web (consigliata)

1. Vai su https://github.com/WjRKO/ForgeFPS/releases
2. Clicca **`Draft a new release`** (bottone verde in alto a destra)
3. **Choose a tag** → digita `v0.7.4` → **"Create new tag: v0.7.4 on publish"**
4. **Target branch**: `main`
5. **Release title**: `v0.7.4 — Monitor fix + primo scan condizionale`
6. **Description** (copia-incolla):

```markdown
## Novità v0.7.4

### 🐛 Fix critico — "Avvia monitor sul PC" ora funziona davvero
Prima: cliccare "Avvia monitor" apriva la GUI ottimizza col primo scan invece
del monitor. Root cause: `launch_secure_gui()` hardcodato a `-Mode optimize`
faceva collassare tutte le mode UI-visibili (`monitor / fullbench / booster /
prematch / bufferbloat`) sull'optimize.
Ora: routing esplicito per ogni mode con la finestra corretta.

### 🚫 Fix — Sync automatico ad ogni login rimosso
Il `FreshnessBadge` non fa più launch automatico se i dati sono >24h vecchi,
e il `prefetchAdvisorSync` su hover del navlink Advisor è stato rimosso.
Zero azioni automatiche: la sync parte solo quando l'utente clicca.

### ⚡ Fix — Primo scan ad ogni apertura della GUI condizionato
Quando la GUI (mode=optimize) si apre, ora chiama `/api/pc-specs-agent`:
se l'ultima sync è < 15 min salta il primo scan (3-5s di attesa risparmiati).

### 🔐 Fix — Firma URI ko + silent=1 → uscita silenziosa
Prima: se il token locale era di un altro account, la firma HMAC dell'URI
`frameforge://` falliva e l'exe cadeva sul fallback che apriva una GUI
visibile con primo scan. Ora: se il chiamante voleva silent, l'exe esce con
codice 2 senza aprire nulla. Il web mostra un toast chiaro.

### Backward-compat
- Protocol handler `frameforge://` invariato: URI vecchi continuano a
  funzionare.
- CLI flag `--mode sync|benchmark|restore|logout|monitor|fullbench|prematch|booster|bufferbloat|optimize|gui` tutti supportati.

---

**Sicurezza**: build non firmata (SignPath in attesa). Verifica sempre lo SHA256
sotto prima di eseguire.
```

7. **⚠️ NON allegare file manualmente** — GitHub Actions genera e allega
   `forgefps-agent.zip` automaticamente.
8. Clicca **`Publish release`**.

### Opzione B — Da terminale locale (se hai il repo clonato)

```bash
cd /path/to/ForgeFPS
git pull origin main
git tag -a v0.7.4 -m "monitor routing + primo scan condizionale + no auto-sync"
git push origin v0.7.4
```
Poi su https://github.com/WjRKO/ForgeFPS/releases scrivi le release notes.

### ⏱ Attendere la build

Vai su https://github.com/WjRKO/ForgeFPS/actions

- Trova il workflow **`build`** col tag **`v0.7.4`** (dovrebbe apparire in cima)
- Aspetta ~5 min: passa da 🟡 (in corso) a 🟢 (successo)
- Al successo, il file `forgefps-agent.zip` è **automaticamente** allegato
  alla release e il log contiene:
  ```
  SHA256 = <hash di 64 caratteri esadecimali>
  ```

Se diventa 🔴 (fail) → apri il run, screenshot dello step rosso e mandami
in chat.

---

## 🔐 Step 3 — Aggiorna SHA256 + versione nella dashboard (2 min)

Serve per far vedere agli utenti **v0.7.4** nel pannello "FrameForge Agent"
e per la verifica integrità.

1. Vai su https://github.com/WjRKO/ForgeFPS/releases/tag/v0.7.4
2. Nella descrizione, copia lo SHA256 (64 caratteri esadecimali, riga
   `**SHA256 (ZIP):** '<hash>'`)
3. **Torna in chat Emergent e scrivimi**:
   > "SHA256 v0.7.4: `<hash che hai copiato>`"

Io faccio queste 2 modifiche automaticamente:

| File | Cosa cambia |
|---|---|
| `frontend/src/config/agent.js` | `AGENT_EXE_VERSION = "v0.7.4"`, `AGENT_EXE_SHA256`, `AGENT_EXE_DATE` |
| `backend/routers/pc.py` | `AGENT_ZIP_UPSTREAM` default (il proxy cache riscarica il nuovo ZIP) |

Dopo di che ti dico **"pronto per redeploy"**.

---

## 🌐 Step 4 — Redeploy produzione (5 min)

Nella chat Emergent:
1. Digita "**deploy**" o usa il tuo bottone di deploy (dovresti essere su
   `forgefps.dev` hosted Emergent).
2. Attendi il completamento.
3. **Verifica live** su https://forgefps.dev/app/desktop:
   - Sotto "Scarica FrameForge Agent" deve comparire **`v0.7.4`**
   - Lo SHA256 mostrato deve corrispondere a quello della release GitHub

---

## ✅ Step 5 — Test manuale sul tuo PC Windows (5 min)

**A. Test monitor** (la fix principale di questa release):
1. Scarica lo ZIP dalla nuova release
2. Estrai `forgefps-agent/` (sostituisci la cartella vecchia)
3. Se vuoi partire pulito → cancella `%APPDATA%\FrameForge\token.dat`
4. Doppio click su `Avvia-FrameForge.bat` (il nuovo scaricato dal tuo account) → GUI si apre
5. Vai sul web → **Live Monitoring** → clicca **"Avvia monitor sul PC"**
6. **Atteso**: si apre una finestra PowerShell con "Monitoraggio live avviato",
   NON il primo scan della GUI. La pagina web comincia a ricevere telemetria
   CPU/GPU/temp/FPS.

**B. Test primo scan condizionale**:
1. Chiudi la GUI del monitor
2. Doppio click sull'`.exe` una volta → GUI si apre col primo scan (normale)
3. Chiudi, riaprilo entro 15 min → **atteso**: vedi `[SKIP] Ultima sync cloud:
   X.Y min fa (< 15 min). Salto il primo scan e vado alla GUI.` e la GUI si
   apre subito senza fare il primo scan.

**C. Test no-auto-sync**:
1. Fai logout dal web e re-login
2. **Atteso**: nessun popup "Aprire FrameForge?", nessuna finestra visibile
   che parte da sola. Il badge in alto mostra lo stato ma è passivo.
3. Puoi cliccare tu il badge per forzare un sync se vuoi.

Se tutto funziona → **v0.7.4 è live**. 🎉

---

## 🆘 Troubleshooting

### Build 🔴 su GitHub Actions
- Apri il run, clicca lo step rosso, copia gli ultimi 20 righe di log e
  mandamele in chat.
- Cause tipiche:
  - `version_info.txt` malformato → è il motivo #1 di fail sulla v0.7.x
  - Timeout runner Windows → `Re-run failed jobs` sulla release
  - PyInstaller crash su Python 3.12 → il workflow usa già 3.12 stabile

### "Avvia monitor" ancora apre il primo scan dopo update
- Hai fatto sia (a) push GitHub + (b) tag v0.7.4 + (c) rebuild ZIP + (d)
  scaricato il nuovo `.exe` sul tuo PC + (e) sovrascritto la vecchia cartella?
- Se sì e non funziona → mandami in chat lo screenshot del task manager
  mentre clicchi "Avvia monitor" (per vedere se parte davvero `powershell.exe`
  o `forgefps-agent.exe`).

### La GUI mostra ancora "Primo scan" ogni volta
- Il fix è lato `ps_agent.py` (script scaricato dal backend), non dal `.exe`.
- Quindi basta il **redeploy backend** — non serve rebuilder l'`.exe`.
- Se ancora vedi il primo scan: la sync precedente potrebbe essere > 15 min
  (comportamento corretto). Attendi meno di 15 min tra due aperture consecutive
  della GUI per vederlo skippato.

### Utente v0.7.3 aggiorna a v0.7.4: perde qualcosa?
- **No**. Il file `%APPDATA%\FrameForge\token.dat` resta. Il file di backup
  `forgefps_backup.json` resta nella cartella `forgefps-agent/`. I preset
  cloud (game profiles, prematch settings ecc.) sono sul server.
- L'unica cosa che cambia: le mode `monitor / fullbench / booster / prematch /
  bufferbloat` ora funzionano davvero invece di aprire `optimize`.

---

## 📞 Bloccato?

Scrivimi in chat cosa stai vedendo o mandami screenshot. Ti sblocco in 30 s.

Buon rilascio! 🚀
