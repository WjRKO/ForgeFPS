# -*- coding: utf-8 -*-
"""Il catalogo dei tweak: uno, e solo uno.

Fino alla v0.9.0 lo stesso catalogo esisteva in quattro copie scritte a mano:
`$script:TWEAKS` nell'agent PowerShell (35 voci, le uniche con apply/rollback
reali), `TWEAK_CATALOG` in routers/profiles.py (35 voci, id+nome+categoria),
`TWEAKS` in lab_registry.py (15 voci, i tweak che il Laboratorio misura) e
`_GD_GUI_TWEAKS` in routers/advisor.py (15 voci dentro una stringa di prompt).

Quattro copie di un elenco che nessuno aggiorna tutto insieme derivano, e
avevano gia' derivato: il prompt del Gameplay Doctor descriveva `debloat` come
"Debloat servizi" mentre l'apply rimuove app UWP, e non conosceva ne' `gpu_msi`
ne' `standby_clear` — cioe' proprio i due tweak per micro-stutter e latenza DPC,
gli unici pertinenti alle diagnosi che quel prompt deve produrre.

Qui vive il dato; altrove vive il comportamento. Restano in PowerShell solo i
blocchi eseguibili di ogni tweak — `fit`, `plan`, `state`, `apply` — perche'
sono codice che interroga la macchina, non testo: l'agent li tiene accanto a un
`id` e riceve tutto il resto da qui, iniettato in `PS_SCRIPT` all'import.

--- I campi -----------------------------------------------------------------

`risk` sta sulla scala a quattro livelli (safe|medium|expert|hardware) che usa
il Laboratorio. L'agent ne usava una a due (safe|caution) per decidere tre cose
diverse: il colore della card, la spunta iniziale e l'ammissione all'Auto-Pilot.
Quelle tre cose sono una proprieta' sola e non sono il rischio, quindi hanno un
campo loro, `default_on`; `agent_risk()` ricostruisce la vecchia stringa binaria
per la GUI, che continua a ragionare per 'caution' senza sapere di derivarla.

`lab_prior` a None significa "il Laboratorio non misura questo tweak": e' il
criterio che separa i 15 dai 35, prima implicito nell'esistenza di una riga in
lab_registry.py. Con `why`, `conflicts_with` e `synergy_candidates` completa i
metadati di cui il motore di selezione ha bisogno.

`requires` dichiara l'hardware necessario invece di nasconderlo in un
predicato: lab_registry lo traduce in una funzione, l'agent ha gia' il suo
`fit` che dice la stessa cosa all'utente con parole sue.

I testi sono in ASCII senza apostrofi perche' finiscono nella console
PowerShell; `name` fa eccezione e porta gli accenti (lo legge il web), che
`_fold()` toglie sulla via dell'agent.
"""
import unicodedata

CATALOG_VERSION = "1.0.0"

TWEAKS = [
    {
        "id": "power", "cat": "gaming", "risk": "safe", "default_on": True,
        "name": "Piano energetico prestazioni massime",
        "family": "power", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows usa un piano energetico bilanciato che rallenta CPU/GPU e parcheggia i core per risparmiare.",
        "reason": "Con il core parking e il throttling la CPU non gira mai al 100% quando serve, causando cali di FPS e stutter.",
        "desc": "Attiva Ultimate/High Performance, disattiva core parking, processore al 100%, USB suspend e PCIe ASPM off.",
        "impact": "+3-8% FPS medi e 1% low piu stabili, meno micro-stutter. Consuma piu energia (irrilevante su desktop).",
        "lab_prior": 0.35, "conflicts_with": [], "synergy_candidates": ["power_throttling"],
        "why": "Core parking e throttling limitano la CPU nei momenti di picco.",
    },
    {
        "id": "gaming", "cat": "gaming", "risk": "safe", "default_on": True,
        "name": "Boost gaming (Game Mode, HAGS, Game DVR off)",
        "family": "scheduling", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Game DVR registra in background e la GPU scheduling hardware potrebbe essere disattivata.",
        "reason": "Il Game DVR ruba CPU/GPU durante il gioco; HAGS riduce la latenza di pianificazione dei frame.",
        "desc": "Attiva Game Mode + Hardware GPU Scheduling, disattiva Game DVR/registrazione in background.",
        "impact": "+2-5% FPS e frametime piu costante, meno overhead durante il gioco.",
        "lab_prior": 0.24, "conflicts_with": [], "synergy_candidates": ["priority"],
        "why": "Il Game DVR ruba CPU/GPU registrando in background.",
    },
    {
        "id": "priority", "cat": "gaming", "risk": "safe", "default_on": True,
        "name": "Priorità GPU/CPU ai giochi (MMCSS)",
        "family": "scheduling", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows assegna le stesse risorse ai processi in background e al gioco in primo piano.",
        "reason": "MMCSS/SystemResponsiveness a 0 da priorita reale ai task multimediali e ai giochi attivi.",
        "desc": "Imposta SystemResponsiveness=0 e priorita GPU/CPU ai giochi in primo piano.",
        "impact": "Frametime piu regolare, meno spike quando ci sono app in background.",
        "lab_prior": 0.25, "conflicts_with": [], "synergy_candidates": ["gaming"],
        "why": "SystemResponsiveness=0 da priorita reale al gioco in primo piano.",
    },
    {
        "id": "mpo", "cat": "gaming", "risk": "medium", "default_on": True,
        "name": "Disabilita MPO (Multi-Plane Overlay)",
        "family": "display", "requires_reboot": True, "reversible": "auto",
        "requires": None,
        "problem": "Il Multi-Plane Overlay causa flickering, stutter e SCHERMO NERO in OBS Game Capture.",
        "reason": "MPO ha bug noti con molti driver: interferisce con la cattura schermo e il DWM.",
        "desc": "Imposta OverlayTestMode=5 per disattivare MPO nel Desktop Window Manager.",
        "impact": "Elimina flickering/schermo nero in OBS, meno stutter sul desktop. Richiede riavvio.",
        "lab_prior": 0.18, "conflicts_with": [], "synergy_candidates": [],
        "why": "MPO causa stutter/flickering su molte GPU, specie con OBS attivo.",
    },
    {
        "id": "gpu_msi", "cat": "gaming", "risk": "medium", "default_on": True,
        "name": "GPU: MSI mode ON (latenza DPC)",
        "family": "gpu_vendor", "requires_reboot": True, "reversible": "auto",
        "requires": None,
        "problem": "La GPU usa interrupt line-based, che aumentano la latenza DPC e causano micro-stutter.",
        "reason": "I Message Signaled Interrupts (MSI) riducono la latenza di interrupt della GPU.",
        "desc": "Attiva MSISupported=1 nel ramo Interrupt Management della GPU (NVIDIA/AMD).",
        "impact": "Latenza DPC piu bassa, input piu reattivo. Richiede riavvio.",
        "lab_prior": 0.16, "conflicts_with": [], "synergy_candidates": [],
        "why": "Message Signaled Interrupts riducono la latenza DPC della GPU.",
    },
    {
        "id": "amd_ulps", "cat": "gaming", "risk": "safe", "default_on": True,
        "name": "AMD: disabilita ULPS",
        "family": "gpu_vendor", "requires_reboot": False, "reversible": "auto",
        "requires": {"gpu_vendor": "AMD"},
        "problem": "Le Radeon abbassano troppo il clock in idle (Ultra Low Power State), causando stutter.",
        "reason": "ULPS mette la GPU in stato a bassissimo consumo, con risvegli lenti che generano scatti.",
        "desc": "Disattiva ULPS nelle chiavi di registro AMD (solo GPU AMD).",
        "impact": "Meno stutter e latenza su schede AMD, clock piu stabile.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "nvidia_tel", "cat": "gaming", "risk": "safe", "default_on": True,
        "name": "NVIDIA: disabilita telemetria",
        "family": "gpu_vendor", "requires_reboot": False, "reversible": "auto",
        "requires": {"gpu_vendor": "NVIDIA"},
        "problem": "I driver NVIDIA installano task/servizi di telemetria che girano in background.",
        "reason": "La telemetria consuma CPU e rete senza alcun beneficio per il gaming.",
        "desc": "Disattiva i task pianificati e il servizio di telemetria NVIDIA (solo GPU NVIDIA).",
        "impact": "Meno processi in background, CPU leggermente piu libera.",
        "lab_prior": 0.12, "conflicts_with": [], "synergy_candidates": [],
        "why": "Task e servizi di telemetria NVIDIA girano in background.",
    },
    {
        "id": "hibernate", "cat": "gaming", "risk": "medium", "default_on": False,
        "name": "Disabilita ibernazione",
        "family": "power", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Il file hiberfil.sys occupa diversi GB di disco anche se non usi mai la sospensione.",
        "reason": "Su desktop l ibernazione e raramente usata; il file pesa quanto la RAM installata.",
        "desc": "Esegue powercfg -h off per rimuovere hiberfil.sys (reversibile con -h on).",
        "impact": "Libera 4-32 GB su disco. Perdi la sospensione ibrida/avvio rapido.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "mouse", "cat": "input", "risk": "safe", "default_on": True,
        "name": "Accelerazione mouse OFF (raw input)",
        "family": "input", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "L Enhance Pointer Precision di Windows accelera il mouse in modo imprevedibile.",
        "reason": "L accelerazione rende la mira incoerente: lo stesso movimento fisico da spostamenti diversi.",
        "desc": "Disattiva MouseSpeed/Threshold per un input 1:1 (raw).",
        "impact": "Mira piu precisa e costante negli sparatutto. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "timer", "cat": "input", "risk": "medium", "default_on": True,
        "name": "Timer resolution globale",
        "family": "scheduling", "requires_reboot": True, "reversible": "auto",
        "requires": None,
        "problem": "Su Windows 11 la timer resolution puo essere variabile, con scheduling meno preciso.",
        "reason": "Una timer resolution alta e costante rende piu regolari i frametime e la latenza.",
        "desc": "Attiva GlobalTimerResolutionRequests=1 (richiesta timer globale).",
        "impact": "Frametime piu costante, meno stutter. Richiede riavvio.",
        "lab_prior": 0.14, "conflicts_with": [], "synergy_candidates": [],
        "why": "Timer a bassa risoluzione producono frametime piu' costanti.",
    },
    {
        "id": "usb", "cat": "input", "risk": "safe", "default_on": True,
        "name": "USB power management OFF",
        "family": "input", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows sospende le porte USB per risparmiare energia, causando cali di polling.",
        "reason": "Se il mouse/tastiera vanno in standby, si hanno input drop e micro-freeze.",
        "desc": "Disattiva il risparmio energetico sui controller USB.",
        "impact": "Input di mouse/tastiera piu stabile, niente drop. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "stickykeys", "cat": "input", "risk": "safe", "default_on": True,
        "name": "Sticky/Filter/Toggle Keys OFF",
        "family": "input", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Premendo Shift ripetutamente compare il popup delle Sticky Keys che ti butta fuori dal gioco.",
        "reason": "Le funzioni di accessibilita tastiera si attivano per errore durante il gioco.",
        "desc": "Disattiva Sticky/Filter/Toggle Keys.",
        "impact": "Niente piu popup che rubano il focus in game. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "startupdelay", "cat": "input", "risk": "safe", "default_on": True,
        "name": "Startup delay app ridotto",
        "family": "shell", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows ritarda artificialmente l avvio delle app in autostart.",
        "reason": "Il delay serve a non sovraccaricare l avvio, ma rallenta l accesso al desktop utile.",
        "desc": "Imposta StartupDelayInMSec=0 per avviare subito le app.",
        "impact": "Desktop e app pronti prima dopo l accensione. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "network", "cat": "network", "risk": "safe", "default_on": True,
        "name": "Rete: Nagle OFF + TCP tuning",
        "family": "network", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "L algoritmo di Nagle accumula piccoli pacchetti, aggiungendo latenza nei giochi online.",
        "reason": "I giochi inviano tanti pacchetti piccoli: Nagle li ritarda, aumentando il ping percepito.",
        "desc": "Disattiva Nagle sulla scheda attiva e regola autotuning/ECN/RSS.",
        "impact": "Ping piu basso e stabile online. Reversibile con Ripristina.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "dns", "cat": "network", "risk": "safe", "default_on": True,
        "name": "DNS veloci (Cloudflare 1.1.1.1)",
        "family": "network", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "I DNS del provider sono spesso lenti e possono rallentare la risoluzione dei domini.",
        "reason": "DNS piu veloci riducono i tempi di connessione a server di gioco e matchmaking.",
        "desc": "Imposta 1.1.1.1 / 1.0.0.1 sulla scheda attiva (reversibile a DHCP).",
        "impact": "Connessioni piu rapide. Reversibile in un click.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "qos", "cat": "network", "risk": "safe", "default_on": True,
        "name": "Rimuovi 20% banda riservata QoS",
        "family": "network", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows riserva fino al 20% della banda per il QoS di sistema.",
        "reason": "Recuperando quella banda hai piu throughput reale per download e streaming.",
        "desc": "Imposta NonBestEffortLimit=0.",
        "impact": "Piu banda disponibile per gioco/stream. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "deliveryopt", "cat": "network", "risk": "safe", "default_on": True,
        "name": "Delivery Optimization P2P OFF",
        "family": "network", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows usa la tua banda in upload per distribuire aggiornamenti ad altri PC (P2P).",
        "reason": "Durante lo streaming quell upload occupa banda e destabilizza il bitrate.",
        "desc": "Imposta DODownloadMode=0 (nessun P2P).",
        "impact": "Upload piu libero, stream piu stabile. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "obs_priority", "cat": "network", "risk": "safe", "default_on": True,
        "name": "OBS ad alta priorità",
        "family": "capture", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "OBS gira a priorita normale e puo perdere frame in encoding sotto carico.",
        "reason": "Alzando la priorita CPU di OBS l encoding resta fluido anche con la CPU occupata dal gioco.",
        "desc": "Imposta CpuPriorityClass alta per obs64/obs32.exe (via Image File Execution Options).",
        "impact": "Meno frame persi in registrazione/stream. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "clean", "cat": "system", "risk": "safe", "default_on": True,
        "name": "Pulizia temp + cache Windows Update",
        "family": "storage", "requires_reboot": False, "reversible": "none",
        "requires": None,
        "problem": "File temporanei e cache degli aggiornamenti si accumulano e occupano spazio.",
        "reason": "Ripulire libera disco e puo velocizzare alcune operazioni di sistema.",
        "desc": "Rimuove temp utente/sistema, cache Windows Update e svuota il DNS.",
        "impact": "Libera spazio su disco. Nessun file personale toccato.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "visual", "cat": "system", "risk": "safe", "default_on": True,
        "name": "Effetti visivi: modalità prestazioni",
        "family": "shell", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Animazioni e trasparenze consumano GPU/CPU e rendono la UI meno reattiva.",
        "reason": "In modalita prestazioni Windows disattiva gli effetti superflui.",
        "desc": "Imposta VisualFXSetting=2 (prestazioni).",
        "impact": "UI piu snella e reattiva. Estetica leggermente piu spartana.",
        "lab_prior": 0.08, "conflicts_with": [], "synergy_candidates": [],
        "why": "Impatto quasi nullo in fullscreen: prior basso, di solito filtrato.",
    },
    {
        "id": "telemetry", "cat": "system", "risk": "medium", "default_on": False,
        "name": "Telemetria (DiagTrack) OFF",
        "family": "services", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Il servizio DiagTrack invia dati di diagnostica e gira sempre in background.",
        "reason": "Disattivarlo riduce l uso di CPU e rete senza impatti sulle funzioni essenziali.",
        "desc": "Ferma e disabilita il servizio DiagTrack (Connected User Experiences).",
        "impact": "Meno CPU/rete in background. NON tocca Defender ne la sicurezza.",
        "lab_prior": 0.14, "conflicts_with": [], "synergy_candidates": ["search_index", "sysmain"],
        "why": "DiagTrack genera I/O e CPU in background.",
    },
    {
        "id": "ads", "cat": "system", "risk": "safe", "default_on": True,
        "name": "Suggerimenti/ads di Windows OFF",
        "family": "shell", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows mostra app suggerite e contenuti promozionali nel menu Start e altrove.",
        "reason": "Sono distrazioni e consumano risorse per scaricare i contenuti suggeriti.",
        "desc": "Disattiva SilentInstalledApps, suggerimenti e Consumer Features.",
        "impact": "Start piu pulito, niente app installate a sorpresa. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "bgapps", "cat": "system", "risk": "safe", "default_on": True,
        "name": "App in background OFF (globale)",
        "family": "services", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Le app UWP restano attive in background consumando CPU/RAM e rete.",
        "reason": "Bloccarle libera risorse per il gioco senza disinstallare nulla.",
        "desc": "Imposta GlobalUserDisabled=1 e LetAppsRunInBackground.",
        "impact": "Meno consumo di CPU/RAM in background. Alcune notifiche UWP potrebbero ritardare.",
        "lab_prior": 0.18, "conflicts_with": [], "synergy_candidates": [],
        "why": "Le app UWP in background consumano CPU e RAM durante il gioco.",
    },
    {
        "id": "gamebar_rec", "cat": "system", "risk": "safe", "default_on": True,
        "name": "Xbox Game Bar recording OFF",
        "family": "capture", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "La Game Bar registra in background per la funzione clip, usando risorse.",
        "reason": "Se non usi le clip Xbox, la registrazione continua e uno spreco di CPU/GPU.",
        "desc": "Disattiva GameDVR_Enabled e AppCaptureEnabled.",
        "impact": "Meno overhead in game. Perdi la registrazione automatica Xbox.",
        "lab_prior": 0.14, "conflicts_with": [], "synergy_candidates": [],
        "why": "La registrazione di sfondo della Game Bar pesa su GPU/disco.",
    },
    {
        "id": "debloat", "cat": "system", "risk": "medium", "default_on": False,
        "name": "Debloat app superflue (UWP)",
        "family": "services", "requires_reboot": False, "reversible": "manual",
        "requires": None,
        "problem": "Windows preinstalla app come Candy Crush, Solitaire, Bing, 3D Builder che non usi.",
        "reason": "Occupano spazio e alcune girano in background inutilmente.",
        "desc": "Rimuove una lista curata di app UWP (reinstallabili dallo Store).",
        "impact": "Sistema piu pulito. Puoi reinstallarle in qualsiasi momento dallo Store.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "search_index", "cat": "system", "risk": "medium", "default_on": False,
        "name": "Windows Search indexing OFF (invasivo)",
        "family": "services", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Il servizio di indicizzazione della ricerca puo generare carico su disco/CPU.",
        "reason": "Su alcuni PC l indicizzazione rallenta il sistema, ma serve alla ricerca file veloce.",
        "desc": "Ferma e disabilita il servizio WSearch.",
        "impact": "Meno carico su disco/CPU, MA la ricerca file diventa piu lenta. Reversibile.",
        "lab_prior": 0.11, "conflicts_with": [], "synergy_candidates": ["telemetry"],
        "why": "L'indicizzazione a scatti consuma CPU e disco durante il gioco.",
    },
    {
        "id": "fse", "cat": "gaming", "risk": "safe", "default_on": True,
        "name": "Fullscreen Optimizations OFF",
        "family": "display", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows forza il fullscreen ottimizzato (borderless) invece del fullscreen esclusivo reale.",
        "reason": "Il fullscreen esclusivo bypassa il compositor DWM: input piu diretto e frametime piu pulito.",
        "desc": "Imposta FSEBehaviorMode=2 e HonorUserFSEBehavior nel GameConfigStore.",
        "impact": "Input lag ridotto nei giochi a schermo intero. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "power_throttling", "cat": "gaming", "risk": "medium", "default_on": True,
        "name": "Power throttling CPU OFF",
        "family": "power", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows rallenta (throttla) i processi che considera poco importanti per risparmiare energia.",
        "reason": "A volte il throttling colpisce anche giochi, OBS o launcher, causando cali improvvisi.",
        "desc": "Imposta PowerThrottlingOff=1: nessun processo viene mai rallentato dal risparmio energetico.",
        "impact": "CPU sempre reattiva per giochi e streaming. Consuma un po piu di energia.",
        "lab_prior": 0.2, "conflicts_with": [], "synergy_candidates": ["power"],
        "why": "Windows limita i processi in background che il gioco potrebbe usare.",
    },
    {
        "id": "standby_clear", "cat": "gaming", "risk": "safe", "default_on": True,
        "name": "Svuota RAM standby (azione istantanea)",
        "family": "memory", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Windows tiene in RAM una cache standby che a volte non viene liberata abbastanza in fretta.",
        "reason": "Svuotare la standby list prima di giocare rende la memoria subito disponibile per il gioco.",
        "desc": "Purge della standby memory list via API di sistema (richiede Amministratore). Nessuna modifica permanente.",
        "impact": "RAM libera immediata prima della sessione di gioco. Azione una tantum, sempre sicura.",
        "lab_prior": 0.15, "conflicts_with": [], "synergy_candidates": [],
        "why": "La standby list piena causa micro-stutter negli accessi memoria.",
    },
    {
        "id": "nic_power", "cat": "network", "risk": "safe", "default_on": True,
        "name": "Scheda di rete a piena potenza",
        "family": "network", "requires_reboot": True, "reversible": "auto",
        "requires": None,
        "problem": "Windows puo spegnere la scheda di rete per risparmiare energia e usa interrupt moderation che aggiunge latenza.",
        "reason": "Il risparmio energetico della NIC causa micro-disconnessioni; la moderazione degli interrupt ritarda i pacchetti.",
        "desc": "Disattiva il power saving della scheda attiva (PnPCapabilities=24) e la interrupt moderation.",
        "impact": "Ping piu stabile, niente drop di connessione in game. Richiede riavvio o riconnessione.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "paging_exec", "cat": "system", "risk": "safe", "default_on": True,
        "name": "Kernel sempre in RAM (16GB+)",
        "family": "memory", "requires_reboot": False, "reversible": "auto",
        "requires": {"min_ram_gb": 16},
        "problem": "Windows puo spostare parti del kernel e dei driver nel file di paging su disco.",
        "reason": "Con abbastanza RAM, tenere il kernel in memoria elimina micro-attese di paging.",
        "desc": "Imposta DisablePagingExecutive=1 in Memory Management.",
        "impact": "Sistema piu scattante sotto carico. Consigliato solo con 16 GB o piu.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "sysmain", "cat": "system", "risk": "medium", "default_on": False,
        "name": "SysMain/Superfetch OFF (solo SSD)",
        "family": "services", "requires_reboot": False, "reversible": "auto",
        "requires": {"ssd": True},
        "problem": "SysMain precarica app in RAM analizzando l uso del disco: su SSD e superfluo e consuma CPU/disco.",
        "reason": "Gli SSD sono gia velocissimi in lettura casuale: il preload di SysMain non serve e genera carico.",
        "desc": "Ferma e disabilita il servizio SysMain (ex Superfetch).",
        "impact": "Meno attivita disco/CPU in background su SSD. Su HDD invece va lasciato attivo.",
        "lab_prior": 0.12, "conflicts_with": [], "synergy_candidates": ["telemetry"],
        "why": "Il prefetching aggressivo puo' causare I/O e stutter su alcuni sistemi.",
    },
    {
        "id": "trim", "cat": "system", "risk": "safe", "default_on": True,
        "name": "Verifica TRIM SSD attivo",
        "family": "storage", "requires_reboot": False, "reversible": "auto",
        "requires": {"ssd": True},
        "problem": "Se il TRIM e disattivato, l SSD rallenta progressivamente con l uso.",
        "reason": "Il TRIM permette all SSD di riorganizzare le celle libere mantenendo le prestazioni di scrittura.",
        "desc": "Esegue fsutil behavior set DisableDeleteNotify 0 (TRIM attivo).",
        "impact": "SSD sempre alla massima velocita nel tempo. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "ntfs", "cat": "system", "risk": "safe", "default_on": True,
        "name": "NTFS: last-access timestamp OFF",
        "family": "storage", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "NTFS aggiorna la data di ultimo accesso di ogni file letto, generando scritture inutili.",
        "reason": "Disattivarlo riduce le scritture su disco a ogni lettura di file (utile anche per la vita dell SSD).",
        "desc": "Esegue fsutil behavior set disablelastaccess 1 (con backup del valore precedente).",
        "impact": "Meno I/O su disco nelle operazioni quotidiane. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
    {
        "id": "edge_preload", "cat": "system", "risk": "safe", "default_on": True,
        "name": "Edge preload/background OFF",
        "family": "services", "requires_reboot": False, "reversible": "auto",
        "requires": None,
        "problem": "Microsoft Edge si precarica all avvio e resta in background anche se non lo usi.",
        "reason": "Lo startup boost di Edge occupa RAM e CPU all accensione per un browser che magari non apri mai.",
        "desc": "Imposta StartupBoostEnabled=0 e BackgroundModeEnabled=0 via policy.",
        "impact": "Avvio piu pulito e RAM libera se non usi Edge. Nessun rischio.",
        "lab_prior": None, "conflicts_with": [], "synergy_candidates": [],
        "why": None,
    },
]

_BY_ID = {t["id"]: t for t in TWEAKS}
IDS = [t["id"] for t in TWEAKS]
ID_SET = set(IDS)

# Le categorie della GUI, nell'ordine in cui compaiono le schede.
CATEGORIES = ["gaming", "input", "network", "system"]


def by_id(tweak_id: str):
    return _BY_ID.get(tweak_id)


def _fold(s: str) -> str:
    """Accenti via, per la console PowerShell: 'Priorita' e' brutto ma leggibile,
    'PrioritÃ ' no. Lo script viene letto da powershell.exe senza BOM, quindi
    l'unica garanzia sui non-ASCII e' che non ce ne siano."""
    if not s:
        return s
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def agent_risk(t: dict) -> str:
    """La scala binaria che la GUI dell'agent si aspetta ancora."""
    return "safe" if t["default_on"] else "caution"


def agent_entries():
    """I metadati che l'agent PowerShell fonde nel suo catalogo, per id."""
    return [{
        "id": t["id"],
        "cat": t["cat"],
        "name": _fold(t["name"]),
        "risk": agent_risk(t),
        "problem": _fold(t["problem"]),
        "reason": _fold(t["reason"]),
        "desc": _fold(t["desc"]),
        "impact": _fold(t["impact"]),
        "requires_reboot": bool(t["requires_reboot"]),
    } for t in TWEAKS]


def web_catalog():
    """L'elenco per la web app: profili di gioco e selezione manuale."""
    return [{"id": t["id"], "name": t["name"], "cat": t["cat"]} for t in TWEAKS]


def advisor_catalog_line() -> str:
    """Il catalogo come lo legge il modello: 'id=nome; id=nome; ...'.

    Tutti e 35, non un sottoinsieme scritto a mano: un tweak assente da qui e'
    un tweak che l'AI non puo' consigliare nemmeno quando e' la risposta giusta.
    """
    return "; ".join("%s=%s" % (t["id"], _fold(t["name"])) for t in TWEAKS)


def lab_entries():
    """I tweak che il Laboratorio misura, nella forma attesa dal registro."""
    out = []
    for t in TWEAKS:
        if t["lab_prior"] is None:
            continue
        out.append({
            "tweak_id": t["id"],
            "name": t["name"],
            "family": t["family"],
            "risk_level": t["risk"],
            "requires_reboot": t["requires_reboot"],
            "reversible": t["reversible"],
            "base_prior": t["lab_prior"],
            "conflicts_with": list(t["conflicts_with"]),
            "synergy_candidates": list(t["synergy_candidates"]),
            "why": t["why"],
            "requires": t["requires"],
        })
    return out
