from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from bson.errors import InvalidId

from database import db
from models import RoleInput


def _oid(user_id: str) -> ObjectId:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="ID utente non valido")


def _public(u: dict) -> dict:
    return {"id": str(u["_id"]), "email": u["email"], "name": u.get("name", ""),
            "role": u.get("role", "user"), "created_at": u.get("created_at")}


def build(get_current_user):
    r = APIRouter(prefix="/api/admin", tags=["admin"])

    async def require_admin(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Accesso riservato agli amministratori")
        return user

    @r.get("/users")
    async def list_users(admin: dict = Depends(require_admin)):
        users = await db.users.find({}, {"password_hash": 0}).sort("created_at", -1).to_list(1000)
        out = []
        for u in users:
            pub = _public(u)
            uid = str(u["_id"])
            pub["tracked_products"] = await db.products.count_documents({"user_id": uid})
            pub["builds"] = await db.builds.count_documents({"user_id": uid})
            out.append(pub)
        return out

    @r.patch("/users/{user_id}/role")
    async def change_role(user_id: str, data: RoleInput, admin: dict = Depends(require_admin)):
        if data.role not in ("user", "admin"):
            raise HTTPException(status_code=400, detail="Ruolo non valido")
        if user_id == str(admin["_id"]) and data.role != "admin":
            raise HTTPException(status_code=400, detail="Non puoi rimuovere il tuo stesso ruolo admin")
        res = await db.users.update_one({"_id": _oid(user_id)}, {"$set": {"role": data.role}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")
        return {"ok": True, "id": user_id, "role": data.role}

    @r.delete("/users/{user_id}")
    async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
        if user_id == str(admin["_id"]):
            raise HTTPException(status_code=400, detail="Non puoi eliminare il tuo stesso account")
        oid = _oid(user_id)
        if not await db.users.find_one({"_id": oid}):
            raise HTTPException(status_code=404, detail="Utente non trovato")
        await db.users.delete_one({"_id": oid})
        for coll in ("products", "price_history", "builds", "chat_sessions", "chat_messages",
                     "notifications", "pc_specs", "agent_tokens", "push_subscriptions"):
            await db[coll].delete_many({"user_id": user_id})
        return {"ok": True}

    @r.get("/stats")
    async def global_stats(admin: dict = Depends(require_admin)):
        return {
            "total_users": await db.users.count_documents({}),
            "total_admins": await db.users.count_documents({"role": "admin"}),
            "total_products": await db.products.count_documents({}),
            "total_builds": await db.builds.count_documents({}),
            "total_chat_sessions": await db.chat_sessions.count_documents({}),
            "total_notifications": await db.notifications.count_documents({}),
        }

    return r
