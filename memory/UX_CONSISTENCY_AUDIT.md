# FrameForge — Audit di coerenza & uniformità

> Audit del 2026-02-22 · Confronto tra ciò che l'app **promette** (landing/marketing) e ciò che l'app **fa** (features implementate), più consistenza design & terminologia.

---

## 🎯 Executive summary

FrameForge ha una landing chiara e ben scritta che promette **4 pilastri**. Ma dopo il login, l'utente trova un menu con **12+ voci** con nomi ambigui e non collegati direttamente ai pilastri promessi. **La promessa si dilata in un'esperienza dispersa**.

**Il problema più grosso**: l'app è tecnicamente ricca ma **soffre di sovraccarico cognitivo**. Sembra 3 app in una: PC Optimizer + Gaming Advisor + Price Tracker + Community.

**Suggerimento top**: ridurre il menu a **5-6 voci principali**, allineate ai pilastri della landing, spostando il resto in sotto-tab o "strumenti avanzati".

---

## 📋 1. Promessa vs Realtà

### Cosa promette la Landing
> *"Trova i colli di bottiglia. Ottimizza in sicurezza."*
> *"Il tuo PC lascia prestazioni sul tavolo. Analizza il setup, trova i colli di bottiglia su FPS e latenza e ottimizza in modo sicuro."*

**4 pilastri (sezione "Cosa ottieni")**:
1. **AI Advisor** — chat AI che conosce il tuo hardware, risolve stutter, riduce input lag, configura OBS
2. **Health Score & Telemetria** — punteggio real-time con CPU/GPU temp + benchmark prima/dopo
3. **Tracker prezzi** — monitora componenti PC su Amazon per acquisti smart
4. **Agent locale** — companion Windows che esegue azioni reversibili: cleanup, tweak gaming, booster automatico

### Cosa trova l'utente dopo login (menu attuale)
| # | Menu label | Cosa fa | Pilastro landing? |
|---|---|---|---|
| 1 | Dashboard | Overview globale | (nessuno diretto) |
| 2 | Il mio PC | Health Score + Live Monitor + Benchmark (in tabs) | ✅ Pilastro 2 |
| 3 | AI Advisor | Chat AI | ✅ Pilastro 1 |
| 4 | Comandi Utili | Lista comandi PowerShell copiabili | (bonus, non promesso) |
| 5 | Rete & Bufferbloat | Test di rete | (bonus) |
| 6 | BIOS & Ripristino | Guide BIOS + restore | (bonus) |
| 7 | Report Prima/Dopo | PDF export | ✅ Pilastro 2 (parziale) |
| 8 | Collega il PC | Download agent + istruzioni | ✅ Pilastro 4 |
| 9 | Gaming | Giochi + profili | (bonus) |
| 10 | Consiglia Build | AI build generator | (bonus) |
| 11 | Upgrade & FPS | Confronto upgrade | (bonus) |
| 12 | Prezzi | Tracker Amazon | ✅ Pilastro 3 |

**Gap principali**:
- La landing dice **4 features**. Il menu ne mostra **12**. Rapporto 1:3.
- Il **bottleneck detector** promesso ("trova i colli di bottiglia") **non esiste come pagina** — solo alcuni hint indiretti nel Live Monitor.
- Il **benchmark prima/dopo** promesso è dentro `/app/pc → tab Benchmark`, non nel menu top-level.
- L'**agent locale** ha una pagina che si chiama "Collega il PC" invece di "Agent" o "Ottimizzazioni PC" — nome non evocativo.

---

## 🔴 2. Problemi di coerenza terminologica

### Score / punteggio / health
- Landing: "Health Score"
- Menu: "Il mio PC"
- Report: "Punteggio salute PC"
- Advisor: "score del tuo PC"
- Benchmark: "punteggio benchmark"

**Confusione**: `Health Score` (0-100) è diverso da `Benchmark Score` (0-100 ma calcolato differente). Un utente non capisce quali sono le 2 metriche.

**Fix**: standardizzare
- `Health Score` = punteggio globale di salute PC (temp, ottimizzazioni, sync)
- `Performance Score` = punteggio benchmark (CPU/RAM/disco/net)
- Usare sempre l'anglicismo con badge colorato uniforme

### Benchmark / Bench / test
- Landing: "benchmark prima/dopo"
- UI: "Benchmark ora", "Bench", "run", "confronto"
- Report: "Benchmark PDF"

**Fix**: usare sempre "Benchmark" o "Test performance" — mai abbreviazioni.

### Agent / Companion / Desktop Agent / GUI
- Landing: "companion locale per Windows"
- Menu: "Collega il PC"
- URL: `/app/desktop`
- GUI: "FrameForge Desktop Agent"

**Fix**: uso univoco = **FrameForge Agent** (rimuovi "Desktop" ovunque, il nome del prodotto locale)

### Tweak / Ottimizzazione / Fix
- GUI: "Tweak"
- Landing: "ottimizzazioni reali e reversibili"
- Advisor: "fix suggeriti"

**Fix**: pubblico = "ottimizzazione", interno GUI = "tweak" (già è convenzione tecnica accettata dai gamer).

---

## 🎨 3. Problemi di uniformità design

### 3.1 Menu troppo lungo
12 voci principali + 6 sotto-tab dentro `/app/pc` (Overview, Live, Benchmark, Report, Commands). Cognitive load altissimo.

**Proposta di ristrutturazione a 5 voci**:
```
┌─────────────────────────┐
│ 📊 Dashboard            │  ← Overview + Bottleneck detector
├─────────────────────────┤
│ 🖥️ Il mio PC             │  ← Health + Live + Benchmark + Report (già)
│    ├── Panoramica       │
│    ├── Monitor Live     │
│    ├── Benchmark        │
│    └── Report PDF       │
├─────────────────────────┤
│ 💬 AI Advisor           │  ← Chat + Recommendations
├─────────────────────────┤
│ 🎮 Gaming               │  ← Giochi + Profili + Build + Upgrade
│    ├── Miei giochi      │
│    ├── Consiglia build  │
│    └── Upgrade & FPS    │
├─────────────────────────┤
│ 🛒 Prezzi & Tracker     │  ← Amazon watch
└─────────────────────────┘
Footer:
  🔧 Strumenti (Comandi, BIOS, Rete)
  📥 Agent locale (Download & Setup)
```

Voci nascoste nel footer/menu "Strumenti":
- Comandi PowerShell
- BIOS & Ripristino
- Rete & Bufferbloat

### 3.2 CTA visivamente incoerenti
- Landing: bottone giallo grande "Accedi gratis"
- Dashboard: card multiple con bottoni piccoli
- MyPc: badge freshness + bottoni sparsi
- Live: mix di bottoni pill e blocchi

**Fix**: definire 3 varianti bottone canoniche in `hud.jsx`:
- **`btn-primary`** (giallo #E5FF00, azione principale — max 1 per pagina)
- **`btn-secondary`** (bordo grigio, azioni normali)
- **`btn-ghost`** (solo testo, azioni terziarie)

E imporre l'uso via ESLint rule o code review.

### 3.3 Card style diverse
- Advisor: card scure grandi
- Dashboard: card scure con bordo giallo per hero
- MyPc: card con hud-tick pattern
- Guide: card più grigie con radius diversi

**Fix**: unica `<HUDCard>` component in `hud.jsx` (già esiste ma sottoutilizzata). Standardizzare tutti gli usi.

### 3.4 Iconografia mista
- Web: lucide-react (SVG line icons)
- GUI locale: emoji Unicode (🎮, ⚡, 🔴)
- Alcuni menu voci: emoji nel testo (`🎮 Gaming & FPS`)

**Fix**: solo lucide-react nel web, sempre. Emoji riservate per placeholder informali (empty states, quick wins).

---

## 🧭 4. Problemi di UX/flusso

### 4.1 Onboarding assente
Nuovo utente arriva sulla Dashboard e vede una griglia vuota. Non sa da dove partire.

**Fix**: onboarding modale 3-step al primo login:
1. **"Benvenuto — connetti il tuo PC"** → apre `/app/desktop`
2. **"Sync automatica in corso"** → progress bar (usa Ambient Sync)
3. **"Health Score calcolato: 68 · Vediamo cosa migliorare"** → apre `/app/advisor`

### 4.2 Nessun "next step" contestuale
Dopo aver applicato tweak, l'utente non sa cosa fare dopo. Nessun banner "Ora esegui un benchmark per vedere il miglioramento".

**Fix**: dopo ogni azione significativa, banner "next best action":
- Post-sync: `"Ora esegui l'AI Advisor per suggerimenti personalizzati"`
- Post-apply tweak: `"Fai un benchmark per misurare il guadagno"`
- Post-benchmark: `"Salva il report PDF per confronti futuri"`

### 4.3 Statuses inconsistenti
- Health Score usa: `Ottimo / Buono / Da ottimizzare / Critico`
- Benchmark usa: `Eccellente / Buono / Nella media / Basso`
- Tweak status usa: `Attivo / Da ottimizzare / Non applicabile`

**Fix**: 4 stati universali con colori fissi:
- 🟢 **Ottimale** (verde #00FF66)
- 🟡 **Buono** (accento #E5FF00)
- 🟠 **Da migliorare** (arancione #FFAA00)
- 🔴 **Critico** (rosso #FF3355)

### 4.4 "Continua sul Telefono" solo nella GUI
Feature killer per streamer (mobile handoff QR), ma esposta solo nell'header della GUI locale. Il web dashboard non ne parla mai.

**Fix**: aggiungere bottone "Continua sul telefono" in header web (accanto al nome utente).

### 4.5 Freshness badge sparso
Ambient Sync mostra "Sincronizzato 2m fa" solo in alcune pagine. Coerenza?

**Fix**: sempre in alto a destra della pagina, in tutte le pagine post-login, con lo stesso wording e colore.

---

## 🗣 5. Problemi di voice & tone

### 5.1 Italiano mista formale/informale
- "Il tuo PC lascia prestazioni sul tavolo" (informale ✓)
- "Configurare le opzioni del piano energetico" (formale)
- "Sto analizzando il tuo hardware" (informale ✓)

**Fix**: sempre **tono informale, seconda persona singolare, tu**. Come un gamer che parla a un altro gamer.

### 5.2 Terminologia tecnica non spiegata
- "Bufferbloat" — cos'è? Non spiegato in landing
- "MPO" — solo tech
- "MSI Mode" — solo tech
- "HAGS" — solo tech

**Fix**: tooltip semplici. Es. `Bufferbloat ℹ️` → tooltip "Ritardo di rete che causa lag anche con ping basso"

### 5.3 CTA vaghe
- "Analizza il PC" — cosa succede dopo? Quanto tempo?
- "Ottimizza" — quali? Rischio?
- "Applica" — cosa? Reversibile?

**Fix**: CTA descrittive:
- "Analizza il PC (30s)"
- "Ottimizza per Gaming (12 tweak reversibili)"
- "Applica ora (backup automatico)"

---

## 📱 6. Uniformità mobile / responsive

### Verifiche empiriche
- Landing è responsive ✓
- Dashboard: alcune card non si adattano bene sotto 640px
- Live: chart Recharts diventa illeggibile sotto 768px
- Benchmark: layout single-column fine

**Fix**: audit responsive dedicato con `@screen` breakpoints coerenti (`sm:` 640, `md:` 768, `lg:` 1024, `xl:` 1280).

---

## 🎯 7. Piano d'azione — quick wins ordinati

### 🔥 P0 — Fix in 3-4 ore (alto impatto)
1. **Rinominare voci menu** per coerenza col landing (~30 min)
2. **Uniformare terminologia** score/health/performance (~1h, sostituzione stringhe)
3. **Definire 3 varianti bottone canoniche** in `hud.jsx` (~1h)
4. **Aggiungere onboarding 3-step** al primo login (~2h)

### 🟡 P1 — Fix in ~1 giornata (medio impatto)
5. **Ristrutturare menu a 5 voci principali** + strumenti nel footer (~4h)
6. **Aggiungere banner "next best action"** dopo ogni azione (~3h)
7. **Standardizzare freshness badge** in tutte le pagine (~1h)
8. **Bottone Mobile Handoff nel web header** (~30 min)

### 🟢 P2 — Fix in una settimana (polish)
9. Audit responsive completo (~4h)
10. Tooltip per termini tecnici (bufferbloat, MPO, HAGS, MSI mode) (~2h)
11. CTA descrittive ovunque (~3h)
12. Iconografia unificata (rimuovere emoji da UI web) (~2h)

---

## 💡 8. Feature mancante coerente col messaging

La landing dice **"trova i colli di bottiglia"**. Manca però una pagina dedicata al bottleneck detector.

**Proposta**: nuova pagina `/app/bottleneck` (o widget in Dashboard) che analizza in real-time:
- Se CPU% > 90% e GPU% < 60% → "CPU-BOUND"
- Se GPU% > 90% e CPU% < 60% → "GPU-BOUND"
- Se RAM > 90% → "RAM saturation"
- Se disco > 90% throughput → "IO bottleneck"

Con consiglio contestuale: *"Chiudi Chrome/Discord per liberare thread CPU"* → 1 click apre la GUI in modalità Booster.

**Questo unico feature colma il gap più grande tra promessa e realtà.**

---

## 📊 Metriche di successo

Come misureremo che i fix funzionano:

1. **Bounce rate post-login**: utente che chiude la app entro 30s. Baseline ignoto. Target: <10%.
2. **First "aha moment"**: tempo per applicare il primo tweak. Target: <5 min dal signup.
3. **Menu depth**: % utenti che visita voci oltre le top-3. Target: >40%.
4. **Time-to-second-session**: tempo tra login #1 e login #2. Target: <7 giorni.
5. **Feature discovery**: % utenti che scopre il bottleneck detector se implementato. Target: >60% in prima settimana.

---

## 🎬 Prossimi passi consigliati

**Opzione A (Cosmetic)**: Fai solo P0 (~3-4h) → app immediatamente più coerente, effort basso.

**Opzione B (Deep restructure)**: P0 + P1 (~1 giornata) → esperienza completamente riorganizzata.

**Opzione C (Killer feature)**: P0 minimo + **Bottleneck detector** → chiude il gap principale col messaging.

**Opzione D**: Discuti prima quale gap ti risuona di più, poi decidiamo lo sprint.

*Fine audit. Salvato per rilettura in `/app/memory/UX_CONSISTENCY_AUDIT.md`.*
