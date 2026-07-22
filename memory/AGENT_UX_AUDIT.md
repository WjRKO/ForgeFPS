# FrameForge Agent — Audit di coerenza & uniformità

> Audit del 2026-02-22 · Focus sui due file dell'agent locale:
> - `/app/backend/ps_agent.py` (3.766 righe · script PowerShell + GUI HTML/JS embedded, servito on-the-fly da `/api/agent/script`)
> - `/app/agent-build/forgefps_agent.py` (1.084 righe · launcher Python compilato in `.exe`, gestore protocollo `frameforge://`, menu CLI legacy)
>
> Rispetta le regole già codificate in `FRONTEND_RULES.md` (terminologia unificata, tono informale, stati universali).

---

## 🎯 Executive summary

L'Agent tecnicamente funziona bene, ma **la sua identità testuale è dispersa**: convive un naming legacy ("Desktop Agent", "boostpc", "Companion"), prefissi di console arbitrari (`[*]`, `[FF]`, `[i]`, `[8]`, `[HW]`, `[FPS]`, `[diag]`, `[BOOST ATTIVO]`, `[FATTO]`…), un menu CLI con numerazione non contigua (`G, 1, 3, 4, 7, 8, B, A`) e stati dei tweak in **7 varianti** diverse (`Attivo`/`Da ottimizzare`/`Da attivare`/`Disabilitato`/`Attivo (da disattivare)`/`Prestazioni`/`n/d`).

Fix con **alto ROI e rischio basso**:
1. **Rinominare "Desktop Agent" → "FrameForge Agent"** ovunque (7 occorrenze)
2. **Unificare i prefissi console** in 5 stati (`[OK] [INFO] [WARN] [ERR] [STEP]`)
3. **Uniformare stati tweak** in 4 label (`Ottimale`/`Da applicare`/`Non applicabile`/`Sconosciuto`)
4. **Distinguere Health Score da Performance Score** anche nell'output del benchmark
5. **Aggiornare pill versione GUI** (`GUI v2` → `GUI v2.5`) — allinearsi al numero di build reale

---

## 📋 1. Naming legacy da eliminare

### 1.1 "Desktop Agent" → "FrameForge Agent"

**`agent-build/forgefps_agent.py`**
| Riga | Stringa attuale | Nuova stringa |
|---|---|---|
| 3 | `FrameForge - Desktop Agent (Windows)` | `FrameForge Agent (Windows)` |
| 4 | `Companion locale: ottimizzazioni…` | `Agent locale: ottimizzazioni…` |
| 24 | `argparse(description="FrameForge Desktop Agent")` | `"FrameForge Agent"` |
| 211 | `print("  FrameForge Desktop Agent")` | `"  FrameForge Agent"` |
| 1032 | `"   FrameForge - Desktop Agent  v%s"` | `"   FrameForge Agent  v%s"` |

Anche il docstring linea 6:
- `Uso:  python boostpc_agent.py` → `Uso:  python forgefps_agent.py`

### 1.2 File legacy `boostpc_*`

**`agent-build/forgefps_agent.py`**
- Linea 36: `BACKUP_FILE = "boostpc_backup.json"` → `"forgefps_backup.json"`
  ⚠️ **Attenzione**: se cambi il nome del file di backup, gli utenti con la v0.7.2 già installata perdono la traccia del backup precedente. Fix suggerito: fallback lettura **anche** dal vecchio nome per una release, poi rimuovere. Documentare in `REBUILD_v0.7.0.md`.
- Linea 541: `tmp = "boostpc_bench.bin"` → `"forgefps_bench.bin"` (nessun impatto: file temporaneo effimero)

### 1.3 Menu label in agent che citano vecchie voci web

**`agent-build/forgefps_agent.py`** — righe 213, 202-203:
- `"pagina 'Collega il PC' del tuo account"` → `"pagina 'FrameForge Agent' del tuo account"`
  *(La voce di menu web è stata rinominata da "Collega il PC" a "FrameForge Agent" in questa sessione.)*

**`backend/ps_agent.py`** — riga 26:
- `'Il token si trova nella pagina "Collega il PC"…'` → `'Il token si trova nella pagina "FrameForge Agent"…'`

Altri riferimenti web nell'output PowerShell sono già coerenti col menu attuale:
- `FrameForge -> Il mio PC` ✅
- `FrameForge -> Live` ✅
- `FrameForge -> Rete` ✅

---

## 🎨 2. Console output: prefissi caotici

### 2.1 Situazione attuale
Ho contato **11 prefissi** diversi tra `Say`/`Write-Host`/`print` nei due file:

| Prefisso | Semantica implicita | Occorrenze |
|---|---|---|
| `[OK]` | Successo | 8× |
| `[*]` | Step in corso | 6× |
| `[!]` | Warning / errore lieve | 4× |
| `[i]` | Info opzionale | 5× |
| `[FrameForge]` | Errore di sistema | 6× |
| `[HW]` | Info hardware | 1× |
| `[FPS]` | Presentmon | 8× |
| `[diag]`, `[diag FPS]` | Diagnostica | 4× |
| `[SICUREZZA]` | Modifica bloccata | 2× |
| `[BOOST ATTIVO]`, `[BOOST]`, `[STOP]`, `[FATTO]` | Stati game booster | 5× |
| `[1]`, `[3]`, `[4]`, `[7]`, `[8]`, `[B]` | Numerazione menu CLI (Python) | 6× |

**Problema**: l'utente non ha un modello mentale coerente. `[i]` in PowerShell e `[!]` in Python significano cose diverse. `[FrameForge]` è l'unico prefisso branded e viene usato solo per errori seri.

### 2.2 Proposta: 5 prefissi universali + colori fissi

```
[ OK  ]  Verde   → operazione completata
[STEP ]  Cyan    → fase iniziata (barra di avanzamento)
[INFO ]  Grigio  → info opzionale, non azione utente
[WARN ]  Giallo  → attenzione, l'operazione prosegue
[ERR  ]  Rosso   → operazione fallita
```

Contesti speciali diventano sotto-tag: `[STEP] Benchmark rete...`, `[STEP][FPS] Avvio PresentMon...`, `[WARN][SEC] Modifica bloccata (area protetta)`.

Il vantaggio: gli utenti leggono meglio i log e possiamo introdurre un "log level" (--verbose / --quiet) senza cambiare la struttura.

### 2.3 Casi speciali "prematch/booster" (`ps_agent.py:3598, 3702, 3714, 3723`)

Le frasi celebrative (`[BOOST ATTIVO] Avvia pure il tuo gioco. Buon match!`, `[FATTO] A presto!`) creano attaccamento emotivo. **Le tengo**, ma sotto forma di riga separata dopo il `[OK]` finale:

```
[ OK  ] Ottimizzazioni pre-match applicate.
        Buon match! ⚡
```

Nessun bracket, riga indentata: il messaggio esce dallo schema "log tecnico" e sembra un cheer, non un errore.

---

## 🧭 3. Menu CLI legacy (`forgefps_agent.py` linee 1020-1046)

### 3.1 Situazione attuale
```
G. GUI SICURA
1. Pulizia temp
3. Piano energetico
4. Mostra processi pesanti
7. Rileva hardware
8. Ripristina
B. Benchmark
A. OTTIMIZZA TUTTO
Q. Esci
```

**Problemi**:
- Numerazione salta 2, 5, 6 → cognitive load ("cos'è successo alle voci mancanti?")
- Etichette mescolano IT e sintesi tecnica ("GUI SICURA", "OTTIMIZZA TUTTO + benchmark prima/dopo (avanzato)")
- La voce `G` (GUI sicura) è la più usata al 99% ma sta in mezzo alle altre
- Nessuna voce per "aggiorna token" / "cambia account" (obbligo di editare `%APPDATA%\FrameForge\token.dat` a mano)

### 3.2 Proposta: menu compatto 6 voci

```
FrameForge Agent  v0.7.2
────────────────────────────────────────────────────────
   Consigliato
  1  Apri GUI (Problema · Motivo · Impatto per ogni tweak)

   Altre azioni
  2  Rileva hardware e sincronizza con il cloud
  3  Benchmark rapido (CPU / RAM / disco / rete)
  4  Ripristina (annulla tutti i tweak)
  5  Cambia account (rimuovi il token salvato)

  Q  Esci
```

Voci rimosse dal CLI (spostate solo dentro la GUI dove il contesto è visibile):
- "Pulizia temp": è già inclusa nell'ottimizzazione GUI (`_cleanup` viene chiamato in `apply_all_tweaks`) → duplicato
- "Piano energetico alte prestazioni": stessa cosa, è un tweak dentro la GUI
- "Mostra processi pesanti": rumore per un utente non-tecnico. Info equivalente disponibile nel Task Manager

Voci aggiunte:
- **Cambia account** → chiama `_forget_saved_token()` (già esiste, non usato dal menu)

---

## 🎨 4. Stati dei tweak: 7 label diverse

### 4.1 Situazione attuale (`ps_agent.py:$script:TWEAKS`)

Ho contato in `Attivo`, `Da ottimizzare`, `Da attivare`, `Disabilitato`, `Disattivato`, `Attivo (da disattivare)`, `Attivo (da disabilitare)`, `Prestazioni`, `Gia`, `n/d`.

**Problema utente**: l'utente non capisce se `Da ottimizzare` = tweak NON ancora applicato, o SE lo dovrebbe fare. `Attivo` a volte significa "buono, lascia stare" e a volte "brutto, va disattivato" (dipende dal contesto della singola opzione).

Esempio (`ps_agent.py:965`):
> MPO: `state={ ... 'Disabilitato' oppure 'Attivo (da disabilitare)' }`

Qui "Attivo" è il caso da fixare (l'utente deve leggere `(da disabilitare)` tra parentesi per capire). Confuso.

### 4.2 Proposta: 4 stati universali

Sempre dal punto di vista dell'utente = "questo tweak nel MIO PC è in linea col target?":

| Label | Colore | Significato |
|---|---|---|
| `● Ottimale` | verde (`--ok`) | Il tweak è già applicato con successo |
| `● Da applicare` | giallo (`--warn`) | Va cliccato per essere applicato |
| `● Non applicabile` | grigio (`--muted`) | Non compatibile col tuo hardware (skip) |
| `● Sconosciuto` | grigio scuro (`--dim`) | Stato non rilevabile (permessi, driver, ecc.) |

Ogni funzione `state={}` va ristrutturata per ritornare uno di questi 4 valori. Il codice cliente CSS/JS della GUI locale segue con `stateClass()` (già esiste, riga 2201-2204, semplifico).

**Impatto**: modifica di ~20 blocchi `state={}` in PowerShell. Zero rischio di regressione (i controlli sono stringhe puramente decorative — il codice `apply={}` non guarda mai `state`).

---

## 🔬 5. Health Score vs Performance Score nel benchmark

### 5.1 Bug di terminologia

Il benchmark PowerShell (`ps_agent.py:485`) e Python (`forgefps_agent.py:629`) producono un valore `score` che **è il Performance Score** (calcolato pesando CPU/RAM/disco/DPC/ping/jitter), **ma lo chiamano semplicemente `SCORE /100`** in output console. Questo confonde con l'Health Score globale del web dashboard.

Riga 492 di `ps_agent.py`:
```
CPU 42000 | ... | SCORE 71/100
```

Va rinominato:
```
CPU 42000 | ... | PERFORMANCE SCORE 71/100
```

E analogamente `forgefps_agent.py:648`:
```
SCORE          : {score}/100
```
diventa:
```
Performance    : {score}/100
```

Bonus: chiarire in `show_bench` che quello è il **Performance Score** e non l'Health Score che l'utente vede sulla dashboard. Aggiungere una nota in fondo al benchmark:

```
[INFO] Il Performance Score misura la velocità del PC ora.
       L'Health Score globale (temp + tweak + freschezza) lo vedi su
       forgefps.dev → Il mio PC.
```

---

## 🖼 6. GUI locale HTML (embedded in `ps_agent.py`)

### 6.1 Titolo e branding
| Elemento | Attuale | Proposta |
|---|---|---|
| `<title>` (l.1350) | `FrameForge - Ottimizzazioni sicure` | `FrameForge Agent — Ottimizzazioni` |
| Header brand (l.2036) | `FRAMEFORGE` | `FRAMEFORGE AGENT` |
| Sub-brand (l.2037) | `Ottimizzazioni trasparenti per streamer &amp; gamer` | idem, o `Trova i colli di bottiglia. Ottimizza in sicurezza.` (=headline landing) |
| Version pill (l.2038) | `GUI v2` | `GUI v2.5` (auto-injectare da `AGENT_VERSION`?) |
| Safety banner (l.2041) | `SICUREZZA GARANTITA - Non tocchiamo MAI…` | `SICUREZZA - Non tocchiamo mai Windows Defender, Firewall o servizi di sicurezza. Ogni modifica ha backup automatico ed è reversibile.` (togliere "GARANTITA" = marketing) |

### 6.2 Sort select (l.2112-2117)
- `Ordina: Impatto` / `Categoria` / `Nome` / `Da fare per primi`
- Ultimo caso è la forma esplicita, altri sono etichette secche. Uniforma:
  - `Impatto stimato`
  - `Categoria`
  - `Nome (A-Z)`
  - `Da applicare per primi`

### 6.3 Empty state profili personali (l.2518)
Attuale: `Nessun profilo personale ancora. Creane uno su forgefps.dev/app/profiles.`

Manca la voce `/app/profiles` nel menu attuale del web. Verificare la rotta (potrebbe non esistere) o cambiare CTA:

- Sostituire con: `Crea profili personali su forgefps.dev → Gaming → Preset`

### 6.4 Copy nei toast

Le 6 stringhe di toast sono OK, ma senza icona/simbolo → può migliorare con emoji semantica (già consentita per placeholder informali):

| Toast | Ora | Proposta |
|---|---|---|
| `toast("Applicato")` | plain | `toast("✓ Applicato", "ok")` |
| `toast("Ripristino completato", "ok")` | plain | `toast("↩ Ripristinato", "ok")` |
| `toast("Aggiornato", "ok")` | plain | `toast("⟳ Aggiornato", "ok")` |
| `toast("Nessun tweak compatibile con il tuo hardware", "err")` | ok | ok |

---

## 🧹 7. Opportunità di refactor (P2)

### 7.1 Duplicazione download script (`forgefps_agent.py:882-907` vs `910-962`)

Le funzioni `launch_secure_gui()` e `launch_silent_mode()` ripetono lo stesso pattern (download URL, scrittura in `%TEMP%\forgefps.ps1`, exception handling). Estrarre un helper:

```python
def _download_ps_script() -> str | None:
    """Ritorna il path locale dello script PS scaricato, o None se fallisce."""
```

### 7.2 Duplicazione benchmark logic

`ps_agent.py:Run-Benchmark` (PowerShell) e `forgefps_agent.py:run_benchmark` (Python) producono metriche simili ma con **algoritmi diversi**. Rischio: due utenti sullo stesso PC ottengono Performance Score diversi a seconda di quale entry point ha lanciato il benchmark.

**Proposta**: rendere Python launcher uno **shim** che invoca sempre il PowerShell `-Mode benchmark`. Il codice `run_benchmark` in Python diventa dead code (~140 righe). Il launcher Python non deve calcolare il benchmark, deve solo lanciare l'agent che lo fa e attendere il risultato.

⚠️ **Impatto**: richiede rebuild `.exe`. Effort medio.

### 7.3 Dead code `prematch`

`ps_agent.py:3578-3606` implementa `if ($MODE -eq 'prematch')` ma la modalità è stata deprecata (menzionato nel handoff summary del fork precedente: "removed deprecated 'prematch' logic"). Verificare che nessun call site lo usi (backend URI builder `/api/agent/launch-uri` accetta ancora questo mode?), quindi rimuovere il blocco.

### 7.4 `ps_agent.py` monolite (3.766 righe)

Il file contiene:
- L'header docstring PowerShell (righe 1-30)
- Il core script PowerShell (30-1300)
- L'HTML della GUI locale (1350-2160)
- Il JavaScript client-side (2170-2900)
- Il resto dello script PowerShell (2900-3766)

**Proposta di split** (senza rompere il flow di download → esecuzione):
```
backend/
  agent/
    ps_agent.py           # entry (routes /api/agent/script)
    templates/
      forgefps.ps1.j2     # PowerShell payload (Jinja2)
      gui.html            # GUI locale HTML
      gui.css             # CSS
      gui.js              # JavaScript
```

`ps_agent.py` diventerebbe una funzione di **500 righe** che compone i file template al momento del download. Effort: 4-6 ore. **Bloccato** su testing di regressione (troppo rischioso senza browser test locale).

---

## 🔒 8. Sanity check sicurezza (nessuna modifica richiesta)

Ho verificato i punti sensibili — non ci sono buchi evidenti:

- ✅ **HMAC signature** `frameforge://` URI copre `mode|ts` con token utente come chiave (l.174-180)
- ✅ **Anti-replay**: URI scade dopo 60 secondi (`_URI_MAX_AGE_SEC`)
- ✅ **Silent flag** documentato come non-autenticato (`can only change UX, not security-critical`) — riga 154-155
- ✅ **Forbidden reg paths** definiti in `$script:FORBIDDEN_REG` (l.53-56)
- ✅ **Forbidden services** definiti (`WinDefend, WdNisSvc, ...`) e verificati in `Test-ForbiddenSvc`
- ✅ **Token storage**: `%APPDATA%\FrameForge\token.dat`, per-user NTFS ACL
- ✅ **URL Protocol** registrato in HKCU (no admin), path fisso all'`exe` corrente

Un solo miglioramento suggerito (**opzionale**):
- Il `--backend` parametro viene passato al command handler del protocollo (l.118). Se un attaccante può scrivere in HKCU, può cambiare `--backend` → l'agent parlerebbe con un server malevolo. Non è un bypass del token (HMAC verifica lato client), ma è un canale per esfiltrazione se il PC è già compromesso. Valutare se hardcodare `BACKEND_URL="https://forgefps.dev"` nella build e ignorare l'arg da HKCU. Trade-off: rompe l'ambiente preview vs prod (già segnalato nel commento).

---

## 📊 9. Piano d'azione — quick wins ordinati

### 🔥 P0 — Fix rapido (~2h, alto impatto testuale)
| # | Fix | File | Effort | Rischio |
|---|---|---|---|---|
| 1 | "Desktop Agent" → "FrameForge Agent" | `forgefps_agent.py` (5 occ) | 10 min | zero |
| 2 | `boostpc_backup.json` → `forgefps_backup.json` con fallback lettura | `forgefps_agent.py` l.36, 967, 970 | 30 min | basso (perdita traccia backup su installazioni esistenti) |
| 3 | Prefissi console unificati (`[OK]`,`[STEP]`,`[INFO]`,`[WARN]`,`[ERR]`) | Entrambi i file | 45 min | zero |
| 4 | Menu CLI da 8 voci → 5 voci | `forgefps_agent.py:1020-1046` | 20 min | basso |
| 5 | `SCORE /100` → `PERFORMANCE SCORE /100` | Entrambi i file | 5 min | zero |
| 6 | Version pill GUI `v2` → `v2.5` (o auto-inject) | `ps_agent.py:2038` | 5 min | zero |
| 7 | Menu references `"Collega il PC"` → `"FrameForge Agent"` | `ps_agent.py:26`, `forgefps_agent.py:202-203, 213` | 5 min | zero |

**Totale: ~2h**. Nessun test frontend richiesto. Verifica: build locale del `.exe` + esecuzione manuale del `.ps1` scaricato. Il PowerShell si può testare con `curl "$BACKEND/api/agent/script?t=<test-token>"` + inspezione visiva del contenuto.

### 🟡 P1 — Fix medio (~4h)
| # | Fix | Effort | Rischio |
|---|---|---|---|
| 8 | Stati tweak universali (4 label) in `$script:TWEAKS` | 90 min | basso |
| 9 | Toast icons + copy tuning nella GUI locale | 30 min | zero |
| 10 | Titolo GUI + banner sicurezza refresh | 15 min | zero |
| 11 | Sort select label uniformi | 5 min | zero |
| 12 | Rimozione dead code `prematch` (verifica prima!) | 30 min | medio (backend potrebbe ancora emettere questo URI) |
| 13 | Empty state profili (l.2518) → link corretto | 5 min | zero |

### 🟢 P2 — Refactor (~1 giornata)
| # | Fix | Effort |
|---|---|---|
| 14 | Extract helper `_download_ps_script()` | 30 min |
| 15 | Rimuovere `run_benchmark` Python (delega a PS) — richiede rebuild `.exe` | 3h |
| 16 | Split `ps_agent.py` in template files | 4-6h |
| 17 | Hardcoding `BACKEND_URL` in release build (security hardening) | 1h |

---

## 🎬 Prossimi passi consigliati

**Opzione A (Cosmetic — consigliata)**: applico solo i **7 P0** in un batch (~2h effettive di lavoro con parallel edit) → l'Agent diventa immediatamente coerente col naming/tono del web dashboard, zero rischi di regressione, nessun rebuild `.exe` necessario per la maggior parte (solo `forgefps_agent.py` cambierà, ma il resto degli utenti ha già il vecchio `.exe` che continua a funzionare).

**Opzione B (Deep)**: P0 + P1 (~6h) → tocca anche gli stati dei tweak nella GUI locale.

**Opzione C (Selettiva)**: dimmi tu quali fix P0/P1 vuoi che io applichi (per esempio `1,3,4,5,7` = solo il minimo indispensabile per allineamento naming).

**Opzione D (Refactor)**: passiamo direttamente ai P2 (dead code + split file). Alto ROI di lungo periodo ma effort >1 giornata.

---

*Fine audit. Salvato in `/app/memory/AGENT_UX_AUDIT.md`.*
