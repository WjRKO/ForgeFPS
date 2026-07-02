from fastapi import APIRouter, Depends

import push
from database import db, now_iso
from models import PushSubInput


def build(get_current_user):
    r = APIRouter(prefix="/api/push", tags=["push"])

    @r.get("/vapid-public-key")
    async def vapid_public_key():
        return {"publicKey": push.get_public_key()}

    @r.post("/subscribe")
    async def push_subscribe(data: PushSubInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        endpoint = data.subscription.get("endpoint")
        await db.push_subscriptions.update_one(
            {"user_id": uid, "subscription.endpoint": endpoint},
            {"$set": {"user_id": uid, "subscription": data.subscription, "created_at": now_iso()}},
            upsert=True)
        return {"ok": True}

    @r.post("/unsubscribe")
    async def push_unsubscribe(data: PushSubInput, user: dict = Depends(get_current_user)):
        endpoint = data.subscription.get("endpoint")
        await db.push_subscriptions.delete_one({"user_id": str(user["_id"]), "subscription.endpoint": endpoint})
        return {"ok": True}

    @r.post("/test")
    async def push_test(user: dict = Depends(get_current_user)):
        await push.send_push_to_user(db, str(user["_id"]), {
            "title": "🔔 BOOST PC", "body": "Le notifiche push sono attive!", "url": "/app/tracker"})
        return {"ok": True}

    return r
