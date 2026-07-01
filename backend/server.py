from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import uuid
import secrets
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import StreamingResponse, PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from auth import build_auth_router, seed_admin
from scraper import scrape_product, search_products
import ai_engine
import push
from desktop_agent import AGENT_SCRIPT

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="BOOST PC AI")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("boostpc")

auth_router, get_current_user = build_auth_router(db)
scheduler = AsyncIOScheduler()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def specs_to_text(specs: dict) -> str:
    if not specs:
        return ""
    d = specs.get("data", {})
    parts = []
    for label, key in [("OS", "os"), ("CPU", "cpu"), ("GPU", "gpu"), ("RAM", "ram"),
                       ("Storage", "disk"), ("Scheda madre", "motherboard"), ("Risoluzione", "resolution")]:
        if d.get(key):
            parts.append(f"{label}: {d[key]}")
    return "\n".join(parts)


async def create_notification(user_id: str, product: dict, old_price, new_price, hit_target: bool):
    payload_title = product.get("title")
    notif = {
        "id": str(uuid.uuid4()), "user_id": user_id, "product_id": product["id"],
        "title": payload_title, "old_price": old_price, "new_price": new_price,
        "currency": product.get("currency", "EUR"),
        "type": "target" if hit_target else "drop",
        "message": (f"Prezzo target raggiunto! Ora {new_price}" if hit_target
                    else f"Prezzo sceso da {old_price} a {new_price}"),
        "read": False, "created_at": now_iso()}
    await db.notifications.insert_one(notif)
    await push.send_push_to_user(db, user_id, {
        "title": "📉 Calo di prezzo!" if not hit_target else "🎯 Prezzo target!",
        "body": f"{payload_title} → {new_price} {product.get('currency', 'EUR')}",
        "url": f"/app/tracker/{product['id']}"})


# ---------- Models ----------
class ChatMessageInput(BaseModel):
    message: str
    session_id: Optional[str] = None


class BuildInput(BaseModel):
    budget: int = Field(ge=300, le=15000)
    use_case: str
    resolution: str
    notes: Optional[str] = ""


class TrackInput(BaseModel):
    url: str
    target_price: Optional[float] = None


class ManualPriceInput(BaseModel):
    price: float


class TargetInput(BaseModel):
    target_price: float


class SearchInput(BaseModel):
    query: str


# ---------- AI Advisor ----------
@api.get("/advisor/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    sessions = await db.chat_sessions.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return sessions


@api.get("/advisor/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    msgs = await db.chat_messages.find(
        {"session_id": session_id, "user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return msgs


@api.delete("/advisor/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    await db.chat_messages.delete_many({"session_id": session_id, "user_id": str(user["_id"])})
    await db.chat_sessions.delete_one({"id": session_id, "user_id": str(user["_id"])})
    return {"ok": True}


@api.post("/advisor/chat")
async def advisor_chat(data: ChatMessageInput, user: dict = Depends(get_current_user)):
    uid = str(user["_id"])
    session_id = data.session_id or str(uuid.uuid4())
    existing = await db.chat_sessions.find_one({"id": session_id, "user_id": uid})
    if not existing:
        title = data.message[:40] + ("..." if len(data.message) > 40 else "")
        await db.chat_sessions.insert_one({"id": session_id, "user_id": uid, "title": title,
                                           "created_at": now_iso(), "updated_at": now_iso()})
    history = await db.chat_messages.find(
        {"session_id": session_id, "user_id": uid}, {"_id": 0}).sort("created_at", 1).to_list(500)
    await db.chat_messages.insert_one({"id": str(uuid.uuid4()), "session_id": session_id, "user_id": uid,
                                       "role": "user", "content": data.message, "created_at": now_iso()})
    specs = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0})
    specs_text = specs_to_text(specs)

    async def gen():
        yield f"__SESSION__{session_id}__\n"
        full = ""
        try:
            async for chunk in ai_engine.stream_advisor(session_id, history, data.message, specs_text):
                full += chunk
                yield chunk
        except Exception as e:
            err = f"\n\n[Errore AI: {str(e)[:120]}]"
            full += err
            yield err
        await db.chat_messages.insert_one({"id": str(uuid.uuid4()), "session_id": session_id, "user_id": uid,
                                           "role": "assistant", "content": full, "created_at": now_iso()})
        await db.chat_sessions.update_one({"id": session_id, "user_id": uid}, {"$set": {"updated_at": now_iso()}})

    return StreamingResponse(gen(), media_type="text/plain",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- Build Generator ----------
@api.post("/builds/generate")
async def generate_build_ep(data: BuildInput, user: dict = Depends(get_current_user)):
    try:
        build = await ai_engine.generate_build(data.budget, data.use_case, data.resolution, data.notes)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    doc = {"id": str(uuid.uuid4()), "user_id": str(user["_id"]),
           "budget": data.budget, "use_case": data.use_case, "resolution": data.resolution,
           "build": build, "saved": False, "created_at": now_iso()}
    return doc


@api.post("/builds/save")
async def save_build(doc: dict, user: dict = Depends(get_current_user)):
    doc["user_id"] = str(user["_id"])
    doc["saved"] = True
    doc["id"] = doc.get("id") or str(uuid.uuid4())
    doc.pop("_id", None)
    await db.builds.update_one({"id": doc["id"], "user_id": doc["user_id"]}, {"$set": doc}, upsert=True)
    return {"ok": True, "id": doc["id"]}


@api.get("/builds")
async def list_builds(user: dict = Depends(get_current_user)):
    return await db.builds.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.delete("/builds/{build_id}")
async def delete_build(build_id: str, user: dict = Depends(get_current_user)):
    await db.builds.delete_one({"id": build_id, "user_id": str(user["_id"])})
    return {"ok": True}


# ---------- Product Search ----------
@api.post("/products/search")
async def product_search(data: SearchInput, user: dict = Depends(get_current_user)):
    results = await search_products(data.query, limit=10)
    return {"query": data.query, "results": results}


# ---------- Product Tracker ----------
def _record_history(product_id: str, price: float):
    return {"product_id": product_id, "price": price, "recorded_at": now_iso()}


@api.post("/products/track")
async def track_product(data: TrackInput, user: dict = Depends(get_current_user)):
    scraped = await scrape_product(data.url)
    pid = str(uuid.uuid4())
    price = scraped.get("price")
    doc = {"id": pid, "user_id": str(user["_id"]), "url": data.url,
           "title": scraped.get("title") or "Prodotto senza titolo",
           "platform": scraped.get("platform"), "image": scraped.get("image"),
           "currency": scraped.get("currency", "EUR"),
           "current_price": price, "initial_price": price, "lowest_price": price,
           "target_price": data.target_price, "status": scraped.get("status"),
           "last_error": scraped.get("error"), "created_at": now_iso(), "updated_at": now_iso()}
    await db.products.insert_one(doc)
    if price is not None:
        await db.price_history.insert_one(_record_history(pid, price))
    doc.pop("_id", None)
    return doc


@api.get("/products")
async def list_products(user: dict = Depends(get_current_user)):
    return await db.products.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.get("/products/{product_id}")
async def get_product(product_id: str, user: dict = Depends(get_current_user)):
    p = await db.products.find_one({"id": product_id, "user_id": str(user["_id"])}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    history = await db.price_history.find({"product_id": product_id}, {"_id": 0}).sort("recorded_at", 1).to_list(1000)
    p["history"] = history
    return p


async def _refresh_one(product: dict) -> dict:
    scraped = await scrape_product(product["url"])
    price = scraped.get("price")
    update = {"updated_at": now_iso(), "status": scraped.get("status"), "last_error": scraped.get("error")}
    if scraped.get("title") and product.get("title") == "Prodotto senza titolo":
        update["title"] = scraped["title"]
    if scraped.get("image") and not product.get("image"):
        update["image"] = scraped["image"]
    notified = False
    if price is not None:
        old = product.get("current_price")
        update["current_price"] = price
        low = product.get("lowest_price")
        if low is None or price < low:
            update["lowest_price"] = price
        await db.price_history.insert_one(_record_history(product["id"], price))
        target = product.get("target_price")
        dropped = old is not None and price < old
        hit_target = target is not None and price <= target
        if dropped or hit_target:
            merged = {**product, **update, "id": product["id"], "user_id": product["user_id"]}
            await create_notification(product["user_id"], merged, old, price, hit_target)
            notified = True
    await db.products.update_one({"id": product["id"]}, {"$set": update})
    update["notified"] = notified
    return update


@api.post("/products/{product_id}/refresh")
async def refresh_product(product_id: str, user: dict = Depends(get_current_user)):
    p = await db.products.find_one({"id": product_id, "user_id": str(user["_id"])})
    if not p:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    await _refresh_one(p)
    updated = await db.products.find_one({"id": product_id}, {"_id": 0})
    return updated


@api.put("/products/{product_id}/price")
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
    await db.price_history.insert_one(_record_history(product_id, data.price))
    target = p.get("target_price")
    dropped = old is not None and data.price < old
    hit_target = target is not None and data.price <= target
    if dropped or hit_target:
        await create_notification(str(user["_id"]), {**p, "id": product_id}, old, data.price, hit_target)
    return await db.products.find_one({"id": product_id}, {"_id": 0})


@api.put("/products/{product_id}/target")
async def set_target(product_id: str, data: TargetInput, user: dict = Depends(get_current_user)):
    res = await db.products.update_one({"id": product_id, "user_id": str(user["_id"])},
                                       {"$set": {"target_price": data.target_price}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    return await db.products.find_one({"id": product_id}, {"_id": 0})


@api.delete("/products/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(get_current_user)):
    await db.products.delete_one({"id": product_id, "user_id": str(user["_id"])})
    await db.price_history.delete_many({"product_id": product_id})
    return {"ok": True}


# ---------- Notifications ----------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    return await db.notifications.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.post("/notifications/{notif_id}/read")
async def read_notification(notif_id: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one({"id": notif_id, "user_id": str(user["_id"])}, {"$set": {"read": True}})
    return {"ok": True}


@api.post("/notifications/read-all")
async def read_all(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": str(user["_id"])}, {"$set": {"read": True}})
    return {"ok": True}


# ---------- Dashboard stats ----------
@api.get("/stats")
async def stats(user: dict = Depends(get_current_user)):
    uid = str(user["_id"])
    products = await db.products.find({"user_id": uid}, {"_id": 0}).to_list(500)
    total_saved = 0.0
    for p in products:
        init, cur = p.get("initial_price"), p.get("current_price")
        if init and cur and cur < init:
            total_saved += (init - cur)
    return {
        "tracked_products": len(products),
        "builds": await db.builds.count_documents({"user_id": uid}),
        "chat_sessions": await db.chat_sessions.count_documents({"user_id": uid}),
        "unread_notifications": await db.notifications.count_documents({"user_id": uid, "read": False}),
        "total_saved": round(total_saved, 2),
    }


# ---------- Push Notifications ----------
class PushSubInput(BaseModel):
    subscription: dict


@api.get("/push/vapid-public-key")
async def vapid_public_key():
    return {"publicKey": push.get_public_key()}


@api.post("/push/subscribe")
async def push_subscribe(data: PushSubInput, user: dict = Depends(get_current_user)):
    uid = str(user["_id"])
    endpoint = data.subscription.get("endpoint")
    await db.push_subscriptions.update_one(
        {"user_id": uid, "subscription.endpoint": endpoint},
        {"$set": {"user_id": uid, "subscription": data.subscription, "created_at": now_iso()}},
        upsert=True)
    return {"ok": True}


@api.post("/push/unsubscribe")
async def push_unsubscribe(data: PushSubInput, user: dict = Depends(get_current_user)):
    endpoint = data.subscription.get("endpoint")
    await db.push_subscriptions.delete_one({"user_id": str(user["_id"]), "subscription.endpoint": endpoint})
    return {"ok": True}


@api.post("/push/test")
async def push_test(user: dict = Depends(get_current_user)):
    await push.send_push_to_user(db, str(user["_id"]), {
        "title": "🔔 BOOST PC", "body": "Le notifiche push sono attive!", "url": "/app/tracker"})
    return {"ok": True}


# ---------- PC Hardware Specs ----------
async def get_or_create_agent_token(uid: str) -> str:
    rec = await db.agent_tokens.find_one({"user_id": uid})
    if rec:
        return rec["token"]
    token = secrets.token_urlsafe(24)
    await db.agent_tokens.insert_one({"user_id": uid, "token": token, "created_at": now_iso()})
    return token


class SpecsInput(BaseModel):
    data: dict


@api.get("/agent/token")
async def agent_token(user: dict = Depends(get_current_user)):
    return {"token": await get_or_create_agent_token(str(user["_id"]))}


@api.post("/agent/report-specs")
async def report_specs(data: SpecsInput, x_agent_token: str = Header(default="")):
    rec = await db.agent_tokens.find_one({"token": x_agent_token})
    if not rec:
        raise HTTPException(status_code=401, detail="Token agent non valido")
    uid = rec["user_id"]
    await db.pc_specs.update_one({"user_id": uid},
                                 {"$set": {"user_id": uid, "data": data.data, "updated_at": now_iso()}},
                                 upsert=True)
    return {"ok": True}


@api.get("/pc-specs")
async def get_specs(user: dict = Depends(get_current_user)):
    return await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})


# ---------- Desktop Agent ----------
@api.get("/desktop-agent/download")
async def download_agent(user: dict = Depends(get_current_user)):
    token = await get_or_create_agent_token(str(user["_id"]))
    backend = os.environ.get("FRONTEND_URL", "http://localhost:8001")
    script = AGENT_SCRIPT.replace("__BACKEND_URL__", backend).replace("__AGENT_TOKEN__", token)
    return PlainTextResponse(script, headers={
        "Content-Disposition": "attachment; filename=boostpc_agent.py"})


@api.get("/")
async def root():
    return {"message": "BOOST PC AI online"}


# ---------- Scheduler ----------
async def scheduled_price_check():
    logger.info("Running scheduled price check...")
    cursor = db.products.find({})
    async for product in cursor:
        try:
            await _refresh_one(product)
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Price check failed for {product.get('id')}: {e}")


app.include_router(auth_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    await db.products.create_index("user_id")
    await db.price_history.create_index("product_id")
    await db.agent_tokens.create_index("token")
    await db.agent_tokens.create_index("user_id")
    await db.push_subscriptions.create_index("user_id")
    await db.pc_specs.create_index("user_id")
    await seed_admin(db)
    Path("/app/memory").mkdir(exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("# Test Credentials\n\n## Admin\n- Email: admin@boostpc.io\n- Password: admin123\n- Role: admin\n\n"
                "## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- GET /api/auth/me\n"
                "- POST /api/auth/logout\n- POST /api/auth/refresh\n")
    scheduler.add_job(scheduled_price_check, "interval", minutes=45, id="price_check", replace_existing=True)
    scheduler.start()
    logger.info("BOOST PC AI started")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)
    client.close()
