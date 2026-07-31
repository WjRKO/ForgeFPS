"""FrameForge Milestone System v1.

Design:
- Single collection `user_progress` per utente con counters + xp + tier + unlocked list.
- Catalogo statico (MILESTONES_CATALOG) — 14 traguardi iniziali.
- Ogni endpoint di dominio chiama `bump_counter(...)` che:
    1. incrementa un contatore (o aggiunge a un set per unique)
    2. valuta tutte le milestone dipendenti da quel contatore
    3. sblocca quelle raggiunte, aggiunge XP, aggiorna tier
    4. mette in coda notifica (per toast + OBS overlay popup)

XP tier scale:
    bronze:   0 - 99
    silver:   100 - 299
    gold:     300 - 799
    platinum: 800+

Reward types (server-side flags in user_progress.features):
- unlock: sblocca una feature flag (es. advanced_registry_tweaks)
- badge:  solo cosmetico/condivisibile
- slot:   incrementa un contatore di slot (es. profile_slots +1)
"""

from __future__ import annotations
from datetime import datetime, timezone, date
from typing import Any


# ---------------- Catalogo (14 milestone) ----------------
MILESTONES_CATALOG: list[dict[str, Any]] = [
    # ---- Onboarding (bronze) ----
    {
        "code": "first_scan", "category": "onboarding", "tier": "bronze", "xp": 10,
        "name_it": "Primo Contatto", "name_en": "First Contact",
        "desc_it": "Hai completato la tua prima scansione hardware.",
        "desc_en": "You completed your first hardware scan.",
        "icon": "Search",
        "condition": {"counter": "pc_scans", "threshold": 1},
        "reward": {"type": "unlock", "key": "profile_template_slot", "label_it": "1 template profilo custom", "label_en": "1 custom profile template"},
    },
    {
        "code": "first_advisor", "category": "onboarding", "tier": "bronze", "xp": 10,
        "name_it": "Consulta l'Oracolo", "name_en": "Consult the Oracle",
        "desc_it": "Prima chat con l'AI Advisor.",
        "desc_en": "First chat with the AI Advisor.",
        "icon": "Sparkles",
        "condition": {"counter": "advisor_messages", "threshold": 1},
    },
    {
        "code": "first_tweak", "category": "onboarding", "tier": "bronze", "xp": 10,
        "name_it": "Primo Boost", "name_en": "First Boost",
        "desc_it": "Hai applicato il tuo primo tweak.",
        "desc_en": "You applied your first tweak.",
        "icon": "Zap",
        "condition": {"counter": "tweaks_applied", "threshold": 1},
    },
    {
        "code": "first_overlay", "category": "onboarding", "tier": "bronze", "xp": 15,
        "name_it": "On Air", "name_en": "On Air",
        "desc_it": "Hai creato il tuo primo overlay OBS.",
        "desc_en": "You created your first OBS overlay.",
        "icon": "Radio",
        "condition": {"counter": "overlays_created", "threshold": 1},
    },

    # ---- Performance (silver / gold) ----
    {
        "code": "tweaks_10", "category": "performance", "tier": "silver", "xp": 25,
        "name_it": "Tuning Solido", "name_en": "Solid Tuner",
        "desc_it": "10 tweak applicati con successo.",
        "desc_en": "10 tweaks applied successfully.",
        "icon": "Wrench",
        "condition": {"counter": "tweaks_applied", "threshold": 10},
        "reward": {"type": "unlock", "key": "advanced_registry_tweaks", "label_it": "Advanced Registry Tweaks", "label_en": "Advanced Registry Tweaks"},
    },
    {
        "code": "tweaks_50", "category": "performance", "tier": "gold", "xp": 100,
        "name_it": "Overclock Master", "name_en": "Overclock Master",
        "desc_it": "50 tweak totali. Sai il fatto tuo.",
        "desc_en": "50 total tweaks. You know your stuff.",
        "icon": "Cpu",
        "condition": {"counter": "tweaks_applied", "threshold": 50},
    },
    {
        "code": "health_streak_7", "category": "performance", "tier": "silver", "xp": 40,
        "name_it": "Zen Mode", "name_en": "Zen Mode",
        "desc_it": "Health Score sopra 85 per 7 giorni consecutivi.",
        "desc_en": "Health score above 85 for 7 straight days.",
        "icon": "Activity",
        "condition": {"counter": "health_streak_days", "threshold": 7},
        "reward": {"type": "slot", "key": "profile_slots", "amount": 1, "label_it": "+1 slot Profile custom", "label_en": "+1 custom Profile slot"},
    },
    {
        "code": "pc_whisperer", "category": "performance", "tier": "gold", "xp": 75,
        "name_it": "PC Whisperer", "name_en": "PC Whisperer",
        "desc_it": "Hai portato il tuo Health Score da sotto 65 a sopra 85. Salvataggio riuscito.",
        "desc_en": "You brought your Health Score from below 65 to above 85. Rescue succeeded.",
        "icon": "HeartPulse",
        "condition": {"flag": "pc_whisperer_earned"},
        "reward": {"type": "badge", "shareable": True, "label_it": "Badge condivisibile", "label_en": "Shareable badge"},
    },

    # ---- Gaming (bronze -> gold) ----
    {
        "code": "first_game", "category": "gaming", "tier": "bronze", "xp": 15,
        "name_it": "Player One", "name_en": "Player One",
        "desc_it": "Primo gioco rilevato dall'Universal Game Detector.",
        "desc_en": "First game detected by the Universal Game Detector.",
        "icon": "Gamepad2",
        "condition": {"counter_unique": "games_detected", "threshold": 1},
    },
    {
        "code": "games_5", "category": "gaming", "tier": "silver", "xp": 40,
        "name_it": "Curatore", "name_en": "Curator",
        "desc_it": "Rilevati 5 giochi diversi.",
        "desc_en": "5 different games detected.",
        "icon": "Library",
        "condition": {"counter_unique": "games_detected", "threshold": 5},
        "reward": {"type": "unlock", "key": "auto_profile_match", "label_it": "Auto-Profile Match", "label_en": "Auto-Profile Match"},
    },
    {
        "code": "session_100h", "category": "gaming", "tier": "gold", "xp": 100,
        "name_it": "Centurione", "name_en": "Centurion",
        "desc_it": "100 ore totali di gaming tracciate.",
        "desc_en": "100 total gaming hours tracked.",
        "icon": "Clock",
        "condition": {"counter": "session_minutes", "threshold": 6000},
    },
    {
        "code": "session_marathon", "category": "gaming", "tier": "silver", "xp": 30,
        "name_it": "Maratoneta", "name_en": "Marathoner",
        "desc_it": "Sessione singola > 4h con FPS stabili.",
        "desc_en": "Single session > 4h with stable FPS.",
        "icon": "Timer",
        "condition": {"flag": "session_marathon_earned"},
    },

    # ---- Meta (gold / platinum) ----
    {
        "code": "veteran_30d", "category": "meta", "tier": "gold", "xp": 100,
        "name_it": "Veterano", "name_en": "Veteran",
        "desc_it": "Attivo su FrameForge per 30 giorni.",
        "desc_en": "Active on FrameForge for 30 days.",
        "icon": "Crown",
        "condition": {"counter": "days_active", "threshold": 30},
        "reward": {"type": "badge", "shareable": True, "label_it": "Badge VIP", "label_en": "VIP badge"},
    },
    {
        "code": "beta_tester", "category": "meta", "tier": "platinum", "xp": 250,
        "name_it": "Beta Tester", "name_en": "Beta Tester",
        "desc_it": "Account registrato prima del 1 marzo 2026. Grazie per aver creduto in FrameForge.",
        "desc_en": "Account created before March 1, 2026. Thanks for believing in FrameForge.",
        "icon": "Star",
        "condition": {"flag": "beta_tester_earned"},
        "reward": {"type": "badge", "shareable": True, "label_it": "Badge Founding Member", "label_en": "Founding Member badge"},
    },

    # ---- Segreti (nascosti finche' non sbloccati) ----
    {
        "code": "night_owl", "category": "secret", "tier": "silver", "xp": 30, "secret": True,
        "name_it": "Gufo Notturno", "name_en": "Night Owl",
        "desc_it": "Hai completato uno scan nel cuore della notte.",
        "desc_en": "You completed a scan in the dead of night.",
        "icon": "Clock",
        "condition": {"flag": "night_owl_earned"},
    },
    {
        "code": "surgeon", "category": "secret", "tier": "gold", "xp": 75, "secret": True,
        "name_it": "Chirurgo", "name_en": "Surgeon",
        "desc_it": "10 tra servizi e app d'avvio disattivati seguendo i consigli.",
        "desc_en": "10 services and startup apps disabled following our advice.",
        "icon": "Wrench",
        "condition": {"flag": "surgeon_earned"},
    },
    {
        "code": "mad_scientist", "category": "secret", "tier": "gold", "xp": 100, "secret": True,
        "name_it": "Scienziato Pazzo", "name_en": "Mad Scientist",
        "desc_it": "5 esperimenti del Performance Lab completati.",
        "desc_en": "5 Performance Lab experiments completed.",
        "icon": "Timer",
        "condition": {"counter": "lab_experiments", "threshold": 5},
    },
    {
        "code": "speed_demon", "category": "secret", "tier": "gold", "xp": 75, "secret": True,
        "name_it": "Demone della Velocità", "name_en": "Speed Demon",
        "desc_it": "Benchmark con punteggio complessivo di almeno 90.",
        "desc_en": "Benchmark with an overall score of at least 90.",
        "icon": "Gauge",
        "condition": {"flag": "speed_demon_earned"},
    },
    {
        "code": "mission_hunter", "category": "secret", "tier": "silver", "xp": 50, "secret": True,
        "name_it": "Cacciatore di Missioni", "name_en": "Mission Hunter",
        "desc_it": "10 missioni completate.",
        "desc_en": "10 missions completed.",
        "icon": "Swords",
        "condition": {"counter": "missions_completed", "threshold": 10},
    },
    {
        "code": "collector", "category": "secret", "tier": "platinum", "xp": 150, "secret": True,
        "name_it": "Collezionista", "name_en": "Collector",
        "desc_it": "15 giochi diversi rilevati dall'Universal Game Detector.",
        "desc_en": "15 different games detected by the Universal Game Detector.",
        "icon": "Library",
        "condition": {"counter_unique": "games_detected", "threshold": 15},
    },
]

MILESTONE_BY_CODE = {m["code"]: m for m in MILESTONES_CATALOG}
_TIER_ORDER = ["bronze", "silver", "gold", "platinum"]

# XP thresholds per tier
_TIER_XP = {"bronze": 0, "silver": 100, "gold": 300, "platinum": 800}


def xp_to_tier(xp: int) -> str:
    if xp >= 800:
        return "platinum"
    if xp >= 300:
        return "gold"
    if xp >= 100:
        return "silver"
    return "bronze"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_progress_doc(db, user_id: str) -> dict:
    """Fetch or create per-user progress doc. Idempotent."""
    doc = await db.user_progress.find_one({"user_id": user_id})
    if doc:
        return doc
    doc = {
        "user_id": user_id,
        "counters": {},
        "unique_sets": {},   # counter_name -> list of unique values
        "flags": {},         # e.g. pc_whisperer_earned=True
        "xp": 0,
        "tier": "bronze",
        "unlocked": [],       # list of milestone codes
        "unlocked_at": {},    # code -> iso timestamp
        "pending_notify": [], # codes yet to be shown in dashboard toast
        "obs_pending": [],    # codes yet to be shown in OBS overlay
        "features": {},       # reward flags (advanced_registry_tweaks=True, profile_slots=int)
        "created_at": _now_iso(),
        "last_active_day": None,
        "health_lowest_recent": None,  # per PC Whisperer tracking
    }
    await db.user_progress.insert_one(doc)
    return doc


async def _evaluate_and_unlock(db, user_id: str, progress: dict) -> list[str]:
    """Given current progress, return list of newly unlocked milestone codes."""
    unlocked_set = set(progress.get("unlocked", []))
    counters = progress.get("counters", {}) or {}
    unique_sets = progress.get("unique_sets", {}) or {}
    flags = progress.get("flags", {}) or {}

    new_unlocks: list[str] = []
    for m in MILESTONES_CATALOG:
        if m["code"] in unlocked_set:
            continue
        cond = m.get("condition", {})
        matched = False
        if "counter" in cond:
            val = int(counters.get(cond["counter"], 0))
            if val >= int(cond["threshold"]):
                matched = True
        elif "counter_unique" in cond:
            uniq = unique_sets.get(cond["counter_unique"]) or []
            if len(uniq) >= int(cond["threshold"]):
                matched = True
        elif "flag" in cond:
            if bool(flags.get(cond["flag"])):
                matched = True
        if matched:
            new_unlocks.append(m["code"])

    if not new_unlocks:
        return []

    now = _now_iso()
    total_xp = int(progress.get("xp", 0))
    features = dict(progress.get("features", {}) or {})
    unlocked_list = list(progress.get("unlocked", []))
    unlocked_at = dict(progress.get("unlocked_at", {}))
    pending_notify = list(progress.get("pending_notify", []))
    obs_pending = list(progress.get("obs_pending", []))

    for code in new_unlocks:
        m = MILESTONE_BY_CODE[code]
        total_xp += int(m.get("xp", 0))
        unlocked_list.append(code)
        unlocked_at[code] = now
        pending_notify.append(code)
        obs_pending.append(code)
        # Apply reward
        r = m.get("reward") or {}
        if r.get("type") == "unlock" and r.get("key"):
            features[r["key"]] = True
        elif r.get("type") == "slot" and r.get("key"):
            features[r["key"]] = int(features.get(r["key"], 0)) + int(r.get("amount", 1))

    await db.user_progress.update_one(
        {"user_id": user_id},
        {"$set": {
            "unlocked": unlocked_list,
            "unlocked_at": unlocked_at,
            "pending_notify": pending_notify,
            "obs_pending": obs_pending,
            "xp": total_xp,
            "tier": xp_to_tier(total_xp),
            "features": features,
            "updated_at": now,
        }},
    )
    return new_unlocks


async def bump_counter(db, user_id: str, counter: str, increment: int = 1) -> list[str]:
    """Increment a counter and evaluate unlocks. Returns newly-unlocked codes."""
    if not user_id or not counter:
        return []
    try:
        progress = await _ensure_progress_doc(db, user_id)
        await db.user_progress.update_one(
            {"user_id": user_id},
            {"$inc": {f"counters.{counter}": int(increment)}},
        )
        progress = await db.user_progress.find_one({"user_id": user_id})
        return await _evaluate_and_unlock(db, user_id, progress)
    except Exception:
        # Milestones must never break the calling endpoint.
        return []


async def add_unique(db, user_id: str, counter: str, value: str) -> list[str]:
    """Add a unique value to a set (e.g. distinct game appids)."""
    if not user_id or not counter or not value:
        return []
    try:
        await _ensure_progress_doc(db, user_id)
        await db.user_progress.update_one(
            {"user_id": user_id},
            {"$addToSet": {f"unique_sets.{counter}": str(value)}},
        )
        progress = await db.user_progress.find_one({"user_id": user_id})
        return await _evaluate_and_unlock(db, user_id, progress)
    except Exception:
        return []


async def set_flag(db, user_id: str, flag: str, value: bool = True) -> list[str]:
    """Set a boolean flag (for milestones that use flag conditions)."""
    if not user_id or not flag:
        return []
    try:
        await _ensure_progress_doc(db, user_id)
        await db.user_progress.update_one(
            {"user_id": user_id},
            {"$set": {f"flags.{flag}": bool(value)}},
        )
        progress = await db.user_progress.find_one({"user_id": user_id})
        return await _evaluate_and_unlock(db, user_id, progress)
    except Exception:
        return []


async def track_daily_active(db, user_id: str) -> list[str]:
    """Bump days_active at most once per calendar day (UTC)."""
    if not user_id:
        return []
    try:
        progress = await _ensure_progress_doc(db, user_id)
        today = date.today().isoformat()
        if progress.get("last_active_day") == today:
            return []
        await db.user_progress.update_one(
            {"user_id": user_id},
            {"$set": {"last_active_day": today}, "$inc": {"counters.days_active": 1}},
        )
        progress = await db.user_progress.find_one({"user_id": user_id})
        return await _evaluate_and_unlock(db, user_id, progress)
    except Exception:
        return []


async def track_health_score(db, user_id: str, score: int) -> list[str]:
    """Update health score tracking:
    - health_streak_days: increment if >85 today, reset if not
    - PC Whisperer: if we've seen a value <65 previously and now >=85 → set flag
    """
    if not user_id or score is None:
        return []
    try:
        progress = await _ensure_progress_doc(db, user_id)
        today = date.today().isoformat()
        last_streak_day = progress.get("last_streak_day")
        streak = int((progress.get("counters") or {}).get("health_streak_days", 0))
        lowest_recent = progress.get("health_lowest_recent")

        updates: dict[str, Any] = {}
        # Streak logic: only count once per day
        if last_streak_day != today:
            if score >= 85:
                streak += 1
            else:
                streak = 0
            updates["counters.health_streak_days"] = streak
            updates["last_streak_day"] = today

        # PC Whisperer tracking: track lowest recent health
        if lowest_recent is None or score < lowest_recent:
            updates["health_lowest_recent"] = int(score)
        if lowest_recent is not None and lowest_recent < 65 and score >= 85:
            updates["flags.pc_whisperer_earned"] = True
            updates["health_lowest_recent"] = int(score)  # reset dopo rescue

        if updates:
            await db.user_progress.update_one({"user_id": user_id}, {"$set": updates})
        progress = await db.user_progress.find_one({"user_id": user_id})
        return await _evaluate_and_unlock(db, user_id, progress)
    except Exception:
        return []


async def check_beta_tester(db, user_id: str, user_created_at: str | None) -> list[str]:
    """One-shot flag for accounts created before 2026-03-01."""
    if not user_id or not user_created_at:
        return []
    try:
        try:
            dt = datetime.fromisoformat(user_created_at.replace("Z", "+00:00"))
        except Exception:
            return []
        cutoff = datetime(2026, 3, 1, tzinfo=timezone.utc)
        if dt.replace(tzinfo=dt.tzinfo or timezone.utc) < cutoff:
            return await set_flag(db, user_id, "beta_tester_earned", True)
    except Exception:
        pass
    return []


async def dismiss_notification(db, user_id: str, code: str, channel: str = "dashboard") -> bool:
    """Mark milestone popup as seen. channel = 'dashboard' or 'obs'."""
    field = "pending_notify" if channel == "dashboard" else "obs_pending"
    try:
        await db.user_progress.update_one(
            {"user_id": user_id},
            {"$pull": {field: code}},
        )
        return True
    except Exception:
        return False


def enrich_catalog_for_user(progress: dict) -> list[dict]:
    """Return catalog with per-milestone progress data merged in."""
    counters = (progress or {}).get("counters", {}) or {}
    unique_sets = (progress or {}).get("unique_sets", {}) or {}
    flags = (progress or {}).get("flags", {}) or {}
    unlocked_set = set((progress or {}).get("unlocked", []) or [])
    unlocked_at = (progress or {}).get("unlocked_at", {}) or {}

    out = []
    for m in MILESTONES_CATALOG:
        cond = m.get("condition", {}) or {}
        current = 0
        threshold = 1
        if "counter" in cond:
            threshold = int(cond["threshold"])
            current = min(int(counters.get(cond["counter"], 0)), threshold)
        elif "counter_unique" in cond:
            threshold = int(cond["threshold"])
            uniq = unique_sets.get(cond["counter_unique"]) or []
            current = min(len(uniq), threshold)
        elif "flag" in cond:
            current = 1 if flags.get(cond["flag"]) else 0
            threshold = 1
        entry = dict(m)
        entry["unlocked"] = m["code"] in unlocked_set
        entry["progress"] = current
        entry["threshold"] = threshold
        entry["unlocked_at"] = unlocked_at.get(m["code"]) if m["code"] in unlocked_set else None
        out.append(entry)
    return out
