"""FrameForge Missions — obiettivi attivi verificati sui dati reali dell'agent.

Differenza con milestones: le milestones sono trofei passivi a vita; le missioni
sono obiettivi ATTIVI (max 3 alla volta) con baseline all'attivazione e verifica
automatica sui dati gia' raccolti (scan, benchmark, lab, boost, rete).
Completamento -> XP nello stesso pool tier di user_progress.

Modes di verifica:
- delta:    contatore user_progress (baseline catturata all'attivazione)
- since:    conteggio documenti con timestamp >= activated_at
- absolute: valore corrente (es. health score)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAX_ACTIVE = 3
STARTER_MISSIONS = ["svc_purge", "bench_first", "advisor_consult"]

MISSIONS_CATALOG: list[dict[str, Any]] = [
    {
        "code": "svc_purge", "category": "performance", "xp": 60, "icon": "Wrench",
        "metric": "services_done", "mode": "since", "target": 2, "link": "/app/pc",
        "name_it": "Caccia ai servizi", "name_en": "Service hunt",
        "desc_it": "Disattiva 2 servizi Windows consigliati nella pagina Il mio PC. Verifichiamo al prossimo scan.",
        "desc_en": "Disable 2 recommended Windows services from the My PC page. Verified on your next scan.",
        "cta_it": "Vai ai servizi", "cta_en": "Go to services",
    },
    {
        "code": "startup_slim", "category": "performance", "xp": 50, "icon": "Zap",
        "metric": "startup_done", "mode": "since", "target": 2, "link": "/app/pc",
        "name_it": "Avvio pulito", "name_en": "Clean boot",
        "desc_it": "Disattiva 2 app all'avvio tra quelle segnalate. Verificato automaticamente allo scan successivo.",
        "desc_en": "Disable 2 flagged startup apps. Automatically verified on the next scan.",
        "cta_it": "Vai all'avvio", "cta_en": "Go to startup",
    },
    {
        "code": "bench_first", "category": "benchmark", "xp": 40, "icon": "Gauge",
        "metric": "benchmarks", "mode": "since", "target": 1, "link": "/app/benchmark",
        "name_it": "Misura la potenza", "name_en": "Measure the power",
        "desc_it": "Completa un benchmark con l'agent per fotografare le prestazioni del tuo PC.",
        "desc_en": "Complete one benchmark with the agent to snapshot your PC's performance.",
        "cta_it": "Avvia benchmark", "cta_en": "Run benchmark",
    },
    {
        "code": "health_80", "category": "performance", "xp": 60, "icon": "HeartPulse",
        "metric": "health_score", "mode": "absolute", "target": 80, "link": "/app/pc",
        "name_it": "Salute di ferro", "name_en": "Iron health",
        "desc_it": "Porta l'Health Score del tuo PC ad almeno 80 seguendo i consigli dell'app.",
        "desc_en": "Bring your PC Health Score to at least 80 by following the app's advice.",
        "cta_it": "Vedi salute PC", "cta_en": "View PC health",
    },
    {
        "code": "scan_week", "category": "habit", "xp": 40, "icon": "Activity",
        "metric": "pc_scans", "mode": "delta", "target": 3, "link": "/app/desktop",
        "name_it": "Sotto controllo", "name_en": "Under control",
        "desc_it": "Esegui 3 scan con l'agent per tenere aggiornati salute e telemetria.",
        "desc_en": "Run 3 agent scans to keep health and telemetry up to date.",
        "cta_it": "Apri l'agent", "cta_en": "Open the agent",
    },
    {
        "code": "advisor_consult", "category": "ai", "xp": 20, "icon": "Sparkles",
        "metric": "advisor_messages", "mode": "delta", "target": 1, "link": "/app/advisor",
        "name_it": "Chiedi al coach", "name_en": "Ask the coach",
        "desc_it": "Fai una domanda all'AI Advisor: conosce il tuo hardware e il tuo health score.",
        "desc_en": "Ask the AI Advisor a question: it knows your hardware and health score.",
        "cta_it": "Apri Advisor", "cta_en": "Open Advisor",
    },
    {
        "code": "tweak_hero", "category": "performance", "xp": 50, "icon": "Cpu",
        "metric": "tweaks_applied", "mode": "delta", "target": 3, "link": "/app/desktop",
        "name_it": "Mano al motore", "name_en": "Hands on the engine",
        "desc_it": "Applica 3 tweak sicuri e reversibili tramite l'agent FrameForge.",
        "desc_en": "Apply 3 safe, reversible tweaks via the FrameForge agent.",
        "cta_it": "Apri l'agent", "cta_en": "Open the agent",
    },
    {
        "code": "net_check", "category": "network", "xp": 30, "icon": "Radio",
        "metric": "net_tests", "mode": "since", "target": 1, "link": "/app/network",
        "name_it": "Linea sotto esame", "name_en": "Line under review",
        "desc_it": "Esegui il test di rete (bufferbloat) per scoprire se la tua connessione regge il gaming.",
        "desc_en": "Run the network (bufferbloat) test to see if your connection is game-ready.",
        "cta_it": "Testa la rete", "cta_en": "Test network",
    },
    {
        "code": "boost_match", "category": "gaming", "xp": 40, "icon": "Gamepad2",
        "metric": "boost_sessions", "mode": "since", "target": 1, "link": "/app/gaming",
        "name_it": "Partita boostata", "name_en": "Boosted match",
        "desc_it": "Completa una sessione di gioco con il Boost attivo: l'agent ottimizza e ripristina da solo.",
        "desc_en": "Complete one gaming session with Boost on: the agent optimizes and restores automatically.",
        "cta_it": "Vai al Gaming", "cta_en": "Go to Gaming",
    },
    {
        "code": "lab_scientist", "category": "lab", "xp": 100, "icon": "Timer",
        "metric": "lab_completed", "mode": "since", "target": 1, "link": "/app/lab",
        "name_it": "Scienziato delle prestazioni", "name_en": "Performance scientist",
        "desc_it": "Completa un esperimento del Performance Lab con validazione statistica.",
        "desc_en": "Complete one Performance Lab experiment with statistical validation.",
        "cta_it": "Apri il Lab", "cta_en": "Open the Lab",
    },
]

MISSION_BY_CODE = {m["code"]: m for m in MISSIONS_CATALOG}
_COUNTER_METRICS = {"pc_scans", "advisor_messages", "tweaks_applied"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _metric_value(db, uid: str, metric: str, since_iso: str | None) -> int:
    if metric in _COUNTER_METRICS:
        p = await db.user_progress.find_one({"user_id": uid}, {"counters": 1})
        return int(((p or {}).get("counters") or {}).get(metric, 0))
    if metric in ("services_done", "startup_done"):
        doc = await db.pc_specs.find_one({"user_id": uid}, {metric: 1})
        items = [i for i in ((doc or {}).get(metric) or []) if isinstance(i, dict)]
        if since_iso:
            items = [i for i in items if str(i.get("done_at") or "") >= since_iso]
        return len(items)
    if metric == "benchmarks":
        return await db.benchmarks.count_documents({"user_id": uid, "created_at": {"$gte": since_iso or ""}})
    if metric == "boost_sessions":
        return await db.boost_sessions.count_documents({"user_id": uid, "created_at": {"$gte": since_iso or ""}})
    if metric == "lab_completed":
        return await db.lab_sessions.count_documents(
            {"user_id": uid, "status": "completed", "started_at": {"$gte": since_iso or ""}})
    if metric == "net_tests":
        doc = await db.net_results.find_one({"user_id": uid}, {"updated_at": 1})
        return 1 if doc and str(doc.get("updated_at") or "") >= (since_iso or "") else 0
    if metric == "health_score":
        doc = await db.health_history.find_one({"user_id": uid}, sort=[("created_at", -1)])
        return int(doc["score"]) if doc and doc.get("score") is not None else 0
    return 0


async def _activation_record(db, uid: str, mission: dict) -> dict:
    rec = {"activated_at": _now_iso(), "baseline": 0}
    if mission["mode"] == "delta":
        rec["baseline"] = await _metric_value(db, uid, mission["metric"], None)
    return rec


async def _progress(db, uid: str, mission: dict, state: dict) -> int:
    since = state.get("activated_at")
    cur = await _metric_value(db, uid, mission["metric"], since if mission["mode"] == "since" else None)
    if mission["mode"] == "delta":
        cur = cur - int(state.get("baseline") or 0)
    return max(0, min(int(cur), int(mission["target"])))


async def _award_xp(db, uid: str, xp: int) -> None:
    from milestones import _ensure_progress_doc, xp_to_tier
    p = await _ensure_progress_doc(db, uid)
    total = int(p.get("xp", 0)) + int(xp)
    await db.user_progress.update_one(
        {"user_id": uid}, {"$set": {"xp": total, "tier": xp_to_tier(total)}})


async def _ensure_missions_doc(db, uid: str) -> dict:
    doc = await db.user_missions.find_one({"user_id": uid})
    if doc:
        return doc
    # Primo accesso: 3 missioni starter auto-attivate (l'utente puo' abbandonarle)
    active = {}
    for code in STARTER_MISSIONS:
        active[code] = await _activation_record(db, uid, MISSION_BY_CODE[code])
    doc = {"user_id": uid, "active": active, "completed": {}, "created_at": _now_iso()}
    await db.user_missions.insert_one(doc)
    return doc


def _enrich(mission: dict, extra: dict) -> dict:
    return {k: v for k, v in {**mission, **extra}.items()}


async def get_state(db, uid: str, lang_hint: str | None = None) -> dict:
    doc = await _ensure_missions_doc(db, uid)
    active: dict = dict(doc.get("active") or {})
    completed: dict = dict(doc.get("completed") or {})
    just_completed: list[dict] = []
    out_active: list[dict] = []
    dirty = False

    for code in list(active.keys()):
        m = MISSION_BY_CODE.get(code)
        if not m:
            active.pop(code)
            dirty = True
            continue
        st = active[code]
        prog = await _progress(db, uid, m, st)
        if prog >= int(m["target"]):
            completed[code] = {"completed_at": _now_iso(), "xp": int(m["xp"])}
            active.pop(code)
            await _award_xp(db, uid, int(m["xp"]))
            just_completed.append(_enrich(m, {"completed_at": completed[code]["completed_at"]}))
            dirty = True
        else:
            out_active.append(_enrich(m, {"progress": prog, "activated_at": st.get("activated_at")}))

    if dirty:
        await db.user_missions.update_one(
            {"user_id": uid}, {"$set": {"active": active, "completed": completed, "updated_at": _now_iso()}})

    available = [
        _enrich(m, {}) for m in MISSIONS_CATALOG
        if m["code"] not in active and m["code"] not in completed
    ]
    out_completed = [
        _enrich(MISSION_BY_CODE[c], {"completed_at": v.get("completed_at")})
        for c, v in completed.items() if c in MISSION_BY_CODE
    ]
    out_completed.sort(key=lambda x: x.get("completed_at") or "", reverse=True)

    prog_doc = await db.user_progress.find_one({"user_id": uid}, {"xp": 1, "tier": 1})
    return {
        "active": out_active,
        "available": available,
        "completed": out_completed,
        "just_completed": just_completed,
        "slots": {"used": len(out_active), "max": MAX_ACTIVE},
        "xp": int((prog_doc or {}).get("xp", 0)),
        "tier": (prog_doc or {}).get("tier", "bronze"),
    }


async def activate(db, uid: str, code: str) -> dict:
    m = MISSION_BY_CODE.get(code)
    if not m:
        return {"ok": False, "error": "unknown_mission"}
    doc = await _ensure_missions_doc(db, uid)
    active = dict(doc.get("active") or {})
    completed = dict(doc.get("completed") or {})
    if code in active:
        return {"ok": False, "error": "already_active"}
    if code in completed:
        return {"ok": False, "error": "already_completed"}
    if len(active) >= MAX_ACTIVE:
        return {"ok": False, "error": "slots_full"}
    active[code] = await _activation_record(db, uid, m)
    await db.user_missions.update_one(
        {"user_id": uid}, {"$set": {"active": active, "updated_at": _now_iso()}})
    return {"ok": True}


async def abandon(db, uid: str, code: str) -> dict:
    doc = await _ensure_missions_doc(db, uid)
    active = dict(doc.get("active") or {})
    if code not in active:
        return {"ok": False, "error": "not_active"}
    active.pop(code)
    await db.user_missions.update_one(
        {"user_id": uid}, {"$set": {"active": active, "updated_at": _now_iso()}})
    return {"ok": True}
