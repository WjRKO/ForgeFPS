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
SLOTS_BY_TIER = {"bronze": 3, "silver": 4, "gold": 5, "platinum": 6}
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

# ------------------------- Catena Recluta (onboarding) -------------------------
# Step sequenziali con metriche LIFETIME (i veterani la completano subito).
# Non occupa gli slot delle missioni normali.
CHAIN_MISSIONS: list[dict[str, Any]] = [
    {
        "code": "recruit_scan", "order": 1, "xp": 15, "icon": "Search",
        "metric": "pc_scans_total", "target": 1, "link": "/app/desktop",
        "name_it": "Primo contatto", "name_en": "First contact",
        "desc_it": "Scarica l'agent FrameForge ed esegui il tuo primo scan hardware.",
        "desc_en": "Download the FrameForge agent and run your first hardware scan.",
        "cta_it": "Scarica l'agent", "cta_en": "Download the agent",
    },
    {
        "code": "recruit_optimize", "order": 2, "xp": 25, "icon": "Wrench",
        "metric": "optimize_total", "target": 1, "link": "/app/pc",
        "name_it": "Prima ottimizzazione", "name_en": "First optimization",
        "desc_it": "Disattiva un servizio o un'app all'avvio tra quelli consigliati (o applica un tweak).",
        "desc_en": "Disable one recommended service or startup app (or apply one tweak).",
        "cta_it": "Vai ai consigli", "cta_en": "See advice",
    },
    {
        "code": "recruit_benchmark", "order": 3, "xp": 30, "icon": "Gauge",
        "metric": "benchmarks_total", "target": 1, "link": "/app/benchmark",
        "name_it": "Battesimo del fuoco", "name_en": "Baptism of fire",
        "desc_it": "Completa il tuo primo benchmark: da qui misuriamo ogni miglioramento futuro.",
        "desc_en": "Complete your first benchmark: every future improvement is measured from here.",
        "cta_it": "Avvia benchmark", "cta_en": "Run benchmark",
    },
]

# --------------------------- Missioni settimanali AI ---------------------------
# L'AI (o il fallback deterministico) sceglie 2 template parametrici in base ai
# dati reali del PC. Solo template VERIFICABILI. "{n}" nel nome = target.
WEEKLY_TEMPLATES: dict[str, dict[str, Any]] = {
    "w_svc": {
        "xp": 40, "metric": "services_done", "mode": "since", "link": "/app/pc",
        "icon": "Wrench", "target_max": 3,
        "name_it": "Pulizia servizi ×{n}", "name_en": "Service cleanup ×{n}",
        "desc_it": "Disattiva {n} servizi consigliati questa settimana.",
        "desc_en": "Disable {n} recommended services this week.",
    },
    "w_startup": {
        "xp": 35, "metric": "startup_done", "mode": "since", "link": "/app/pc",
        "icon": "Zap", "target_max": 3,
        "name_it": "Avvio snello ×{n}", "name_en": "Lean boot ×{n}",
        "desc_it": "Disattiva {n} app all'avvio tra quelle segnalate.",
        "desc_en": "Disable {n} flagged startup apps.",
    },
    "w_scan": {
        "xp": 30, "metric": "pc_scans", "mode": "delta", "link": "/app/desktop",
        "icon": "Activity", "target_max": 5,
        "name_it": "Guardia attiva ×{n}", "name_en": "Active watch ×{n}",
        "desc_it": "Esegui {n} scan con l'agent questa settimana.",
        "desc_en": "Run {n} agent scans this week.",
    },
    "w_bench": {
        "xp": 40, "metric": "benchmarks", "mode": "since", "link": "/app/benchmark",
        "icon": "Gauge", "target_max": 2,
        "name_it": "Check prestazioni", "name_en": "Performance check",
        "desc_it": "Esegui un benchmark per aggiornare la fotografia delle prestazioni.",
        "desc_en": "Run a benchmark to refresh your performance snapshot.",
    },
    "w_boost": {
        "xp": 40, "metric": "boost_sessions", "mode": "since", "link": "/app/gaming",
        "icon": "Gamepad2", "target_max": 3,
        "name_it": "Sessione boostata ×{n}", "name_en": "Boosted session ×{n}",
        "desc_it": "Completa {n} sessioni di gioco con il Boost attivo.",
        "desc_en": "Complete {n} gaming sessions with Boost on.",
    },
    "w_net": {
        "xp": 30, "metric": "net_tests", "mode": "since", "link": "/app/network",
        "icon": "Radio", "target_max": 1,
        "name_it": "Check di rete", "name_en": "Network check",
        "desc_it": "Esegui il test bufferbloat per verificare la tua connessione.",
        "desc_en": "Run the bufferbloat test to verify your connection.",
    },
    "w_advisor": {
        "xp": 20, "metric": "advisor_messages", "mode": "delta", "link": "/app/advisor",
        "icon": "Sparkles", "target_max": 3,
        "name_it": "Consulto col coach", "name_en": "Coach consult",
        "desc_it": "Chiedi {n} consigli all'AI Advisor sul tuo hardware.",
        "desc_en": "Ask the AI Advisor {n} questions about your hardware.",
    },
    "w_health": {
        "xp": 50, "metric": "health_score", "mode": "absolute", "link": "/app/pc",
        "icon": "HeartPulse", "target_max": 95,
        "name_it": "Health score a {n}", "name_en": "Health score to {n}",
        "desc_it": "Porta l'health score del PC ad almeno {n} entro fine settimana.",
        "desc_en": "Bring your PC health score to at least {n} by the end of the week.",
    },
}


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
    from milestones import _ensure_progress_doc, xp_to_tier, bump_counter
    p = await _ensure_progress_doc(db, uid)
    total = int(p.get("xp", 0)) + int(xp)
    await db.user_progress.update_one(
        {"user_id": uid}, {"$set": {"xp": total, "tier": xp_to_tier(total)}})
    # Trofeo segreto 'mission_hunter': ogni missione completata bumpa il counter
    await bump_counter(db, uid, "missions_completed", 1)


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


async def _max_slots(db, uid: str) -> int:
    p = await db.user_progress.find_one({"user_id": uid}, {"tier": 1})
    return SLOTS_BY_TIER.get((p or {}).get("tier") or "bronze", MAX_ACTIVE)


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

    chain, just_chain = await _eval_chain(db, uid, doc)
    weekly, just_weekly = await _eval_weekly(db, uid, doc)
    just_completed = just_completed + just_chain + just_weekly

    prog_doc = await db.user_progress.find_one({"user_id": uid}, {"xp": 1, "tier": 1})
    tier = (prog_doc or {}).get("tier", "bronze")
    return {
        "active": out_active,
        "available": available,
        "completed": out_completed,
        "just_completed": just_completed,
        "chain": chain,
        "weekly": weekly,
        "slots": {"used": len(out_active), "max": SLOTS_BY_TIER.get(tier, MAX_ACTIVE)},
        "xp": int((prog_doc or {}).get("xp", 0)),
        "tier": tier,
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
    if len(active) >= await _max_slots(db, uid):
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


# =========================== Catena Recluta engine ===========================

async def _lifetime_value(db, uid: str, metric: str) -> int:
    if metric == "pc_scans_total":
        p = await db.user_progress.find_one({"user_id": uid}, {"counters": 1})
        return int(((p or {}).get("counters") or {}).get("pc_scans", 0))
    if metric == "benchmarks_total":
        return await db.benchmarks.count_documents({"user_id": uid})
    if metric == "optimize_total":
        doc = await db.pc_specs.find_one({"user_id": uid}, {"services_done": 1, "startup_done": 1})
        p = await db.user_progress.find_one({"user_id": uid}, {"counters": 1})
        tweaks = int(((p or {}).get("counters") or {}).get("tweaks_applied", 0))
        return (len((doc or {}).get("services_done") or [])
                + len((doc or {}).get("startup_done") or []) + tweaks)
    return 0


async def _eval_chain(db, uid: str, doc: dict):
    completed = dict(((doc.get("chain") or {}).get("completed")) or {})
    steps, just, dirty = [], [], False
    unlocked = True
    for m in CHAIN_MISSIONS:
        code = m["code"]
        if code in completed:
            steps.append({**m, "status": "completed", "progress": m["target"],
                          "completed_at": completed[code]})
            continue
        if not unlocked:
            steps.append({**m, "status": "locked", "progress": 0})
            continue
        val = min(await _lifetime_value(db, uid, m["metric"]), int(m["target"]))
        if val >= int(m["target"]):
            completed[code] = _now_iso()
            await _award_xp(db, uid, int(m["xp"]))
            just.append({**m, "completed_at": completed[code]})
            steps.append({**m, "status": "completed", "progress": m["target"],
                          "completed_at": completed[code]})
            dirty = True
        else:
            steps.append({**m, "status": "active", "progress": val})
            unlocked = False
    if dirty:
        await db.user_missions.update_one(
            {"user_id": uid}, {"$set": {"chain.completed": completed, "updated_at": _now_iso()}})
    return {"steps": steps, "done": len(completed) == len(CHAIN_MISSIONS)}, just


# ========================= Missioni settimanali engine =========================

def _week_id() -> str:
    y, w, _ = datetime.now(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def _week_expires_iso() -> str:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    monday = (now + timedelta(days=7 - now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.isoformat()


async def _weekly_context(db, uid: str) -> dict:
    from datetime import timedelta
    specs = await db.pc_specs.find_one({"user_id": uid}, {"data": 1, "services_audit": 1, "startup": 1, "games": 1})
    specs = specs or {}
    svc_actionable = 0
    if specs.get("services_audit"):
        from services_kb import analyze_services
        res = analyze_services(specs["services_audit"], specs.get("data"), specs.get("games"))
        svc_actionable = res["summary"]["disattiva"] + res["summary"]["valuta"]
    from services_kb import is_startup_noise
    startup_active = sum(
        1 for s in (specs.get("startup") or [])
        if isinstance(s, dict) and s.get("enabled") is not False
        and not is_startup_noise(s.get("name"), s.get("publisher")))
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    bench_recent = await db.benchmarks.count_documents({"user_id": uid, "created_at": {"$gte": week_ago}}) > 0
    net_done = bool(await db.net_results.find_one({"user_id": uid}, {"_id": 1}))
    hdoc = await db.health_history.find_one({"user_id": uid}, sort=[("created_at", -1)])
    health = int(hdoc["score"]) if hdoc and hdoc.get("score") is not None else None
    boost_total = await db.boost_sessions.count_documents({"user_id": uid})
    return {
        "has_specs": bool((specs.get("data") or {}).get("cpu")),
        "cpu": (specs.get("data") or {}).get("cpu"),
        "gpu": (specs.get("data") or {}).get("gpu"),
        "svc_actionable": svc_actionable,
        "startup_active": startup_active,
        "bench_recent": bench_recent,
        "net_done": net_done,
        "health": health,
        "boost_total": boost_total,
    }


_WEEKLY_AI_SYSTEM = (
    "Sei il coach prestazioni di FrameForge. Scegli 2 missioni settimanali su misura per "
    "l'utente in base ai dati REALI del suo PC. Rispondi SOLO con JSON valido, senza markdown.")


async def _pick_weekly_ai(uid: str, ctx: dict) -> list[dict] | None:
    import ai_engine
    tpl_list = "\n".join(
        f"- {k}: {v['desc_it']} (target 1..{v['target_max']})" for k, v in WEEKLY_TEMPLATES.items())
    prompt = (
        f"Dati del PC dell'utente:\n"
        f"CPU: {ctx.get('cpu')} | GPU: {ctx.get('gpu')}\n"
        f"Health score attuale: {ctx.get('health')}\n"
        f"Servizi consigliati da disattivare ancora attivi: {ctx.get('svc_actionable')}\n"
        f"App all'avvio attive: {ctx.get('startup_active')}\n"
        f"Benchmark negli ultimi 7 giorni: {ctx.get('bench_recent')}\n"
        f"Test di rete mai fatto: {not ctx.get('net_done')}\n"
        f"Sessioni Boost totali: {ctx.get('boost_total')}\n\n"
        f"Template disponibili (scegline ESATTAMENTE 2 diversi, i piu' utili per QUESTO utente):\n{tpl_list}\n\n"
        "Regole: non scegliere w_svc se i servizi da disattivare sono 0; non scegliere w_startup se le app attive sono <2; "
        "per w_health il target deve essere tra health+3 e min(health+10, 95) e sceglilo solo se health < 85.\n"
        'Rispondi con JSON: {"missions":[{"template":"w_svc","target":2,'
        '"why_it":"1 frase personalizzata sul perche","why_en":"same in english"}]}')
    out = await ai_engine._run_json(f"weekly-missions-{uid}-{_week_id()}", _WEEKLY_AI_SYSTEM, prompt)
    picks = []
    seen = set()
    for p in (out.get("missions") or []):
        tkey = str(p.get("template") or "")
        tpl = WEEKLY_TEMPLATES.get(tkey)
        if not tpl or tkey in seen:
            continue
        seen.add(tkey)
        try:
            target = int(p.get("target") or 1)
        except (TypeError, ValueError):
            target = 1
        if tkey == "w_health":
            base = int(ctx.get("health") or 70)
            target = max(base + 3, min(target, min(base + 10, 95)))
        else:
            target = max(1, min(target, int(tpl["target_max"])))
        picks.append({"template": tkey, "target": target,
                      "why_it": str(p.get("why_it") or "")[:200] or None,
                      "why_en": str(p.get("why_en") or "")[:200] or None})
    return picks[:2] or None


def _pick_weekly_fallback(ctx: dict) -> list[dict]:
    picks = []
    if ctx.get("svc_actionable"):
        picks.append({"template": "w_svc", "target": min(2, int(ctx["svc_actionable"])),
                      "why_it": None, "why_en": None})
    if ctx.get("startup_active", 0) > 2:
        picks.append({"template": "w_startup", "target": 2, "why_it": None, "why_en": None})
    if not ctx.get("bench_recent"):
        picks.append({"template": "w_bench", "target": 1, "why_it": None, "why_en": None})
    if not ctx.get("net_done"):
        picks.append({"template": "w_net", "target": 1, "why_it": None, "why_en": None})
    picks.append({"template": "w_scan", "target": 3, "why_it": None, "why_en": None})
    dedup, seen = [], set()
    for p in picks:
        if p["template"] not in seen:
            seen.add(p["template"])
            dedup.append(p)
    return dedup[:2]


def _weekly_enrich(rec: dict, tpl: dict, progress: int) -> dict:
    n = str(rec["target"])
    return {
        "code": rec["code"], "template": rec["template"], "xp": int(tpl["xp"]),
        "icon": tpl["icon"], "link": tpl["link"], "target": int(rec["target"]),
        "metric": tpl["metric"], "mode": tpl["mode"],
        "progress": progress, "completed_at": rec.get("completed_at"),
        "why_it": rec.get("why_it"), "why_en": rec.get("why_en"),
        "name_it": tpl["name_it"].replace("{n}", n), "name_en": tpl["name_en"].replace("{n}", n),
        "desc_it": tpl["desc_it"].replace("{n}", n), "desc_en": tpl["desc_en"].replace("{n}", n),
        "cta_it": "Vai", "cta_en": "Go",
    }


async def _eval_weekly(db, uid: str, doc: dict):
    wk = dict(doc.get("weekly") or {})
    if wk.get("week_id") != _week_id():
        ctx = await _weekly_context(db, uid)
        picks = None
        if ctx.get("has_specs"):
            try:
                picks = await _pick_weekly_ai(uid, ctx)
            except Exception:
                picks = None
        if not picks:
            picks = _pick_weekly_fallback(ctx)
        missions = []
        for p in picks:
            tpl = WEEKLY_TEMPLATES[p["template"]]
            rec = {"code": f'{p["template"]}:{_week_id()}', "template": p["template"],
                   "target": int(p["target"]), "why_it": p.get("why_it"), "why_en": p.get("why_en"),
                   "activated_at": _now_iso(), "baseline": 0}
            if tpl["mode"] == "delta":
                rec["baseline"] = await _metric_value(db, uid, tpl["metric"], None)
            missions.append(rec)
        wk = {"week_id": _week_id(), "missions": missions, "generated_at": _now_iso()}
        await db.user_missions.update_one(
            {"user_id": uid}, {"$set": {"weekly": wk, "updated_at": _now_iso()}}, upsert=True)

    out, just, dirty = [], [], False
    for rec in wk.get("missions") or []:
        tpl = WEEKLY_TEMPLATES.get(rec.get("template"))
        if not tpl:
            continue
        target = int(rec["target"])
        if rec.get("completed_at"):
            out.append(_weekly_enrich(rec, tpl, target))
            continue
        pseudo = {"metric": tpl["metric"], "mode": tpl["mode"], "target": target}
        prog = await _progress(db, uid, pseudo, rec)
        if prog >= target:
            rec["completed_at"] = _now_iso()
            await _award_xp(db, uid, int(tpl["xp"]))
            enriched = _weekly_enrich(rec, tpl, target)
            just.append(enriched)
            out.append(enriched)
            dirty = True
        else:
            out.append(_weekly_enrich(rec, tpl, prog))
    if dirty:
        await db.user_missions.update_one(
            {"user_id": uid}, {"$set": {"weekly": wk, "updated_at": _now_iso()}})
    return {"week_id": wk.get("week_id"), "expires_at": _week_expires_iso(), "missions": out}, just
