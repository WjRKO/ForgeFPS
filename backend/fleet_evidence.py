"""fleet_evidence.py — l'evidenza misurata dal Laboratorio, portata all'AI.

Il Laboratorio misura ogni tweak con run ripetuti, test di significativita' e
decisione kept/rolled_back, e accumula il risultato in `lab_fleet_stats`. Finora
quel dato serviva solo a riordinare la coda del Lab stesso: l'Advisor continuava
a consigliare senza vederlo, e poteva suggerire un tweak che sull'hardware
dell'utente era gia' stato misurato e scartato decine di volte.

Qui l'aggregato viene tradotto in poche righe di contesto per il prompt.

Da non confondere con `_community_insights` in routers/advisor.py: quello conta
quanti utenti hanno *dichiarato* di aver applicato un tweak (popolarita'), questo
riporta quante volte un tweak e' stato *misurato* e con che effetto (evidenza).
"""
from __future__ import annotations

# Sotto questa soglia il tasso di successo e' aneddoto, non statistica.
MIN_TESTED = 3
MAX_ITEMS = 6


def _rate(doc: dict) -> dict | None:
    tested = int(doc.get("tested") or 0)
    if tested < MIN_TESTED:
        return None
    kept = int(doc.get("kept") or 0)
    return {
        "tweak_id": doc.get("tweak_id"),
        "tested": tested,
        "kept": kept,
        "success_pct": round(100 * kept / tested),
        "avg_delta_pct": round(float(doc.get("delta_sum") or 0.0) / tested, 1),
        "scope": doc.get("scope") or "vendor",
    }


def pick_evidence(vendor_docs: list[dict], family_docs: list[dict],
                  limit: int = MAX_ITEMS) -> list[dict]:
    """Unisce i due livelli di aggregazione preferendo la famiglia hardware.

    Il documento di famiglia ('ryzen-7|rtx-30') descrive macchine molto piu'
    simili a quella dell'utente; quello di vendor ('nvidia_amd') e' un ripiego
    che pero' ha molti piu' campioni. Mai sommati: contano gli stessi test.
    """
    out: dict[str, dict] = {}
    for doc in vendor_docs or []:
        item = _rate(doc)
        if item and item["tweak_id"]:
            out[item["tweak_id"]] = item
    for doc in family_docs or []:
        item = _rate(doc)
        if item and item["tweak_id"]:
            item["scope"] = "family"
            out[item["tweak_id"]] = item
    items = list(out.values())
    # Prima l'evidenza piu' specifica, poi quella con l'effetto misurato maggiore,
    # a parita' quella con piu' campioni.
    items.sort(key=lambda i: (i["scope"] != "family", -i["avg_delta_pct"], -i["tested"]))
    return items[:limit]


def format_lines(items: list[dict], names: dict[str, str] | None = None) -> list[str]:
    """Righe da iniettare nel prompt. Esplicitano sempre la numerosita' del campione:
    senza, l'AI presenta come solido un dato che poggia su 3 misure."""
    names = names or {}
    lines = []
    for i in items or []:
        name = names.get(i["tweak_id"]) or i["tweak_id"]
        scope = "hardware della stessa famiglia" if i["scope"] == "family" else "hardware dello stesso tipo"
        # Due accortezze: la percentuale deve accompagnare il verbo giusto ("scartato
        # nel 14%" quando il 14% e' il tasso di mantenimento e' falso, e l'AI lo
        # ripete all'utente), e la formula evita l'articolo, che andrebbe elidato
        # davanti a certi numeri ("nell'86%") complicando la costruzione.
        if i["success_pct"] >= 50:
            verdetto = f"mantenuto {i['success_pct']}% delle volte"
        else:
            verdetto = f"scartato {100 - i['success_pct']}% delle volte"
        segno = "+" if i["avg_delta_pct"] >= 0 else ""
        lines.append(
            f"- '{name}': misurato {i['tested']} volte su {scope}, "
            f"{verdetto}, effetto medio {segno}{i['avg_delta_pct']}% sugli FPS"
        )
    return lines


async def load_for_specs(db, specs_data: dict | None, vendor_key: str | None,
                         family_key: str | None, limit: int = MAX_ITEMS) -> list[dict]:
    """Legge `lab_fleet_stats` per l'hardware dell'utente. Lista vuota se non c'e'
    abbastanza evidenza: meglio nessun contesto che un contesto sottile."""
    vendor_docs, family_docs = [], []
    if vendor_key:
        vendor_docs = await db.lab_fleet_stats.find(
            {"hw_class": vendor_key, "scope": {"$ne": "family"}}, {"_id": 0}).to_list(200)
    if family_key:
        family_docs = await db.lab_fleet_stats.find(
            {"hw_class": family_key, "scope": "family"}, {"_id": 0}).to_list(200)
    return pick_evidence(vendor_docs, family_docs, limit)
