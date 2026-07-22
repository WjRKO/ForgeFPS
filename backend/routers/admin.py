from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from database import db
from models import RoleInput


def _oid(user_id: str) -> ObjectId:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="ID utente non valido")


def _public(u: dict) -> dict:
    return {"id": str(u["_id"]), "email": u["email"], "name": u.get("name", ""),
            "role": u.get("role", "user"), "created_at": u.get("created_at"),
            "plan": u.get("plan", "free"),
            "discord_user_id": u.get("discord_user_id") or None}


class BroadcastInput(BaseModel):
    title: str
    body: str = ""
    link: str = ""
    # scope: 'all' | 'admins' | 'boosted' (Discord-linked) | 'has_agent' (con pc_specs)
    scope: str = "all"


def build(get_current_user):
    r = APIRouter(prefix="/api/admin", tags=["admin"])

    async def require_admin(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Accesso riservato agli amministratori")
        return user

    @r.get("/users")
    async def list_users(admin: dict = Depends(require_admin)):
        users = await db.users.find({}, {"password_hash": 0}).sort("created_at", -1).to_list(2000)
        product_counts = {d["_id"]: d["count"] async for d in db.products.aggregate(
            [{"$group": {"_id": "$user_id", "count": {"$sum": 1}}}])}
        build_counts = {d["_id"]: d["count"] async for d in db.builds.aggregate(
            [{"$group": {"_id": "$user_id", "count": {"$sum": 1}}}])}
        # user_id -> updated_at (denota che l'utente ha l'agent installato e almeno un sync)
        pc_specs_map = {}
        async for d in db.pc_specs.find({}, {"user_id": 1, "updated_at": 1}):
            pc_specs_map[d.get("user_id")] = d.get("updated_at")
        out = []
        for u in users:
            pub = _public(u)
            uid = str(u["_id"])
            pub["tracked_products"] = product_counts.get(uid, 0)
            pub["builds"] = build_counts.get(uid, 0)
            pub["last_pc_sync"] = pc_specs_map.get(uid)
            pub["has_agent"] = uid in pc_specs_map
            pub["discord_linked"] = bool(pub.get("discord_user_id"))
            out.append(pub)
        return out

    @r.get("/users/{user_id}/details")
    async def user_details(user_id: str, admin: dict = Depends(require_admin)):
        """Dettaglio completo utente per la riga espandibile del pannello admin.
        Include: pc_specs (hardware, ultima sync), ultimo health score, plan,
        Discord user, ultimo benchmark, notifiche non lette."""
        u = await db.users.find_one({"_id": _oid(user_id)}, {"password_hash": 0})
        if not u:
            raise HTTPException(status_code=404, detail="Utente non trovato")
        pub = _public(u)
        specs = await db.pc_specs.find_one({"user_id": user_id}, {"_id": 0, "data": 1, "updated_at": 1, "benchmark": 1, "health": 1})
        last_health = await db.health_history.find_one({"user_id": user_id}, sort=[("created_at", -1)])
        pub["pc_specs"] = specs or None
        pub["last_health"] = {
            "score": last_health.get("score") if last_health else None,
            "grade": last_health.get("grade") if last_health else None,
            "created_at": last_health.get("created_at") if last_health else None,
        } if last_health else None
        pub["products_count"] = await db.products.count_documents({"user_id": user_id})
        pub["builds_count"] = await db.builds.count_documents({"user_id": user_id})
        pub["benchmarks_count"] = await db.benchmarks.count_documents({"user_id": user_id})
        pub["notifications_unread"] = await db.notifications.count_documents({"user_id": user_id, "read": {"$ne": True}})
        return pub

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
        now = datetime.now(timezone.utc)
        seven_days_ago = (now - timedelta(days=7)).isoformat()
        one_day_ago = (now - timedelta(days=1)).isoformat()
        return {
            "total_users": await db.users.count_documents({}),
            "total_admins": await db.users.count_documents({"role": "admin"}),
            "total_products": await db.products.count_documents({}),
            "total_builds": await db.builds.count_documents({}),
            "total_chat_sessions": await db.chat_sessions.count_documents({}),
            "total_notifications": await db.notifications.count_documents({}),
            # v0.7.4: extended stats
            "signups_last_7d": await db.users.count_documents({"created_at": {"$gte": seven_days_ago}}),
            "signups_last_24h": await db.users.count_documents({"created_at": {"$gte": one_day_ago}}),
            "users_with_agent": len(await db.pc_specs.distinct("user_id")),
            "users_discord_linked": await db.users.count_documents({"discord_user_id": {"$exists": True, "$ne": None}}),
            "total_benchmarks": await db.benchmarks.count_documents({}),
            "total_health_snapshots": await db.health_history.count_documents({}),
        }

    @r.get("/signups-timeline")
    async def signups_timeline(admin: dict = Depends(require_admin), days: int = 30):
        """Serie temporale delle registrazioni per il grafico admin.
        Ritorna una lista di {date: YYYY-MM-DD, count: N} per gli ultimi N giorni."""
        days = max(1, min(days, 90))
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
        cursor = db.users.find(
            {"created_at": {"$gte": start.isoformat()}},
            {"_id": 0, "created_at": 1},
        )
        buckets = {}
        # Pre-populate all days with 0
        for i in range(days + 1):
            d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            buckets[d] = 0
        async for u in cursor:
            ca = u.get("created_at") or ""
            if isinstance(ca, str) and len(ca) >= 10:
                day = ca[:10]
                if day in buckets:
                    buckets[day] += 1
        series = [{"date": k, "count": v} for k, v in sorted(buckets.items())]
        return {"days": days, "series": series, "total": sum(b["count"] for b in series)}

    @r.post("/broadcast")
    async def broadcast_notification(data: BroadcastInput, admin: dict = Depends(require_admin)):
        """Invia una notifica in-app a un target di utenti.
        scope: 'all' | 'admins' | 'boosted' (Discord-linked) | 'has_agent' (con pc_specs)

        Ritorna il numero di destinatari (documenti creati nella collezione notifications).
        """
        title = (data.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="Titolo richiesto")
        if len(title) > 120:
            raise HTTPException(status_code=400, detail="Titolo troppo lungo (max 120)")
        body = (data.body or "").strip()[:500]
        link = (data.link or "").strip()[:500]
        scope = data.scope if data.scope in ("all", "admins", "boosted", "has_agent") else "all"

        if scope == "all":
            user_ids = [str(u["_id"]) async for u in db.users.find({}, {"_id": 1})]
        elif scope == "admins":
            user_ids = [str(u["_id"]) async for u in db.users.find({"role": "admin"}, {"_id": 1})]
        elif scope == "boosted":
            user_ids = [str(u["_id"]) async for u in db.users.find(
                {"discord_user_id": {"$exists": True, "$ne": None}}, {"_id": 1})]
        else:  # has_agent
            user_ids = list(await db.pc_specs.distinct("user_id"))

        if not user_ids:
            return {"ok": True, "recipients": 0, "scope": scope}

        now_iso = datetime.now(timezone.utc).isoformat()
        docs = [{
            "user_id": uid,
            "type": "broadcast",
            "title": title,
            "body": body,
            "link": link,
            "created_at": now_iso,
            "read": False,
            "from_admin": admin["email"],
        } for uid in user_ids]
        await db.notifications.insert_many(docs)
        return {"ok": True, "recipients": len(docs), "scope": scope}

    @r.post("/releases/mark-announced")
    async def mark_releases_announced(data: dict, admin: dict = Depends(require_admin)):
        """Marca una lista di versioni come gia' annunciate su Discord senza postare.
        Utile per il primo redeploy dopo aver aggiunto molte release al manifest:
        eviti che il release_announcer spammi il canale con embed vecchi.
        Body: {"versions": ["0.6.6", "0.6.7", ...]}"""
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
