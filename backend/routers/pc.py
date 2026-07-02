import os

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse

import ai_engine
from database import db, now_iso
from helpers import specs_to_text, compute_health, get_or_create_agent_token
from desktop_agent import AGENT_SCRIPT
from models import SpecsInput, GoalInput, FpsInput, PcSpecsInput


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["pc"])

    @r.get("/agent/token")
    async def agent_token(user: dict = Depends(get_current_user)):
        return {"token": await get_or_create_agent_token(str(user["_id"]))}

    @r.post("/agent/report-specs")
    async def report_specs(data: SpecsInput, x_agent_token: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        uid = rec["user_id"]
        fields = {"user_id": uid, "data": data.data, "updated_at": now_iso()}
        if data.health is not None:
            fields["health"] = data.health
        if data.startup is not None:
            fields["startup"] = data.startup
        await db.pc_specs.update_one({"user_id": uid}, {"$set": fields}, upsert=True)
        return {"ok": True}

    @r.get("/pc-specs")
    async def get_specs(user: dict = Depends(get_current_user)):
        return await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})

    @r.post("/pc-specs")
    async def save_specs(payload: PcSpecsInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        existing = await db.pc_specs.find_one({"user_id": uid})
        base = (existing or {}).get("data", {}) if existing else {}
        merged = {**base, **{k: v for k, v in payload.data.items() if v not in (None, "")}}
        await db.pc_specs.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, "data": merged, "source": payload.source, "updated_at": now_iso()}},
            upsert=True)
        return await db.pc_specs.find_one({"user_id": uid}, {"_id": 0})

    @r.get("/pc-health")
    async def pc_health(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        if not doc or not doc.get("health"):
            return {"available": False}
        return {**compute_health(doc["health"]), "available": True}

    @r.post("/upgrade/analyze")
    async def upgrade_analyze(data: GoalInput, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        if not specs or not specs.get("data"):
            raise HTTPException(status_code=400,
                                detail="Nessun hardware rilevato. Usa il Desktop Agent (opzione 7) per inviare le specifiche.")
        try:
            return await ai_engine.generate_upgrade(specs_to_text(specs), data.budget, data.goal)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    @r.post("/fps/estimate")
    async def fps_estimate(data: FpsInput, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        try:
            return await ai_engine.estimate_fps(specs_to_text(specs) if specs else "", data.game, data.resolution)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    @r.post("/startup/analyze")
    async def startup_analyze(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        startup = (doc or {}).get("startup") or []
        if not startup:
            raise HTTPException(status_code=400, detail="Nessun dato di avvio. Usa il Desktop Agent (opzione 7).")
        try:
            return await ai_engine.analyze_startup(startup)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    @r.get("/desktop-agent/download")
    async def download_agent(user: dict = Depends(get_current_user)):
        token = await get_or_create_agent_token(str(user["_id"]))
        backend = os.environ.get("FRONTEND_URL", "http://localhost:8001")
        script = AGENT_SCRIPT.replace("__BACKEND_URL__", backend).replace("__AGENT_TOKEN__", token)
        return PlainTextResponse(script, headers={"Content-Disposition": "attachment; filename=boostpc_agent.py"})

    return r
