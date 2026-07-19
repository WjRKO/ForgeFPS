import uuid

from fastapi import APIRouter, Depends, HTTPException

from database import db, now_iso
from helpers import record_history, refresh_product_price, create_notification
from scraper import scrape_product, search_products
from models import TrackInput, ManualPriceInput, TargetInput, SearchInput, TitleInput


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["products"])

    @r.post("/products/search")
    async def product_search(data: SearchInput, user: dict = Depends(get_current_user)):
        results = await search_products(data.query, limit=10)
        return {"query": data.query, "results": results}

    @r.post("/products/track")
    async def track_product(data: TrackInput, user: dict = Depends(get_current_user)):
        scraped = await scrape_product(data.url)
        pid = str(uuid.uuid4())
        price = scraped.get("price")
        doc = {"id": pid, "user_id": str(user["_id"]), "url": data.url,
               "title": scraped.get("title") or "Prodotto senza titolo",
               "platform": scraped.get("platform"), "store": scraped.get("store"),
               "image": scraped.get("image"),
               "currency": scraped.get("currency", "EUR"),
               "current_price": price, "initial_price": price, "lowest_price": price,
               "target_price": data.target_price, "status": scraped.get("status"),
               "last_error": scraped.get("error"), "created_at": now_iso(), "updated_at": now_iso()}
        await db.products.insert_one(doc)
        if price is not None:
            await db.price_history.insert_one(record_history(pid, price))
        doc.pop("_id", None)
        return doc

    @r.get("/products")
    async def list_products(user: dict = Depends(get_current_user)):
        return await db.products.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(200)

    @r.get("/products/{product_id}")
    async def get_product(product_id: str, user: dict = Depends(get_current_user)):
        p = await db.products.find_one({"id": product_id, "user_id": str(user["_id"])}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Prodotto non trovato")
        p["history"] = await db.price_history.find(
            {"product_id": product_id}, {"_id": 0}).sort("recorded_at", -1).limit(200).to_list(200)
        p["history"].reverse()  # ripristina ordine cronologico (ascendente) come atteso dal FE
        return p

    @r.post("/products/{product_id}/refresh")
    async def refresh_product(product_id: str, user: dict = Depends(get_current_user)):
        p = await db.products.find_one({"id": product_id, "user_id": str(user["_id"])})
        if not p:
            raise HTTPException(status_code=404, detail="Prodotto non trovato")
        await refresh_product_price(p)
        return await db.products.find_one({"id": product_id}, {"_id": 0})

    @r.put("/products/{product_id}/price")
    async def set_manual_price(product_id: str, data: ManualPriceInput, user: dict = Depends(get_current_user)):
        p = await db.products.find_one({"id": product_id, "user_id": str(user["_id"])})
        if not p:
            raise HTTPException(status_code=404, detail="Prodotto non trovato")
        old = p.get("current_price")
        low = p.get("lowest_price")
        new_low = data.price if (low is None or data.price < low) else low
        await db.products.update_one({"id": product_id}, {"$set": {
            "current_price": data.price, "initial_price": p.get("initial_price") or data.price,
            "lowest_price": new_low, "status": "ok", "last_error": None, "updated_at": now_iso()}})
        await db.price_history.insert_one(record_history(product_id, data.price))
        target = p.get("target_price")
        dropped = old is not None and data.price < old
        hit_target = target is not None and data.price <= target
        if dropped or hit_target:
            await create_notification(str(user["_id"]), {**p, "id": product_id}, old, data.price, hit_target)
        return await db.products.find_one({"id": product_id}, {"_id": 0})

    @r.put("/products/{product_id}/title")
    async def set_manual_title(product_id: str, data: TitleInput, user: dict = Depends(get_current_user)):
        title = data.title.strip()[:200]
        if not title:
            raise HTTPException(status_code=400, detail="Il nome non può essere vuoto")
        res = await db.products.update_one({"id": product_id, "user_id": str(user["_id"])},
                                           {"$set": {"title": title, "updated_at": now_iso()}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Prodotto non trovato")
        return await db.products.find_one({"id": product_id}, {"_id": 0})

    @r.put("/products/{product_id}/target")
    async def set_target(product_id: str, data: TargetInput, user: dict = Depends(get_current_user)):
        res = await db.products.update_one({"id": product_id, "user_id": str(user["_id"])},
                                           {"$set": {"target_price": data.target_price}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Prodotto non trovato")
        return await db.products.find_one({"id": product_id}, {"_id": 0})

    @r.delete("/products/{product_id}")
    async def delete_product(product_id: str, user: dict = Depends(get_current_user)):
        await db.products.delete_one({"id": product_id, "user_id": str(user["_id"])})
        await db.price_history.delete_many({"product_id": product_id})
        return {"ok": True}

    # ---------- Notifications ----------
    @r.get("/notifications")
    async def list_notifications(user: dict = Depends(get_current_user)):
        return await db.notifications.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(100)

    @r.post("/notifications/{notif_id}/read")
    async def read_notification(notif_id: str, user: dict = Depends(get_current_user)):
        await db.notifications.update_one({"id": notif_id, "user_id": str(user["_id"])}, {"$set": {"read": True}})
        return {"ok": True}

    @r.post("/notifications/read-all")
    async def read_all(user: dict = Depends(get_current_user)):
        await db.notifications.update_many({"user_id": str(user["_id"])}, {"$set": {"read": True}})
        return {"ok": True}

    # ---------- Dashboard stats ----------
    @r.get("/stats")
    async def stats(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        products = await db.products.find(
            {"user_id": uid},
            {"_id": 0, "initial_price": 1, "current_price": 1},
        ).to_list(500)
        total_saved = sum((p["initial_price"] - p["current_price"]) for p in products
                          if p.get("initial_price") and p.get("current_price")
                          and p["current_price"] < p["initial_price"])
        return {
            "tracked_products": len(products),
            "builds": await db.builds.count_documents({"user_id": uid}),
            "chat_sessions": await db.chat_sessions.count_documents({"user_id": uid}),
            "unread_notifications": await db.notifications.count_documents({"user_id": uid, "read": False}),
            "total_saved": round(total_saved, 2),
        }

    return r
