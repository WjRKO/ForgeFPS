# -*- coding: utf-8 -*-
"""Come si scrive `pc_specs.data`: fondere, non sostituire.

I due percorsi che scrivevano lo stesso documento avevano semantiche opposte:
`POST /agent/report-specs` sostituiva `data` in blocco, `POST /pc-specs` (il form
manuale) fondeva campo per campo. La sostituzione perdeva dati, e in silenzio:
una scansione degradata - agent senza privilegi, `nvidia-smi` assente, WMI che
singhiozza - produce meno campi, e quei campi non diventavano vecchi, diventavano
**vuoti**. Il PC aveva meno hardware di ieri.

La regola qui e' una sola: **un campo assente non cancella un campo presente**.
Resta il valore di prima e accanto, in `data_meta`, la data in cui e' stato visto
l'ultima volta e da quale fonte. Cosi' "vecchio" e "sparito" smettono di
somigliarsi, e chi legge puo' decidere se fidarsi.

Il prezzo, dichiarato: un componente rimosso davvero - una GPU secondaria tolta
dal case - resta nel documento finche' qualcosa non lo sovrascrive, con una data
sempre piu' vecchia. E' il lato giusto del compromesso: `diff_specs` gia' non
segnala i campi che spariscono, proprio perche' sparire e' quasi sempre un
difetto di misura e non un fatto.

Tutte le funzioni sono pure: nessun db, nessuna rete.
"""
from __future__ import annotations

# Sorgenti possibili di un campo, dalla piu' alla meno diretta.
SOURCE_AGENT = "agent"
SOURCE_MANUAL = "manual"


def is_empty(value) -> bool:
    """Un campo "non rilevato". `False` e `0` sono valori, non assenze.

    Distinzione che sembra pedante e non lo e': `hvci_on = False` e
    `scan_context.admin = False` sono esattamente i casi in cui il dato conta di
    piu', e un controllo di verita' li avrebbe scartati come vuoti.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def merge_specs(prev_data: dict | None, prev_meta: dict | None, new_data: dict | None,
                *, source: str, at: str) -> tuple[dict, dict]:
    """Fonde le specs in arrivo su quelle presenti. Ritorna (data, data_meta).

    `data_meta` e' `{campo: {"src": ..., "at": ...}}` e viene aggiornato solo per
    i campi che questa scansione ha davvero visto: la data di un campo assente
    resta indietro, ed e' esattamente quello che la rende leggibile come vecchia.
    """
    prev_data = prev_data or {}
    prev_meta = prev_meta or {}
    new_data = new_data or {}

    data = dict(prev_data)
    meta = {k: dict(v) for k, v in prev_meta.items() if isinstance(v, dict)}

    for chiave, valore in new_data.items():
        if is_empty(valore):
            continue
        data[chiave] = valore
        meta[chiave] = {"src": source, "at": at}

    # Un campo puo' esistere da prima che `data_meta` esistesse: senza una voce
    # sua non e' "mai visto", e' "visto prima che ne tenessimo traccia".
    for chiave in data:
        meta.setdefault(chiave, {"src": None, "at": None})

    return data, meta


def field_source(meta: dict | None, campo: str) -> str | None:
    return ((meta or {}).get(campo) or {}).get("src")


def field_seen_at(meta: dict | None, campo: str) -> str | None:
    return ((meta or {}).get(campo) or {}).get("at")


def stale_fields(meta: dict | None, latest_at: str | None) -> list[str]:
    """I campi che l'ultima scansione NON ha confermato.

    Non e' un elenco di errori: e' l'elenco di cio' che stiamo mostrando sulla
    fiducia di una misura precedente.
    """
    if not latest_at:
        return []
    return sorted(
        campo for campo, voce in (meta or {}).items()
        if isinstance(voce, dict) and voce.get("at") != latest_at
    )
