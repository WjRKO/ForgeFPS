"""system_changes.py — "cos'e' cambiato nel tuo PC".

`pc_specs` viene sovrascritto a ogni sync: la storia delle configurazioni non
esiste da nessuna parte. Qui il diff viene calcolato **al momento della scrittura**
(dove prev e new sono entrambi disponibili) e ne viene salvato solo il delta nella
collezione `system_changes`, append-only.

Il valore non e' la timeline in se': e' poter rispondere a "perche' il mio PC va
peggio di due settimane fa" incrociando i cambiamenti con le serie di performance
gia' raccolte (benchmark, health score).

Tutte le funzioni sono pure: nessun db, nessuna rete.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Campi di `pc_specs.data` sorvegliati.
#   key -> (label, impact)
# impact: quanto e' plausibile che il cambiamento spieghi una variazione di performance.
WATCHED_FIELDS: dict[str, tuple[str, str]] = {
    "gpu_driver_version": ("Driver GPU", "high"),
    "ram_speed_mhz": ("Velocita RAM", "high"),
    "rebar_status": ("Resizable BAR", "high"),
    "cpu": ("CPU", "high"),
    "gpu": ("GPU", "high"),
    "ram": ("RAM installata", "high"),
    "ram_modules": ("Moduli RAM", "high"),
    "os_build": ("Build di Windows", "medium"),
    "bios": ("BIOS", "medium"),
    "motherboard": ("Scheda madre", "medium"),
    "refresh_hz": ("Refresh del monitor", "medium"),
    "resolution": ("Risoluzione", "medium"),
    "gpu_secondary": ("GPU secondaria", "low"),
    "cpu_socket": ("Socket CPU", "low"),
}

# Quante voci di avvio elencare per esteso nell'evento (il conteggio resta completo).
MAX_STARTUP_NAMES = 5

# Soglia oltre la quale una variazione di performance e' considerata reale e non
# rumore di misura: i benchmark ripetuti sullo stesso PC ballano di qualche punto.
REGRESSION_PCT = 5.0

# Tolleranza sul bordo destro della finestra di correlazione.
# Un singolo sync scrive prima il record di health e poi gli eventi di cambiamento:
# senza tolleranza il cambiamento risulta posteriore alla misura di qualche
# millisecondo e verrebbe scartato proprio nel caso piu' comune.
CORRELATION_TOLERANCE_S = 300


def _norm(v) -> str:
    return str(v).strip() if v is not None else ""


def diff_specs(prev_data: dict | None, new_data: dict | None) -> list[dict]:
    """Confronta due snapshot di `pc_specs.data` e ritorna gli eventi di cambiamento.

    Un campo che compare per la prima volta NON e' un cambiamento: al primo sync
    risulterebbe "cambiato" tutto. Stesso discorso per un campo che sparisce (scan
    parziale, agent senza admin) — segnalarlo produrrebbe un falso allarme a ogni
    run degradato.
    """
    prev, new = prev_data or {}, new_data or {}
    out: list[dict] = []
    for key, (label, impact) in WATCHED_FIELDS.items():
        before, after = _norm(prev.get(key)), _norm(new.get(key))
        if not before or not after or before == after:
            continue
        out.append({"kind": key, "label": label, "impact": impact, "from": before, "to": after})
    return out


def _startup_names(items: list | None) -> set[str]:
    """Nomi delle voci di avvio ATTIVE. Accetta sia list[str] (agent legacy) sia
    list[dict] (agent attuale), come fa report-specs."""
    names = set()
    for it in items or []:
        if isinstance(it, str):
            name = it
        elif isinstance(it, dict):
            if it.get("enabled") is False:
                continue
            name = it.get("name") or ""
        else:
            continue
        name = _norm(name)
        if name:
            names.add(name)
    return names


def diff_startup(prev_startup: list | None, new_startup: list | None) -> list[dict]:
    """Programmi all'avvio aggiunti o rimossi tra due sync."""
    # `None` = l'agent non ha inviato la sezione, che e' diverso da "lista vuota".
    if prev_startup is None or new_startup is None:
        return []
    before, after = _startup_names(prev_startup), _startup_names(new_startup)
    if not before and not after:
        return []
    added, removed = sorted(after - before), sorted(before - after)
    out = []
    if added:
        out.append({
            "kind": "startup_added", "label": "Nuovi programmi all'avvio", "impact": "medium",
            "from": None, "to": ", ".join(added[:MAX_STARTUP_NAMES]), "count": len(added),
        })
    if removed:
        out.append({
            "kind": "startup_removed", "label": "Programmi all'avvio rimossi", "impact": "low",
            "from": ", ".join(removed[:MAX_STARTUP_NAMES]), "to": None, "count": len(removed),
        })
    return out


def build_change_events(prev: dict | None, new_data: dict | None,
                        new_startup: list | None) -> list[dict]:
    """Tutti gli eventi generati da un singolo sync dell'agent.

    `prev` e' il documento `pc_specs` precedente (con `data` e `startup`);
    `new_data` / `new_startup` sono i valori in arrivo, gia' normalizzati.
    """
    prev = prev or {}
    events = diff_specs(prev.get("data"), new_data)
    events += diff_startup(prev.get("startup"), new_startup)
    return events


# ---------- correlazione con le serie di performance ----------

def _parse_ts(v):
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def analyze_trend(series: list[dict]) -> dict | None:
    """Confronta l'ultimo punto della serie con la mediana dei precedenti.

    La mediana e' voluta: un singolo benchmark fatto mentre girava un download
    sposta la media e produrrebbe un falso allarme di regressione.

    `series`: [{"at": iso, "value": number}, ...] in qualsiasi ordine.
    Ritorna None sotto i 3 punti: con 2 non si distingue un trend dal rumore.
    """
    pts = []
    for p in series or []:
        ts, val = _parse_ts(p.get("at")), p.get("value")
        if ts is None or not isinstance(val, (int, float)) or isinstance(val, bool) or val <= 0:
            continue
        pts.append((ts, float(val)))
    if len(pts) < 3:
        return None
    pts.sort(key=lambda x: x[0])
    current_at, current = pts[-1]
    prev_vals = sorted(v for _, v in pts[:-1])
    n = len(prev_vals)
    baseline = prev_vals[n // 2] if n % 2 else (prev_vals[n // 2 - 1] + prev_vals[n // 2]) / 2
    if baseline <= 0:
        return None
    delta_pct = round((current - baseline) / baseline * 100, 1)
    direction = "down" if delta_pct <= -REGRESSION_PCT else ("up" if delta_pct >= REGRESSION_PCT else "stable")
    return {
        "current": round(current, 1),
        "baseline": round(baseline, 1),
        "delta_pct": delta_pct,
        "direction": direction,
        "current_at": current_at.isoformat(),
        "since": pts[0][0].isoformat(),
        "samples": len(pts),
    }


def correlate(trend: dict | None, changes: list[dict]) -> list[dict]:
    """Cambiamenti avvenuti tra il primo punto della serie e l'ultimo, ordinati
    per plausibilita' (impatto) e, a parita', dal piu' recente.

    Nessuna pretesa di causalita': e' un elenco di sospetti nella finestra giusta,
    che e' esattamente cio' che serve all'utente per sapere dove guardare.
    """
    if not trend:
        return []
    start, end = _parse_ts(trend.get("since")), _parse_ts(trend.get("current_at"))
    if not start or not end:
        return []
    # Un cambiamento successivo alla misura non puo' spiegarla: la finestra si chiude
    # sull'ultimo rilevamento, con la sola tolleranza per gli eventi dello stesso sync.
    end = end + timedelta(seconds=CORRELATION_TOLERANCE_S)
    rank = {"high": 0, "medium": 1, "low": 2}
    picked = []
    for c in changes or []:
        at = _parse_ts(c.get("created_at") or c.get("at"))
        if at and start <= at <= end:
            picked.append((rank.get(c.get("impact"), 3), -at.timestamp(), c))
    picked.sort(key=lambda x: (x[0], x[1]))
    return [c for _, _, c in picked]
