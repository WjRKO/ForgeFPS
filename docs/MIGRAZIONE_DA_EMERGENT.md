# Migrazione di FrameForge fuori da Emergent

Stato del branch `detach-emergent`. Questo documento descrive cosa e' gia' stato
staccato nel codice, cosa resta, e in che ordine eseguire il cutover.

---

## 1. Cosa e' gia' fatto in questo branch

| Aggancio | Dov'era | Come e' stato risolto |
|---|---|---|
| SDK LLM proprietario | `backend/ai_engine.py` | Sostituito da `backend/llm/`, un'interfaccia neutra. `ai_engine.py` non importa piu' nessun SDK di fornitore. |
| Script di terze parti | `frontend/public/index.html` | Rimosso `assets.emergent.sh/scripts/emergent-main.js`, che veniva caricato per ogni visitatore. |
| Plugin visual-edits | `frontend/package.json`, `craco.config.js` | Rimossi dipendenza (tarball esterno) e blocco di attivazione. |
| Cron della piattaforma | `.emergent/` | Cartella eliminata. Lo scheduling applicativo era gia' interno (APScheduler in `server.py`). |
| Identita' git dell'agent | `.gitconfig` | Eliminato. |
| Percorso `/app/backend/.env` | `setup_stripe.py` | Ricavato dalla posizione del file, con override `BACKEND_ENV_FILE`. |
| Rilevamento ambiente da hostname | `services/release_announcer.py` | Sostituito da `RELEASE_ANNOUNCER_ENABLED` esplicita. **Vedi §4, cambia comportamento.** |
| Metadata Stripe `managed_by: emergent` | `setup_stripe.py` | Ora si scrive `forgefps_product_id`; la chiave storica resta letta in fallback per non duplicare i prodotti live. |
| Credenziali admin in chiaro | 37 file di test + 34 report | Sostituite da lettura da ambiente; `test_reports/` rimossa. **Vedi §5.** |
| Scrittura credenziali su disco all'avvio | `server.py` | Funzione `_write_test_credentials()` rimossa: scriveva la password admin in chiaro a ogni boot e impediva l'avvio fuori da un container con `/app`. |

### L'unico aggancio rimasto (voluto)

Il motore AI. `backend/llm/emergent.py` continua a usare `emergentintegrations`
con `EMERGENT_LLM_KEY`, perche' la scelta del sostituto e' rinviata.

E' ora isolato: **un solo file** del backend importa quell'SDK. Per cambiare
motore servono due mosse, senza toccare `ai_engine.py` ne' i router:

1. creare `backend/llm/<nome>.py` con una classe che eredita da `LLMProvider`
   e implementa `stream()`;
2. registrarla in `_PROVIDERS` dentro `backend/llm/__init__.py` e impostare
   `LLM_PROVIDER=<nome>`.

Finche' resta il provider Emergent, in `requirements.txt` restano necessari
`emergentintegrations` e il wheel `litellm` ospitato sul CDN Emergent. Quel
wheel e' un punto singolo di rottura esterno: se il CDN diventa irraggiungibile,
`pip install` del backend fallisce.

---

## 2. Cosa manca e non e' codice applicativo

**Nel repository non esiste nessun file di deploy**: niente `Dockerfile`,
`docker-compose.yml`, `Procfile` o equivalenti. Il confezionamento lo faceva la
piattaforma. Va scritto prima di poter ospitare l'app altrove.

Servono tre pezzi:

- **Database.** MongoDB gestito. MongoDB Atlas e' la via piu' diretta: si crea
  il cluster, si migra con `mongodump`/`mongorestore`, si aggiorna `MONGO_URL`.
- **Backend.** Un processo sempre attivo (non serverless): APScheduler gira
  dentro il processo FastAPI. Render, Railway o Fly.io vanno tutti bene; in
  alternativa un VPS con Docker e un reverse proxy.
- **Frontend.** Build statica React, quindi qualunque CDN: Cloudflare Pages,
  Netlify, Vercel.

> **Vincolo operativo importante:** il backend deve girare in **una sola
> istanza**. Gli scheduler in `server.py` (controllo prezzi ogni 45 minuti,
> reminder trial, reminder streak) non hanno lock distribuito: con due repliche
> ogni notifica parte due volte. Se in futuro serve scalare orizzontalmente, gli
> scheduler vanno estratti in un worker separato.

---

## 3. Variabili d'ambiente da ricreare

Inventario estratto dal codice, non dalla memoria. Le voci senza default
mandano in errore l'avvio se mancanti.

### Backend — obbligatorie

| Variabile | Note |
|---|---|
| `MONGO_URL` | Nessun default: l'avvio fallisce se manca. |
| `DB_NAME` | Nessun default. |
| `JWT_SECRET` | Nessun default. **Se cambia, tutte le sessioni attive decadono.** |
| `FRONTEND_URL` | Usata per i link nelle email e nelle notifiche push. |
| `CORS_ORIGINS` | Deve includere il dominio del frontend. |

### Backend — per funzionalita'

| Variabile | Serve a |
|---|---|
| `EMERGENT_LLM_KEY` | AI advisor, finche' resta il provider Emergent. |
| `LLM_PROVIDER` | Opzionale; default `emergent`. |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Pagamenti e webhook. |
| `RESEND_API_KEY`, `SENDER_EMAIL`, `REPLY_TO_EMAIL`, `APP_ORIGIN` | Invio email. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Web push. **Se cambiano, tutte le iscrizioni push esistenti smettono di funzionare.** |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Seed dell'account admin all'avvio. |
| `RELEASE_ANNOUNCER_ENABLED` | Annunci release su Discord. **Vedi §4.** |
| `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_ROLE_PRO`, `DISCORD_ROLE_BOOSTED_ID`, `DISCORD_ROLE_CREATOR_VERIFIED`, `DISCORD_CHANNEL_CREATOR_REVIEW`, `DISCORD_WEBHOOK_FEEDBACK` | Bot e integrazione Discord. |
| `DISCORD_REDIRECT_URI` | Se assente viene dedotto dal request. |
| `DISCORD_PRO_SYNC_INTERVAL`, `DISCORD_CREATOR_REAPPLY_DAYS` | Hanno default. |

### Frontend

| Variabile | Note |
|---|---|
| `REACT_APP_BACKEND_URL` | Iniettata a build time, non a runtime: va impostata **prima** della build. |
| `ENABLE_HEALTH_CHECK` | Opzionale. |

---

## 4. Trappole da conoscere prima del cutover

**Il dominio va conservato.** `frontend/src/config/agent.js` fissa
`AGENT_DEFAULT_BACKEND = "https://forgefps.dev"`, e quel valore e' compilato
dentro ogni agent desktop gia' installato sui PC degli utenti. Se la nuova
infrastruttura non risponde su `forgefps.dev`, **tutti gli agent gia'
distribuiti smettono di comunicare** e non si aggiornano piu' da soli. La
migrazione deve essere un ripuntamento DNS dello stesso dominio, non un dominio
nuovo.

**L'announcer Discord ora e' spento per default.** Prima decideva da solo
guardando l'hostname del pod; adesso parte solo con
`RELEASE_ANNOUNCER_ENABLED=true`. Se non la si imposta in produzione, gli
annunci di release smettono silenziosamente. E' intenzionale: meglio muto che
doppio, ma va ricordato.

**Webhook e redirect da riconfigurare** presso i fornitori, non nel codice:

- endpoint webhook Stripe → nuovo backend;
- `DISCORD_REDIRECT_URI` nell'applicazione Discord → nuovo dominio.

**Cron invisibili.** `.emergent/crons.yml` non e' mai stato nel repository:
viveva solo nel pod. Prima di spegnere l'ambiente Emergent, aprire il loro
pannello e annotare se esistono cron configurati li'. Quelli applicativi noti
(prezzi, reminder) sono in `server.py` e migrano da soli; un eventuale cron
aggiuntivo configurato dal pannello andrebbe perso senza accorgersene.

**Prodotti Stripe.** `setup_stripe.py` ritrova i prodotti live anche con la
vecchia chiave metadata, quindi e' sicuro rilanciarlo. Opzionalmente, dopo la
migrazione si puo' aggiornare a mano il metadata dei due prodotti su Stripe
sostituendo `emergent_product_id` con `forgefps_product_id` e rimuovendo il
fallback dal codice.

---

## 5. Sicurezza: azione richiesta

La password dell'account `admin@boostpc.io` e' stata pubblicata in chiaro in
questo repository **pubblico** dal 9 luglio 2026, in 37 file di test e 34
report. Questo branch la rimuove dai file, ma **resta nella storia git**: chi ha
gia' clonato o consultato il repository l'ha vista.

Rimuoverla dai file non e' una misura sufficiente. L'unico rimedio e' **cambiare
la password dell'account admin**. Da valutare anche la riscrittura della storia
(`git filter-repo`) o, piu' semplicemente, considerare quel valore bruciato per
sempre.

Le credenziali di test ora si passano dall'ambiente:

```sh
export ADMIN_PASSWORD='...'      # obbligatoria
export ADMIN_EMAIL='...'         # opzionale
export STARTER_PASSWORD='...'    # solo per i test sul piano Starter
export REACT_APP_BACKEND_URL='http://localhost:8001'
```

`backend/tests/conftest.py` blocca la suite con un messaggio esplicito se
`ADMIN_PASSWORD` non c'e', invece di lasciar fallire i test con un 401 opaco.

---

## 6. Sequenza di cutover consigliata

Ordine pensato per tenere l'app viva e poter tornare indietro fino all'ultimo.

1. **Ruotare la password admin.** Indipendente da tutto il resto, da fare subito.
2. **Scrivere i file di deploy** (Dockerfile backend, build frontend) e provarli
   in locale contro un MongoDB di prova.
3. **Creare il cluster MongoDB** gestito. Ancora nessun traffico reale.
4. **Deployare il backend** sul nuovo host, su un dominio temporaneo, con le env
   var ricreate e `RELEASE_ANNOUNCER_ENABLED` **spento** (per non annunciare due
   volte mentre convivono i due ambienti).
5. **Deployare il frontend** con `REACT_APP_BACKEND_URL` puntato al backend
   temporaneo, e verificare a mano: login, advisor AI, benchmark, pagamenti in
   modalita' test.
6. **Migrare i dati**: `mongodump` dal database Emergent, `mongorestore` sul
   nuovo. Da fare in finestra di fermo, per non perdere scritture.
7. **Ripuntare il DNS** di `forgefps.dev` alla nuova infrastruttura. Da qui gli
   agent installati parlano con il nuovo backend.
8. **Riconfigurare** webhook Stripe e redirect Discord sul dominio definitivo.
9. **Accendere** `RELEASE_ANNOUNCER_ENABLED=true` e spegnere l'ambiente Emergent.
10. **Solo dopo**, decidere il motore AI e rimuovere l'ultimo aggancio (§1).

---

## 7. Note a margine emerse durante il lavoro

Non sono legate a Emergent, ma sono state notate strada facendo e conviene
sistemarle prima o poi:

- `frontend/src/config/agent.js` pubblicizza `v.0.8.0` mentre l'ultima release
  e' `v0.8.1`: gli utenti scaricano l'agent precedente.
- In `.github/workflows/build.yml` il corpo della release e' fisso al testo di
  `v0.7.8`, quindi ogni release da `v0.7.9` in poi annuncia le note sbagliate.
- Le copie di `forgefps_agent.py`, `version_info.txt` e `build.bat` nella radice
  sono ferme alla v0.6.8 e non vengono compilate da nessuno: la CI usa solo
  `agent-build/`. Sono codice morto che sembra vivo.
- `README.md` inizia con `# Here are your Instructions` in un repository
  pubblico da cui gli utenti scaricano un eseguibile.
- Il file `=2.0.0` nella radice e' l'output di un `pip install` finito in
  redirezione su Windows.
