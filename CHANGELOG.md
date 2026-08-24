# Changelog

Tutte le modifiche significative a **FrameForge** (agent + web app).
Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — Versioning: [SemVer](https://semver.org/lang/it/).

---

## [Unreleased]

_Prossime feature in sviluppo — vedi `/app/memory/ROADMAP.md`._

### Security — il link di reset arriva all'utente, non ai log

`POST /api/auth/forgot-password` stampava il token su stdout:

```python
print(f"[PASSWORD RESET] Link: /reset-password?token={token}")
```

In un deploy containerizzato quella riga finisce nell'aggregatore di log della
piattaforma, e un token di reset e' una **presa di controllo dell'account** per
un'ora. Non era una riga di debug dimenticata: era il canale di consegna,
perche' `email_service` era collegato a benvenuto, trial e pagamenti ma **non al
reset**. Di conseguenza l'unico altro modo di consegnare il link era
`/api/admin/password-resets`, cioe' un admin che legge il token di un utente.

- `send_password_reset` collegata al flusso: il link va all'utente per email,
  con il template delle altre transazionali.
- La `print` non c'e' piu'. Se l'invio fallisce, nel log va **il fatto e dove
  trovare il link** (il pannello admin resta la via di riserva), non il segreto.
- **Un solo invio ogni due minuti per account.** L'endpoint e' pubblico e manda
  email: senza freno e' un modo per riempire la casella di qualcun altro e per
  bruciare la quota di invio. Dentro la finestra non si conia nemmeno un nuovo
  token, cosi' il link gia' ricevuto resta valido.
- La risposta resta identica per un indirizzo che esiste e per uno che non
  esiste: l'endpoint non dice chi ha un account.

Il fake di collezione usato dai test unit ha imparato `insert_one` e i confronti
d'ordine (`$gte` e compagnia), che servivano alla finestra temporale.

### Security — un '*' in una variabile d'ambiente non apre piu' il CORS

`get_cors_origin_regex()` traduceva un `*` in `CORS_ORIGINS` nella regex `.*`,
e il middleware gira con `allow_credentials=True`: qualunque sito avrebbe potuto
fare richieste autenticate e **leggerne la risposta**. E' la combinazione che le
librerie normalmente vietano, ed era raggiungibile con un carattere in un file di
configurazione — cosa gia' successa una volta per far funzionare un preview
(`memory/PRD.md`, deployment run 1). La stessa PRD annotava che il codice
«scarta '*'»: era vero prima che quella funzione lo reintroducesse dall'altra
parte.

- Un `*` in `CORS_ORIGINS` viene **ignorato con un avviso** che spiega cosa
  usare al posto suo. Il servizio non si ferma e non resta aperto.
- La regex non si deriva piu' da niente: si dichiara in `CORS_ORIGIN_REGEX`.
  Serve perche' il caso vero esiste — i preview URL con prefisso casuale — e
  senza una via legittima il `*` torna.
- **Una regex che accetta anche gli estranei viene rifiutata**, perche' sarebbe
  lo stesso buco da un'altra porta. Il controllo guarda il comportamento e non
  la stringa: si prova la regex contro due origin estranei con lo stesso
  `fullmatch` che usa Starlette, cosi' cadono `.*`, `.+`, `(?s).*` e
  `https?://.*` senza doverli elencare.

Verificato durante l'audit: nessun wildcard nel `.env` di questa macchina, e
`.env` non e' mai stato committato (`git log --all` vuoto, ignorato da
`.gitignore:121`). Il buco era latente, non aperto.

### Security — il backend non va piu' dove gli dice l'utente

`POST /api/products/track` accettava un `url: str` **senza alcuna validazione** e
lo passava a `requests.get`. Il backend e' l'unica cosa che raggiunge MongoDB —
il `docker-compose` lo mette apposta su una rete interna non pubblicata — quindi
quell'URL era la strada per arrivarci, insieme a `169.254.169.254` (metadata del
cloud) e agli endpoint interni del backend stesso. Bastava un account
registrato, e la registrazione e' aperta.

Due aggravanti:

- **Non era cieca.** L'errore restituito era `f"Impossibile leggere la pagina:
  {str(e)[:120]}"`: connessione rifiutata, timeout ed errore DNS diventavano
  distinguibili, cioe' una scansione della rete interna fatta dal server.
- **Era persistente.** `scheduled_price_check` rilegge gli URL salvati a
  intervalli: bastava salvarne uno una volta perche' la richiesta venisse
  rifatta per sempre, senza l'attaccante collegato.

Ora ogni uscita passa da **`backend/url_guard.py`**: solo `http`/`https`, solo
porte 80/443, e l'host deve risolvere a indirizzi **tutti pubblici** — basta un
indirizzo privato fra quelli restituiti dal DNS per rifiutare, perche' chi
controlla il DNS puo' rispondere con uno pubblico e uno privato. Gli IPv4
mappati in IPv6 (`::ffff:127.0.0.1`) vengono ricondotti al loro IPv4 prima del
giudizio, altrimenti il loopback rientrerebbe dalla porta di servizio.

- **I redirect non sono piu' automatici.** `allow_redirects=False` e la stessa
  verifica rifatta a ogni salto: un sito che risponde 302 verso `127.0.0.1`
  aggirerebbe qualunque controllo fatto sul solo URL iniziale.
- **I messaggi non sono piu' un oracolo**: il motivo preciso resta nel log del
  server, all'utente arriva una frase sola. Distinguere «non risolve» da «e' un
  indirizzo interno» sarebbe uno strumento per mappare la rete.
- `requests` non e' piu' importato in `scraper.py`: lasciarlo li' e' un invito a
  rifare una GET diretta.

**Limite dichiarato nel modulo**: fra la risoluzione del nome e l'apertura della
connessione il DNS puo' cambiare risposta (DNS rebinding). Chiuderlo del tutto
richiede un transport adapter che si connetta all'IP verificato passando il nome
nell'header Host. Qui il costo dell'attacco si alza molto, ma la finestra resta —
ed e' meglio scritta nel codice che scoperta dopo.


### Security — l'agent non esegue piu' un binario che non ha messo lui

`Start-Fps` scaricava PresentMon in `%TEMP%\PresentMon.exe` e lo lanciava, con
un solo controllo: se il file esiste, non riscaricarlo. Quindi un file **gia'
presente** con quel nome veniva eseguito senza verifiche — e con l'agent elevato,
eseguito elevato. In `%TEMP%` scrive qualunque processo che gira come l'utente:
e' la stessa ragione per cui il backup dell'agent non sta li', scritta nei
commenti in cima allo script e mai applicata a questo caso.

- L'eseguibile vive ora in `%APPDATA%\FrameForge` accanto a backup e journal.
- Si esegue **solo** il file di cui conosciamo l'impronta, registrata da noi al
  momento del download e ricontrollata a ogni avvio: un file diverso — sostituito,
  o troncato da un download interrotto — viene rimosso e riscaricato.
- La firma Authenticode viene **raccontata ma non decide**: se una release
  uscisse non firmata, un blocco spegnerebbe la cattura FPS per tutti senza che
  nessuno capisca perche'.

Limite dichiarato nel codice: chi puo' riscrivere sia l'exe sia il file
dell'impronta puo' gia' riscrivere l'agent. La difesa che si guadagna e' contro
il file di passaggio in una cartella condivisa, che e' il caso reale.

### Fixed — lo Stop del monitor riguarda un PC, non l'account

`monitor_control` era indicizzato sul solo `user_id` mentre la telemetria era
gia' salvata per device: premere Stop per il desktop fermava **anche il
portatile**, e avviare il monitor sul portatile azzerava il flag che il desktop
stava per leggere.

E il flag non si spegneva quando l'agent lo eseguiva: lo azzerava solo
`/monitor/reset`, chiamato dalla sola pagina Live. Chi riavviava il monitor dal
link `frameforge://` copiato o dal comando manuale — due strade che la pagina
stessa offre — vedeva la finestra aprirsi e **chiudersi al primo giro**, senza
spiegazioni. Ora il segnale si spegne quando viene consegnato.

### Fixed — il gioco mostrato non era sempre quello misurato

Tre difetti distinti nella catena che porta dal monitor alla card del gioco.

- **Il rilevatore mangiava i frame.** `Get-Fps` consuma le righe nuove di
  PresentMon e sposta il segnalibro, e il ciclo del monitor lo chiamava **due
  volte**: la prima dentro `Get-CurrentGame`, che teneva solo il nome del gioco e
  buttava FPS, latenza e frametime; la seconda trovava il vuoto. Nel ramo in cui
  il rilevatore arriva a PresentMon — gioco non-Steam, o non riconosciuto a
  schermo intero, caso sistematico per chi gioca su un monitor secondario piu'
  piccolo del primario — il campione partiva con il nome del gioco e **senza una
  sola misura**. Ora si legge una volta per giro e il risultato viene passato.
- **Chi disegna di piu' non e' automaticamente un gioco.** `Get-Fps` sceglieva il
  processo con piu' frame senza alcun filtro: senza giochi aperti il vincitore
  era il browser, e finiva nel campo `game`, nella card degli FPS e fra i
  «giochi rilevati» dei trofei. La lista per escluderli esisteva gia' in due
  copie dentro gli altri rilevatori: ora e' una sola e vale anche qui. Se non
  resta nessun gioco la risposta e' «niente FPS», non «il primo processo».
- **L'istogramma cumulativo mescolava applicazioni diverse.** Serve a calcolare
  1% e 0.1% low sulla sessione, ma i frametime di un gioco e di un video non
  stanno nella stessa distribuzione: ora si azzera quando cambia l'applicazione.
- La card dichiara quando **nome e misure non vengono dallo stesso processo**:
  «Gli FPS mostrati sono di chrome, non di questo gioco».

### Changed — cosa costa un secondo di monitoraggio

- `/api/pc-telemetry` leggeva l'intero documento — fino a **1800 campioni** — per
  restituirne 60, una volta al secondo per ogni scheda Live aperta. Ora il taglio
  e' nella proiezione (`$slice`), come si fa gia' in `/devices/compare`.
- Il nome del PC per gli alert termici veniva cercato nel database **prima** di
  guardare le soglie: una query al secondo per una stringa che serve quando un
  alert scatta davvero, cioe' quasi mai.
- Indici per `monitor_control` e `alert_settings`, interrogate a ogni campione, e
  per `agent_launches`, che in piu' ora **scade da sola**. Il TTL sta su un campo
  di tipo data: su una stringa ISO un indice TTL non da' errore, semplicemente
  non cancella niente.
- La pagina Live rallenta a un sondaggio ogni 5 secondi quando il monitor e'
  fermo: una scheda dimenticata aperta faceva 3.600 richieste all'ora per non
  mostrare nulla. E l'insieme dei campioni gia' visti, che cresceva di un
  elemento al secondo senza essere mai potato, ora ha un tetto.
- Il tetto dei campioni conservati ha un nome e una spiegazione: a un campione al
  secondo sono trenta minuti, ed e' anche il limite di cio' che il Gameplay
  Doctor puo' analizzare, perche' legge da li'.


### Fixed — misurare meglio un campo non e' vederlo cambiare

Il fix sulla precisione cambia il **valore** di campi che `system_changes.py`
sorveglia. Alla prima sincronizzazione dopo l'aggiornamento, `diff_specs` avrebbe
confrontato il vecchio valore (misurato male) col nuovo (misurato bene) e
registrato un cambiamento mai avvenuto — il caso piu' comune «Refresh del
monitor: 59 → 60», perche' WMI arrotondava per difetto.

Non sarebbe stata solo una riga di troppo nella cronologia: `correlate()` incrocia
i cambiamenti con l'andamento delle prestazioni, quindi su un PC che sta andando
peggio per altri motivi il refresh sarebbe comparso **fra i sospetti**. Un dato
inventato dentro la funzione che esiste per spiegare i cali.

L'agent dichiara ora `specs_schema`, e `REMEASURED_IN` elenca per ogni versione i
campi la cui misura e' cambiata. La soppressione vale **una volta sola**, nel
passaggio fra due versioni: dal sync successivo ogni differenza torna a essere un
cambiamento vero. Un test lega i due numeri, perche' alzare lo schema senza dire
cosa e' cambiato renderebbe la protezione silenziosamente inutile.

### Fixed — un campo assente non cancella piu' un campo presente

I due percorsi che scrivono `pc_specs` avevano semantiche opposte: l'agent
sostituiva `data` in blocco, il form manuale fondeva campo per campo. La
sostituzione perdeva dati in silenzio — una scansione degradata (agent senza
privilegi, `nvidia-smi` assente, WMI che singhiozza) produce meno campi, e quei
campi non diventavano vecchi, diventavano **vuoti**: il PC aveva meno hardware di
ieri.

Ora entrambi i percorsi passano da `backend/specs_merge.py`, che ha una regola
sola: un campo assente lascia il valore precedente, e `data_meta` registra **per
campo** da quale fonte e in che momento e' stato visto l'ultima volta. Cosi'
«vecchio» e «sparito» smettono di somigliarsi. La pagina «Il mio PC» marca i
campi che l'ultimo sync non ha confermato.

- `False` e `0` sono valori, non assenze: `hvci_on = False` e
  `scan_context.admin = False` sono i casi in cui il dato conta di piu', e un
  controllo di verita' li avrebbe scartati come vuoti.
- `source` viene scritto anche dal percorso agent: prima lo scriveva solo il form
  manuale, quindi dopo un sync il documento dichiarava una provenienza non piu'
  vera.
- Prezzo dichiarato: un componente rimosso davvero resta finche' qualcosa non lo
  sovrascrive, con una data sempre piu' vecchia. E' il lato giusto del
  compromesso — `diff_specs` gia' non segnala i campi che spariscono.

### Added — le condizioni in cui la misura e' stata fatta

L'agent sapeva se girava come amministratore e se l'Integrita' della memoria
stava bloccando i sensori, ma **non lo diceva a nessuno**: lo mostrava in console
e lo passava alla GUI locale. Il backend riceveva una fotografia senza sapere se
era stata scattata al buio, e non poteva distinguere «questo PC non ha sensori»
da «l'agent girava senza privilegi» — due dati identici che significano cose
opposte.

`scan_context` porta ora admin, blocklist driver, se `nvidia-smi` ha risposto,
versione dell'agent e durata della scansione. Serve all'AI advisor per non
leggere una temperatura assente come «PC freddo», al Laboratorio per rifiutare
una baseline raccolta in condizioni diverse dal test, e soprattutto
all'aggregazione di flotta per smettere di mescolare scansioni degradate con
scansioni pulite — il punto in cui un dato sbagliato su un PC diventa una
raccomandazione sbagliata per tutti.

### Added — il pulsante sa qual e' il PC di questa postazione

`/api/pc-specs` legge il device **attivo**, che l'utente sceglie a mano e che
spesso non e' la macchina davanti a cui e' seduto: da li' veniva il caso in cui
il sync riusciva e la pagina non lo vedeva mai. Finora se ne accorgeva solo dopo
i 60 secondi di timeout.

Ogni lancio lascia ora una traccia (`agent_launches`), e il primo agent che
riporta dati per quell'utente entro dieci minuti viene legato a quel lancio. Il
browser lo memorizza in `localStorage` — che e' per-browser, cioe' per-macchina —
e dalla volta dopo mette a fuoco il device giusto **prima** di partire, dicendolo:
«Passo a DESKTOP-MIRKO, il PC di questa postazione».

Non e' una prova ma una correlazione, quindi si lega solo quando la richiesta in
attesa e' **una sola**: con due lanci aperti non si puo' dire quale abbia
risposto, e attribuirne uno a caso rifarebbe il messaggio falso che si voleva
togliere. Nell'ambiguita' si preferisce non sapere.


### Removed — una sola rilevazione hardware, non tre

`agent-build/forgefps_agent.py` aveva un `collect_specs()` / `collect_health()` /
`collect_startup()` che scriveva sugli **stessi endpoint** dello script
PowerShell servito dal backend, ma con dati piu' poveri: refresh preso dal
massimo fra i controller invece che dallo schermo primario, risoluzione dal primo
controller della lista grezza, RAM descritta dal primo modulo, nessun
`hw_confidence`, nessuna temperatura via LibreHardwareMonitor.

Quale delle due girasse dipendeva da **come** era stato avviato l'agent:

| strada | prima | ora |
|---|---|---|
| bottone «Sincronizza ora» (silent via URI) | script servito | script servito |
| doppio-click / `--mode sync` | rilevazione locale dell'exe | script servito |

Lo stesso PC scriveva due specs diverse nello stesso documento a seconda del
percorso, e nessuna delle due sapeva dell'altra — quindi le correzioni di
precisione appena fatte allo script arrivavano solo a meta' degli utenti.

- `--mode sync` passa ora da `run_ps_mode_inline()`, che esegue lo script
  **nella console corrente e aspetta che finisca**: `launch_secure_gui` e
  `launch_silent_mode` lanciano e tornano subito, quindi l'exe stamperebbe
  «Premi INVIO per chiudere» mentre lo script sta ancora partendo.
- Come effetto collaterale il sync da doppio-click ora invia anche le cose che
  solo lo script raccoglie: giochi rilevati, app in background, diagnostica dei
  sensori.
- Lo script si scarica da **un posto solo** (`_download_agent_script`): le stesse
  dieci righe stavano in due funzioni e con la mode inline sarebbero diventate
  tre copie della stessa richiesta HTTP.
- 214 righe in meno nel sorgente dell'exe.

**Nota di rilascio**: la versione dell'agent non e' stata toccata. Perche' questo
arrivi agli utenti servono i passi di release consueti — build, upload dello ZIP
e aggiornamento di `AGENT_ZIP_UPSTREAM`/`AGENT_ZIP_SHA256`, da cui
`LATEST_AGENT_VERSION` viene derivata.

Lo stesso trattamento e' andato a **`backend/desktop_agent.py`**, lo script
`.py` che la pagina «FrameForge Agent» offre in download: era la terza copia e la
piu' silenziosa, perche' nessuna schermata segnalava che quei dati fossero di
qualita' diversa. La voce 7 del menu interattivo e il nuovo `--mode sync` passano
ora dallo script servito, e anche li' il download e' uno solo invece di due.

- In entrambi gli agent `_clean` **e' rimasto**: sembrava morto insieme ai
  collector, ma nell'exe viene passato dentro `TweakContext` (e `tweaks.py` lo
  chiama una decina di volte) e nel `.py` lo usa `apply_all_tweaks`. Toglierlo
  avrebbe rotto l'applicazione dei tweak, non la rilevazione - e non al build, al
  primo click su «Applica».
- 407 righe rimosse fra i due file, 136 aggiunte.

### Fixed — risoluzione e refresh non vengono piu' da schermi diversi

Tre campi erano presi da tre insiemi diversi e nessuno li appaiava: la
**risoluzione** dal PRIMO `Win32_VideoController` della lista grezza (non
ordinata e non filtrata, quindi anche un adattatore virtuale o la iGPU mentre
`gpu` riportava la discreta), il **refresh corrente** dal MASSIMO fra tutti i
controller, il **refresh massimo** dal MASSIMO fra tutti i monitor via EDID.

Su una macchina reale con due schermi — 1920x1080 @ 240Hz primario e 2560x1440 @
165Hz secondario, **entrambi gia' al loro massimo** — il risultato memorizzato
era `refresh_hz=239` (WMI arrotonda male) e `max_refresh_hz=75` (l'EDID di quel
pannello non elenca i modi veloci). Due numeri veri di due pannelli diversi che
insieme non descrivono nessun computer esistente, e che finivano nel contesto
dell'AI advisor e nella regola che consiglia di alzare il refresh.

Ora `Get-DisplayInfo` chiede a `EnumDisplayDevices`/`EnumDisplaySettings` il modo
corrente e i modi supportati **dello stesso dispositivo**, e i campi vengono
dallo schermo **primario** — quello su cui il gioco parte. Il massimo si cerca
solo fra i modi della risoluzione attuale: un pannello che fa 240Hz a 1080p ma
144Hz a 1440p non sta andando piano se e' a 1440p. Sulla stessa macchina il
risultato e' ora `240 / 240 Hz`. Nuovi campi `monitor_count` e `monitors`.

- Il ripiego, se l'API display non risponde, usa la lista di controller **gia'
  ordinata e filtrata** e accetta il massimo EDID **solo con un monitor solo**,
  perche' con due si tornerebbe ad appaiare pannelli diversi.
- Trappola di marshalling documentata sul posto: in PowerShell `$null` passato a
  un parametro `string` diventa una stringa **vuota**, ed `EnumDisplayDevices`
  con stringa vuota fallisce. Senza `[NullString]::Value` la funzione trova zero
  schermi e il ripiego copre il buco in silenzio.

### Fixed — la RAM non si descrive piu' col primo banco

`ram_speed_mhz`, `ram_type` e `ram_manufacturer` uscivano tutti dal primo modulo.
Un kit misto — che e' esattamente il caso che vale la pena segnalare, perche'
costa prestazioni vere — veniva descritto dal banco in slot 1 e nessuno se ne
accorgeva. Ora i moduli si guardano tutti: la frequenza riportata e' quella del
**piu' lento** (che e' quella a cui gira il canale), tipi e produttori vengono
uniti, e un nuovo campo `ram_mismatch` dichiara la discordanza invece di
appianarla. La pagina lo mostra accanto alla RAM.

### Changed — `hw_confidence` dice se le fonti erano d'accordo

Era un conteggio, e un conteggio non e' una confidenza: due fonti che si
contraddicono valevano quanto due che confermano. Il conflitto veniva poi risolto
da una regola implicita — per la CPU **vinceva la stringa piu' lunga** — quindi
il disaccordo spariva senza lasciare traccia proprio nei casi in cui il dato e'
meno affidabile.

Ogni componente porta ora `{ sources, agree, conflict }`:

- **CPU**: WMI e registro confrontati dopo normalizzazione (`Intel(R) Core(TM)
  i7-12700K CPU @ 3.60GHz` e `12th Gen Intel Core i7-12700K` sono lo stesso
  pezzo di silicio). Il registro resta preferito, ma il disaccordo si vede.
- **GPU**: `nvidia-smi` confrontato con il controller WMI primario. Quando
  discordano di solito e' un portatile ibrido in cui lo schermo lo pilota la
  iGPU: chi legge le specs merita di saperlo.
- **RAM**: `$ramSources = 2  # le due fonti concordano` era un **commento**, non
  un controllo. Ora la somma delle capacita' dei moduli viene confrontata col
  totale di sistema, e se un banco non viene riportato il conto non torna.
- **Storage**: `agree` resta **nullo**, cioe' "non verificabile" — dichiararlo
  concorde senza due fonti da confrontare sarebbe la stessa bugia di prima.

Il badge nella pagina diventa rosso col dettaglio del conflitto nel tooltip, e
accetta ancora la forma vecchia (un numero) dagli agent non aggiornati, che vale
"accordo non verificato".

- Il nome della CPU viene ripulito dal padding: `ProcessorNameString` arriva
  imbottito di spazi, e quel padding finiva nella pagina, nei prompt dell'AI e
  nella chiave con cui si aggregano i PC simili della flotta.
- `cpu_clock_ghz` e' `MaxClockSpeed`, cioe' il clock **base**: scritto "3.4GHz"
  accanto al nome della CPU veniva letto come la frequenza in gioco. Ora la
  pagina scrive "3.4GHz base".

### Fixed — un sync aggiornava due pannelli su sei

«Il mio PC» monta sei pannelli che leggono dal backend **una volta sola**, al
mount, senza ricevere prop. Dopo un sync riuscito la pagina aggiornava solo la
griglia specs e quella della salute; gli altri quattro restavano fermi sui dati
di prima. L'effetto era assurdo in due casi:

- attivi XMP nel BIOS, riavvii, sincronizzi: la griglia mostra la RAM a 6000 MHz
  e **subito sotto resta il cartello «la tua RAM gira a 4800 MHz, attiva XMP»**;
- il grafico che disegna i sync non conteneva il sync appena fatto.

Un contatore `syncVersion`, alzato quando il sync arriva (e quando si cambia PC
attivo dal toast), fa da `key` a `DevicesPanel`, `DeviceCompare`,
`HwInsightsPanel`, `HealthHistoryCard`, `WhatChangedCard` e `SyncTimeline`: sono
pannelli di sola lettura senza stato da conservare, quindi il rimontaggio e' la
via onesta. L'alternativa - farli pollare ognuno per conto suo - sarebbe stata
sei sorgenti di verita' sulla stessa domanda.

### Added — il sync dice cosa e' cambiato, non solo che e' finito

«Sync completato. Dati aggiornati.» e' vero e non dice niente: chi preme il
pulsante vuole sapere se qualcosa e' cambiato, e nel caso piu' frequente - non e'
cambiato niente - restava col dubbio di aver premuto invano. Il diff fra due sync
il backend lo calcola gia' (`system_changes.py`) e lo serve su `/api/pc/changes`.

- `useSilentLaunch` ha ora `summarize`, gemello di `diagnose` sul ramo riuscito:
  il toast diventa **«Sync completato · Driver GPU: 566.36 → 572.16»**, oppure
  **«nessuna modifica rilevata dall'ultima volta»**, che e' una risposta e non un
  silenzio. Oltre due cambiamenti si contano gli altri.
- Le etichette dei campi sorvegliati passano da `WhatChangedCard` a
  `frontend/src/lib/changeLabels.js`: adesso le mostrano in due punti, e due
  mappe della stessa cosa sono due mappe che divergeranno.

### Changed — «Aggiorna» non sta piu' accanto a «Sincronizza ora»

Nella stessa barra c'erano due pulsanti con la **stessa icona** `RefreshCw`: uno
accende l'agent e impegna il PC per un minuto, l'altro rilegge il database in un
istante. Non c'era modo di indovinare quale fosse quale, e chi voleva dati nuovi
premeva quello sbagliato la meta' delle volte. Il ricarica manuale si sposta
accanto alla riga «Ultimo sync: 3 min fa», dove il suo significato si capisce da
solo; l'icona di aggiornamento resta a un pulsante solo.

### Fixed — «Sincronizza ora» smette di dare la colpa al token

Il pulsante lancia l'agent via `frameforge://` e poi fa polling su
`/api/pc-specs` cercando un `updated_at` diverso. Ma `/api/pc-specs` legge il
**device attivo** (quello scelto nel pannello PC), mentre l'agent scrive sul PC
**su cui gira**: se non coincidono il sync riesce, la pagina non lo vede mai, e
dopo 60 secondi l'utente legge «il token locale e' disallineato». Scenario
normale per chi ha desktop + laptop, cioe' proprio chi paga per il multi-PC.

- Alla scadenza il pulsante ora **confronta le specs di tutti i PC**
  (`/api/devices/compare` -> `specs_updated_at`) contro una fotografia presa al
  click. Se il sync e' arrivato altrove lo dice con i nomi dei due PC e offre il
  rimedio nel toast: «Passa a DESKTOP-MIRKO», che chiama `/activate` e ricarica.
- Se invece non si e' mosso niente, il messaggio **elenca le cause plausibili**
  invece di sceglierne una: non installato, versione vecchia, token di un altro
  account. Se i PC collegati hanno saturato il limite del piano lo aggiunge, che
  e' il caso in cui `resolve_device` risponde 402 e l'agent muore in silenzio.
- Il fallimento della richiesta a `/agent/launch-uri` non e' piu' lo stesso
  messaggio: li' la richiesta non e' nemmeno uscita dal browser, e parlare del
  token dell'agent significa accusare una macchina non interrogata.
- Il messaggio dice **«entro 60 secondi»** invece di «non risponde»: il primo e'
  un fatto, il secondo un'impressione. Il numero viene dalla stessa costante che
  fa da timeout, ora dichiarata una volta sola.

### Fixed — il badge di freschezza parlava italiano anche in inglese

`useAutoSync` passava quattro etichette vuote per non mostrare toast, ma l'hook
le risolveva con `labels.starting || "Avvio in corso..."` e `""` in JavaScript
e' falso: chiedere silenzio restituiva i default **hardcoded in italiano**. Il
badge e il pulsante fanno la stessa cosa e rispondevano in modo diverso, uno dei
due nella lingua sbagliata. Ora la risoluzione usa `??` (una stringa vuota resta
silenzio, per chi la vuole davvero) e le etichette stanno in
`frontend/src/lib/syncLabels.js`, da cui pescano entrambi i punti di lancio.

- Tre stringhe della pagina «Il mio PC» (`services_done`, `services_show_ok`,
  `services_hide_ok`) esistevano **solo in italiano**: aggiunte in inglese. Le
  ha trovate il test nuovo, non una segnalazione.

### Removed — euristiche e impalcature che non facevano niente

- L'«app non installata» si deduceva dal fatto che la tab non perdesse mai il
  focus. Il ramo `if` era **vuoto** in `useSilentLaunch` e alzava un flag che
  nessuno leggeva in `OneClickLaunchButton`, mentre il JSDoc prometteva un hint
  dopo 3 secondi che non e' mai esistito: si aspettavano comunque i 60 secondi
  pieni. E il segnale era anche invertito, perche' in modalita' `silent=1`
  l'agent non prende **mai** il focus: acceso com'era, avrebbe detto «non
  installato» proprio quando funzionava.
- In `useAutoSync` restava l'impalcatura dei trigger automatici spenti in
  v0.7.4: il debounce `canAutoSync()` definito e mai chiamato, il timestamp
  dell'ultimo idle scritto in localStorage e mai riletto «per potenziali future
  analytics», le costanti che li taravano.
- `error` e l'etichetta `notInstalled` di `useSilentLaunch`: scritti a ogni
  timeout, non letti da nessun chiamante.

### Changed — si puo' annullare, e si sonda meno

- Il toast «in corso» ha un bottone **Annulla**: prima il pulsante restava
  disabilitato fino a 60 secondi anche a chi aveva gia' capito che non sarebbe
  partito. E' lo stesso `cancel` esposto dall'hook, cosi' non ci sono due strade
  che mostrano due toast diversi.
- Sondaggio ogni 2s per i primi 12s, poi ogni 4s: un'attesa piena passa da ~30 a
  ~18 richieste, senza rendere piu' lenta la rilevazione nel caso normale.

### Fixed — l'Auto-Pilot non applica piu' tweak che aspettano un riavvio

L'Auto-Pilot misura la salute, applica ogni tweak `safe` non ancora attivo,
aspetta **due secondi** e rimisura. Quattro tweak del lotto hanno effetto solo
dopo il riavvio — `mpo`, `gpu_msi`, `timer`, `nic_power` — e venivano comunque
applicati, contati fra gli `applied` e spediti a `/api/autopilot/agent/result`
dentro un confronto prima/dopo in cui **non erano ancora attivi**.

- Il rapporto sottostimava proprio i tweak di latenza: quelli che avrebbero
  potuto guadagnare qualcosa erano gli unici a non poterlo mostrare.
- L'utente restava con un riavvio in sospeso che nessuno gli aveva detto: il
  Laboratorio ha `Invoke-LabRebootPrompt` apposta, l'Auto-Pilot non aveva nulla.
- `gpu_msi` scrive nel ramo Interrupt Management della GPU — la modifica piu'
  pesante del catalogo — e partiva senza una domanda, perche' la scala binaria
  dell'agent non aveva un gradino fra 'safe' e 'caution'.

Il filtro ora e' `requires_reboot`, non il rischio: sono due cose diverse, e il
campo esiste gia' nel catalogo per tutti e 35 i tweak. I quattro esclusi
vengono **elencati a fine corsa** — «richiedono un riavvio e restano fuori:
... Applicali dalla GUI quando puoi riavviare» — perche' un tweak che sparisce
senza una riga e' un tweak che l'utente crede applicato.

- **La GUI non indovina piu' il riavvio dalla prosa.** `needsReboot()` cercava
  `richiede riavvio` dentro `desc`/`impact`/`problem`/`reason`: funzionava per
  coincidenza, e da quella regex dipendono il filtro «No riavvio», la pillola
  del tempo, il conteggio del riepilogo e il dialogo finale col bottone
  «Riavvia ora». Riscrivere un `impact` in «serve un riavvio» li avrebbe spenti
  tutti in silenzio. Ora il DTO porta `requires_reboot` e la GUI lo preferisce,
  con la regex come ripiego per gli agent che non inviano ancora il campo.
- Nel merge dei metadati il booleano **non passa dall'interpolazione**: in
  PowerShell `[bool]'False'` e' `$true`, quindi un campo booleano reso stringa
  sarebbe vero per sempre e il filtro avrebbe escluso tutti i tweak.

### Fixed — il bottone del Gameplay Doctor nomina un tweak che esiste

`gui_tweak` e' l'unico campo del referto scelto dal modello che diventa poi un
comando nell'interfaccia, e non lo validava nessuno: l'id finiva nel referto
salvato e da li' sull'etichetta del bottone. Un id inventato, o rimasto indietro
dopo una rinomina, veniva mostrato all'utente com'era.

- Il backend risolve ogni `gui_tweak` contro il catalogo, **sia in scrittura sia
  in lettura**: riaprire un referto vecchio non rimette in pagina un bottone che
  mente. Un id sconosciuto diventa `null` e il bottone non viene disegnato — il
  consiglio testuale resta, la promessa che non si puo' mantenere no. La chiave
  resta sempre presente, quindi la forma del referto non cambia.
- Il referto porta ora anche `gui_tweak_name`, e il bottone mostra **il nome del
  tweak invece dell'id**: «Applica in GUI: Piano energetico prestazioni massime»
  al posto di «Applica in GUI: power». Vale anche per le alternative, dove l'id
  compariva fra parentesi quadre. Il nome e' quello del catalogo, in italiano
  anche in inglese: e' gia' cosi' che la pagina Profili elenca i tweak.
- **Resta aperto**: il click apre comunque la GUI generica in modalita'
  `optimize`, perche' `onApply` scarta il proprio argomento e
  `/agent/launch-uri` accetta solo `mode` e `silent`. Ora l'etichetta e' vera e
  il tweak esiste, ma non viene pre-selezionato. La meccanica per farlo c'e'
  gia' (`$script:PROFILE` / `__PROFILE_IDS__`); manca il pezzo nell'URI firmato,
  che ha un vincolo di retrocompatibilita' sull'HMAC `mode|ts`.

### Changed — un catalogo dei tweak, non quattro

Nome, categoria, rischio e testi di ogni tweak vivevano in **quattro elenchi
scritti a mano**: `$script:TWEAKS` nell'agent PowerShell, `TWEAK_CATALOG` in
`routers/profiles.py`, `TWEAKS` in `lab_registry.py` e `_GD_GUI_TWEAKS` dentro
la stringa di prompt del Gameplay Doctor. Aggiungere un tweak voleva dire
ricordarsene in quattro posti, e il quarto era quello che nessuno ricordava.

Erano gia' divergenti, e non in modo innocuo:

- il prompt del Gameplay Doctor descriveva `debloat` come «Debloat servizi»
  mentre l'apply rimuove **app UWP**: il consiglio dato all'utente non era la
  cosa che il bottone esegue;
- lo stesso prompt conosceva **15 tweak su 35**, e fra i 20 assenti c'erano
  `gpu_msi`, `standby_clear`, `power_throttling` e `nic_power` — cioe' proprio i
  tweak per micro-stutter e latenza DPC, che sono due delle diagnosi che quel
  prompt deve produrre. Diagnosi corretta, fix non proponibile;
- `lab_registry` chiamava `gaming` «Boost gaming (Game Mode, Game DVR off)»
  mentre l'apply attiva **anche HAGS**;
- `mpo`, `dns`, `search_index` e `standby_clear` avevano nomi diversi fra web e
  agent.

Ora il catalogo e' **`backend/tweak_catalog.py`** e i quattro consumatori lo
derivano. In PowerShell restano gli `id` e i soli blocchi eseguibili — `fit`,
`plan`, `state`, `apply` — perche' sono codice che interroga la macchina, non
testo; i metadati vengono iniettati in `PS_SCRIPT` all'import, come si faceva
gia' con `agent_gui.html`. I valori che l'agent riceve sono **identici a prima**,
verificati confrontando il catalogo fuso in PowerShell con quello precedente.

- **Il rischio e la spunta predefinita non sono piu' la stessa cosa.** L'agent
  usava `caution` per decidere tre cose insieme (colore della card, spunta
  iniziale, ammissione all'Auto-Pilot) mentre il Lab ragionava su una scala a
  quattro livelli, e le due scale erano in disaccordo su `mpo`, `gpu_msi` e
  `timer`. Ora `risk` sta sulla scala del Lab e la spunta ha il suo campo,
  `default_on`; `agent_risk()` ricostruisce la stringa binaria per la GUI, che
  non si accorge di niente.
- **Un livello di rischio sconosciuto non e' piu' il piu' sicuro.**
  `_RISK_ORDER.get(x, 0)` faceva passare per `safe` qualunque valore non
  previsto: un errore di battitura promuoveva il tweak invece di fermarlo. Ora
  il registro si rifiuta di caricarsi e `/api/lab/registry` risponde 422 invece
  di trattare un livello inventato come `medium`.
- **`requires` dichiara l'hardware necessario** invece di nasconderlo in un
  predicato Python, e vale sia per il Lab sia come documentazione. Conseguenza
  voluta: **SysMain non viene piu' proposto dal Lab a chi non ha un SSD**, come
  gia' faceva l'agent per conto suo — prima il Lab poteva sceglierlo e l'agent
  applicarlo lo stesso, perche' il percorso del Lab non consulta `fit`. Il
  registro passa a **1.2.0** proprio perche' la selezione puo' cambiare.
- Un requisito **non verificabile** non fa piu' scartare il tweak: se le
  `pc_specs` non elencano i dischi, l'assenza del dato non e' la prova che non
  ci sia un SSD. Fa eccezione il produttore della GPU, dove restare prudenti era
  gia' la regola.
- `tests_unit/test_tweak_catalog.py` impedisce il ritorno del copia-incolla: gli
  id dell'agent devono essere quelli del catalogo, l'array PowerShell non deve
  tornare a contenere `name=` o `risk=`, e i preset dell'agent e i template dei
  profili non possono citare tweak che non esistono.

### Fixed — la GUI non si rompe piu' sugli array di un elemento
- `ConvertTo-Json` (PS 5.1) serializza un array di UN elemento come scalare:
  `@('x')` diventa `"x"`, non `["x"]`. La Diagnosi chiamava `.some` sul piano di
  un tweak e si rompeva al primo avvio su una macchina con un tweak che tocca una
  chiave sola. Lo stesso valeva per il journal alla prima sessione, per un passo
  fallito solo e per chi ha un solo profilo cloud — a volte con un errore, a
  volte peggio: `.length` di un oggetto e' `undefined`, quindi "1 passo non
  riuscito" diventava "nessun problema".
- La normalizzazione (`lista()`) sta ora alle cinque porte d'ingresso — stato,
  risultato di un lavoro, job, journal, profili — invece che ai quaranta punti
  d'uso. Un test vieta il modo di scrivere che ha causato il guasto:
  `(x || []).map` non protegge da niente, perche' se `x` e' un oggetto il `||`
  non scatta.
- **L'harness di test ora collassa gli array di un elemento come PowerShell.**
  Un mock che manda sempre array veri non poteva vedere questo difetto: la GUI
  passava tutte le prove e si rompeva sul primo PC.

## [0.9.1] — 2026-08-24

### Changed — versione dell'agent, per portare in campo la rilevazione unica

L'exe non ha piu' un `collect_specs()` suo: `--mode sync` e la voce 7 del menu
delegano allo script servito dal backend, che e' l'unico posto in cui la
rilevazione viene mantenuta. Finche' il pacchetto pubblicato resta alla 0.9.0,
chi avvia l'agent dall'icona continua a scrivere specs di qualita' diversa da
chi preme il pulsante nella dashboard.

**La correzione di sicurezza su PresentMon non e' in questo pacchetto, e non ne
ha bisogno**: vive in `backend/ps_agent.py`, cioe' nello script PowerShell che
l'exe riscarica a ogni lancio. Quella arriva agli utenti con il **deploy del
backend**, non con questa release.

- Le note di release del workflow non sono piu' inchiodate alla v0.7.8: usano il
  tag e ricordano il passo successivo, cioe' aggiornare `AGENT_ZIP_UPSTREAM` e
  `AGENT_ZIP_SHA256`. `LATEST_AGENT_VERSION` e' derivata dall'URL, quindi
  finche' non si aggiorna quello il self-updater degli agent gia' installati
  continua a vedere la versione precedente e nessuno riceve il pacchetto nuovo.
- Backend e pagina Download puntano al pacchetto `v0.9.1`. Lo SHA256 non e'
  stato copiato dalle note della release: l'allegato pubblicato e' stato
  scaricato e l'impronta ricalcolata, perche' e' l'unico controllo di integrita'
  fra una release e le macchine degli utenti finche' l'eseguibile non e' firmato
  — e con l'hash sbagliato il backend rifiuta di distribuire il pacchetto e la
  pagina Download smette di funzionare, com'e' successo con la 0.9.0.

## [0.9.0] — 2026-08-22

### Fixed — un tweak che fallisce in silenzio non risulta piu' applicato
- **L'esito di un tweak si verifica guardando la macchina, non gli errori.** Lo
  script gira con `$ErrorActionPreference = 'SilentlyContinue'` dalla prima riga
  e non puo' non girarci — meta' delle sonde interroga cose che su molti PC non
  esistono. Il prezzo era che un tweak che non scriveva niente (permessi negati,
  chiave protetta, criterio di dominio) risultava applicato esattamente come uno
  riuscito, e finiva cosi' nel journal, nel riepilogo e nel conteggio. Ora, dopo
  l'apply, si **rilegge il piano**: le righe che dovevano cambiare devono
  risultare a posto.
  - Nessuna delle modifiche previste risulta scritta &rarr; **il tweak e'
    fallito**, con il motivo, e le chiavi di backup appena create vengono
    rimosse: il backup deve contenere solo cio' che e' stato davvero cambiato,
    altrimenti "Annulla" rimette valori che nessuno ha toccato.
  - Alcune si' e altre no &rarr; **applicato in parte**, che non e' un
    fallimento (qualcosa e' passato ed e' annullabile) e non e' un successo
    pieno: passo giallo nella schermata di lavoro, riga gialla nel Journal con
    l'elenco di cosa non e' passato, e riepilogo che li conta separati.
  - Quello che il piano non sa rileggere (powercfg, netsh, fsutil) resta **non
    verificabile** e non viene spacciato per verificato: il journal registra
    quante modifiche erano controllabili.
- Il test statico fra piano e apply ora confronta anche i **valori**, non solo
  le chiavi: da quando la verifica si basa sul piano, un valore sbagliato li'
  farebbe dichiarare fallito un tweak riuscito.

### Changed — nessun lavoro gira piu' dentro la richiesta
- `/api/apply-one`, `/api/restore-one`, `/api/restore` e
  `/api/bloatware/remove` diventano job a passi come `/api/apply`: rimettere
  tutto com'era puo' voler dire venti tweak e servizi da riavviare,
  `Remove-AppxPackage` ci mette secondi per app, e applicare un tweak solo puo'
  comunque scandire tutte le schede di rete. Tutti mostrano la schermata di
  lavoro, tutti rimbalzano con `409` se ce n'e' gia' uno in corso.
- **Anche la rimozione di una app si verifica guardando**: `Remove-AppxPackage`
  non alza la voce quando non riesce, quindi si ricontrolla se la app c'e'
  ancora invece di contare i tentativi. Una che non si lascia rimuovere lo dice.
- I passi si costruiscono in un posto solo (`New-TweakStep`, `New-RevertStep`,
  `New-StateStep`) e il client avvia i lavori in un posto solo (`runJob`):
  applicare un tweak da `/api/apply` e applicarlo da `/api/apply-one` facevano
  cose leggermente diverse, e la differenza non la voleva nessuno.

### Fixed — un solo backup e un solo journal per tutti e due gli agent
- L'.exe Python teneva il proprio backup **accanto all'eseguibile**: se l'exe e'
  in Program Files quella cartella non e' scrivibile, se sta in Download
  sparisce col primo riordino, e ogni reinstallazione ci passa sopra. Era il
  file piu' fragile del prodotto, e serve ad annullare le modifiche.
- Ed era un **secondo** backup: i due motori hanno cataloghi di tweak diversi
  (`tcp-nagle-off` di qua, `network` di la') ma scrivono le stesse chiavi di
  registro nello stesso formato, in due file che non si parlavano. "Ripristina"
  da riga di comando non annullava quello che aveva fatto la finestra, e
  viceversa. Ora e' lo stesso `%APPDATA%\FrameForge\backup.json`, e un
  ripristino solo rimette tutto.
- I backup vecchi vengono **fusi** nel condiviso invece che abbandonati, e
  cancellati solo dopo che il nuovo e' stato scritto. I metadati dell'altro
  motore (`__tweak_keys__`, `__applied_at__`) sopravvivono al giro: senza,
  sparirebbe la possibilita' di annullare un singolo tweak dalla finestra.
- Il ripristino da CLI **non tratta piu' i metadati come chiavi di registro**:
  finivano nel ramo generico e producevano comandi `reg add` su percorsi
  inventati, che fallivano in silenzio.
- **Anche la riga di comando scrive nel journal condiviso**, con l'esito vero
  del Recipe System (applicato / applicato ma non verificato / fallito) invece
  di un totale, e con `via: cli` — la schermata Journal marca quelle righe,
  altrimenti sembrerebbe che la finestra abbia fatto cose che non ha fatto.
- Resta separato quello che non si puo' unire con un rename: **due cataloghi di
  tweak e due motori di apply**. Lo stesso `--mode apply-one` passa dal motore
  Python da riga di comando e da quello PowerShell dai bottoni della dashboard.
  E' una scelta di architettura, non un bug da correggere di lato.

### Added — Diagnosi: il risultato prima del catalogo
- **La schermata di partenza non e' piu' il catalogo dei tweak.** Era un
  pannello con le checkbox: giusto per chi vuole controllo, servito al 90% di
  gente che vuole un bottone. Ora la prima cosa e' cosa c'e' da sistemare su
  questo PC, con il diff gia' visibile riga per riga, un solo primario
  **"Ottimizza"** e il catalogo dietro **"Personalizza"**.
- **Il punteggio misura una cosa sola e la schermata la scrive per intero**:
  quanta parte delle ottimizzazioni che FrameForge sa fare e' gia' attiva qui,
  pesata per l'impatto che ogni tweak dichiara. Non e' un voto alla macchina, e
  non finge di esserlo — un numero che promette piu' di quello che misura e'
  esattamente la promessa dei "booster" da cui questo prodotto vuole
  distinguersi. La legenda mostra i conteggi da cui esce, e i tweak non
  applicabili a questo PC restano fuori dal calcolo, ne' come merito ne' come
  colpa.
- **Nessuna percentuale aggregata inventata.** Sommare le stime dichiarate di
  dodici tweak e stampare "+11% FPS" in cima e' precisione finta: gli effetti
  non si sommano e quel numero non lo puo' controllare nessuno. La stima resta
  accanto a ogni singolo tweak, dove si puo' valutare. **L'unico numero grande
  e' quello misurato**: il benchmark prima/dopo dell'ultima volta — che ora
  viene scritto anche nel journal, non solo spedito al cloud, quindi sul PC ne
  resta traccia (`104 → 113, +9%`).
- **Chi ha bisogno dei privilegi di amministratore si deduce dai piani**: le
  righe che scrivono in `HKLM` o sui servizi lo dicono da sole, quindi l'avviso
  conta le modifiche vere invece di dire "alcune". Una lista scritta a mano si
  sarebbe disallineata al primo tweak nuovo.
- **Il bottone unico non decide sui tweak marcati "cautela"**: restano fuori,
  nominati sotto, e si applicano da Personalizza. Un click solo puo' fare le
  cose sicure, non le scelte.
- Con niente da sistemare la schermata lo dice ("Non ho trovato niente da
  sistemare") invece di sembrare rotta.

### Added — ogni tweak dice cosa cambia, non cosa fa
- **Il piano di un tweak**: tutti e 35 i tweak dichiarano ora, chiave per
  chiave, cosa cambierebbe su **questa** macchina — `Game Mode: 0 → 1`,
  `MouseSpeed: 1 → 0`, `Schema energetico: Bilanciato → Prestazioni eccellenti`.
  Una descrizione vale per tutti i PC, un piano vale per questo: "disattiva
  l'accelerazione del mouse" e "MouseSpeed: 1 → 0" dicono la stessa cosa, ma
  solo la seconda si puo' controllare — e chi accetta che un programma gli
  scriva nel registro ha diritto di controllare prima, non dopo. Dove il piano
  c'e', prende il posto della riga "Modifica" nella scheda.
- **Il valore attuale non si dichiara mai: si legge.** `PlReg` interroga il
  registro al momento; `PlSvc` chiede lo stato del servizio. Dichiarare il
  "prima" vorrebbe dire scrivere nel piano quello che ci si aspetta di trovare,
  che e' il modo in cui un diff comincia a mentire. Dove il valore non si legge
  a buon mercato (powercfg, fsutil, chiavi sparse su tutte le schede di rete) il
  "prima" manca e si mostra solo il "dopo", invece di inventarlo.
- **Le righe che non cambiano niente lo dicono.** Lo stato di un tweak lo decide
  una chiave sola, ma il tweak ne scrive parecchie: senza questo il piano
  prometteva `0 → 0`. Ora quelle righe restano visibili — fanno vedere tutta
  l'impronta del tweak — ma sono marcate "gia a posto" e non si contano fra le
  modifiche.
- **Un test statico tiene il piano legato all'apply**: per ogni `Set-Reg` con
  argomenti risolvibili dentro le funzioni di apply, il test verifica che ci sia
  la riga corrispondente nel piano, e viceversa dove l'apply e' interamente
  statica. Un piano che promette qualcosa di diverso da quello che l'apply fa
  sarebbe peggio di nessun piano. Ha gia' trovato un percorso di registro
  sbagliato in `priority`.
- **Il piano si calcola solo per i tweak da applicare**: per uno gia' ottimale
  sarebbe una lista vuota pagata con decine di letture del registro; per uno non
  applicabile una promessa che non si mantiene.
- In lista compatta la scheda mostra una riga sola (la prima modifica piu' il
  conteggio delle altre); la tabella completa compare espandendo.

### Added — il lavoro in corso e' una schermata, e si puo' fermare
- **Schermata di lavoro a tutta finestra** mentre l'agent applica: elenco dei
  passi con l'esito di ciascuno (fatto, in corso, saltato, **non riuscito col
  motivo**), barra a una tacca per passo, log dal vivo accanto. Prima l'unico
  segno che stesse succedendo qualcosa erano due bottoni disabilitati e un
  riquadro di log alto 140px in fondo alla finestra. E' una modalita', non una
  scheda: prende la finestra finche' dura e la restituisce quando finisce.
- **Il job espone i propri passi** (`GET /api/job` porta `steps[]` con
  `state` per indice, non solo `step`/`total`): e' quello che permette di
  mostrare una lista invece di una percentuale, e di dire QUALE passo non e'
  riuscito mentre gli altri andavano avanti. La percentuale di un lavoro fatto
  di pezzi disuguali — due benchmark da 40s e dieci tweak da mezzo secondo — e'
  un numero che si inventa.
- **`POST /api/job/cancel`: "Ferma qui".** Non interrompe il passo in corso —
  interrompere a meta' una scrittura nel registro sarebbe il modo peggiore di
  dare il controllo all'utente — ma alza una bandiera che il loop legge fra un
  passo e l'altro. I passi rimasti si saltano; **i passi di chiusura no**: il
  backup viene salvato e lo stato riletto, perche' fermarsi non deve voler dire
  uscire con il registro modificato e nessun modo di tornare indietro. Il
  benchmark DOPO invece si salta: misurare un'ottimizzazione fermata a meta'
  produce un confronto che non descrive niente.
- **Un lavoro fermato non si chiama finito**: lo stato del job diventa
  `cancelled`, e il riepilogo dice "Fermato a meta'" contando applicati,
  saltati e non riusciti separatamente.
- **La schermata compare anche se non e' stata questa pagina ad avviare il
  lavoro** (finestra ricaricata a ottimizzazione in corso).
- **Gli errori si vedono dentro il log verde**: le righe `[ERR ]` e `[STOP]`
  sono rosse. Un errore dentro un muro di verde e' un errore che non si vede.

### Added — Journal: cosa FrameForge ha cambiato su questo PC
- **I dati dell'undo non stanno piu' in `%TEMP%`.** Backup e journal vivono in
  `%APPDATA%\FrameForge\` (dove sta gia' `token.dat`). `%TEMP%` lo svuota
  Windows, lo svuotano i "pulitori" e — soprattutto — lo cancella
  ricorsivamente `Do-Cleanup`, cioe' il tweak **"Pulizia temp" di questo stesso
  agent**: bastava sceglierlo per ultimo perche' l'agent cancellasse il proprio
  backup, e un backup cancellato non e' un file perso, e' un PC che non torna
  piu' indietro. I percorsi vecchi vengono letti finche' esistono e cancellati
  solo *dopo* che il nuovo backup e' stato scritto.
- **Nuovo `%APPDATA%\FrameForge\journal.jsonl`**: un evento per riga, aggiunto
  in coda, mai riscritto. Il file di backup e' una fotografia del presente —
  quali chiavi sono modificate adesso — e non sa raccontare cosa e' successo: un
  tweak annullato ne sparisce, uno fallito non ci e' mai entrato. Il log della
  GUI quella storia ce l'aveva, ma viveva in memoria e moriva con la finestra.
  Il journal registra applicazioni, **fallimenti** e annullamenti, con il valore
  precedente e quello nuovo di ogni chiave toccata. Una riga corrotta costa
  quella riga, non il file; un journal che non si scrive non ferma
  un'ottimizzazione.
- **Valori in chiaro invece che in formato di serializzazione**: `__ABSENT__`
  diventa "non esisteva", `String|1` diventa `1`, e il GUID del piano energetico
  diventa il suo nome (`Bilanciato → Prestazioni elevate`). Dove il valore
  attuale non si rilegge a buon mercato manca del tutto, e la GUI mostra solo il
  prima: meglio una meta' vera che una freccia inventata.
- **La scheda "Cosa ho cambiato" diventa "Journal"**, raggruppata per sessione,
  con il diff per riga e **Annulla per riga**. Ogni giro di ottimizzazione e'
  una sessione, annullabile in blocco con **"Annulla la sessione"** (nuovo
  `POST /api/revert-session`, che gira come job a passi come `/api/apply`).
  Quattro forme distinte per una riga: applicata e ancora attiva, gia'
  annullata, annullamento, non riuscita ("nessuna chiave e' stata scritta").
- **Cosa e' ancora annullabile lo decide il backup, non il journal**: il journal
  e' cronologia e non cambia, il backup e' lo stato di adesso. Senza
  quell'incrocio un tweak gia' annullato continuerebbe a offrire "Annulla".
- **Rimosso `GET /api/changes`**, che ricostruiva la cronologia dal solo file di
  backup: `GET /api/journal` la serve per sessioni, ed e' l'unica fonte.

### Changed — la GUI dell'agent non si blocca piu' mentre applica
- **`/api/apply` registra un job e risponde subito** (`202`) invece di fare tutto
  il lavoro dentro la richiesta. Il server locale della GUI e' un `HttpListener`
  a thread singolo: finche' benchmark PRIMA, N tweak, benchmark DOPO e invio dati
  giravano dentro la POST, per tutti quei minuti **nessun'altra richiesta veniva
  servita**. La GUI continuava a chiedere `/api/log` ogni 400 ms senza ricevere
  risposta, quindi mostrava un log fermo e nessun avanzamento proprio mentre
  l'agent scriveva nel registro. Anche il flag `applying` era inutile: nessuno
  poteva leggerlo mentre valeva `true`.
- **Il loop del listener esegue un passo per giro**, e fra un passo e l'altro
  serve le richieste. La granularita' e' il singolo tweak, quindi il log non puo'
  restare indietro piu' di un passo. Tutto resta nello stesso runspace: i passi
  vedono `$script:BK` e le funzioni del motore come prima, senza runspace
  paralleli da risincronizzare.
- **Nuovo `GET /api/job`**: passo corrente, `n/totale`, percentuale ed elenco dei
  passi falliti. Il log dice cosa e' successo, non a che punto e': il bottone
  "Applica" ora mostra `Nome del tweak · 3/12` mentre lavora.
- **Un passo che fallisce non ferma gli altri ma non sparisce piu'**: finisce nel
  log come `[ERR ]` e in `job.errors`, e il riepilogo finale conta i tweak
  riusciti ("Applicati in parte") invece di dichiarare applicato tutto quello che
  era stato chiesto. Prima, con `$ErrorActionPreference = 'SilentlyContinue'`, un
  tweak fallito era indistinguibile da uno riuscito.
- **I passi lenti vengono annunciati un giro prima di partire** (tetto 1,5 s),
  altrimenti la riga "Benchmark PRIMA in corso..." arriverebbe alla GUI solo a
  misura finita, cioe' quando non serve piu'.
- **Il backup viene scritto dopo ogni tweak**, non piu' solo a fine giro: ora il
  lavoro e' interrompibile, e un tweak applicato con sul disco il backup di prima
  sarebbe un tweak non piu' annullabile. Per lo stesso motivo il loop **non esce
  finche' un job e' in corso**, nemmeno se la finestra viene chiusa: meglio
  finire i passi rimasti parlando a nessuno che lasciare il registro a meta'.
- **Due apply in parallelo non si sovrappongono**: il secondo riceve `409 busy`
  invece di partire e mangiarsi il backup del primo.

### Changed — precisione delle misure (Lab v2, `metrics_version: 2`)
- **Schema appaiato ABBA** come default del test loop: invece di tre run col tweak
  attivo confrontati con un blocco di baseline misurato minuti prima, si alternano
  coppie ON/OFF (`on,off,off,on,on,off`) e si analizzano le differenze interne a
  ogni coppia. La deriva comune — temperatura, scena, shader cache — si cancella
  invece di finire nel confronto. Decisione su `paired_t_test` + IC di Welch sulle
  differenze. `POST /api/lab/start` accetta `paired: false` per tornare allo schema
  a blocchi, che resta l'unica strada per i tweak che richiedono un riavvio.
  Nuove azioni agent: `pair_toggle`, `run_pair`, `rollback_tweaks`.
- **Percentili dall'istogramma dei frametime**: l'agent invia un istogramma a 306
  bucket a risoluzione variabile (0.1 ms sotto i 20 ms), il backend somma gli
  istogrammi del blocco e ne ricava i percentili. `fps_p1` non e' piu' la media dei
  p99 per-run — la media di percentili non e' un percentile — ma la media dell'1%
  peggiore dei frame dell'intero blocco.
- **Correzione Holm applicata, non annotata**: i tweak mantenuti che non reggono la
  correzione per test multipli vengono ora davvero annullati sul PC prima della
  validazione finale (stato sessione `rollback`).
- **Baseline coerente**: dopo un tweak mantenuto avanzano sia le statistiche sia i
  run di riferimento. Prima il p-value guardava la baseline iniziale mentre il
  delta guardava quella aggiornata: due domande diverse nello stesso verdetto.
- **Guardie sulle condizioni di misura**: run rifiutati e ripetuti se presi a
  batteria, su un gioco diverso o con troppi pochi frame; avvisi su risoluzione,
  refresh, piano energetico e OBS cambiati rispetto alla baseline. Ogni run porta
  con se' il proprio contesto.
- **Frame cap / V-Sync rilevato sulla baseline**: con un limite attivo ogni tweak e'
  ininfluente per costruzione, e il Lab lo dice invece di produrre dieci "nessun
  effetto" che sembrano un risultato.
- **Bersaglio bloccato**: i frametime vengono letti solo dal processo del gioco
  rilevato (nome + PID). Prima si prendeva a ogni tick l'app con piu' present, e un
  overlay poteva infilare i propri frame nel campione.
- **Telemetria del run campionata** ogni 5s (media e massimo) invece di
  un'istantanea presa alla fine; `nvidia-smi` gira una volta sola scrivendo su file
  invece di essere rilanciato a ogni campione. CPU dai contatori di prestazione
  invece di `Win32_Processor.LoadPercentage`, anche nella telemetria live.
- **Benchmark rapido**: `dpc_ms` non ha mai misurato le DPC — e' l'oversleep del
  timer, ora esposto come `timer_jitter_ms`, affiancato dal tempo in DPC vero letto
  dai contatori raw (`dpc_time_pct`). CPU misurata a priorita' alta con un giro di
  riscaldamento scartato e 5 ripetizioni, con il carico di fondo registrato; disco
  testato sul drive dei giochi con 1000 operazioni e la profondita' di coda
  dichiarata; ping su 20 campioni con perdita, p95 e jitter RFC 3550. `score_version: 2`.
- **Aggregato di flotta**: tetto di 3 contributi per utente e tweak (prima un solo
  utente che rilanciava il Lab dieci volte pesava dieci volte), `delta_sq_sum` per
  poter dare una dispersione accanto alla media, breakdown per gioco, intervalli di
  Wilson sui tassi di successo e nessun contributo dalle sessioni con frame cap.
- **Casi degeneri**: con varianza campionaria nulla i t-test restituivano `p = 0`,
  cioe' certezza assoluta da manciate di numeri identici. Ora ricadono sul p esatto
  del test dei segni (appaiato) e sul minimo di un test di permutazione (Welch).

## [0.6.5] — 2026-07-19

### Added
- **Persistenza diagnosi**: nuovo `GET /api/advisor/diagnose/latest` + `useEffect` mount in `DiagnosePanel` che ripesca l'ultima diagnosi. Badge "generata Xh fa" con timestamp tooltip.
- **Feedback thumbs 👍/👎** su diagnosi actions + chat messages via `POST /api/advisor/feedback` (target_type/target_id/action_title/rating/comment). Upsert idempotente.
- **Applied Tweaks (personalization memory)**: `POST /api/advisor/applied-tweaks` toggle + `GET` list. Slug generato dal titolo. `_get_user_profile()` passa la lista all'AI come contesto.
- **Community insights (RAG-lite)**: `_community_insights()` aggrega top 5 tweak applicati da utenti con hardware CPU/GPU simile (via Counter dei titoli) → iniettati nel prompt come esempi few-shot.
- **Verify hint**: nuovo campo obbligatorio `verify` in ogni action della diagnosi. Frontend: sezione espandibile "Come verificare se è già attivo" con testo mono-space.
- **Outcome tracking**: `GET /api/advisor/outcome` calcola delta benchmark tra il momento dell'ultima diagnosi e il primo benchmark successivo. Badge visualizzato nel header della diagnosi.
- **Chat multi-modale (vision)**: `stream_advisor` accetta `image_data_url` (data URL base64). Se presente → `UserMessage(text=..., file_contents=[ImageContent(image_base64=...)])`. Frontend: paperclip button, preview con X, salvato nella bolla del messaggio user.
- **Coach modes**: 5 personas (default/fps/streaming/troubleshoot/build) via `COACH_PROMPTS` che appende un suffix al system prompt. Frontend: dropdown in cima chat, preferenza in `localStorage.advisor_mode`.
- **Follow-up chips**: `POST /api/advisor/followups?session_id=` + `ai_engine.generate_followups()` che chiede all'AI 3 domande brevi contestuali. Frontend: chip cliccabili sotto l'ultima risposta AI.
- **Message actions**: thumbs, copia (clipboard API + Check animation), rigenera (rimuove ultima bolla AI e re-invia ultima query utente). Compaiono in hover.
- **Auto-detect release announcer** ora funziona anche in prod: rimosso hardcode env, check `HOSTNAME.startswith("agent-env-")`.

### Fixed
- **Compilazione DiagnosePanel**: `CheckCircle2` non era stato aggiunto agli import (search_replace fallito silenziosamente). Fix applicato manualmente.

### Changed
- Nuove collezioni Mongo: `ai_feedback`, `applied_tweaks`, `diagnoses` (già presente).

## [0.6.4] — 2026-07-19
  - Nuovo endpoint `POST /api/advisor/diagnose` che chiama Claude Sonnet in modalità one-shot con schema JSON strutturato → ritorna `{summary, actions: [{title, description, impact, difficulty, kind, cta, priority}]}`.
  - Nuovo modulo `ai_engine.one_shot_advisor()` per invocazioni singole con context PC completo (no chat history).
  - Nuovo helper `_enrich_specs_for_ai()` in `routers/advisor.py`: arricchisce le specs con benchmark_history (ultimi 5) e tracker_summary (count + total_saved). Anche `advisor_chat` beneficia del context arricchito.
  - `pc_context_text()` in `helpers.py` estesa con sezioni `[TREND BENCH]` (delta % tra ultimo e primo benchmark degli ultimi 5) e `[TRACKER]` (numero prodotti + risparmio totale).
  - CRUD `/api/advisor/planned-actions` (GET list / POST create / POST done / DELETE) per la todo list "Salva per dopo".
  - Frontend: `<DiagnosePanel>` componente riutilizzabile in cima a `/app/advisor` con stati idle/loading/done/error, big button "Diagnosi PC AI", card risultati con azioni prioritizzate, badge difficoltà colorato (facile/medio/avanzato), impatto in verde, CTA "Apri agent"/"Pulisci disco ora" + "Salva per dopo" con toast conferma.
  - Empty state se PC non connesso → CTA "Connetti il PC →".
- **Discord — comandi mini-guida**:
  - `/help` completamente riscritto con embed rich (Onboarding · Gaming · Creator · Admin · Link utili).
  - Nuovi `/come-iniziare` (3 step onboarding), `/ruoli` (Boosted PC, Pro, Creator Verified, Staff), `/canali` (mappa canali).
- **Discord — flusso `/apply-creator`**:
  - Slash command con validazione URL (twitch.tv, youtube.com, youtu.be, kick.com).
  - View persistente `CreatorReviewView` con bottoni ✅ Approva / ❌ Rifiuta (custom_id fissi → sopravvive ai restart).
  - Cooldown 7 giorni dopo un rifiuto (configurabile via `DISCORD_CREATOR_REAPPLY_DAYS`).
  - Anti-doppio submit (max 1 pending per utente).
  - DM automatico all'utente con esito (approvazione: ruolo assegnato + link; rifiuto: cooldown days).
  - Embed originale aggiornato con colore verde/rosso e nota "APPROVATA/RIFIUTATA da @staff".
  - Nuove env: `DISCORD_ROLE_CREATOR_VERIFIED`, `DISCORD_CHANNEL_CREATOR_REVIEW`.
- **Sync automatico ruolo Boosted PC**:
  - Il periodic task nel bot Discord (già usato per Pro) ora sync anche il ruolo Boosted per tutti gli utenti con `discord_user_id` in DB → ruolo assegnato retroattivamente se OAuth flow ha fallito.
  - Refactor: nuovi helper `_sync_role()` (generico) + `_sync_all_roles_for_member()` (Boosted + Pro insieme).
- **`/set-plan` admin command** con `defer(ephemeral=True)` per evitare timeout Discord 3s.
- **`/announce-release <version> [force]`** admin command per forzare l'annuncio di una release. Nuovo helper `announce_release_by_version()` in `services/release_announcer.py`.
- **Auto-detect ambiente per release announcer**: check `HOSTNAME.startswith("agent-env-")` → in preview skippa automatico, in prod parte. Override manuale con `RELEASE_ANNOUNCER_ENABLED=true/false`.

### Fixed
- **CORS wildcard bloccante**: `settings.get_cors_origins()` filtrava `"*"` producendo lista vuota. Nuovo `get_cors_origin_regex()` usa `allow_origin_regex=".*"` compatibile con `allow_credentials=True`.
- **Email footer**: sostituita `hello@forgefps.dev` (non attiva) con `forgefps.support@gmail.com`. Al click ora copia negli appunti + toast Sonner "Email copiata".
- **Query non ottimizzate**: `/api/stats` ora fetcha solo 2 field da products; `/api/products/{id}` limita history a 200 record (era 1000).

### Changed
- Nuove collezioni Mongo: `diagnoses` (snapshot delle diagnosi AI), `planned_actions` (todo list utente), `creator_applications` (pipeline verifica creator).

## [0.6.3] — 2026-07-18
  - Nuovo componente riutilizzabile `FooterExtras.jsx` (`FooterCommunity` + `FooterLegal`) usato sia in `Landing.jsx` (5 colonne: Brand · Product · Community · Account · con legal row) sia in `MarketingChrome.jsx` (4 colonne).
  - **Discord** con badge live "🟢 XX online adesso" — dot verde pulsante — via `GET /api/discord/live-stats` (cache in-memory 5 min, fallback silenzioso se widget server non abilitato).
  - **GitHub** repo link + **Report a bug** (deep-link a `/issues/new/choose`) + email `hello@forgefps.dev`.
  - **Guida** aggiunta alla colonna Product (era invisibile).
- **Endpoint `GET /api/discord/live-stats` (pubblico, no auth)** in `backend/routers/discord.py`:
  - Chiama `https://discord.com/api/guilds/{DISCORD_GUILD_ID}/widget.json`.
  - Cache in-memory 5 min per limitare rate-limit.
  - Ritorna sempre 200: `{enabled, presence_count, invite_url, instant_invite, name}` — `enabled=false` se widget non attivo.
- **Nuova pagina `/terms`** (`Terms.jsx`): Termini di servizio con 9 sezioni bilingue IT/EN (Cos'è FrameForge, Account & sicurezza, Uso agent, Contenuti AI, Uso accettabile, Prezzi, Limitazione responsabilità, Modifiche termini, Contatti). Route lazy in `App.js`.
- **Legal row nel footer**:
  - Copyright "© 2026 FrameForge — Tutti i diritti riservati"
  - Link a Cookie policy (`/privacy-telemetry#cookies`), Terms of service (`/terms`), Privacy (`/privacy-telemetry`)
  - Firma discreta "Costruito con ❤️ da un gamer per gamer" (bilingue).
- **Env var `DISCORD_INVITE_URL`** letta da `/api/discord/status` e restituita al frontend → il bottone "Apri il server" nella Dashboard usa ora il link reale.
- **Feature flag `RELEASE_ANNOUNCER_ENABLED`** in `services/release_announcer.py`: default OFF in preview per evitare duplicati Discord tra preview e produzione. In prod si abilita via Custom Keys del pannello Deployments Emergent.
- **Chiave i18n `landing.nav_guide`** (IT: "Guida" / EN: "Guide") — mancava nonostante la route /guida esistesse.

### Fixed
- **Dashboard → "Apri il server" invito Discord non valido**: il link era hardcoded a `discord.gg/frameforge` (placeholder). Ora `Dashboard.jsx` legge `discord.invite_url` dallo status endpoint con fallback al vero invito permanente.
- **Duplicati changelog Discord**: preview e produzione avevano lo stesso `DISCORD_WEBHOOK_CHANGELOG` ma DB Mongo separati → l'idempotency `announced_releases` non copriva l'altro ambiente. Fix: flag `RELEASE_ANNOUNCER_ENABLED` con default OFF; solo la produzione (che imposta `=true` via Custom Keys) annuncerà.

### Changed
- **Rimozione hardcode `RELEASE_ANNOUNCER_ENABLED` dal `.env`**: il file `.env` è shared tra preview e prod, quindi il flag va gestito solo via Custom Keys del pannello Deployments (prod-only).

## [0.6.2] — 2026-07-18
  - Layout 2 colonne (main + sticky panel), coerente con `/app/desktop` e le altre tool pages.
  - **PC Hero card**: HealthRing grande con score 0-100 e grade colorato (verde/giallo/rosso), badge hardware CPU/GPU/RAM, contatori issue/warn, CTA "Ottimizza ora" con colore adattivo (rossa se score<55, gialla altrimenti). Se PC non connesso → empty state con CTA "Connetti il PC →".
  - **Benchmark card**: score latest, delta % vs precedente (verde/rosso), `Sparkline` degli ultimi 8 benchmark, bottone "Condividi su Discord" attivo solo se Discord linkato (chiama `POST /api/discord/share-score`).
  - **Activity Feed unificato**: merge cronologico di price drops (`/api/notifications`), ultimo benchmark, nuova release agent (mostrata solo se `localStorage.ff_agent_seen_v0.6.0` è false). Ordinato desc, top 6, con relative time.
  - **Recent Products** compatto con empty state migliorato.
  - **Sticky panel a destra**: `OnboardingChecklist` (5 step: Connect PC, First benchmark, Track a product, Link Discord, Enable 2FA — con checkmark verde, strikethrough, progress bar animata gradient volt→green; auto-hide a 5/5), `QuickActionsCard` (griglia 2×3 con Advisor/Agent/Games/Tracker/Builds/Network), `DiscordCard` (linked → avatar + username + link server; unlinked → CTA "Link account (30s)"), `AgentCard` (solo se nuova versione non ancora cliccata: badge NEW + CTA Download).
  - **Greeting contestuale**: "Ciao, {name} — Il tuo PC è a {score}/100" (se health disponibile), oppure "Hai risparmiato {saved}€" (se total_saved>0), oppure "Pronto a boostare il PC?" (fallback).
  - **Empty state hero**: `HeroEmpty` con 3 CTA giganti numerate (Fai il primo scan, Genera una build, Traccia un prodotto) mostrato solo se l'utente è brand new (no specs, no products, no builds, no chat sessions).
  - i18n: aggiunte ~45 chiavi sotto `dashboard.*` (IT + EN).
- **Preview GUI Edge nella sticky card `/app/desktop`**:
  - Nuovo componente `AgentPreview.jsx` con fallback a 3 livelli: `<video>` → `<img>` GIF → mock CSS animato.
  - Probe HEAD iniziale al `.mp4` per evitare flash: se non esiste va diretto al GIF.
  - GIF reale (1.9MB) caricata in `/app/frontend/public/assets/agent-preview.gif`.
  - Mock fallback CSS: finestra "FrameForge Agent" con title bar macOS-style, tab sidebar Gaming/Latenza/Rete/Sistema, 6 tweak con badge "GIÀ ATTIVO" a cascata, progress bar arcobaleno.
  - Badge overlay "LIVE GUI PREVIEW" con dot pulsante top-left, aspect 16:10.

### Changed
- **`/app/dashboard`**: layout completamente riprogettato (120 → 743 righe di codice). Le vecchie 4 stat card di base (tracked/builds/chats/saved) sono state sostituite dai widget dinamici sopra descritti.

## [0.6.1] — 2026-07-18
- **Redesign coerente `/app/commands` e `/app/bios-restore`** con lo stesso pattern sticky panel di DesktopAgent:
  - **Comandi Utili**: barra di ricerca fuzzy in tempo reale, filter chips (`Solo sicuri` / `Solo admin` / `Solo avanzati`), contatore "visibili/totali", hardware rilevato compact, jump-to categorie con badge count. Empty state se filtri non producono match.
  - **BIOS e Ripristino**: tabs BIOS/Restore spostati nel panel destro, hardware detected compatto, jump-to sezioni con pallino colorato + count, box "regola d'oro" compatto sempre visibile.
  - Layout `grid lg:grid-cols-[1fr_320px]`: contenuto scrollabile a sinistra, panel sticky a destra su desktop, stacking verticale su mobile.
- **Layout sticky action panel** in `/app/agent`: pannello destro con download button + versione + SHA256 + comando exe sempre visibili anche scrollando. Feature grid spostata in cima come value proposition. Metodo PowerShell ora in accordion collassato. Backend notice mostrato solo su preview (nascosto in prod). Su mobile il layout stacka in verticale (nessun impatto UX).
- **Integrazione Discord completa (A + B + C)**:
  - **A) Server community template**: `docs/DISCORD_SERVER_SETUP.md` con struttura 7 categorie/20 canali, 6 ruoli, testi regole/welcome, config bot moderazione (Dyno/YAGPDB), server onboarding con 3 domande, obiettivi Server Boost e Vanity URL.
  - **B) Bot Discord persistente (`discord.py 2.7.1`)**: worker `backend/discord_bot.py` gestito da supervisor come processo separato dal FastAPI. 5 slash commands sincronizzati nel guild: `/mypc` (Health Score), `/benchmark` (ultimo bench), `/leaderboard` (top 10), `/link` (istruzioni collegamento), `/help`. Handler `on_member_join` con welcome DM + auto-role Boosted PC.
  - **B2) OAuth2 account linking (`identify guilds.join`)**: `backend/routers/discord.py` con `/connect` (redirect Discord), `/callback` (state CSRF con TTL 10 min, exchange code, guilds.join, assign role opzionale), `/status`, `/disconnect`. Salva `discord_user_id`, `discord_username`, `discord_avatar`, `discord_linked_at` nel documento utente.
  - **C) Outbound webhooks**: `backend/services/discord_webhooks.py` con `post_release(version, notes_md)`, `post_price_drop(product, old, new)`, `post_milestone(text, subtitle)`, `post_raw()`. Colori brand FrameForge (`#E5FF00`, `#00E0FF`, `#00FF66`).
  - **Frontend**: nuova card "Discord" in `/app/account` con stato collegato/scollegato, avatar + username, pulsanti "Collega Discord" (colore Discord `#5865F2`) e "Scollega". Success banner al ritorno dal callback OAuth. Stringhe i18n IT/EN dedicate (chiave `account.discord_*`).
  - **Supervisor**: nuovo program `discord-bot` in `/etc/supervisor/conf.d/discord-bot.conf` (autostart, autorestart, log dedicati).
- **Pagina Guida in-app (`/guida`, `/guide` → redirect)** — 5 walkthrough step-by-step con:
  - Primo boost in 3 minuti · Setup gaming competitivo · Setup streaming OBS · Leggere il benchmark 0-100 · Se qualcosa va storto
  - Ogni step marcato con badge "Sul sito" / "Sul PC" e comando PowerShell copiabile con feedback visivo
  - TOC iniziale, sezione Tips per guida, CTA finale verso login / download agent, tempo stimato in minuti
  - Bilingue IT/EN via i18n
  - Aggiunto link "Guida" nella `MarketingNav` e route lazy in `App.js`
- **Tour interattivo di onboarding (react-joyride v3.2.0)**:
  - 8 step: Il mio PC, Advisor, Rete, Agent desktop, Giochi, Notifiche, chiusura
  - Auto-start al primo atterraggio su `/app` (localStorage flag `ff_tour_done_v1`)
  - Skippabile, personalizzato con palette FrameForge (accent `#E5FF00`, tooltip dark `#0F0F12`)
  - Pulsante "Rifammi il tour" nella pagina Account (`data-testid="restart-tour-btn"`) che azzera il flag e dispatcha evento globale `ff:tour:start`
  - Stringhe i18n IT/EN dedicate (chiave `tour.*`)
- **GUI moderna via Edge WebView (Option C)** — nuovo pannello ottimizzazioni in HTML/CSS/JS servito localmente:
  - Server HTTP locale su `127.0.0.1` con **porta random** e **session token da 48 caratteri** per ogni request
  - Lancio di `msedge.exe --app=` in modalità chromeless (finestra pulita, no barra Edge)
  - UI dark responsive con animazioni CSS, ricerca tweak, categorie a tab
  - Card interattive con Problema/Motivo/Modifica/Impatto per ogni tweak
  - Bottone "Applica" singolo per ogni tweak + preset chip (Competitivo/Streaming/Completo/Nessuno)
  - Log console live via polling (400 ms), toast di conferma, indicatore backup real-time
  - Fallback automatico a **WinForms GUI** (legacy) se Edge non installato
  - Isolation: profilo Edge dedicato in `%TEMP%\forgefps-gui\edge-profile`
- **UX "GIÀ ATTIVO" per tweak già ottimizzati**:
  - Card con barra verde e opacità ridotta (72% → 100% al hover)
  - Pill outline verde "GIÀ ATTIVO" nell'header della card
  - Pulsante "Applica" sostituito da "*Nessuna azione necessaria*"
  - Tab counter mostra `da_fare/totali` (es. `Gaming 3/10`)
  - Preset (Competitivo/Streaming/Completo) saltano automaticamente i tweak già attivi
- Workflow GitHub Actions **senza SignPath** (`agent-build/github-workflow-build-nosign.yml`) — build + release automatica dell'exe unsigned finché SignPath Foundation non è approvata.

### Fixed
- **Edge process detection**: il launcher `msedge.exe` esce subito se c'è già un'istanza Edge attiva → `-PassThru` restituiva un process già terminato → listener chiuso prima che Edge caricasse la pagina (`ERR_CONNECTION_REFUSED`). Fix: recupero del process reale via WMI `Win32_Process` filtrando per `--user-data-dir` custom.
- **Safety net inactivity timeout**: se il process Edge non è rilevabile, uscita automatica dopo 30s di inattività.
- **URL locale stampato in console** prima di lanciare Edge: se la finestra non si apre l'utente può incollare l'URL in qualunque browser.
- **Regex `stateClass`**: aggiunto pattern "nessun" per riconoscere anche stati tipo "Nessuna app in avvio".

### Changed
- Landing page — KPI "tweak reali" allineato al catalogo effettivo: **26 → 35** (IT + EN).
- `frontend/src/config/agent.js` — puntamento a release **v0.6.0**:
  - URL: `https://github.com/WjRKO/ForgeFPS/releases/download/v0.6.0/forgefps-agent.exe`
  - SHA256: `18645e38ef463cb7a1e9afff40e2194416518589be080840654b4dc9aed45a1c`
  - Data: `2026-07-18`
- Branch `optimize` del PowerShell agent — prova prima `Show-WebGui`, poi fallback a `Show-Gui` (WinForms).

### Docs
- Aggiunta guida rapida push GitHub con branch dedicato (evita "Changes conflict detected" su `main`).

---

## [0.6.0] — 2026-07-17

### Added
- **Adaptive Boost Engine** — 35 tweak si adattano dinamicamente all'hardware rilevato:
  - Rilevamento laptop vs desktop (chassis type WMI), RAM installata, tipo disco (SSD/HDD/NVMe), GPU brand (NVIDIA/AMD/Intel)
  - Ogni tweak espone un `fit` block che decide `ok`/`warn`/`skip` in base al profilo hardware (es. `nvidia_tel` skippato su GPU AMD, `sysmain` disattivato solo su SSD, `paging_exec` solo con ≥16 GB RAM)
  - Preset "Competitivo", "Streaming", "Completo" ora rispettano i vincoli hardware
- **Game Booster (opt-in, real-time)**:
  - Il PS agent monitora l'avvio di processi gioco (whitelist configurabile)
  - Quando parte un gioco: **sospende** processi non essenziali in background (Chrome, Discord update, OneDrive, ecc.) tramite `NtSuspendProcess`
  - Alla chiusura del gioco: **riprende automaticamente** tutti i processi sospesi
  - Sempre opt-in: l'utente decide dalla pagina `/games` se attivarlo per titolo (nessun automatismo)
- **Benchmark Avanzato (0-100 score)**:
  - Misura **latenza DPC** (via performance counters + timer resolution sampling)
  - **Disk IOPS reali** (test 4K random R/W su file temp)
  - **Network jitter** (100 ping su target Cloudflare)
  - **CPU responsiveness** (context switch rate)
  - Punteggio composito 0-100 con formula ponderata
  - **Spiegazione AI** dei risultati via Claude Sonnet 4.5 (endpoint `POST /api/benchmark/explain`)
- Standalone Python `.exe` (PyInstaller) aggiornato a v0.6.0 con lo stesso Adaptive Boost + Game Booster + Benchmark del PS script.
- Metadati exe (`version_info.txt`) → riduce falsi positivi AV.
- Guide: `REBUILD_v0.6.0.md`, `SIGNING_AND_TRUST.md`, `SIGNPATH_SETUP.md`, `CODE_SIGNING_POLICY.md`.

### Changed
- Frontend: pagine `Games.jsx`, `MyPc.jsx`, `DesktopAgent.jsx` aggiornate per esporre le nuove feature.
- Backend DB schema: nuove collection `prematch_settings`, `benchmarks`, `benchmark_explanations`.

---

## [0.5.x] — precedenti

- AI Advisor (Claude) per ottimizzazioni PC context-aware
- Price Tracker multi-store (Amazon, Newegg, ecc.)
- Telemetria PC live (CPU/GPU/RAM/temp)
- Health Score storico
- MFA (TOTP), RBAC, rate limiting
- Landing page marketing, sistema profili per gioco
- Report PDF (base), Report BIOS-restore
