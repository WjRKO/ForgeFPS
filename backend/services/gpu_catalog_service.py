"""
GPU reference catalog service — fuzzy match del modello rilevato dall'agent
verso il catalogo statico con score PassMark / 3DMark Time Spy noti.

Perche' e' un valore aggiunto per l'utente:
- Un utente con RTX 4070 che vede "il tuo Performance Score e' 68/100" non sa se e' buono.
- Con questo endpoint gli diciamo: "La tua RTX 4070 dovrebbe dare 20.500 punti G3D;
  il tuo Performance Score attuale suggerisce che stai facendo l'82% del reference —
  probabilmente driver vecchi o thermal throttling."
- Rende il PC scoring azionabile.

L'agent NON esegue un vero benchmark GPU (troppo complesso in PowerShell puro).
Usa questo lookup come proxy: se il tuo hardware sta sotto il 90% del reference,
allora c'e' qualcosa che non va.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).parent.parent / "data" / "gpu_catalog.json"


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, Any]:
    """Load once at first call. Cached in-process for the lifetime of the worker."""
    with _CATALOG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize(s: str) -> str:
    """Lowercase, remove common noise ('nvidia geforce', 'amd radeon', extra spaces).
    Also collapses 'RTX 4070Ti' -> 'rtx 4070 ti' (adds space before ti/xt/super/gre)."""
    if not s:
        return ""
    s = s.lower()
    # Strip trademark/copyright markers first (Intel loves them)
    s = re.sub(r"\(\s*(r|tm|c)\s*\)", " ", s)
    s = s.replace("nvidia geforce", "").replace("nvidia", "").replace("geforce", "")
    s = s.replace("amd radeon", "").replace("radeon", "").replace("amd", "")
    s = s.replace("intel arc", "arc").replace("intel", "")
    # Add space before ti/xt/super/gre if glued to the number
    s = re.sub(r"(\d)(ti|xt|super|gre)\b", r"\1 \2", s)
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _score_match(query: str, candidate: str) -> int:
    """Number of consecutive token matches. Longer specific tokens win over generic ones.
    Es. query 'rtx 4070 super' -> candidate 'rtx 4070 super' = 3 token match (full).
        query 'rtx 4070' -> candidate 'rtx 4070 super' = 2 token match (partial).
    """
    q_tokens = query.split()
    c_tokens = candidate.split()
    if not q_tokens or not c_tokens:
        return 0
    # All query tokens must appear in candidate (in order); count consecutive
    if all(t in c_tokens for t in q_tokens):
        return len(q_tokens)
    return 0


def find_gpu_reference(gpu_string: str) -> dict[str, Any] | None:
    """Ritorna il dict del reference per la GPU passata, o None se non trovata.

    Es. input 'NVIDIA GeForce RTX 4070 Ti SUPER' -> ritorna il record 'rtx 4070 ti super'.
    Preferisce SEMPRE il match piu' specifico (piu' token = piu' specifico).

    Response format:
      {
        "gpu_model": "rtx 4070 super",
        "vendor": "nvidia",
        "g3d": 22800,
        "timespy": 19000,
        "vram_gb": 12,
        "tdp_w": 220,
        "class": "high",
        "matched_query": "geforce rtx 4070 super"
      }
    """
    if not gpu_string:
        return None
    catalog = _load_catalog()
    normalized = _normalize(gpu_string)
    if not normalized:
        return None

    best_match: tuple[int, str, str, dict[str, Any]] | None = None
    for vendor, models in catalog.items():
        if vendor.startswith("_"):
            continue
        for model_key, model_data in models.items():
            # Prefer exact substring match — 'rtx 4070 super' in normalized query.
            if model_key in normalized:
                # Score = number of tokens matched (specificity).
                # 'rtx 4070 super' (3 tokens) beats 'rtx 4070' (2 tokens).
                score = len(model_key.split())
                if best_match is None or score > best_match[0]:
                    best_match = (score, vendor, model_key, model_data)

    if not best_match:
        return None
    _, vendor, model_key, data = best_match
    return {
        "gpu_model": model_key,
        "vendor": vendor,
        "matched_query": normalized,
        **data,
    }


def compute_health_vs_reference(reference: dict[str, Any], measured_perf_score: int) -> dict[str, Any]:
    """Given a measured Performance Score from the local benchmark (0-100 scale)
    and the reference score for this GPU, compute a health indicator.

    L'idea: il Performance Score locale sale con hardware migliore. Un utente con RTX 4090
    dovrebbe fare punteggio ~85-95. Se fa 55, c'e' un problema (throttling, driver, PSU).

    Molto approssimativo — la vera calibrazione arrivera' con il Full Benchmark
    multi-thread. Per ora e' un proxy grezzo.
    """
    if not reference or not reference.get("g3d"):
        return {"status": "unknown", "expected_perf_min": 0, "expected_perf_max": 100}
    # Defensive cap: dati legacy possono avere overall > 100 (pre-cap-a-100 dell'agent).
    # In quel caso ignora — non ha senso calcolare health con quella scala.
    if not isinstance(measured_perf_score, (int, float)) or measured_perf_score < 0 or measured_perf_score > 100:
        return {"status": "unknown", "reason": "measured_out_of_range", "measured_perf_score": measured_perf_score}

    g3d = reference["g3d"]
    # Empirical mapping G3D -> expected quick-bench Performance Score (very rough).
    # RTX 4090 (g3d 39000) -> expected ~90. RX 6600 (g3d 12500) -> expected ~55. GTX 1650 (5900) -> ~35.
    expected = min(95, int(30 + (g3d / 500)))
    # Tolerance band: +/- 8 points due to CPU/RAM/disk variance in the "quick" bench.
    lo, hi = max(0, expected - 8), min(100, expected + 8)

    status = "ok"
    delta = measured_perf_score - expected
    if measured_perf_score < lo - 5:
        status = "underperforming"  # >13 points below expected: real issue
    elif measured_perf_score < lo:
        status = "borderline"       # 5-13 points below: watch closely
    elif measured_perf_score > hi:
        status = "overperforming"   # Above expected: great cooling / overclocking

    return {
        "status": status,
        "expected_perf": expected,
        "expected_perf_min": lo,
        "expected_perf_max": hi,
        "delta": delta,
        "reference_g3d": g3d,
        "reference_timespy": reference.get("timespy"),
    }
