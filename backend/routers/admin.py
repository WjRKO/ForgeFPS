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
        product_counts = {d["_id"]: d["count"] async for d in db.products.aggregate(
            [{"$group": {"_id": "$user_id", "count": {"$sum": 1}}}])}
        build_counts = {d["_id"]: d["count"] async for d in db.builds.aggregate(
            [{"$group": {"_id": "$user_id", "count": {"$sum": 1}}}])}
        out = []
        for u in users:
            pub = _public(u)
            uid = str(u["_id"])
            pub["tracked_products"] = product_counts.get(uid, 0)
            pub["builds"] = build_counts.get(uid, 0)
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

    @r.post("/releases/mark-announced")
    async def mark_releases_announced(data: dict, admin: dict = Depends(require_admin)):
        """Marca una lista di versioni come gia' annunciate su Discord senza postare.
        Utile per il primo redeploy dopo aver aggiunto molte release al manifest:
        eviti che il release_announcer spammi il canale con embed vecchi.
        Body: {"versions": ["0.6.6", "0.6.7", ...]}"""
        from datetime import datetime, timezone
        versions = (data or {}).get("versions") or []
        if not isinstance(versions, list) or not versions:
            raise HTTPException(status_code=400, detail="Body deve essere {'versions': ['x.y.z', ...]}")
        now = datetime.now(timezone.utc).isoformat()
        marked, already = [], []
        for v in versions:
            if not isinstance(v, str):
                continue
            v = v.strip()
            if not v:
                continue
            existing = await db.announced_releases.find_one({"_id": v})
            if existing:
                already.append(v)
            else:
                await db.announced_releases.insert_one({
                    "_id": v, "announced_at": now,
                    "title": f"marked by admin {admin['email']}",
                    "date": "", "source": "admin_skip",
                })
                marked.append(v)
        return {"marked_as_announced": marked, "already_announced": already}

    @r.get("/password-resets")
    async def list_password_resets(admin: dict = Depends(require_admin), limit: int = 20):
        """Elenco ultimi N token di reset password generati.
        Utile finche' l'invio email vero (Resend/SendGrid) non e' integrato: l'admin
        vede il link e lo consegna manualmente all'utente. Solo admin.

        Response: lista ordinata per created_at desc, ognuno con:
        - email (denormalizzata)
        - link (path completo /reset-password?token=xxx da concatenare al dominio)
        - created_at, expires_at, used, used_at, ip
        - status: "active" | "used" | "expired"
        """
        from datetime import datetime, timezone
        limit = max(1, min(limit, 100))
        cursor = db.password_reset_tokens.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        rows = await cursor.to_list(limit)
        now = datetime.now(timezone.utc)
        out = []
        for r_ in rows:
            exp = r_.get("expires_at")
            if isinstance(exp, str):
                try: exp = datetime.fromisoformat(exp)
                except Exception: exp = None
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if r_.get("used"): status = "used"
            elif exp and exp < now: status = "expired"
            else: status = "active"
            out.append({
                "email": r_.get("email") or "(unknown — legacy record)",
                "link": f"/reset-password?token={r_.get('token', '')}",
                "created_at": r_.get("created_at"),
                "expires_at": r_.get("expires_at"),
                "used": bool(r_.get("used")),
                "used_at": r_.get("used_at"),
                "ip": r_.get("ip"),
                "status": status,
            })
        return {"items": out, "count": len(out)}

    return r
