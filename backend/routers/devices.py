"""FrameForge Devices router — /api/devices/* (Multi-PC)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import db
from devices import list_devices, get_active_device, DEVICE_ROLES, PER_PC_COLLECTIONS


class DeviceUpdate(BaseModel):
    name: str | None = None
    role: str | None = None


def build(get_current_user):
    r = APIRouter(prefix="/api/devices", tags=["devices"])

    @r.get("")
    async def devices_list(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        devs = await list_devices(db, uid)
        from plan_gate import get_entitlements
        ent = (await get_entitlements(db, user))["entitlements"]
        return {"devices": devs, "active": await get_active_device(db, uid),
                "limit": int(ent.get("device_limit") or 1)}

    @r.get("/compare")
    async def devices_compare(user: dict = Depends(get_current_user)):
        """Confronto fianco a fianco dei PC: health, temperature, live, specs."""
        uid = str(user["_id"])
        devs = await list_devices(db, uid)
        out = []
        for d in devs:
            f = {"user_id": uid, "device_id": d["device_id"]}
            specs = await db.pc_specs.find_one(f, {"_id": 0, "data": 1, "updated_at": 1})
            tel = await db.pc_telemetry.find_one(f, {"_id": 0, "samples": {"$slice": -30}})
            samples = (tel or {}).get("samples") or []

            def avg(k, _s=samples):
                vals = [s.get(k) for s in _s if isinstance(s.get(k), (int, float)) and s.get(k) > 0]
                return round(sum(vals) / len(vals), 1) if vals else None

            h = await db.health_history.find_one(f, sort=[("created_at", -1)])
            out.append({**d,
                        "specs": (specs or {}).get("data") or {},
                        "specs_updated_at": (specs or {}).get("updated_at"),
                        "health": {"score": (h or {}).get("score"), "grade": (h or {}).get("grade"),
                                   "cpu_temp": (h or {}).get("cpu_temp"), "gpu_temp": (h or {}).get("gpu_temp")},
                        "live": {"cpu_util": avg("cpu_util"), "gpu_util": avg("gpu_util"), "fps": avg("fps"),
                                 "cpu_temp": avg("cpu_temp"), "gpu_temp": avg("gpu_temp")}})
        return {"devices": out}

    @r.put("/{device_id}")
    async def device_update(device_id: str, body: DeviceUpdate, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        upd = {}
        if body.name is not None:
            name = body.name.strip()[:40]
            if not name:
                raise HTTPException(400, "Nome non valido")
            upd["name"] = name
        if body.role is not None:
            if body.role not in DEVICE_ROLES:
                raise HTTPException(400, f"Ruolo non valido. Ammessi: {', '.join(DEVICE_ROLES)}")
            upd["role"] = body.role
        if not upd:
            raise HTTPException(400, "Nessun campo da aggiornare")
        res = await db.devices.update_one({"user_id": uid, "device_id": device_id}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(404, "Device non trovato")
        return {"ok": True}

    @r.post("/{device_id}/activate")
    async def device_activate(device_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        if not await db.devices.find_one({"user_id": uid, "device_id": device_id}, {"_id": 1}):
            raise HTTPException(404, "Device non trovato")
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"active_device": device_id}})
        return {"ok": True, "active": device_id}

    @r.delete("/{device_id}")
    async def device_delete(device_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        res = await db.devices.delete_one({"user_id": uid, "device_id": device_id})
        if not res.deleted_count:
            raise HTTPException(404, "Device non trovato")
        for coll in PER_PC_COLLECTIONS:
            await db[coll].delete_many({"user_id": uid, "device_id": device_id})
        # Overlay che puntava a questo PC → torna al PC attivo
        await db.overlay_tokens.update_many(
            {"user_id": uid, "source_device": device_id}, {"$set": {"source_device": None}})
        # Se era l'attivo, ripiega sul primario rimasto
        u = await db.users.find_one({"_id": user["_id"]}, {"active_device": 1})
        if (u or {}).get("active_device") == device_id:
            nxt = await db.devices.find_one({"user_id": uid}, sort=[("first_seen", 1)])
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"active_device": nxt["device_id"]}} if nxt else {"$unset": {"active_device": ""}})
        return {"ok": True}

    return r
