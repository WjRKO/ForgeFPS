"""ai_credits.py — Crediti messaggi AI Advisor (modello Earned Premium).

Regole (scelte utente):
- Starter (Free): 5 messaggi di benvenuto una-tantum (anche utenti esistenti) +
  crediti guadagnati con missioni (+2) e trofei (+5/10/15 per rarita').
  I crediti guadagnati SCADONO a fine settimana ISO; i 5 di benvenuto no.
- Pro: 50 messaggi/settimana, bloccato fino al reset settimanale (lunedi).
- Streamer: illimitato.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

from bson import ObjectId

from plan_gate import compute_effective_plan

WELCOME_CREDITS = 5
PRO_WEEKLY_LIMIT = 50
MISSION_CREDITS = 2
TROPHY_CREDITS = {"bronze": 5, "silver": 5, "gold": 10, "platinum": 15}


def week_id() -> str:
    y, w, _ = datetime.now(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def week_start_iso() -> str:
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.isoformat()


def week_end_iso() -> str:
    now = datetime.now(timezone.utc)
    monday = (now + timedelta(days=7 - now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.isoformat()


async def get_ai_quota(db, user: dict) -> dict:
    """Stato quota AI dell'utente in base al piano effettivo."""
    info = compute_effective_plan(user)
    base = {"plan_effective": info["plan_effective"], "is_pro": info["is_pro"], "is_streamer": info["is_streamer"]}
    if info["is_streamer"]:
        return {**base, "mode": "unlimited"}
    if info["is_pro"]:
        used = await db.chat_messages.count_documents(
            {"user_id": str(user["_id"]), "role": "user", "created_at": {"$gte": week_start_iso()}})
        return {**base, "mode": "weekly", "used": used, "limit": PRO_WEEKLY_LIMIT,
                "remaining": max(0, PRO_WEEKLY_LIMIT - used), "resets_at": week_end_iso()}
    # Starter: benvenuto (one-time) + guadagnati (scadenza settimanale)
    welcome = user.get("ai_welcome_credits")
    if welcome is None:
        welcome = WELCOME_CREDITS
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"ai_welcome_credits": WELCOME_CREDITS}})
    welcome = max(0, int(welcome))
    earned = int(user.get("ai_earned_credits") or 0)
    if user.get("ai_earned_week") != week_id():
        earned = 0
    earned = max(0, earned)
    return {**base, "mode": "credits", "welcome": welcome, "earned": earned,
            "total": welcome + earned, "earned_expires_at": week_end_iso()}


async def consume_credit(db, user: dict) -> None:
    """Scala 1 credito: prima i benvenuto, poi i guadagnati della settimana corrente."""
    res = await db.users.update_one(
        {"_id": user["_id"], "ai_welcome_credits": {"$gt": 0}},
        {"$inc": {"ai_welcome_credits": -1}})
    if res.modified_count:
        return
    await db.users.update_one(
        {"_id": user["_id"], "ai_earned_week": week_id(), "ai_earned_credits": {"$gt": 0}},
        {"$inc": {"ai_earned_credits": -1}})


async def grant_credits(db, uid: str, amount: int) -> None:
    """Aggiunge crediti guadagnati (bucket settimanale). Non deve mai rompere il chiamante."""
    if not uid or int(amount) <= 0:
        return
    try:
        oid = ObjectId(uid)
        wk = week_id()
        res = await db.users.update_one(
            {"_id": oid, "ai_earned_week": wk},
            {"$inc": {"ai_earned_credits": int(amount)}})
        if not res.matched_count:
            await db.users.update_one(
                {"_id": oid},
                {"$set": {"ai_earned_week": wk, "ai_earned_credits": int(amount)}})
    except Exception:
        pass
