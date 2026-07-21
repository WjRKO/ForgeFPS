# Rebuild v0.7.0 — Custom Protocol `frameforge://` (launch da browser senza download)

## Perché
Da v0.7.0 l'exe registra il protocollo `frameforge://` in `HKCU` al primo avvio
(no admin). Da quel momento il bottone "Avvia" nella dashboard può chiamare
`frameforge://launch?mode=optimize&ts=...&sig=...` e Windows apre la GUI locale
**senza scaricare nulla**. La firma HMAC-SHA256 usa il token dell'utente come
chiave: URI di un altro account o modificati vengono rifiutati.

---

## Cosa devi fare (checklist rapida)

- [ ] **Step 1** — Aggiorna 2 file sul repo pubblico `WjRKO/ForgeFPS`
- [ ] **Step 2** — Crea il tag `v0.7.0` → build automatica
- [ ] **Step 3** — Copia lo SHA256 nella config del frontend
- [ ] **Step 4** — Redeploy dell'app Emergent

Tempo stimato totale: **~10 minuti**.

---

## STEP 1 — Aggiorna i file sorgente sul repo pubblico

Vai su `https://github.com/WjRKO/ForgeFPS` e aggiorna questi due file. Puoi
farlo direttamente dall'interfaccia web GitHub (matita → incolla → commit).

### 📝 File 1: `forgefps_agent.py`

Copia il contenuto completo da questo repo Emergent:
👉 `/app/agent-build/forgefps_agent.py`

Il file ora contiene:
- `AGENT_VERSION = "0.7.0"` (linea 33)
- Funzione `register_frameforge_protocol()` per HKCU
- Funzione `parse_and_verify_uri()` con HMAC + freshness check
- Nuovi flag `--uri "..."` e `--register-protocol`

### 📝 File 2: `version_info.txt`

👉 `/app/agent-build/version_info.txt`

Aggiornato con `filevers=(0, 7, 0, 0)` e `ProductVersion 0.7.0.0`.

### 💡 Alternativa via Emergent "Save to Github"

Se il repo Emergent è già collegato a `WjRKO/ForgeFPS`, usa il pulsante
**"Save to Github"** in alto a destra: pusherà entrambi i file in un colpo.
In caso contrario, apri i file in `/app/agent-build/` dall'editor Emergent,
copia il contenuto e incollalo via GitHub web UI.

---

## STEP 2 — Crea il tag `v0.7.0` e trigger della build

Il workflow `.github/workflows/build.yml` è già configurato (`push` su tag `v*`).

### Da GitHub Web UI (consigliato)

1. Vai su `https://github.com/WjRKO/ForgeFPS/releases/new`
2. Click su **"Choose a tag"** → digita `v0.7.0` → **"Create new tag: v0.7.0 on publish"**
3. Titolo: `v0.7.0 — Custom protocol frameforge://`
4. Descrizione (paste):
   ```markdown
   Nuovo:
   - Registrazione automatica del protocollo `frameforge://` in HKCU (no admin).
   - Verifica HMAC-SHA256 lato client per URI firmati dal server.
   - Nuovi flag `--uri` e `--register-protocol`.
   - Dopo l'installazione, i bottoni della dashboard aprono la GUI senza download.
   ```
5. **NON** allegare file manualmente: il workflow li compila e li carica lui.
6. Click **"Publish release"** → parte automaticamente la build su GitHub Actions.

### Aspetta la build (~3-5 min)

Vai su `https://github.com/WjRKO/ForgeFPS/actions` e guarda il job `build`.
Quando è verde:
- Il `forgefps-agent.zip` è pubblicato sulla release.
- Nel **"Summary"** del job trovi lo SHA256 in fondo (`SHA256 = <hex>`).

---

## STEP 3 — Aggiorna `frontend/src/config/agent.js`

Nel repo Emergent, aggiorna questi 4 valori in `/app/frontend/src/config/agent.js`:

```js
export const AGENT_EXE_URL     = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.7.0/forgefps-agent.zip";
export const AGENT_EXE_SHA256  = "<SHA256 dalla release>";
export const AGENT_EXE_VERSION = "v0.7.0";
export const AGENT_EXE_DATE    = "2026-02-XX";  // ← data di oggi
```

Se mi dai lo SHA256 quando la build è finita, faccio io il commit al posto tuo.

---

## STEP 4 — Redeploy dell'app Emergent

Il preview URL (`stream-gear-monitor.preview.emergentagent.com`) prende
automaticamente le modifiche via hot reload. Per la **produzione**
(`forgefps.dev`) devi cliccare **"Redeploy"** dalla UI Emergent (in alto).

Dopo il redeploy:
1. Utenti esistenti: scaricano lo ZIP v0.7.0, lo lanciano una volta,
   e da quel momento **i bottoni della dashboard aprono la GUI senza download**.
2. Utenti nuovi: stesso flusso — la prima installazione registra il protocollo.

---

## Come testare che funzioni

Sul tuo PC Windows, dopo aver installato v0.7.0 almeno una volta:

1. Apri `regedit` → naviga a `HKEY_CURRENT_USER\Software\Classes\frameforge`.
   Deve esserci una chiave con `URL Protocol` (vuota) e il subkey
   `shell\open\command` con path all'exe.
2. Su Chrome/Edge, in barra indirizzi, incolla (esempio finto):
   `frameforge://launch?mode=gui&ts=9999999999&sig=abc`
   → Windows chiede "Apri FrameForge?" → Sì → l'exe si apre, verifica la firma
   (in questo caso NON valida) e mostra la GUI standard.
3. Prova con un URI **vero** dalla dashboard (Step 2 completato del frontend):
   la GUI si apre direttamente sulla mode richiesta.

---

## Se qualcosa va storto

- **Build fallisce con "PyInstaller not found"** → riavvia il workflow: a volte
  il caching pip fa i capricci al primo run.
- **Windows Defender lampeggia sul ZIP** → apri `VENDOR_FALSE_POSITIVE.md` per
  i testi di submission (ma con --onedir non dovrebbe più succedere).
- **Il protocollo non si registra** → l'utente può lanciare da PowerShell:
  ```
  forgefps-agent.exe --register-protocol
  ```
  Output: `[FrameForge] Protocollo frameforge:// registrato -> <path exe>`.

---

## Cosa succede DOPO la release

Quando la v0.7.0 è pubblicata e frontend aggiornato, iniziamo lo **Step 2**:
- Sostituzione dei comandi visibili con bottoni "Ottimizza / Monitor / Benchmark"
  che chiamano l'endpoint `/api/agent/launch-uri` e fanno `window.location = uri`.
- Detection "app installata" via ping locale `127.0.0.1:57329/ping`.
- Accordion "Metodo sicuro PowerShell" collassato (rimane per power user).
- Widget "PC Actions" nella Dashboard.

Fammi sapere quando la release è live e ti mando lo Step 2 pronto.
