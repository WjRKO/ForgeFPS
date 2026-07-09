import os
import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import db, client
from auth import build_auth_router, seed_admin
from helpers import refresh_product_price
from settings import get_cors_origins
from routers import advisor, builds, products, pc, push_routes, admin, profiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("boostpc")

app = FastAPI(title="FrameForge")
auth_router, get_current_user = build_auth_router(db)
scheduler = AsyncIOScheduler()

app.include_router(auth_router)
for module in (advisor, builds, products, pc, push_routes, admin, profiles):
    app.include_router(module.build(get_current_user))


@app.get("/api/")
async def root():
    return {"message": "FrameForge online"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PRICE_CHECK_BATCH = 100


async def scheduled_price_check():
    logger.info("Running scheduled price check...")
    cursor = db.products.find({"url": {"$ne": ""}}).sort("updated_at", 1).limit(PRICE_CHECK_BATCH)
    async for product in cursor:
        try:
            await refresh_product_price(product)
        except Exception as e:
            logger.warning(f"Price check failed for {product.get('id')}: {e}")


async def _ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    await db.products.create_index("user_id")
    await db.price_history.create_index("product_id")
    await db.agent_tokens.create_index("token")
    await db.agent_tokens.create_index("user_id")
    await db.push_subscriptions.create_index("user_id")
    await db.pc_specs.create_index("user_id")


def _write_test_credentials():
    email = os.environ.get("ADMIN_EMAIL", "")
    password = os.environ.get("ADMIN_PASSWORD", "")
    Path("/app/memory").mkdir(exist_ok=True)
    Path("/app/memory/test_credentials.md").write_text(
        f"# Test Credentials\n\n## Admin\n- Email: {email}\n- Password: {password}\n- Role: admin\n\n"
        "## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- GET /api/auth/me\n"
        "- POST /api/auth/logout\n- POST /api/auth/refresh\n")


@app.on_event("startup")
async def startup():
    await _ensure_indexes()
    await seed_admin(db)
    _write_test_credentials()
    scheduler.add_job(scheduled_price_check, "interval", minutes=45, id="price_check", replace_existing=True)
    scheduler.start()
    logger.info("FrameForge started")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)
    client.close()
