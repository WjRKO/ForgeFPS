"""Registro versionato dei tweak del Laboratorio Automatico (Fase 1).

Fase 1: SOLO tweak senza riavvio (safe + medium), applicabilita' valutata sulle
pc_specs reali dell'utente, prior statici per il motore di selezione.

Le voci non stanno piu' qui: sono i tweak di `tweak_catalog.py` con un
`lab_prior` non nullo. Il registro conservava una seconda copia scritta a mano
di nomi e rischi gia' presenti nel catalogo dell'agent, e le due copie erano
divergenti — `gaming` qui si chiamava "Boost gaming (Game Mode, Game DVR off)"
mentre l'apply attiva anche HAGS. Qui resta il motore: soglia, ordinamento,
filtro di rischio e applicabilita'.
"""
import re

import tweak_catalog

# 1.2.0: le voci derivano dal catalogo unico e `requires` filtra per hardware,
# quindi la selezione puo' differire da quella della 1.1.0 (SysMain non viene
# piu' proposto a chi non ha un SSD, come gia' faceva l'agent per conto suo).
REGISTRY_VERSION = "1.2.0"
PRIOR_THRESHOLD = 0.10

_RISK_ORDER = {"safe": 0, "medium": 1, "expert": 2, "hardware": 3}


def _gpu_vendor(specs: dict, vendor: str) -> bool:
    """Vero solo se la GPU e' riconosciuta di quel produttore.

    GPU sconosciuta -> falso: un tweak specifico di un vendore applicato al buio
    e' un rischio, e questa e' la regola che il registro seguiva gia'.
    """
    gpu = specs.get("gpu") or ""
    marchi = {"NVIDIA": r"nvidia|geforce|rtx|gtx", "AMD": r"\bamd\b|radeon|\brx\s*\d"}
    return bool(re.search(marchi.get(vendor.upper(), vendor), gpu, re.I))


def _ha_ssd(specs: dict):
    """True/False/None: None quando le pc_specs non elencano i dischi."""
    dischi = [d for d in (specs.get("disks") or []) if isinstance(d, dict)]
    if not dischi:
        return None
    return any(str(d.get("type") or "").upper() == "SSD" for d in dischi)


def _ram_gb(specs: dict):
    m = re.search(r"\d+", str(specs.get("ram") or ""))
    return int(m.group(0)) if m else None


def _applicabile(requires: dict, specs: dict):
    """(ok, motivo). Al contrario del vendore GPU, un requisito che non si puo'
    verificare non fa scartare il tweak: se le specs non dicono se c'e' un SSD,
    l'assenza del dato non e' la prova che non ci sia, e togliere il tweak dal
    Lab per un campo mancante significa non misurarlo mai piu' su quel PC.
    """
    if not requires:
        return True, ""
    vendor = requires.get("gpu_vendor")
    if vendor and not _gpu_vendor(specs, vendor):
        return False, "Solo GPU %s" % vendor
    if requires.get("ssd") and _ha_ssd(specs) is False:
        return False, "Solo con SSD: su HDD il prefetching serve ancora"
    minimo = requires.get("min_ram_gb")
    if minimo:
        ram = _ram_gb(specs)
        if ram is not None and ram < minimo:
            return False, "Richiede almeno %d GB di RAM (rilevati %d)" % (minimo, ram)
    return True, ""


TWEAKS = tweak_catalog.lab_entries()

_ignoti = sorted({t["risk_level"] for t in TWEAKS} - set(_RISK_ORDER))
if _ignoti:
    # Un livello sconosciuto finiva in `_RISK_ORDER.get(..., 0)`, cioe' veniva
    # trattato come il piu' sicuro che esista: il default silenzioso rendeva un
    # errore di battitura una promozione.
    raise ValueError("livelli di rischio non previsti nel catalogo: %s" % ", ".join(_ignoti))


def select_candidates(specs_data: dict, risk_level: str = "medium", include_reboot: bool = True):
    """Motore di selezione: filtra per rischio + applicabilita', scarta prior <= soglia,
    ordina prima i no-reboot per prior, poi i reboot in coda (meno riavvii possibili).
    Ritorna (candidates, skipped)."""
    specs_data = specs_data or {}
    if risk_level not in _RISK_ORDER:
        raise ValueError("livello di rischio sconosciuto: %r" % (risk_level,))
    max_risk = _RISK_ORDER[risk_level]
    candidates, skipped = [], []
    for t in TWEAKS:
        entry = {k: v for k, v in t.items() if k != "requires"}
        if t.get("requires_reboot") and not include_reboot:
            skipped.append({"tweak_id": t["tweak_id"], "reason": "richiede riavvio (esclusi dall'utente)"})
            continue
        if _RISK_ORDER[t["risk_level"]] > max_risk:
            skipped.append({"tweak_id": t["tweak_id"], "reason": f"rischio {t['risk_level']} > livello scelto ({risk_level})"})
            continue
        ok, motivo = _applicabile(t.get("requires"), specs_data)
        if not ok:
            skipped.append({"tweak_id": t["tweak_id"], "reason": motivo})
            continue
        if t["base_prior"] <= PRIOR_THRESHOLD:
            skipped.append({"tweak_id": t["tweak_id"], "reason": f"prior {t['base_prior']:.2f} <= soglia {PRIOR_THRESHOLD}"})
            continue
        entry["prior"] = t["base_prior"]
        candidates.append(entry)
    candidates.sort(key=lambda c: (bool(c.get("requires_reboot")), -c["prior"]))
    return candidates, skipped


def bios_suggestions(specs_data: dict):
    """Fase 3: suggerimenti BIOS guidati (manuali, non automatizzabili via software)."""
    d = specs_data or {}
    out = []

    def _num(v):
        try:
            return float(str(v).strip())
        except Exception:
            return None

    ram_t = (d.get("ram_type") or "").upper()
    cfg = _num(d.get("ram_speed_mhz"))
    nom = _num(d.get("ram_speed_nominal_mhz"))
    base = 4800 if "DDR5" in ram_t else 2666
    xmp_off = False
    if cfg and nom and nom > cfg + 1:
        xmp_off = True
    elif cfg and cfg <= base:
        xmp_off = True
    if xmp_off:
        out.append({
            "id": "xmp",
            "title": "Attiva XMP/EXPO (profilo RAM)",
            "why": f"La tua RAM gira a {int(cfg)} MHz: quasi certamente sotto il profilo dichiarato. La banda RAM conta soprattutto nei titoli CPU-bound.",
            "steps": [
                "Riavvia ed entra nel BIOS (tasto CANC/F2 all'avvio)",
                "Cerca 'XMP' (Intel) o 'EXPO/DOCP' (AMD) nella sezione memoria/overclock",
                "Seleziona il Profilo 1 e salva (F10)",
                "Se il PC non si avvia: il BIOS ripristina Auto da solo, nessun rischio permanente",
            ],
            "expected_gain": "+3-8% FPS nei giochi CPU-bound",
            "reversible": "manual",
        })
    gpu = (d.get("gpu") or "").lower()
    rebar_on = str(d.get("rebar_status") or "").lower() == "on"
    if not rebar_on and re.search(r"rtx\s*[345]0\d{2}|rx\s*[679]\d{3}|arc\s", gpu):
        is_nv = bool(re.search(r"rtx|nvidia|geforce", gpu))
        verify = ("Verifica: NVIDIA Control Panel -> Informazioni di sistema -> 'BAR ridimensionabile: Si'"
                  if is_nv else "Verifica: AMD Software -> Prestazioni -> Smart Access Memory attivo")
        out.append({
            "id": "rebar",
            "title": "Verifica Resizable BAR",
            "why": "La tua GPU supporta Resizable BAR: se disattivato nel BIOS perdi FPS gratis in molti titoli.",
            "steps": [
                "BIOS -> Advanced/PCI: attiva 'Above 4G Decoding' e 'Re-Size BAR Support'",
                verify,
                "Serve anche il boot in modalita' UEFI (non CSM/Legacy)",
            ],
            "expected_gain": "+1-5% FPS a seconda del gioco",
            "reversible": "manual",
        })
    modules = _num(d.get("ram_modules"))
    if modules == 1:
        out.append({
            "id": "dual_channel",
            "title": "RAM in single channel: passa a dual channel",
            "why": "Un solo modulo RAM dimezza la banda di memoria: uno dei colli di bottiglia peggiori per gli FPS.",
            "steps": [
                "Aggiungi un secondo modulo identico negli slot corretti (di solito 2 e 4)",
                "Verifica 'Dual' in Task Manager -> Prestazioni -> Memoria",
            ],
            "expected_gain": "+5-15% FPS nei giochi CPU/RAM-bound",
            "reversible": "manual",
        })
    return out
