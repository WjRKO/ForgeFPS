"""watchdog.py — verifica differita degli interventi di ottimizzazione.

Auto-Pilot e Laboratorio misurano l'effetto *nell'istante* in cui applicano i
tweak. Nessuno controlla come sta il PC due giorni dopo: se un tweak peggiora le
cose, l'utente non lo scopre, e quando lo scopre da' la colpa a FrameForge.

Qui si definisce quando e come verificare, e cosa contare come regressione.
Logica pura: nessun db, nessuna rete.

## Perche' la metrica e' l'health score

Il benchmark e' la misura piu' fedele, ma sporadica: aspettare che l'utente ne
rifaccia uno spontaneamente significa non verificare mai. L'health score viene
invece registrato a ogni sync dell'agent, quindi la verifica avviene davvero.
Il benchmark resta il segnale usato da `system_changes.analyze_trend`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Quanto aspettare prima di giudicare: sotto le 24h si misura l'effetto immediato,
# che Auto-Pilot ha gia' registrato. L'obiettivo qui e' l'effetto che resta.
VERIFY_AFTER_HOURS = 48

# Oltre quanti giorni dall'intervento smettere di aspettare misure.
GIVE_UP_AFTER_DAYS = 14

# Un calo sotto questa soglia e' rumore: l'health score oscilla con i file
# temporanei e lo spazio libero anche senza che nessuno tocchi nulla.
REGRESSION_PCT = 8.0
IMPROVEMENT_PCT = 5.0

# Un solo campione post-intervento puo' essere un sync fatto a PC carico.
MIN_SAMPLES_AFTER = 2


def parse_ts(v):
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def due_at(created_at: str, hours: int = VERIFY_AFTER_HOURS) -> str | None:
    ts = parse_ts(created_at)
    return (ts + timedelta(hours=hours)).isoformat() if ts else None


def expired_at(created_at: str, days: int = GIVE_UP_AFTER_DAYS) -> str | None:
    ts = parse_ts(created_at)
    return (ts + timedelta(days=days)).isoformat() if ts else None


def _median(values: list[float]) -> float:
    vals = sorted(values)
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def evaluate(baseline: float | None, samples_after: list[float]) -> dict:
    """Confronta la baseline dell'intervento con le misure successive.

    Ritorna `{"status": ..., "delta_pct": ..., "samples": n, "observed": mediana}`.
    status:
      - `waiting`    campioni insufficienti, riprovare piu' tardi
      - `regressed`  il PC sta peggio: va segnalato
      - `improved`   il guadagno ha tenuto
      - `held`       nessuna variazione degna di nota (l'esito piu' comune e
                     desiderabile: l'intervento non si e' degradato)
    """
    clean = [float(v) for v in (samples_after or [])
             if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
    if not baseline or baseline <= 0 or len(clean) < MIN_SAMPLES_AFTER:
        return {"status": "waiting", "delta_pct": None, "samples": len(clean), "observed": None}
    observed = _median(clean)
    delta_pct = round((observed - baseline) / baseline * 100, 1)
    if delta_pct <= -REGRESSION_PCT:
        status = "regressed"
    elif delta_pct >= IMPROVEMENT_PCT:
        status = "improved"
    else:
        status = "held"
    return {"status": status, "delta_pct": delta_pct,
            "samples": len(clean), "observed": round(observed, 1)}


def notification_for(verdict: dict, source: str, baseline: float) -> dict | None:
    """Testo della notifica, o None se non c'e' niente da dire.

    Solo le regressioni interrompono l'utente: una notifica "tutto bene" a ogni
    intervento addestra a ignorare le notifiche, regressione inclusa.
    """
    if verdict.get("status") != "regressed":
        return None
    label = "Auto-Pilot" if source == "autopilot" else "Laboratorio"
    observed = verdict.get("observed")
    return {
        "title": "Le prestazioni sono calate",
        "body": (f"Dopo l'ultimo {label} il tuo Health Score e' passato da "
                 f"{int(baseline)} a {int(observed)} ({verdict['delta_pct']}%). "
                 f"Puoi ripristinare il backup dei tweak."),
        "link": "/app/pc",
    }
