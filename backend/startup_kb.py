"""Quali programmi all'avvio si possono spegnere, e quali no.

L'analisi dei servizi ha una knowledge base curata perche' i servizi Windows
sono un insieme chiuso e conosciuto. Le voci di avvio no: sono qualunque cosa un
installer abbia deciso di piazzare in `Run`, e ogni PC ne ha di diverse. Qui il
match non e' sul nome esatto ma su COSA fa il programma, ricavato da nome,
descrizione, editore e percorso.

Tre verdetti, con una regola sola dietro:

  sicuro   il programma resta installato e funziona: all'avvio ci sta per
           comodita' (updater, launcher di giochi, chat, suite RGB). Lo apri tu
           quando ti serve.
  valuta   toglierlo cambia un comportamento che potresti volere: la sincronia
           del cloud che non parte, la VPN che non sale, le macro che non
           rispondono. Dipende da come usi il PC, quindi decide l'utente.
  critico  non si tocca dall'app: sicurezza, driver, input. Spegnerlo non
           velocizza l'avvio in modo percepibile e puo' lasciare il PC senza
           audio, senza touchpad o senza antivirus.

Lo sconosciuto vale `valuta`, mai `sicuro`: un default ottimista qui significa
proporre a un utente di spegnere qualcosa che nessuno ha guardato.
"""
import re

# Ogni regola: (verdetto, espressione, motivo bilingue, condizione bilingue).
#
# L'ordine conta: si ferma alla prima che matcha, quindi il critico viene prima
# del sicuro (un "Realtek Audio Update" e' un driver, non un updater qualunque).
#
# E conta DOVE si cerca. Le regole che dicono "critico" o "valuta" guardano
# anche percorso e riga di comando: sbagliare in eccesso costa una domanda in
# piu' all'utente. Quelle che dicono "sicuro" no, guardano solo nome, nome
# leggibile ed editore — perche' il percorso raggruppa per cartella, non per
# funzione: sotto `ASUS\ArmouryDevice\` ci stanno sia la suite RGB (spegnibile)
# sia il motore di riduzione del rumore e l'agente di alimentazione del mouse,
# e un match sul percorso li dichiarava tutti "sicuri da spegnere".
_REGOLE = [
    # --- critico: sicurezza ---
    ("critico", r"defender|antimalware|securityhealth|windows security|sicurezza di windows"
                r"|avast|avg |bitdefender|kaspersky|norton|mcafee|eset|malwarebytes|sophos|trend micro",
     {"it": "Sicurezza del PC: deve partire prima di tutto il resto, non all'occorrenza.",
      "en": "PC security: it has to start before everything else, not on demand."}, None),
    # --- critico: driver e periferiche di sistema ---
    ("critico", r"realtek|rtkaud|ravcpl|ravbg|rtkngui|nahimic|waves(svc|audio|sys)|maxxaudio|dts audio"
                r"|synaptic|syntp|etd(ctrl|tray)|elan.*(pointing|touchpad)|touchpad|precision touchpad"
                r"|igfx(tray|pers|hk|em)|intel graphics|nvidia display|amd (external events|user experience)"
                r"|nvcontainer|nvidia (localsystem|display) container|nvidia container"
                r"|xear|xonar|audio (cent(er|re)|control|console|manager)|sound ?card"
                r"|hotkey|atkexcomsvc|hcontrol|smartaudio|conexant|cirrus|\bdrivers?\b",
     {"it": "Driver o pannello di una periferica: audio, video, touchpad o tasti funzione dipendono da lui.",
      "en": "Device driver or control panel: audio, video, touchpad or function keys depend on it."}, None),
    # --- critico: input e accessibilita' ---
    ("critico", r"ctfmon|textinputhost|windows input experience|tablet input|magnify|narrator|assistive",
     {"it": "Servizio di input o accessibilita' di Windows: senza, tastiera virtuale e metodi di scrittura smettono di funzionare.",
      "en": "Windows input or accessibility service: without it the touch keyboard and input methods stop working."}, None),
    # --- valuta: sincronia cloud (spegnerla non e' gratis: i file smettono di allinearsi) ---
    ("valuta", r"onedrive|dropbox|google drive|drivefs|backup and sync|icloud|mega ?sync|nextcloud|pcloud|box sync|sync\.com",
     {"it": "Sincronia cloud: se non parte all'avvio, i file si allineano solo quando apri il programma a mano.",
      "en": "Cloud sync: if it doesn't start at boot, files only sync when you open the app by hand."},
     {"it": "Disattiva solo se ti basta sincronizzare quando lo apri tu.",
      "en": "Disable only if syncing when you open it is enough for you."}),
    # --- valuta: VPN, sicurezza di rete, password ---
    ("valuta", r"vpn|wireguard|openvpn|tailscale|nordvpn|expressvpn|proton|mullvad"
               r"|1password|bitwarden|lastpass|keepass|dashlane",
     {"it": "Rete protetta o gestore password: se non parte da solo, va aperto prima di usarlo.",
      "en": "Protected network or password manager: if it doesn't start on its own, you have to open it first."},
     {"it": "Disattiva solo se ti va bene lanciarlo a mano quando serve.",
      "en": "Disable only if launching it by hand when needed is fine."}),
    # --- valuta: periferiche programmabili (le macro smettono di rispondere) ---
    ("valuta", r"g ?hub|logitech gaming|ghub|razer synapse|synapse|steelseries|corsair icue|icue"
               r"|glorious|wooting|vial|via |qmk|xppen|wacom|elgato|stream ?deck",
     {"it": "Software di mouse, tastiera o periferica programmabile: le macro e i profili si attivano solo con lui in esecuzione.",
      "en": "Mouse, keyboard or programmable device software: macros and profiles only work while it runs."},
     {"it": "Disattiva solo se non usi macro, profili o illuminazione reattiva.",
      "en": "Disable only if you don't use macros, profiles or reactive lighting."}),
    # --- sicuro: aggiornatori ---
    ("sicuro", r"updat|upgrade|patch|installer|setup ?helper|helper ?service|autoupdate|swupdate",
     {"it": "Cerca aggiornamenti in background: il programma si aggiorna comunque quando lo apri.",
      "en": "Checks for updates in the background: the app updates anyway when you open it."}, None),
    # --- sicuro: telemetria e crash report ---
    ("sicuro", r"telemetr|crashreport|crash ?handler|error ?report|analytics|usage ?data|feedback",
     {"it": "Manda dati d'uso o rapporti di errore: non serve a far funzionare niente.",
      "en": "Sends usage data or error reports: nothing depends on it to work."}, None),
    # --- sicuro: launcher e store di giochi ---
    ("sicuro", r"steam|epic ?games|epicgameslauncher|ea ?(desktop|app|launcher)|origin|ubisoft|uplay"
               r"|gog ?galaxy|battle\.?net|blizzard|rockstar|riot ?client|minecraft|roblox|xbox|gaming ?app"
               r"|playnite|itch",
     {"it": "Launcher di giochi: parte da solo quando avvii un gioco, non serve tenerlo pronto dal boot.",
      "en": "Game launcher: it starts on its own when you launch a game, no need to keep it warm from boot."}, None),
    # --- sicuro: chat e comunicazione ---
    ("sicuro", r"discord|slack|teams|skype|telegram|whatsapp|signal|zoom|webex|viber|messenger",
     {"it": "App di messaggistica: si apre in pochi secondi quando ti serve.",
      "en": "Messaging app: it opens in seconds when you need it."},
     {"it": "Se ci ricevi chiamate o notifiche importanti, lasciala attiva.",
      "en": "If you get calls or important notifications there, keep it on."}),
    # --- sicuro: suite RGB e utility del produttore ---
    ("sicuro", r"armoury|armory ?crate|rog live|aura|myasus|asus ?(update|framework)|mystic light|dragon center"
               r"|msi ?center|gaming ?center|alienware|command ?cent(er|re)|omen|predator|control ?cent(er|re)"
               r"|lenovo vantage|vantage|nitrosense|gigabyte|aorus|thermaltake|nzxt|cam",
     {"it": "Utility del produttore: serve quando apri il pannello, non mentre giochi.",
      "en": "Vendor utility: needed when you open its panel, not while you play."},
     {"it": "Se ci gestisci curve delle ventole o profili di alimentazione, valutala.",
      "en": "If you manage fan curves or power profiles there, think twice."}),
    # --- sicuro: media e produttivita' che non hanno motivo di stare al boot ---
    ("sicuro", r"spotify|itunes|deezer|tidal|vlc|adobe|acrobat|creative cloud|java|jre|quicktime"
               r"|officehub|office ?hub|onenote|evernote|notion|obsidian|zotero"
               r"|phone ?link|yourphone|crossdevice|cortana|copilot|edge ?(boost|startup)"
               r"|clipchamp|solitaire|xing|linkedin",
     {"it": "Programma che si apre a mano: all'avvio ci sta solo per partire un secondo prima.",
      "en": "App you open by hand: it's at startup only to launch a second sooner."}, None),
    # --- sicuro: registrazione e overlay (utili ma non dal boot) ---
    ("sicuro", r"obs|streamlabs|shadowplay|geforce experience|nvidia overlay|radeon software|medal\.tv"
               r"|overwolf|bandicam|fraps|action!|xsplit",
     {"it": "Cattura o overlay: si lancia quando ti serve registrare o streammare.",
      "en": "Capture or overlay tool: launch it when you actually need to record or stream."},
     {"it": "Se registri le partite in automatico, tienilo attivo.",
      "en": "If you auto-record your matches, keep it on."}),
]

_COMPILATE = None


def _compila():
    global _COMPILATE
    if _COMPILATE is None:
        _COMPILATE = [(verdetto, re.compile(rx, re.IGNORECASE), why, cond)
                      for verdetto, rx, why, cond in _REGOLE]
    return _COMPILATE


_SCONOSCIUTO = {
    "it": "Nessuna regola conosciuta per questo programma: decidi tu, sapendo che disattivarlo non lo disinstalla.",
    "en": "No known rule for this program: your call — disabling it does not uninstall it.",
}


def classify_startup(voce: dict) -> dict:
    """Verdetto su una singola voce di avvio.

    Guarda tutto quello che l'agent ha raccolto — nome della chiave, nome
    leggibile dell'eseguibile, editore e percorso — perche' nessuno dei quattro
    da solo basta: "RTHDVCPL" non dice niente, il suo FileDescription dice
    "Realtek HD Audio Manager".
    """
    if not isinstance(voce, dict):
        return {"safety": "valuta", "why": _SCONOSCIUTO, "condition": None, "can_disable": True}
    identita = " ".join(str(voce.get(k) or "") for k in ("name", "display", "publisher"))
    tutto = identita + " " + " ".join(str(voce.get(k) or "") for k in ("path", "command"))
    verdetto, why, cond = "valuta", _SCONOSCIUTO, None
    for v, rx, w, c in _compila():
        if rx.search(identita if v == "sicuro" else tutto):
            verdetto, why, cond = v, w, c
            break

    # Un servizio da cui dipendono altri servizi non e' una voce di avvio come
    # le altre: spegnendolo si spengono anche loro, e l'utente vede rompersi
    # qualcosa che non ha toccato.
    if verdetto == "sicuro" and voce.get("source") == "service" and int(voce.get("dependents") or 0) > 0:
        verdetto = "valuta"
        cond = {"it": "Altri servizi dipendono da questo: disattivandolo si fermano anche loro.",
                "en": "Other services depend on this one: disabling it stops them too."}

    return {"safety": verdetto, "why": why, "condition": cond,
            "can_disable": verdetto != "critico"}


def annotate_startup(startup: list | None) -> list:
    """Aggiunge il verdetto a ogni voce della lista, in loco."""
    for voce in startup or []:
        if isinstance(voce, dict):
            voce.update(classify_startup(voce))
    return startup or []


def summarize_startup(startup: list | None) -> dict:
    """Conteggi per la testata della scheda: quante se ne possono spegnere."""
    attive = [v for v in (startup or [])
              if isinstance(v, dict) and v.get("enabled") is not False and not v.get("noise")]
    per_verdetto = {"sicuro": 0, "valuta": 0, "critico": 0}
    ram = 0
    for v in attive:
        s = v.get("safety") or classify_startup(v)["safety"]
        per_verdetto[s] = per_verdetto.get(s, 0) + 1
        if s == "sicuro":
            ram += int(v.get("ram_mb") or 0)
    return {"attive": len(attive), **per_verdetto, "ram_mb_sicuri": ram}
