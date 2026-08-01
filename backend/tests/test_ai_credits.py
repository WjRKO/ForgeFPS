"""Tests for AI Advisor credits system (Earned Premium model)."""
import os
import asyncio
import requests
import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PWD = "4zWK4o_xSw5prU-2b7w9dQ"
STARTER_EMAIL = "credits_test@frameforge.dev"
STARTER_PWD = "Cr3d1ts!Test99"


def _login(email, pwd):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PWD)


@pytest.fixture(scope="module")
def starter_session():
    return _login(STARTER_EMAIL, STARTER_PWD)


async def _mongo():
    c = AsyncIOMotorClient(MONGO_URL)
    return c[DB_NAME]


def _set_starter_credits(welcome, earned, earned_week=None):
    from datetime import datetime, timezone
    async def _run():
        db = await _mongo()
        u = await db.users.find_one({"email": STARTER_EMAIL})
        assert u, "test user missing"
        y, w, _d = datetime.now(timezone.utc).isocalendar()
        wk = earned_week or f"{y}-W{w:02d}"
        await db.users.update_one({"_id": u["_id"]}, {"$set": {
            "ai_welcome_credits": int(welcome),
            "ai_earned_credits": int(earned),
            "ai_earned_week": wk,
        }})
        return str(u["_id"])
    return asyncio.get_event_loop().run_until_complete(_run())


def _get_starter_doc():
    async def _run():
        db = await _mongo()
        return await db.users.find_one({"email": STARTER_EMAIL})
    return asyncio.get_event_loop().run_until_complete(_run())


# ---- streamer (admin) unlimited ----
def test_credits_streamer_unlimited(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/advisor/credits", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "unlimited", d
    assert d.get("is_streamer") is True


# ---- starter mode=credits shape ----
def test_credits_starter_mode(starter_session):
    _set_starter_credits(3, 2)
    r = starter_session.get(f"{BASE_URL}/api/advisor/credits", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "credits", d
    assert d["welcome"] == 3
    assert d["earned"] == 2
    assert d["total"] == 5
    assert "earned_expires_at" in d


# ---- starter consumes welcome first ----
def test_chat_consumes_welcome(starter_session):
    _set_starter_credits(4, 1)
    payload = {"message": "Ciao brevemente in 5 parole.", "session_id": None}
    with starter_session.post(f"{BASE_URL}/api/advisor/chat", json=payload, stream=True, timeout=60) as r:
        assert r.status_code == 200
        for _ in r.iter_content(chunk_size=None):
            pass
    r2 = starter_session.get(f"{BASE_URL}/api/advisor/credits", timeout=10)
    d = r2.json()
    assert d["welcome"] == 3, f"welcome should decrement 4->3, got {d}"
    assert d["earned"] == 1, d


# ---- starter no credits -> 402 no_credits ----
def test_chat_no_credits_returns_402(starter_session):
    _set_starter_credits(0, 0)
    r = starter_session.post(f"{BASE_URL}/api/advisor/chat",
                             json={"message": "test", "session_id": None}, timeout=15)
    assert r.status_code == 402, f"expected 402 got {r.status_code} {r.text[:200]}"
    body = r.json()
    detail = body.get("detail") or {}
    assert detail.get("code") == "no_credits", body


# ---- grant_credits via missions._award_xp ----
def test_mission_grants_earned_credits():
    """Simula mission award: chiama grant_credits direttamente."""
    async def _run():
        import sys
        sys.path.insert(0, "/app/backend")
        from ai_credits import grant_credits, week_id
        db = await _mongo()
        u = await db.users.find_one({"email": STARTER_EMAIL})
        uid = str(u["_id"])
        await db.users.update_one({"_id": u["_id"]},
                                  {"$set": {"ai_earned_credits": 0, "ai_earned_week": week_id()}})
        await grant_credits(db, uid, 2)  # mission
        u2 = await db.users.find_one({"_id": u["_id"]})
        assert u2.get("ai_earned_credits") == 2, u2
        assert u2.get("ai_earned_week") == week_id()
        # trophy bronze +5
        await grant_credits(db, uid, 5)
        u3 = await db.users.find_one({"_id": u["_id"]})
        assert u3.get("ai_earned_credits") == 7
    asyncio.get_event_loop().run_until_complete(_run())


# ---- diagnose still Pro-gated for starter ----
def test_diagnose_starter_gated(starter_session):
    r = starter_session.post(f"{BASE_URL}/api/advisor/diagnose", json={"lang": "it"}, timeout=15)
    assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text[:200]}"


# ---- leave the test user in a healthy state (starter, some credits) ----
def test_zzz_restore_starter_state():
    _set_starter_credits(3, 2)
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": STARTER_EMAIL, "password": STARTER_PWD}, timeout=10)
    s = requests.Session()
    s.cookies.update(r.cookies)
    q = s.get(f"{BASE_URL}/api/advisor/credits", timeout=10).json()
    assert q["total"] >= 5
