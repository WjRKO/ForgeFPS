"""hardware.py — classificazione hardware condivisa (famiglia CPU/GPU).

Estratto da routers/pc.py (fleet-percentile) per essere riusato da chiunque debba
raggruppare utenti per hardware simile: percentili di flotta, community insights
dell'advisor, aggregazione degli effetti dei tweak.

Le funzioni sono pure e sincrone: testabili senza database ne' rete.
"""
from __future__ import annotations


def cpu_family(cpu_str: str | None) -> str | None:
    """'AMD Ryzen 7 5800X3D' -> 'ryzen-7'. None se non riconosciuta."""
    s = (cpu_str or "").lower()
    if not s:
        return None
    if "ultra" in s:
        for t in ("9", "7", "5", "3"):
            if f"ultra {t}" in s or f"ultra{t}" in s:
                return f"intel-ultra-{t}"
    if "ryzen" in s or "amd" in s:
        for t in ("9", "7", "5", "3"):
            if f"ryzen {t}" in s or f"ryzen{t}" in s:
                return f"ryzen-{t}"
    for t in ("i9", "i7", "i5", "i3"):
        if t in s:
            return f"intel-{t}"
    return None


def gpu_family(gpu_str: str | None) -> str | None:
    """'NVIDIA GeForce RTX 3070' -> 'rtx-30'. None se non riconosciuta."""
    s = (gpu_str or "").lower()
    if not s:
        return None
    if "rtx" in s:
        for gen in ("50", "40", "30", "20"):
            if f"rtx {gen}" in s or f"rtx{gen}" in s:
                return f"rtx-{gen}"
        return "rtx"
    if "gtx" in s:
        return "gtx"
    if "arc" in s and "intel" in s:
        return "intel-arc"
    if "rx" in s:
        for gen in ("9", "8", "7", "6", "5"):
            if f"rx {gen}" in s or f"rx{gen}" in s:
                return f"radeon-rx-{gen}000"
        return "radeon-rx"
    return None


def hardware_class(data: dict | None) -> dict:
    """Estrae le famiglie da un doc `pc_specs.data`. Ritorna sempre le due chiavi."""
    d = data or {}
    return {"cpu_family": cpu_family(d.get("cpu")), "gpu_family": gpu_family(d.get("gpu"))}


def is_similar(a: dict | None, b: dict | None) -> bool:
    """Due macchine sono 'simili' se condividono la famiglia CPU **o** la famiglia GPU.

    Stessa definizione usata da /api/benchmarks/fleet-percentile: volutamente larga,
    perche' su una flotta piccola un match esatto CPU+GPU produrrebbe campioni da 0-1
    utenti. Le famiglie None non matchano mai (evita di considerare simili due PC
    solo perche' di entrambi non sappiamo nulla).
    """
    ha, hb = hardware_class(a), hardware_class(b)
    if ha["cpu_family"] and ha["cpu_family"] == hb["cpu_family"]:
        return True
    if ha["gpu_family"] and ha["gpu_family"] == hb["gpu_family"]:
        return True
    return False


def fleet_key(data: dict | None) -> str | None:
    """Chiave di aggregazione fine per le statistiche di flotta: 'ryzen-7|rtx-30'.

    Piu' selettiva del raggruppamento per vendor usato finora dal Lab
    (`nvidia_amd`), che mette una RTX 3050 e una RTX 5090 nello stesso gruppo.
    None quando nessuna delle due famiglie e' riconoscibile: senza famiglie la
    chiave sarebbe 'none|none', cioe' un raccoglitore di PC scollegati tra loro.
    """
    h = hardware_class(data)
    cpu, gpu = h["cpu_family"], h["gpu_family"]
    if not cpu and not gpu:
        return None
    return f"{cpu or 'any'}|{gpu or 'any'}"


def vendor_class(data: dict | None) -> str:
    """Chiave grossolana per vendor: 'nvidia_amd'. Usata dal Lab dal primo giorno.

    Meno predittiva di `fleet_key` (una RTX 3050 e una RTX 5090 finiscono insieme)
    ma con molti piu' campioni, quindi resta il ripiego quando la chiave fine non
    ha ancora abbastanza misure. Ritorna sempre una stringa: e' una chiave di
    aggregazione, non un'affermazione sull'hardware.
    """
    import re as _re
    d = data or {}
    gpu, cpu = d.get("gpu") or "", d.get("cpu") or ""
    gv = ("nvidia" if _re.search(r"nvidia|geforce|rtx|gtx", gpu, _re.I)
          else ("amd" if _re.search(r"amd|radeon|rx", gpu, _re.I) else "other"))
    cv_ = ("intel" if "intel" in cpu.lower()
           else ("amd" if _re.search(r"amd|ryzen", cpu, _re.I) else "other"))
    return f"{gv}_{cv_}"
