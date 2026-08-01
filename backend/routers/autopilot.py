"""FrameForge Auto-Pilot router — /api/autopilot/*

Un click: l'agent applica tutti i tweak sicuri non ancora attivi, misura
prima/dopo (health, temperature) e riporta il rapporto sul dashboard.
Quota: Free 1 esecuzione/settimana, Pro/Streamer illimitato.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from database import db, now_iso
from devices import resolve_device, get_active_device
from ai_credits import week_start_iso

FREE_RUNS_PER_WEEK = 1


class AutopilotResult(BaseModel):
    applied: list[str] = []
    before: dict = {}
    after: dict = {}


def build(get_current_user):
    r = APIRouter(prefix="/api/autopilot", tags=["autopilot"])

    async def _quota(user: dict) -> dict:
        from plan_gate import compute_effective_plan
        info = compute_effective_plan(user)
        if info["is_pro"]:
            return {"plan_effective": info["plan_effective"], "limit": None, "used": 0}
        used = await db.autopilot_runs.count_documents({
            "user_id": str(user["_id"]),
            "created_at": {"$gte": week_start_iso()},
            "status": {"$in": ["pending", "done", "reverted"]},
        })
        return {"plan_effective": info["plan_effective"], "limit": FREE_RUNS_PER_WEEK, "used": used}

    @r.get("/status")
    async def autopilot_status(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        q = await _quota(user)
        latest = await db.autopilot_runs.find_one(
            {"user_id": uid, "status": {"$in": ["pending", "done", "reverted"]}}, {"_id": 0}, sort=[("created_at", -1)])
        remaining = None if q["limit"] is None else max(0, q["limit"] - q["used"])
        return {**q, "remaining": remaining, "latest": latest}

    @r.post("/start")
    async def autopilot_start(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        q = await _quota(user)
        if q["limit"] is not None and q["used"] >= q["limit"]:
            raise HTTPException(status_code=402, detail={
                "code": "autopilot_limit",
                "message": "Auto-Pilot gratuito: 1 esecuzione a settimana. Passa a Pro per usarlo senza limiti.",
                "upgrade_url": "/pricing",
            })
        await db.autopilot_runs.update_many(
            {"user_id": uid, "status": "pending"}, {"$set": {"status": "expired"}})
        run = {"user_id": uid, "device_id": await get_active_device(db, uid),
               "status": "pending", "created_at": now_iso()}
        res = await db.autopilot_runs.insert_one(run)
        return {"ok": True, "run_id": str(res.inserted_id)}

    @r.post("/agent/result")
    async def autopilot_result(payload: AutopilotResult,
                               x_agent_token: str = Header(default=""),
                               x_device: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        uid = rec["user_id"]
        did = await resolve_device(db, uid, x_device)
        from helpers import compute_health
        b = compute_health(payload.before) if payload.before else {}
        a = compute_health(payload.after) if payload.after else {}
        applied = [str(x)[:40] for x in (payload.applied or [])][:60]
        delta = None
        if a.get("score") is not None and b.get("score") is not None:
            delta = int(a["score"]) - int(b["score"])
        upd = {"status": "done", "completed_at": now_iso(), "applied": applied,
               "before": b, "after": a, "delta_score": delta,
               **({"device_id": did} if did else {})}
        run = await db.autopilot_runs.find_one(
            {"user_id": uid, "status": "pending"}, sort=[("created_at", -1)])
        if run:
            await db.autopilot_runs.update_one({"_id": run["_id"]}, {"$set": upd})
        else:
            await db.autopilot_runs.insert_one({"user_id": uid, "created_at": now_iso(), **upd})
        # Gamification: i tweak applicati contano per trofei e missioni giornaliere
        if applied:
            try:
                from milestones import bump_counter
                await bump_counter(db, uid, "tweaks_applied", len(applied))
            except Exception:
                pass
        return {"ok": True, "applied": len(applied)}

    @r.post("/agent/restore-done")
    async def autopilot_restore_done(x_agent_token: str = Header(default=""),
                                     x_device: str = Header(default="")):
        """L'agent segnala che il ripristino dal backup e' completato."""
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        uid = rec["user_id"]
        await resolve_device(db, uid, x_device)
        run = await db.autopilot_runs.find_one(
            {"user_id": uid, "status": "done"}, sort=[("created_at", -1)])
        if run:
            await db.autopilot_runs.update_one(
                {"_id": run["_id"]}, {"$set": {"status": "reverted", "reverted_at": now_iso()}})
        return {"ok": True, "reverted": bool(run)}

    return r
