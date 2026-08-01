"""Knowledge base curata dei servizi Windows disattivabili su un PC da gaming.

Analisi DETERMINISTICA (niente AI): match sull'audit reale dell'agent
(stato, tipo avvio, dipendenze, RAM) + contesto (SSD, stampante, Xbox).
rec: disattiva (sicuro) | valuta (dipende dall'uso) | mantieni.
"""

SERVICES_KB = {
    "diagtrack": {"rec": "disattiva", "cat": "telemetria",
                  "why": {"it": "Telemetria Microsoft (Connected User Experiences): raccoglie dati d'uso in background. Zero impatto sul funzionamento.",
                          "en": "Microsoft telemetry (Connected User Experiences): collects usage data in the background. Zero functional impact."}},
    "dmwappushservice": {"rec": "disattiva", "cat": "telemetria",
                         "why": {"it": "Routing messaggi WAP legato alla telemetria. Non serve su un PC desktop.",
                                 "en": "WAP push message routing tied to telemetry. Not needed on a desktop PC."}},
    "fax": {"rec": "disattiva", "cat": "legacy",
            "why": {"it": "Servizio Fax: inutile se non invii fax dal PC.",
                    "en": "Fax service: useless unless you send faxes from this PC."}},
    "remoteregistry": {"rec": "disattiva", "cat": "sicurezza",
                       "why": {"it": "Permette la modifica del registro da remoto: disattivarlo migliora anche la sicurezza.",
                               "en": "Allows remote registry editing: disabling it also improves security."}},
    "mapsbroker": {"rec": "disattiva", "cat": "consumer",
                   "why": {"it": "Download mappe offline per l'app Mappe. Inutile su un PC da gaming.",
                           "en": "Offline map downloads for the Maps app. Useless on a gaming PC."}},
    "lfsvc": {"rec": "disattiva", "cat": "consumer",
              "why": {"it": "Geolocalizzazione: su un desktop senza GPS non serve.",
                      "en": "Geolocation: not needed on a desktop without GPS."}},
    "retaildemo": {"rec": "disattiva", "cat": "legacy",
                   "why": {"it": "Modalità demo per i negozi. Da disattivare sempre.",
                           "en": "Retail store demo mode. Always safe to disable."}},
    "wmpnetworksvc": {"rec": "disattiva", "cat": "legacy",
                      "why": {"it": "Condivisione multimediale di Windows Media Player (DLNA legacy).",
                              "en": "Windows Media Player network sharing (legacy DLNA)."}},
    "phonesvc": {"rec": "disattiva", "cat": "consumer",
                 "why": {"it": "Collegamento telefono: inutile se non usi l'app 'Collegamento al telefono'.",
                         "en": "Phone service: useless if you don't use the Phone Link app."}},
    "scardsvr": {"rec": "disattiva", "cat": "legacy",
                 "why": {"it": "Smart card: serve solo con lettori di smart card aziendali.",
                         "en": "Smart card: only needed with corporate smart card readers."}},
    "diagnosticshub.standardcollector.service": {"rec": "disattiva", "cat": "telemetria",
                 "why": {"it": "Raccolta diagnostica per Visual Studio. Non serve fuori dallo sviluppo.",
                         "en": "Diagnostics collection for Visual Studio. Not needed outside development."}},
    "sharedaccess": {"rec": "disattiva", "cat": "legacy",
                     "why": {"it": "Condivisione connessione Internet (ICS): quasi nessuno la usa oggi.",
                             "en": "Internet Connection Sharing (ICS): almost nobody uses it today."}},
    "wersvc": {"rec": "valuta", "cat": "telemetria",
               "why": {"it": "Segnalazione errori Windows: disattivandolo non invii più i crash report a Microsoft (i crash restano visibili nel Visualizzatore eventi).",
                       "en": "Windows Error Reporting: disabling stops crash reports to Microsoft (crashes still visible in Event Viewer)."}},
    "sysmain": {"rec": "valuta", "cat": "prestazioni", "cond_id": "ssd",
                "why": {"it": "Superfetch/precaricamento: su SSD/NVMe non dà benefici e consuma CPU/disco in background.",
                        "en": "Superfetch/preloading: on SSD/NVMe it gives no benefit and consumes background CPU/disk."},
                "condition": {"it": "Disattiva solo se hai un SSD (su hard disk meccanico aiuta)",
                              "en": "Disable only if you have an SSD (it helps on mechanical drives)"}},
    "wsearch": {"rec": "valuta", "cat": "prestazioni",
                "why": {"it": "Indicizzazione ricerca Windows: consuma disco/CPU in background. Disattivandolo la ricerca file diventa più lenta.",
                        "en": "Windows Search indexing: consumes background disk/CPU. Disabling makes file search slower."},
                "condition": {"it": "Disattiva solo se non usi spesso la ricerca file di Windows",
                              "en": "Disable only if you rarely use Windows file search"}},
    "spooler": {"rec": "valuta", "cat": "periferiche", "cond_id": "printer",
                "why": {"it": "Coda di stampa: senza stampante è solo superficie di attacco (PrintNightmare) e RAM sprecata.",
                        "en": "Print spooler: without a printer it's just attack surface (PrintNightmare) and wasted RAM."},
                "condition": {"it": "Disattiva solo se non usi stampanti (nemmeno PDF di terze parti)",
                              "en": "Disable only if you never print (not even third-party PDF printers)"}},
    "printnotify": {"rec": "valuta", "cat": "periferiche", "cond_id": "printer",
                    "why": {"it": "Notifiche stampante: inutile senza stampante.",
                            "en": "Printer notifications: useless without a printer."},
                    "condition": {"it": "Disattiva solo se non usi stampanti", "en": "Disable only if you never print"}},
    "tabletinputservice": {"rec": "valuta", "cat": "input",
                           "why": {"it": "Tastiera virtuale e pannello scrittura: serve solo con touchscreen o pannello emoji.",
                                   "en": "Touch keyboard and handwriting panel: only needed with touchscreens or the emoji panel."},
                           "condition": {"it": "Su Win11 gestisce anche il pannello emoji (Win+.)", "en": "On Win11 it also powers the emoji panel (Win+.)"}},
    "wbiosrvc": {"rec": "valuta", "cat": "input",
                 "why": {"it": "Biometria Windows Hello: serve solo se accedi con impronta o riconoscimento volto.",
                         "en": "Windows Hello biometrics: only needed for fingerprint or face login."},
                 "condition": {"it": "Non disattivare se usi impronta/volto per il login", "en": "Keep it if you log in with fingerprint/face"}},
    "xblauthmanager": {"rec": "valuta", "cat": "gaming", "cond_id": "xbox",
                       "why": {"it": "Autenticazione Xbox Live: serve per app Xbox, Game Pass e giochi Microsoft Store (es. Minecraft).",
                               "en": "Xbox Live auth: needed for the Xbox app, Game Pass and Microsoft Store games (e.g. Minecraft)."},
                       "condition": {"it": "Disattiva solo se non usi app Xbox/Game Pass", "en": "Disable only if you don't use Xbox app/Game Pass"}},
    "xblgamesave": {"rec": "valuta", "cat": "gaming", "cond_id": "xbox",
                    "why": {"it": "Salvataggi cloud Xbox: come sopra, serve solo con l'ecosistema Xbox.",
                            "en": "Xbox cloud saves: as above, only needed with the Xbox ecosystem."},
                    "condition": {"it": "Disattiva solo se non usi app Xbox/Game Pass", "en": "Disable only if you don't use Xbox app/Game Pass"}},
    "xboxnetapisvc": {"rec": "valuta", "cat": "gaming", "cond_id": "xbox",
                      "why": {"it": "Rete Xbox Live: multiplayer dei giochi Microsoft Store.",
                              "en": "Xbox Live networking: multiplayer for Microsoft Store games."},
                      "condition": {"it": "Disattiva solo se non usi app Xbox/Game Pass", "en": "Disable only if you don't use Xbox app/Game Pass"}},
    "xboxgipsvc": {"rec": "valuta", "cat": "gaming", "cond_id": "xbox",
                   "why": {"it": "Gestione accessori Xbox (controller via app Accessori).",
                           "en": "Xbox accessory management (controllers via the Accessories app)."},
                   "condition": {"it": "I controller Xbox via USB/Bluetooth funzionano comunque", "en": "Xbox controllers over USB/Bluetooth still work"}},
    "edgeupdate": {"rec": "disattiva", "cat": "updater",
                   "why": {"it": "Updater di Edge sempre attivo: Edge si aggiorna comunque all'apertura.",
                           "en": "Always-on Edge updater: Edge still updates when opened."}},
    "edgeupdatem": {"rec": "disattiva", "cat": "updater",
                    "why": {"it": "Secondo updater di Edge (manuale). Ridondante.",
                            "en": "Second Edge updater (manual). Redundant."}},
    "microsoftedgeelevationservice": {"rec": "disattiva", "cat": "updater",
                    "why": {"it": "Servizio di elevazione per gli update di Edge. Non necessario sempre attivo.",
                            "en": "Elevation service for Edge updates. No need to keep it always on."}},
    "gupdate": {"rec": "disattiva", "cat": "updater",
                "why": {"it": "Google Update: Chrome si aggiorna comunque all'apertura.",
                        "en": "Google Update: Chrome still updates when opened."}},
    "gupdatem": {"rec": "disattiva", "cat": "updater",
                 "why": {"it": "Secondo updater Google (manuale). Ridondante.",
                         "en": "Second Google updater (manual). Redundant."}},
    "adobearmservice": {"rec": "disattiva", "cat": "updater",
                        "why": {"it": "Updater Adobe Acrobat/Reader sempre attivo. Aggiorna manualmente quando serve.",
                                "en": "Always-on Adobe Acrobat/Reader updater. Update manually when needed."}},
    "nvtelemetrycontainer": {"rec": "disattiva", "cat": "telemetria",
                             "why": {"it": "Telemetria NVIDIA: non influisce su driver o prestazioni.",
                                     "en": "NVIDIA telemetry: does not affect drivers or performance."}},
}

_UPDATER_HINT = {
    "it": "Sembra un updater/telemetria di terze parti sempre attivo: valutane la disattivazione, l'app si aggiornerà comunque all'apertura.",
    "en": "Looks like an always-on third-party updater/telemetry service: consider disabling it, the app will still update when opened.",
}


def analyze_services(audit, specs_data=None, games=None):
    import re
    specs_data = specs_data or {}
    games = [str(g).lower() for g in (games or [])]
    disk_text = " ".join(str(specs_data.get(k) or "") for k in ("disk", "disks", "disk_type", "storage")).lower()
    has_ssd = ("ssd" in disk_text or "nvme" in disk_text) or not disk_text
    uses_xbox = any("xbox" in g or "gamingservices" in g or "minecraft" in g for g in games)

    items = []
    ram_saveable = 0
    seen = set()
    for a in audit:
        if not isinstance(a, dict):
            continue
        key = str(a.get("name") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        state = str(a.get("state") or "")
        mode = str(a.get("start_mode") or "")
        dep = int(a.get("dependents") or 0)
        kb = SERVICES_KB.get(key)
        rec, why, cond = None, None, None
        if kb:
            rec = kb["rec"]
            why = kb["why"]
            cond = kb.get("condition")
            cid = kb.get("cond_id")
            if cid == "ssd" and has_ssd:
                rec = "disattiva"
            if cid == "xbox" and uses_xbox:
                rec = "mantieni"
                cond = {"it": "Usi l'ecosistema Xbox/Microsoft Store: lascialo attivo.",
                        "en": "You use the Xbox/Microsoft Store ecosystem: keep it on."}
        else:
            if not a.get("ms") and mode == "Auto" and re.search(r"(?i)updat|telemetr|crash|report", key + " " + str(a.get("display") or "")):
                rec = "valuta"
                why = _UPDATER_HINT
        if not rec:
            continue
        if state != "Running" and mode != "Auto":
            rec = "gia_ok"
        elif dep > 2 and rec == "disattiva":
            rec = "valuta"
            cond = {"it": f"Attenzione: {dep} altri servizi dipendono da questo.",
                    "en": f"Warning: {dep} other services depend on it."}
        if rec == "disattiva" and a.get("ram_mb"):
            ram_saveable += int(a["ram_mb"])
        items.append({
            "name": a.get("name"), "display": a.get("display") or a.get("name"),
            "state": state, "start_mode": mode, "ram_mb": a.get("ram_mb"),
            "dependents": dep, "shared": bool(a.get("shared")),
            "recommendation": rec, "category": (kb or {}).get("cat", "altro"),
            "why": why, "condition": cond,
        })
    order = {"disattiva": 0, "valuta": 1, "gia_ok": 2, "mantieni": 3}
    items.sort(key=lambda x: (order.get(x["recommendation"], 9), -(x.get("ram_mb") or 0)))
    return {
        "items": items,
        "summary": {
            "total_audited": len(audit),
            "disattiva": sum(1 for i in items if i["recommendation"] == "disattiva"),
            "valuta": sum(1 for i in items if i["recommendation"] == "valuta"),
            "gia_ok": sum(1 for i in items if i["recommendation"] == "gia_ok"),
            "ram_mb_saveable": ram_saveable,
        },
    }

_NOISE_RE = None


def is_startup_noise(name, publisher=None):
    """Voci di sistema/driver non azionabili: nascoste dalla UI e dall'analisi AI."""
    global _NOISE_RE
    import re
    if _NOISE_RE is None:
        _NOISE_RE = re.compile(
            r"(?i)securityhealth|windows security|windows defender|msmpeng"
            r"|rtkauduservice|ravcpl|ravbg|rtkngui|realtek hd audio|realtek audio console"
            r"|waves(svc|audio|sys)|maxxaudio"
            r"|syntp|synaptics pointing|etd(ctrl|tray)|elan.*(pointing|touchpad)"
            r"|igfx(tray|pers|hk|em)|intel graphics command"
            r"|windows input experience|textinputhost|ctfmon"
            r"|delayedlauncher|ijplmsvc")
    return bool(_NOISE_RE.search(f"{name or ''} {publisher or ''}"))
