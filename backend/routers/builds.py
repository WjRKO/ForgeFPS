import uuid

from fastapi import APIRouter, Depends, HTTPException

import ai_engine
from database import db, now_iso
from helpers import track_components
from models import BuildInput, TrackComponentsInput


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["builds"])

    @r.post("/builds/generate")
    async def generate_build_ep(data: BuildInput, user: dict = Depends(get_current_user)):
        try:
            result = await ai_engine.generate_build(data.budget, data.use_case, data.resolution, data.notes)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        return {"id": str(uuid.uuid4()), "user_id": str(user["_id"]),
                "budget": data.budget, "use_case": data.use_case, "resolution": data.resolution,
                "build": result, "saved": False, "created_at": now_iso()}

    @r.post("/builds/save")
    async def save_build(doc: dict, user: dict = Depends(get_current_user)):
        doc["user_id"] = str(user["_id"])
        doc["saved"] = True
        doc["id"] = doc.get("id") or str(uuid.uuid4())
        doc.pop("_id", None)
        await db.builds.update_one({"id": doc["id"], "user_id": doc["user_id"]}, {"$set": doc}, upsert=True)
        return {"ok": True, "id": doc["id"]}

    @r.get("/builds")
    async def list_builds(user: dict = Depends(get_current_user)):
        return await db.builds.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(100)

    @r.delete("/builds/{build_id}")
    async def delete_build(build_id: str, user: dict = Depends(get_current_user)):
        await db.builds.delete_one({"id": build_id, "user_id": str(user["_id"])})
        return {"ok": True}

    @r.post("/builds/{build_id}/track")
    async def track_build(build_id: str, user: dict = Depends(get_current_user)):
        b = await db.builds.find_one({"id": build_id, "user_id": str(user["_id"])}, {"_id": 0})
        if not b:
            raise HTTPException(status_code=404, detail="Build non trovata")
        build_data = b.get("build", {})
        group = build_data.get("name", "Build")
        created = await track_components(str(user["_id"]), group, build_data.get("components", []))
        return {"ok": True, "tracked": created, "group": group}

    @r.post("/upgrade/track")
    async def track_upgrade(data: TrackComponentsInput, user: dict = Depends(get_current_user)):
        comps = [{"category": c.get("category"), "name": c.get("suggested"), "price": c.get("price")}
                 for c in data.components]
        created = await track_components(str(user["_id"]), data.group, comps)
        return {"ok": True, "tracked": created, "group": data.group}

    return r
