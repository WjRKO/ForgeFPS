"""devices.py — Multi-PC: registro dispositivi per utente.

Ogni agent invia l'header X-Device ($env:COMPUTERNAME). Il backend registra la
macchina in db.devices e le collezioni per-PC (pc_specs, pc_telemetry,
health_history, net_results, benchmarks) acquisiscono device_id.
Retrocompatibilita': agent legacy senza header -> mappato sul device primario;
alla registrazione del PRIMO device i documenti legacy vengono adottati.
Limiti piano: Free 1 PC, Pro 3, Streamer illimitati.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException

PER_PC_COLLECTIONS = ("pc_specs", "pc_telemetry", "health_history", "net_results", "benchmarks")
DEVICE_ROLES = ("gaming", "streaming", "laptop", "other")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_device(hostname: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (hostname or "").strip().lower()).strip("-")
    return s[:48] or "pc"


async def resolve_device(db, uid: str, hostname: str | None, agent_version: str | None = None) -> str | None:
    """Ritorna il device_id per questo sync. None = modalita' legacy (nessun device)."""
    devs = await db.devices.find({"user_id": uid}).sort("first_seen", 1).to_list(50)
    if not hostname:
        return devs[0]["device_id"] if devs else None
    did = slug_device(hostname)
    now = _now_iso()
    for d in devs:
        if d["device_id"] == did:
            upd = {"last_seen": now}
            if agent_version:
                upd["agent_version"] = agent_version
            await db.devices.update_one({"_id": d["_id"]}, {"$set": upd})
            return did
    # Nuovo device: gate sul limite del piano
    from plan_gate import get_entitlements
    user = await db.users.find_one({"_id": ObjectId(uid)})
    ent = (await get_entitlements(db, user))["entitlements"] if user else {}
    limit = int(ent.get("device_limit") or 1)
    if len(devs) >= limit:
        raise HTTPException(status_code=402, detail={
            "code": "device_limit",
            "message": f"Limite PC collegati raggiunto ({limit}). Passa a un piano superiore per collegarne altri.",
            "upgrade_url": "/pricing",
        })
    role = "gaming" if not devs else ("streaming" if len(devs) == 1 else "other")
    await db.devices.insert_one({
        "user_id": uid, "device_id": did, "hostname": hostname[:64], "name": hostname[:64],
        "role": role, "first_seen": now, "last_seen": now,
        **({"agent_version": agent_version} if agent_version else {}),
    })
    if not devs:
        # Adozione dati legacy (senza device_id) sul primo device registrato
        for coll in PER_PC_COLLECTIONS:
            await db[coll].update_many(
                {"user_id": uid, "device_id": {"$exists": False}}, {"$set": {"device_id": did}})
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"active_device": did}})
    return did


async def get_active_device(db, uid: str) -> str | None:
    """Device attivo scelto dall'utente (fallback: primario). None se nessun device."""
    n = await db.devices.count_documents({"user_id": uid})
    if n == 0:
        return None
    u = await db.users.find_one({"_id": ObjectId(uid)}, {"active_device": 1})
    did = (u or {}).get("active_device")
    if did and await db.devices.find_one({"user_id": uid, "device_id": did}, {"_id": 1}):
        return did
    d = await db.devices.find_one({"user_id": uid}, sort=[("first_seen", 1)])
    return d["device_id"] if d else None


async def device_filter(db, uid: str) -> dict:
    """Filtro Mongo device-aware per le letture/scritture web sulle collezioni per-PC."""
    did = await get_active_device(db, uid)
    return {"user_id": uid, "device_id": did} if did else {"user_id": uid}


async def list_devices(db, uid: str) -> list[dict]:
    devs = await db.devices.find({"user_id": uid}, {"_id": 0}).sort("first_seen", 1).to_list(50)
    active = await get_active_device(db, uid)
    now = datetime.now(timezone.utc)
    out = []
    for d in devs:
        online = False
        try:
            from dateutil import parser as _p
            ls = _p.parse(d.get("last_seen"))
            if ls.tzinfo is None:
                ls = ls.replace(tzinfo=timezone.utc)
            online = (now - ls).total_seconds() < 300
        except Exception:
            pass
        h = await db.health_history.find_one(
            {"user_id": uid, "device_id": d["device_id"]}, sort=[("created_at", -1)])
        out.append({**d, "is_active": d["device_id"] == active, "online": online,
                    "health_score": (h or {}).get("score"), "health_grade": (h or {}).get("grade")})
    return out
