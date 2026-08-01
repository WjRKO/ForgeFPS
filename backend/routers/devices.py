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
        # Se era l'attivo, ripiega sul primario rimasto
        u = await db.users.find_one({"_id": user["_id"]}, {"active_device": 1})
        if (u or {}).get("active_device") == device_id:
            nxt = await db.devices.find_one({"user_id": uid}, sort=[("first_seen", 1)])
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"active_device": nxt["device_id"]}} if nxt else {"$unset": {"active_device": ""}})
        return {"ok": True}

    return r
