# FrameForge — GUI locale come estensione dell'app web

> Piano strategico: trasformare la GUI locale (Windows/HTML) da tool separato a **vista sincronizzata** della web app.
> Autore: Agente E1 · Data: 2026-02-22 · Stato: proposta

---

## 1. Vision

**Un solo prodotto, due volti.**

- **Web app** (`forgefps.dev`) = **Control Tower** → analisi, storico, AI advisor, community, billing, config globale, PDF report.
- **GUI locale** (Windows, HTML in WebView2) = **Control Panel** → esecuzione immediata dei tweak, telemetria real-time, azioni che richiedono accesso al sistema operativo.

Il modello mentale che vogliamo: come **Spotify Web ↔ Desktop app**. Due entry point che condividono account, playlist, preferenze e stato in real-time. L'utente non sceglie "quale usare oggi", le usa **contemporaneamente** in modo naturale.

---

## 2. Cosa manca oggi (analisi dei gap)

### 2.1 Design system
- Web usa **Inter/font-display**, TailwindCSS con radii `rounded-lg`, shadow varie.
- GUI usa **Segoe UI Variable** (system font), border-radius 0, palette leggermente diversa.
- Le icone: web ha `lucide-react`, GUI ha emoji Unicode.
- **Impatto**: sembrano due prodotti differenti dello stesso brand.

### 2.2 Stato utente
- Preferenze GUI (density compact/detailed, filtri attivi, sort mode) vivono in `localStorage` locale.
- Cambi PC → riparti da zero.
- Cambi impostazione sul web → non arriva sulla GUI (e viceversa).

### 2.3 Comunicazione web ↔ GUI
- **Web → GUI**: solo `frameforge://launch?mode=X&silent=1` (protocollo custom). Molto povero: passa solo la modalità.
- **GUI → Web**: solo tramite backend HTTP POST/GET (report-specs, telemetry). Web deve poll manualmente per vedere cambi.
- Nessun canale real-time. Se applichi un tweak nella GUI, il web se ne accorge solo al prossimo refresh (o al prossimo ambient sync tra 24h).

### 2.4 Continuità
- Web mostra "Health Score 78". Vado sulla GUI, applico 5 tweak, chiudo. Torno al web → **non vedo** che qualcosa è cambiato finché non ricarico.
- Nessun deep-linking: se il web dice "consigliato: MSI Mode", non posso cliccare per aprire quella card specifica nella GUI.

### 2.5 Evoluzione parallela
- Un fix (es. copy dei tweak) va fatto in due punti: `ps_agent.py` per la GUI, `i18n.js` per il web.
- Le componenti visive non sono riusabili: `PageHeader`, `HUDCard`, `Toast` esistono solo nel web React.

---

## 3. Principi guida (in ordine di priorità)

### 3.1 Cloud = source of truth
Tutto ciò che è configurabile dall'utente (density, filtri, alert thresholds, colore accent, layout dashboard) **vive nel database**. Web e GUI leggono/scrivono dal cloud. `localStorage` diventa solo cache locale + fallback offline.

### 3.2 Design tokens generati, mai duplicati
Un unico file `design-tokens.json` sul backend definisce colori, spacing, font-size, radii. Web e GUI lo importano al lancio. Cambi il valore in un solo posto → cambia ovunque.

### 3.3 Ogni azione è deep-linkable
Ogni operazione atomica (applicare tweak, aprire benchmark, avviare monitor) deve avere:
- Una **URI** `frameforge://action/{id}?params` per aprire la GUI su quella specifica azione
- Una **URL** `https://forgefps.dev/app/action/{id}` per aprire il web sulla vista collegata
- Il web deve poter generare l'URI, la GUI deve poter generare l'URL

### 3.4 Real-time bidirezionale
Quando entrambe sono aperte, ogni evento significativo (apply, restore, sync, benchmark) viene propagato istantaneamente via WebSocket. L'utente vede feedback in tempo reale in entrambe le UI.

### 3.5 Zero context loss
Torno al web dopo aver usato la GUI → vedo un banner "5 tweak applicati 30s fa · Health +7 · [Guarda i dettagli]". Non devo cercare cosa è cambiato.

---

## 4. Roadmap dettagliata (5 fasi)

### 🎨 Fase A — Design tokens condivisi (~3h)

**Obiettivo**: unificare visualmente web e GUI.

**Cosa fare**:
1. Creare `/app/backend/design_tokens.py` che espone:
   ```python
   TOKENS = {
     "colors": {
       "bg": "#0A0A0F", "bg2": "#12121A", "card": "#0F0F12",
       "accent": "#E5FF00", "ok": "#00FF66", "warn": "#FFAA00",
       "danger": "#FF3355", "info": "#00E0FF",
       "text": "#E6E6EC", "muted": "#7D7D8A", "dim": "#4A4A55",
     },
     "spacing": {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32},
     "font_sizes": {"xs": 10, "sm": 12, "md": 14, "lg": 16, "xl": 20, "hero": 28},
     "radii": {"none": 0, "sm": 2, "md": 4, "lg": 8},
     "fonts": {
       "display": "'Space Grotesk', system-ui, sans-serif",
       "body": "'Inter', system-ui, sans-serif",
       "mono": "'JetBrains Mono', 'Consolas', monospace",
     },
   }
   ```

2. Endpoint `GET /api/design-tokens` (pubblico) che restituisce i tokens sia come JSON sia come CSS variables:
   ```
   GET /api/design-tokens          → JSON
   GET /api/design-tokens?fmt=css  → :root { --color-accent: #E5FF00; ... }
   ```

3. **Web**: `frontend/src/lib/tokens.js` fetcha al boot, inietta `<style>` con le CSS variables. Tailwind config le usa come extend palette.

4. **GUI (`ps_agent.py`)**: al lancio, prima di servire l'HTML, PowerShell fa un `Invoke-RestMethod` a `/api/design-tokens?fmt=css` e lo inietta nel `<head>` dell'HTML. Sostituisce i colori hardcoded in `PS_SCRIPT` con `var(--color-accent)`, `var(--color-ok)`, ecc.

5. **Font**: caricare Space Grotesk + Inter via `@font-face` embedded (usiamo base64 dei .woff2, ~200KB extra ma unifica il look).

**Test**: cambio `--color-accent` da giallo a rosa nel backend → sia web sia GUI diventano rosa al prossimo refresh/lancio.

---

### 💾 Fase B — Shared preferences (~4h)

**Obiettivo**: le preferenze GUI seguono l'utente ovunque.

**Cosa fare**:
1. Nuovo modello `UserPreferences` in `backend/models.py`:
   ```python
   class UserPreferences(BaseDocument):
     user_id: str
     gui_density: str = "detailed"  # "compact" | "detailed"
     gui_filters: list[str] = []
     gui_sort: str = "impact"
     gui_theme_accent: str = "#E5FF00"
     gui_show_intro_banner: bool = True
     gui_default_preset: Optional[str] = None
     alert_cpu_max: int = 90
     alert_gpu_max: int = 85
     alert_fps_drop_threshold: Optional[int] = None
     dashboard_widgets_order: list[str] = ["health", "telemetry", "recent"]
     updated_at: datetime
   ```

2. Endpoint `routers/preferences.py`:
   - `GET /api/preferences` → ritorna preferenze utente (crea record default al primo accesso)
   - `PUT /api/preferences` → aggiorna parziale (patch)

3. **GUI**: al lancio, invece di leggere `localStorage`, chiama `GET /api/preferences` e usa quei valori. Ogni cambio (density toggle, filter chip, sort) triggera `PUT /api/preferences`.

4. **Web**: nuova pagina `/app/account/preferences` con controlli per:
   - Density default della GUI
   - Filtri preferiti (persistenti)
   - Colore accent (color picker)
   - Alert thresholds (CPU/GPU/FPS)
   - Ordine widget dashboard
   - Bottone "Reset a default"

5. **Migrazione**: al primo lancio con il nuovo agent, la GUI legge `localStorage` e fa PUT al cloud (migrazione soft).

**Test**: cambio density su Windows PC A → login su Windows PC B con stesso account → GUI parte in modalità compatta.

---

### 📡 Fase C — Real-time bridge (~5h)

**Obiettivo**: eventi in una UI istantanei nell'altra.

**Cosa fare**:
1. **Backend WebSocket** su `/ws/bridge` (auth via cookie o token query):
   ```python
   # backend/routers/bridge.py
   @app.websocket("/ws/bridge")
   async def bridge_ws(ws: WebSocket, user_id: str):
     await ws.accept()
     # Register connection in per-user pool
     bridge_pool[user_id].append(ws)
     try:
       while True:
         msg = await ws.receive_json()  # incoming from client
         # Optional: process client-side events
     finally:
       bridge_pool[user_id].remove(ws)

   async def broadcast_event(user_id: str, event: dict):
     for ws in bridge_pool.get(user_id, []):
       try: await ws.send_json(event)
       except: pass
   ```

2. **Eventi da broadcastare**:
   - `tweak.applied` `{id, name, timestamp, source: "gui"|"web"}`
   - `tweak.restored` `{id}`
   - `preset.applied` `{name, ids: [...]}`
   - `benchmark.completed` `{score, delta}`
   - `pc.synced` `{health_score}`
   - `preferences.changed` `{key, value}`
   - `alert.triggered` `{metric, value, threshold}`

3. **Web client** (`frontend/src/hooks/useBridge.js`):
   ```js
   export function useBridge(handlers) {
     useEffect(() => {
       const ws = new WebSocket(`${wsUrl}/ws/bridge`);
       ws.onmessage = (e) => {
         const evt = JSON.parse(e.data);
         handlers[evt.type]?.(evt);
       };
       return () => ws.close();
     }, []);
   }
   ```
   - In `Live.jsx`, `MyPc.jsx`, `Benchmark.jsx` → sottoscrivi eventi rilevanti, aggiorna stato senza refresh.
   - Mostra toast "⚙ Tweak applicato sul PC" quando source=gui.

4. **GUI client** (JS embedded in `ps_agent.py`):
   ```js
   const bridge = new WebSocket(`wss://forgefps.dev/ws/bridge?tk=${TOKEN}`);
   bridge.onmessage = (e) => {
     const evt = JSON.parse(e.data);
     if (evt.type === "preferences.changed") applyNewPrefs(evt);
     if (evt.type === "tweak.applied" && evt.source === "web") refreshState();
   };
   ```

5. **Publisher**: dopo ogni applyOne/applySelected nel backend, chiamare `broadcast_event()`.

**Test**: apri web e GUI insieme. Clicca "Applica tweak X" nella GUI → il web mostra istantaneamente toast + update health score senza refresh.

---

### 🔗 Fase D — Deep-linking bidirezionale (~4h)

**Obiettivo**: ogni schermata web ha un "gemello" nella GUI, cliccabile.

#### D.1 Web → GUI (URI protocol)

Estendere il protocollo `frameforge://` oltre `launch?mode=X`:
- `frameforge://tweak/{id}` → GUI apre pre-selezionando quella card
- `frameforge://preset/{name}` → GUI apre con preset armato (non applicato, in preview)
- `frameforge://preset/{name}/apply` → GUI apre e applica subito il preset
- `frameforge://benchmark?compare=v0.7.1` → GUI apre in modalità benchmark comparison
- `frameforge://restore/{tweak_id}` → GUI apre e propone il restore

Implementazione nell'agent Python:
```python
if scheme == "frameforge://":
  path = uri.path.split("/")
  if path[0] == "tweak":
    tweak_id = path[1]
    launch_gui(pre_select=[tweak_id])
  elif path[0] == "preset":
    preset_name = path[1]
    apply_now = len(path) > 2 and path[2] == "apply"
    launch_gui(preset=preset_name, auto_apply=apply_now)
```

#### D.2 GUI → Web (magic URLs)

Ogni card GUI ha un bottone `↗ Vedi nel Web`:
```html
<a href="https://forgefps.dev/app/tweaks/{id}?mt={magic_token}" target="_blank">
  ↗ Vedi nel Web
</a>
```

Nuova web page `/app/tweaks/{id}` che mostra:
- Descrizione estesa tweak
- Storico applicazioni (chi/quando)
- Community stats ("84% degli utenti con RTX 4070 lo applica")
- Link "Documentazione tecnica"
- Bottone "Ripristina se applicato"

Magic token = short-lived JWT che pre-autentica il browser (evita re-login).

#### D.3 Contextual chips nel web

Sulla pagina `/app/live`, sotto il badge REC:
```
[⚙ Apri Booster nella GUI]  [🔧 Applica preset Streaming]  [📊 Nuovo benchmark]
```
Ogni chip lancia URI `frameforge://...`.

Sulla `/app/pc`, banner post-sync:
```
Il tuo score è 68. Applica 3 tweak consigliati per salire a 82 →  [Apri nella GUI]
```

**Test**: cliccando link nel web si apre GUI sul contesto giusto. Cliccando "↗ Vedi nel Web" nella GUI apre pagina web pre-loggata.

---

### 🏢 Fase E — Command Center in GUI (~6h)

**Obiettivo**: portare nella GUI il 10-20% di web più utile in-context.

Aggiungere nuova tab `⌂ Home` come prima categoria (prima di Gaming). Contenuto:

#### E.1 Widget Health Score
Gauge circolare identica al web (usa gli stessi SVG). Mostra:
- Score corrente (0-100)
- Delta vs 7 giorni fa
- Bottone "Vedi trend →" apre `/app/pc` nel browser

#### E.2 Widget Telemetria mini
Chart CPU/GPU/RAM ultimi 60 secondi. Refresh 1s (locale, non da cloud).

#### E.3 Widget "AI Advisor Quick Chat"
Text input embedded. Invia a `/api/advisor/chat`. Risposta AI mostrata in ~2s. Limite: 3 messaggi/giorno per utenti free, illimitato per Pro.

#### E.4 Widget "Ultimi 10 eventi"
Da nuovo endpoint `GET /api/audit-log?limit=10`. Mostra:
```
⚙ Tweak "Piano energetico" applicato · 2m fa · da questo PC
📊 Benchmark completato · 5m fa · Score 87 (+3)
🌐 Sync da altro PC · 10m fa · Score aggiornato
⚠ Alert temperature CPU · 1h fa
```

#### E.5 Widget "Notifiche cloud"
Da nuovo endpoint `GET /api/notifications`. Include:
- Nuovi articoli/tutorial
- Community stats week digest
- Alert Discord bot
- Sconto plan Pro

#### E.6 "Continua dove eri rimasto"
Se l'ultimo touch web è stato <10min fa, mostrare:
```
Stavi guardando: /app/live · Vuoi avviare il monitor? [Avvia →]
Stavi guardando: /app/benchmark · Vuoi rifare il benchmark? [Esegui →]
```
Dato disponibile via `GET /api/session/last-page` (nuovo endpoint che salva la pagina web attiva ogni 30s).

---

## 5. Feature "wow" abilitate dall'integrazione

Una volta implementate le fasi A–E, sbloccano feature che oggi sarebbero impossibili:

### 5.1 QR Handoff universale (bidirezionale)
Già esiste il "Continua sul telefono" (mobile handoff). Estendere:
- QR dalla GUI → apri sul telefono la vista di quella tab
- QR dal telefono → apri sulla GUI l'azione consigliata dall'app mobile

### 5.2 Windows Native Toast bridge
Le push del web (alert temperature) diventano toast Windows nativi via GUI in background. Funziona anche se il browser è chiuso.

### 5.3 Time Machine
Web mostra "Config timeline": ogni giorno degli ultimi 30gg è uno snapshot. Click → GUI ripristina esattamente quello stato di tweak applicati.

Implementazione: nuova collection `config_snapshots` popolata daily con lo stato di tutti i tweak applicati per utente.

### 5.4 Session Recording
Attivi "Record" sul web → registri sequenza di azioni (tweak, benchmark, monitor start/stop) → esporti come JSON "Config Profile" condivisibile su Discord. Chi lo importa può riprodurre esattamente le tue azioni.

### 5.5 Voice command
Web ha bottone `🎤 Boost Now` → registra audio 5s → invia a Whisper (OpenAI STT) → AI Advisor interpreta → invia comando WebSocket alla GUI → GUI esegue silent.
Es: "Attiva profilo streaming" → GUI applica preset streaming senza click.

### 5.6 Multi-device fleet control
Se l'utente ha 2+ PC connessi (uno da gaming, uno da streaming), il web mostra un selettore "Target PC" e i comandi vanno alla GUI del PC scelto. Utile per streamer con setup dual PC.

### 5.7 Config sharing marketplace
Utenti Pro possono pubblicare i loro "Config Profile" (v 5.4) nel marketplace. Altri li importano con un click. GUI mostra "Applica Config Pro Streamer X".

### 5.8 Advisor contestuale in-GUI
Nella GUI, ogni card ha "?" cliccabile → apre chat AI advisor pre-caricata con contesto "Sto guardando il tweak X sul PC con RTX 4070, spiegami perché è consigliato".

---

## 6. Architettura tecnica

```
┌──────────────────┐    HTTP(S)     ┌───────────────────┐    HTTP(S)    ┌──────────────────┐
│   WEB APP        │◄──────────────►│                   │◄─────────────►│   GUI LOCAL      │
│  (React/Tailwind)│                │      BACKEND      │               │  (PowerShell +   │
│                  │                │     (FastAPI)     │               │   HTML/JS in     │
│  · Dashboard     │    WebSocket   │                   │   WebSocket   │   Edge WebView2) │
│  · Advisor       │◄──────────────►│  · MongoDB        │◄─────────────►│                  │
│  · Live/Bench    │  /ws/bridge    │  · Design Tokens  │  /ws/bridge   │  · Tweaks apply  │
│  · Community     │                │  · User Prefs     │               │  · Telemetria    │
│  · Billing       │                │  · Audit Log      │               │  · Booster       │
│                  │                │  · WebSocket Pool │               │  · Command Center│
└──────────────────┘                │  · Config Snapshots│              └──────────────────┘
        ▲                           └───────────────────┘                       ▲
        │                                     ▲                                 │
        │              frameforge://          │            magic URL            │
        └─────────────────────────────────────┴─────────────────────────────────┘
```

**Contratti chiave**:
- Design tokens: JSON versionato (`/api/design-tokens?v=2`)
- Preferences: PATCH JSON via `/api/preferences`
- Events: JSON via WebSocket con schema `{type, timestamp, source, payload}`
- Deep links: URI scheme `frameforge://` + magic URLs con JWT

---

## 7. Migration strategy (non-breaking)

Ogni fase deve essere **retro-compatibile** con l'agent v0.7.2 attualmente installato.

### Approccio
- **Feature detection**: nuovi endpoint restituiscono `501 Not Implemented` per agent vecchi.
- **Backward defaults**: se la GUI non ha ricevuto design tokens, usa i valori hardcoded attuali (fallback).
- **Progressive enhancement**: WebSocket bridge è "extra" — se fallisce, tutto funziona in polling mode.
- **Version handshake**: GUI dice al backend "sono v0.7.2, quali feature supporti?" → backend rispota adattandosi.

### Rollout suggerito
1. Fase A (tokens): shippare backend endpoint, GUI ignora per ora. Web adotta subito.
2. Fase B (preferences): shippare + GUI legge dal cloud al primo lancio (con migrazione localStorage).
3. Fase C (WebSocket): opt-in dietro feature flag utente ("Beta bridge") per validare senza rischi.
4. Fase D (deep links): il web genera link, la GUI vecchia li ignora (`frameforge://tweak/x` non è gestito) — non peggiora nulla.
5. Fase E (Command Center): richiede release GUI nuova (v0.8.0). Utenti con v0.7.2 non vedono, tutto il resto funziona.

**Nota**: la GUI scarica lo script `.ps1` fresco ad ogni lancio, quindi cambiamenti in `ps_agent.py` si propagano **senza rebuild `.exe`**. Serve rebuild solo se cambia `forgefps_agent.py` (URI handling, PS launcher). Fasi A–D non toccano il launcher.

---

## 8. Roadmap incrementale suggerita

| Sprint | Fasi | Ore | Rischio | Rilascio | Testabilità |
|---|---|---|---|---|---|
| **1** | A + B | ~7h | Basso | Web patch + agent hot-update | Alta (backend testing agent) |
| **2** | C | ~5h | Medio | Backend patch + web patch, GUI hot-update | Media (serve Windows reale per full test) |
| **3** | D | ~4h | Basso | Web patch + agent hot-update | Alta (URI test tramite mock) |
| **4** | E | ~6h | Alto | Nuova release agent v0.8.0 | Bassa (WebView2 solo su Windows) |
| **Totale** | | **~22h** | | | |

**Break tra sprint**: mai fare 2 fasi insieme senza testing. Ogni fase è **completa e usabile** da sola.

---

## 9. Cosa **non** cambiare (regole di sicurezza)

Anche in questo redesign profondo, ci sono cose intoccabili:
1. **Sicurezza tweak**: ogni azione GUI deve continuare a essere reversibile e con backup automatico.
2. **Zero remote code execution**: il WebSocket bridge **non deve mai** accettare comandi arbitrari da eseguire lato PC. Solo azioni pre-definite (`apply_tweak_id`, `restore_id`, `run_benchmark`) autorizzate dall'utente.
3. **Auth**: WebSocket richiede stesso auth della web app (cookie session o magic token JWT).
4. **Rate limiting**: max N eventi/sec per utente per evitare flooding.
5. **Privacy**: telemetria live non deve mai finire nel `audit_log` pubblico.

---

## 10. Metriche di successo

Come misureremo che l'integrazione funziona:

1. **Adoption**: % utenti che usa entrambe (web + GUI) in una sessione. Baseline: sconosciuto. Target: >60%.
2. **Cross-navigation**: click su chip "Apri nella GUI" dal web. Target: >20% degli utenti alla settimana.
3. **Session length**: durata media sessione GUI con Command Center. Target: +30% vs oggi.
4. **Support tickets**: riduzione domande tipo "dov'è X?" tra web e GUI. Target: -50%.
5. **Retention**: settimana 4 attivi/totali. Target: +15%.

---

## 11. Decisioni aperte (per te)

Prima di iniziare, ho bisogno che tu confermi:

### D1. Priorità di partenza
- **Opzione X**: Sprint 1 (A+B) — foundation cosmetico + preferences. Basso rischio, tangibile subito.
- **Opzione Y**: Sprint 2 (C) — WebSocket bridge. Più flashy ma meno "utile in silenzio".
- **Opzione Z**: Sprint 4 (E) — Command Center. Killer ma richiede release agent.

### D2. Modalità sviluppo
- **Iterativa** — 1 fase per volta, testing tra ognuna, ~1 settimana per fase.
- **Full sprint** — pianifico tutto insieme, implemento in blocco, testing finale.

### D3. Feature "wow" prioritaria
Quale delle 8 wow features (§5) ti eccita di più? Ordina le top 3.

### D4. Design tokens: single source
Il design system attuale della web app è già maturo. Vuoi:
- Estrarre i valori dal Tailwind config e servirli come API? (retro-fit)
- Creare da zero un nuovo `design_tokens.py` autoritativo? (clean-slate)

### D5. Nuove release GUI
Ok fare release v0.8.0 dell'agent (richiede tuo intervento su GitHub Actions per lo SHA)?

---

## 12. Prossimo passo

Se sei d'accordo con la vision, il **primo commit concreto** che farei è questo:

1. Creare `backend/design_tokens.py` con i valori attuali del web
2. Aggiungere `GET /api/design-tokens` (JSON + CSS format)
3. Iniettare i tokens nel `<head>` della GUI via `ps_agent.py` come primo `<link>` o `<style>`
4. Rimuovere i valori hardcoded da `PS_SCRIPT` sostituendoli con `var(--color-*)`
5. Testing: cambio un colore, verifico che si propaga in entrambe.

Tempo: ~90 minuti. Zero regressioni. **Fase A completa.**

---

*Fine documento. Se vuoi discutere qualsiasi punto o modificare un principio, apri una conversazione dedicata.*
