"""Registro versionato dei tweak del Laboratorio Automatico (Fase 1).

Fase 1: SOLO tweak senza riavvio (safe + medium), applicabilita' valutata sulle
pc_specs reali dell'utente, prior statici per il motore di selezione. Gli id
corrispondono al catalogo $TWEAKS dell'agent PowerShell (apply/rollback reali).
"""
import re

REGISTRY_VERSION = "1.0.0"
PRIOR_THRESHOLD = 0.10

_RISK_ORDER = {"safe": 0, "medium": 1, "expert": 2, "hardware": 3}


def _is_nvidia(specs: dict) -> bool:
    gpu = (specs.get("gpu") or "")
    return bool(re.search(r"nvidia|geforce|rtx|gtx", gpu, re.I))


TWEAKS = [
    {
        "tweak_id": "power", "name": "Piano energetico prestazioni massime",
        "family": "power", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.35, "conflicts_with": [], "synergy_candidates": ["power_throttling"],
        "why": "Core parking e throttling limitano la CPU nei momenti di picco.",
    },
    {
        "tweak_id": "priority", "name": "Priorita GPU/CPU ai giochi (MMCSS)",
        "family": "scheduling", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.25, "conflicts_with": [], "synergy_candidates": ["gaming"],
        "why": "SystemResponsiveness=0 da priorita reale al gioco in primo piano.",
    },
    {
        "tweak_id": "gaming", "name": "Boost gaming (Game Mode, Game DVR off)",
        "family": "scheduling", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.24, "conflicts_with": [], "synergy_candidates": ["priority"],
        "why": "Il Game DVR ruba CPU/GPU registrando in background.",
    },
    {
        "tweak_id": "power_throttling", "name": "Power Throttling OFF",
        "family": "power", "risk_level": "medium", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.20, "conflicts_with": [], "synergy_candidates": ["power"],
        "why": "Windows limita i processi in background che il gioco potrebbe usare.",
    },
    {
        "tweak_id": "bgapps", "name": "App in background OFF",
        "family": "services", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.18, "conflicts_with": [], "synergy_candidates": [],
        "why": "Le app UWP in background consumano CPU e RAM durante il gioco.",
    },
    {
        "tweak_id": "standby_clear", "name": "Svuota RAM standby",
        "family": "memory", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.15, "conflicts_with": [], "synergy_candidates": [],
        "why": "La standby list piena causa micro-stutter negli accessi memoria.",
    },
    {
        "tweak_id": "telemetry", "name": "Telemetria Windows OFF (DiagTrack)",
        "family": "services", "risk_level": "medium", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.14, "conflicts_with": [], "synergy_candidates": ["search_index", "sysmain"],
        "why": "DiagTrack genera I/O e CPU in background.",
    },
    {
        "tweak_id": "gamebar_rec", "name": "Xbox Game Bar recording OFF",
        "family": "capture", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.14, "conflicts_with": [], "synergy_candidates": [],
        "why": "La registrazione di sfondo della Game Bar pesa su GPU/disco.",
    },
    {
        "tweak_id": "nvidia_tel", "name": "NVIDIA: telemetria OFF",
        "family": "gpu_vendor", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.12, "conflicts_with": [], "synergy_candidates": [],
        "applicable": _is_nvidia, "applicability_note": "Solo GPU NVIDIA",
        "why": "Task e servizi di telemetria NVIDIA girano in background.",
    },
    {
        "tweak_id": "sysmain", "name": "SysMain/Superfetch OFF",
        "family": "services", "risk_level": "medium", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.12, "conflicts_with": [], "synergy_candidates": ["telemetry"],
        "why": "Il prefetching aggressivo puo' causare I/O e stutter su alcuni sistemi.",
    },
    {
        "tweak_id": "search_index", "name": "Windows Search indexing OFF",
        "family": "services", "risk_level": "medium", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.11, "conflicts_with": [], "synergy_candidates": ["telemetry"],
        "why": "L'indicizzazione a scatti consuma CPU e disco durante il gioco.",
    },
    {
        "tweak_id": "visual", "name": "Effetti visivi Windows in performance",
        "family": "shell", "risk_level": "safe", "requires_reboot": False, "reversible": "auto",
        "base_prior": 0.08, "conflicts_with": [], "synergy_candidates": [],
        "why": "Impatto quasi nullo in fullscreen: prior basso, di solito filtrato.",
    },
]


def select_candidates(specs_data: dict, risk_level: str = "medium"):
    """Motore di selezione (spec 2/Fase 3): filtra per rischio + applicabilita',
    scarta prior <= soglia, ordina per prior decrescente.
    Ritorna (candidates, skipped)."""
    specs_data = specs_data or {}
    max_risk = _RISK_ORDER.get(risk_level, 1)
    candidates, skipped = [], []
    for t in TWEAKS:
        entry = {k: v for k, v in t.items() if k != "applicable"}
        if t.get("requires_reboot"):
            skipped.append({"tweak_id": t["tweak_id"], "reason": "richiede riavvio (Fase 2)"})
            continue
        if _RISK_ORDER.get(t["risk_level"], 0) > max_risk:
            skipped.append({"tweak_id": t["tweak_id"], "reason": f"rischio {t['risk_level']} > livello scelto ({risk_level})"})
            continue
        fn = t.get("applicable")
        if fn and not fn(specs_data):
            skipped.append({"tweak_id": t["tweak_id"], "reason": t.get("applicability_note", "non applicabile a questo hardware")})
            continue
        if t["base_prior"] <= PRIOR_THRESHOLD:
            skipped.append({"tweak_id": t["tweak_id"], "reason": f"prior {t['base_prior']:.2f} <= soglia {PRIOR_THRESHOLD}"})
            continue
        entry["prior"] = t["base_prior"]
        candidates.append(entry)
    candidates.sort(key=lambda c: -c["prior"])
    return candidates, skipped
