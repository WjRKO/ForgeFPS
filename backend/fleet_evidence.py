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

import math
import re

from lab_stats import wilson_ci

# Sotto questa soglia il tasso di successo e' aneddoto, non statistica.
MIN_TESTED = 3
# Sotto questa il numero va accompagnato dal suo intervallo: '2 su 3' letto come
# '67%' e' un'affermazione che i dati non sostengono.
THIN_TESTED = 10
MAX_ITEMS = 6


def _slug(s) -> str | None:
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").lower()).strip("_")[:40] or None


def _delta_sd(tested: int, dsum: float, dsq) -> float | None:
    """Deviazione standard dei delta misurati, se l'aggregato la conserva."""
    if tested < 2 or dsq is None:
        return None
    var = (float(dsq) - dsum * dsum / tested) / (tested - 1)
    return round(math.sqrt(var), 1) if var > 0 else 0.0


def _rate(doc: dict, game_key: str | None = None) -> dict | None:
    """Un documento di aggregato -> una riga di evidenza.

    Quando l'utente sta giocando a un titolo per cui esiste gia' un breakdown
    con abbastanza misure, si usa quello: un tweak puo' aiutare in un gioco
    CPU-bound e non fare nulla in uno GPU-bound, e la media dei due non
    descrive nessuno dei due casi.
    """
    tested = int(doc.get("tested") or 0)
    kept = int(doc.get("kept") or 0)
    dsum = float(doc.get("delta_sum") or 0.0)
    dsq = doc.get("delta_sq_sum")
    scope = doc.get("scope") or "vendor"
    per_game = ((doc.get("games") or {}).get(game_key) if game_key else None) or {}
    if int(per_game.get("tested") or 0) >= MIN_TESTED:
        tested = int(per_game["tested"])
        kept = int(per_game.get("kept") or 0)
        dsum = float(per_game.get("delta_sum") or 0.0)
        dsq = None
        scope = f"{scope}+game"
    if tested < MIN_TESTED:
        return None
    lo, hi = wilson_ci(kept, tested)
    return {
        "tweak_id": doc.get("tweak_id"),
        "tested": tested,
        "kept": kept,
        "success_pct": round(100 * kept / tested),
        "success_ci_pct": [round(100 * lo), round(100 * hi)],
        "avg_delta_pct": round(dsum / tested, 1),
        "delta_sd_pct": _delta_sd(tested, dsum, dsq),
        "thin": tested < THIN_TESTED,
        "scope": scope,
    }


def pick_evidence(vendor_docs: list[dict], family_docs: list[dict],
                  limit: int = MAX_ITEMS, game: str | None = None) -> list[dict]:
    """Unisce i due livelli di aggregazione preferendo la famiglia hardware.

    Il documento di famiglia ('ryzen-7|rtx-30') descrive macchine molto piu'
    simili a quella dell'utente; quello di vendor ('nvidia_amd') e' un ripiego
    che pero' ha molti piu' campioni. Mai sommati: contano gli stessi test.
    """
    gk = _slug(game)
    out: dict[str, dict] = {}
    for doc in vendor_docs or []:
        item = _rate(doc, gk)
        if item and item["tweak_id"]:
            out[item["tweak_id"]] = item
    for doc in family_docs or []:
        item = _rate(doc, gk)
        if item and item["tweak_id"]:
            item["scope"] = "family+game" if item["scope"].endswith("+game") else "family"
            out[item["tweak_id"]] = item
    items = list(out.values())
    # Prima l'evidenza piu' specifica, poi quella con l'effetto misurato maggiore,
    # a parita' quella con piu' campioni.
    items.sort(key=lambda i: (not i["scope"].startswith("family"), -i["avg_delta_pct"], -i["tested"]))
    return items[:limit]


def format_lines(items: list[dict], names: dict[str, str] | None = None) -> list[str]:
    """Righe da iniettare nel prompt. Esplicitano sempre la numerosita' del campione:
    senza, l'AI presenta come solido un dato che poggia su 3 misure."""
    names = names or {}
    lines = []
    for i in items or []:
        name = names.get(i["tweak_id"]) or i["tweak_id"]
        scope = "hardware della stessa famiglia" if i["scope"].startswith("family") else "hardware dello stesso tipo"
        if i["scope"].endswith("+game"):
            scope += " sullo stesso gioco"
        # Due accortezze: la percentuale deve accompagnare il verbo giusto ("scartato
        # nel 14%" quando il 14% e' il tasso di mantenimento e' falso, e l'AI lo
        # ripete all'utente), e la formula evita l'articolo, che andrebbe elidato
        # davanti a certi numeri ("nell'86%") complicando la costruzione.
        if i["success_pct"] >= 50:
            verdetto = f"mantenuto {i['success_pct']}% delle volte"
        else:
            verdetto = f"scartato {100 - i['success_pct']}% delle volte"
        segno = "+" if i["avg_delta_pct"] >= 0 else ""
        riga = (f"- '{name}': misurato {i['tested']} volte su {scope}, "
                f"{verdetto}, effetto medio {segno}{i['avg_delta_pct']}% sugli FPS")
        if i.get("delta_sd_pct"):
            riga += f" (deviazione {i['delta_sd_pct']} punti)"
        # Con pochi campioni la percentuale da sola e' una precisione finta:
        # l'intervallo dice all'AI quanto puo' appoggiarsi al numero.
        if i.get("thin") and i.get("success_ci_pct"):
            lo, hi = i["success_ci_pct"]
            riga += (f" — campione piccolo: il tasso reale sta tra {lo}% e {hi}%, "
                     f"presentalo come indicazione, non come prova")
        lines.append(riga)
    return lines


async def load_for_specs(db, specs_data: dict | None, vendor_key: str | None,
                         family_key: str | None, limit: int = MAX_ITEMS,
                         game: str | None = None) -> list[dict]:
    """Legge `lab_fleet_stats` per l'hardware dell'utente. Lista vuota se non c'e'
    abbastanza evidenza: meglio nessun contesto che un contesto sottile."""
    vendor_docs, family_docs = [], []
    if vendor_key:
        vendor_docs = await db.lab_fleet_stats.find(
            {"hw_class": vendor_key, "scope": {"$ne": "family"}}, {"_id": 0}).to_list(200)
    if family_key:
        family_docs = await db.lab_fleet_stats.find(
            {"hw_class": family_key, "scope": "family"}, {"_id": 0}).to_list(200)
    return pick_evidence(vendor_docs, family_docs, limit, game)
