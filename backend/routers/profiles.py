import uuid

from fastapi import APIRouter, Depends, HTTPException

from database import db, now_iso
from models import ProfileInput

# Canonical tweak catalogue (ids match ps_agent.py $script:TWEAKS)
TWEAK_CATALOG = [
    {"id": "power", "name": "Piano energetico prestazioni massime", "cat": "gaming"},
    {"id": "gaming", "name": "Boost gaming (Game Mode, HAGS, Game DVR off)", "cat": "gaming"},
    {"id": "priority", "name": "Priorità GPU/CPU ai giochi (MMCSS)", "cat": "gaming"},
    {"id": "mpo", "name": "Disabilita MPO (fix schermo nero OBS)", "cat": "gaming"},
    {"id": "gpu_msi", "name": "GPU: MSI mode ON (latenza DPC)", "cat": "gaming"},
    {"id": "amd_ulps", "name": "AMD: disabilita ULPS", "cat": "gaming"},
    {"id": "nvidia_tel", "name": "NVIDIA: disabilita telemetria", "cat": "gaming"},
    {"id": "hibernate", "name": "Disabilita ibernazione", "cat": "gaming"},
    {"id": "mouse", "name": "Accelerazione mouse OFF (raw input)", "cat": "input"},
    {"id": "timer", "name": "Timer resolution globale", "cat": "input"},
    {"id": "usb", "name": "USB power management OFF", "cat": "input"},
    {"id": "stickykeys", "name": "Sticky/Filter/Toggle Keys OFF", "cat": "input"},
    {"id": "startupdelay", "name": "Startup delay app ridotto", "cat": "input"},
    {"id": "network", "name": "Rete: Nagle OFF + TCP tuning", "cat": "network"},
    {"id": "dns", "name": "DNS veloci (Cloudflare)", "cat": "network"},
    {"id": "qos", "name": "Rimuovi 20% banda riservata QoS", "cat": "network"},
    {"id": "deliveryopt", "name": "Delivery Optimization P2P OFF", "cat": "network"},
    {"id": "obs_priority", "name": "OBS ad alta priorità", "cat": "network"},
    {"id": "clean", "name": "Pulizia temp + cache Windows Update", "cat": "system"},
    {"id": "visual", "name": "Effetti visivi: modalità prestazioni", "cat": "system"},
    {"id": "telemetry", "name": "Telemetria (DiagTrack) OFF", "cat": "system"},
    {"id": "ads", "name": "Suggerimenti/ads di Windows OFF", "cat": "system"},
    {"id": "bgapps", "name": "App in background OFF (globale)", "cat": "system"},
    {"id": "gamebar_rec", "name": "Xbox Game Bar recording OFF", "cat": "system"},
    {"id": "debloat", "name": "Debloat app superflue (UWP)", "cat": "system"},
    {"id": "search_index", "name": "Windows Search indexing OFF", "cat": "system"},
]

_FPS_CORE = ["power", "gaming", "priority", "mpo", "gpu_msi", "mouse", "timer", "usb", "network", "qos", "bgapps"]

TEMPLATES = [
    {"id": "tpl_valorant", "game_name": "Valorant", "template": True,
     "tweak_ids": _FPS_CORE + ["stickykeys"]},
    {"id": "tpl_cs2", "game_name": "CS2", "template": True,
     "tweak_ids": _FPS_CORE + ["stickykeys"]},
    {"id": "tpl_warzone", "game_name": "Warzone / Apex", "template": True,
     "tweak_ids": _FPS_CORE + ["visual"]},
    {"id": "tpl_fortnite", "game_name": "Fortnite", "template": True,
     "tweak_ids": _FPS_CORE},
    {"id": "tpl_streaming", "game_name": "OBS / Streaming", "template": True,
     "tweak_ids": ["power", "gaming", "priority", "mpo", "gpu_msi", "network", "dns", "qos",
                   "deliveryopt", "obs_priority", "telemetry", "bgapps"]},
]

_VALID_IDS = {t["id"] for t in TWEAK_CATALOG}


async def resolve_tweak_ids(database, user_id: str, profile_id: str):
    if not profile_id:
        return []
    if profile_id.startswith("tpl_"):
        for t in TEMPLATES:
            if t["id"] == profile_id:
                return t["tweak_ids"]
        return []
    doc = await database.game_profiles.find_one({"id": profile_id, "user_id": user_id})
    return (doc or {}).get("tweak_ids", [])


def build(get_current_user):
    r = APIRouter(prefix="/api/profiles", tags=["profiles"])

    @r.get("")
    async def list_profiles(user: dict = Depends(get_current_user)):
        return await db.game_profiles.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("updated_at", -1).to_list(100)

    @r.get("/templates")
    async def templates(user: dict = Depends(get_current_user)):
        return {"templates": TEMPLATES, "catalog": TWEAK_CATALOG}

    @r.post("")
    async def create_profile(payload: ProfileInput, user: dict = Depends(get_current_user)):
        ids = [i for i in payload.tweak_ids if i in _VALID_IDS]
        doc = {"id": str(uuid.uuid4()), "user_id": str(user["_id"]),
               "game_name": payload.game_name.strip() or "Profilo", "tweak_ids": ids,
               "created_at": now_iso(), "updated_at": now_iso()}
        await db.game_profiles.insert_one({**doc})
        return doc

    @r.put("/{pid}")
    async def update_profile(pid: str, payload: ProfileInput, user: dict = Depends(get_current_user)):
        ids = [i for i in payload.tweak_ids if i in _VALID_IDS]
        res = await db.game_profiles.update_one(
            {"id": pid, "user_id": str(user["_id"])},
            {"$set": {"game_name": payload.game_name.strip() or "Profilo", "tweak_ids": ids, "updated_at": now_iso()}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Profilo non trovato")
        return await db.game_profiles.find_one({"id": pid}, {"_id": 0})

    @r.delete("/{pid}")
    async def delete_profile(pid: str, user: dict = Depends(get_current_user)):
        await db.game_profiles.delete_one({"id": pid, "user_id": str(user["_id"])})
        return {"ok": True}

    return r
