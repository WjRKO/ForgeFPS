"""Backend tests for SaaS plan gating (Starter/Pro/Streamer) & Earned Premium unlocks.

Covers: /api/subscriptions/status entitlements, 402 gates for advanced tweaks,
tracker limit, health-history 7d limit, milestones catalog rewards,
missions available filter, plan-required 402s.
"""
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

from dotenv import load_dotenv
load_dotenv("../frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
DB_NAME = os.environ.get("DB_NAME") or "test_database"

STARTER_EMAIL = os.environ.get("STARTER_EMAIL", os.environ.get("STARTER_EMAIL", "credits_test@frameforge.dev"))
STARTER_PASS = os.environ.get("STARTER_PASSWORD", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"))
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "")


def _login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def starter_session():
    s = requests.Session()
    _login(s, STARTER_EMAIL, STARTER_PASS)
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASS)
    return s


@pytest.fixture(scope="module")
def starter_uid(mongo):
    u = mongo.users.find_one({"email": STARTER_EMAIL})
    assert u, "starter test user not found in DB"
    return str(u["_id"])


@pytest.fixture(scope="module", autouse=True)
def _restore_starter(mongo, starter_uid):
    """Ensure test user is starter with clean features + progress at start and end."""
    yield
    # Teardown: restore starter plan, remove adv_tweaks feature flag, cleanup TEST_ health points, TEST_ products
    mongo.users.update_one({"email": STARTER_EMAIL},
                           {"$set": {"plan": "starter"},
                            "$unset": {"trial_expires_at": "", "trial_used": ""}})
    mongo.user_progress.update_one({"user_id": starter_uid},
                                   {"$unset": {"features.adv_tweaks": "",
                                               "features.advanced_registry_tweaks": ""}})
    mongo.products.delete_many({"user_id": starter_uid, "url": {"$regex": "TEST_"}})
    mongo.health_history.delete_many({"user_id": starter_uid, "_test_seed": True})


# ------------------------------------------------------------
# 1. subscriptions/status entitlements shape
# ------------------------------------------------------------
class TestEntitlements:
    def test_starter_entitlements(self, starter_session):
        r = starter_session.get(f"{API}/subscriptions/status", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "entitlements" in data, data
        ent = data["entitlements"]
        assert ent["adv_tweaks"] is False
        assert ent["history_90d"] is False
        assert ent["pdf_report"] is False
        assert ent["gpu_reference_full"] is False
        assert ent["full_benchmark"] is False
        assert ent["tracker_limit"] == 3

    def test_admin_streamer_entitlements(self, admin_session):
        r = admin_session.get(f"{API}/subscriptions/status", timeout=10)
        assert r.status_code == 200, r.text
        ent = r.json()["entitlements"]
        assert ent["adv_tweaks"] is True
        assert ent["history_90d"] is True
        assert ent["pdf_report"] is True
        assert ent["gpu_reference_full"] is True
        assert ent["full_benchmark"] is True
        assert ent["tracker_limit"] == 25


# ------------------------------------------------------------
# 2. Advanced tweaks 402 gates for starter
# ------------------------------------------------------------
class TestAdvTweaks402:
    ENDPOINTS = [
        ("GET", "/net-result"),
        ("GET", "/prematch"),
        ("PUT", "/prematch"),
        ("GET", "/booster"),
        ("PUT", "/booster"),
        ("GET", "/booster/sessions"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_starter_402_adv_tweaks(self, starter_session, method, path):
        url = f"{API}{path}"
        body = None
        if method == "PUT" and path == "/prematch":
            body = {"do_not_disturb": False, "clear_shader_cache": False, "close_apps": []}
        elif method == "PUT" and path == "/booster":
            body = {"enabled": False, "game": None}
        r = starter_session.request(method, url, json=body, timeout=10)
        assert r.status_code == 402, f"{method} {path} → {r.status_code} {r.text}"
        detail = r.json().get("detail") or {}
        assert detail.get("code") == "adv_tweaks_required", detail

    def test_starter_full_benchmark_402(self, starter_session):
        r = starter_session.get(f"{API}/pc-benchmark/full", timeout=10)
        assert r.status_code == 402
        detail = r.json().get("detail") or {}
        assert detail.get("code") in ("plan_required", "adv_tweaks_required"), detail

    def test_starter_put_alerts_402(self, starter_session):
        # GET alerts should be 200
        rg = starter_session.get(f"{API}/alerts", timeout=10)
        assert rg.status_code == 200, rg.text
        # PUT alerts → 402
        rp = starter_session.put(f"{API}/alerts",
                                  json={"cpu_temp": 85, "gpu_temp": 85}, timeout=10)
        assert rp.status_code == 402, rp.text


# ------------------------------------------------------------
# 3. Trophy unlock via features.adv_tweaks flips endpoints to 200
# ------------------------------------------------------------
class TestTrophyUnlock:
    def test_setting_adv_tweaks_feature_opens_endpoints(self, mongo, starter_session, starter_uid):
        # Set flag
        mongo.user_progress.update_one({"user_id": starter_uid},
                                       {"$set": {"features.adv_tweaks": True}},
                                       upsert=True)
        try:
            r1 = starter_session.get(f"{API}/booster", timeout=10)
            r2 = starter_session.get(f"{API}/net-result", timeout=10)
            assert r1.status_code == 200, r1.text
            assert r2.status_code == 200, r2.text
        finally:
            mongo.user_progress.update_one({"user_id": starter_uid},
                                           {"$unset": {"features.adv_tweaks": ""}})


# ------------------------------------------------------------
# 4. Tracker limit
# ------------------------------------------------------------
class TestTrackerLimit:
    def test_starter_tracker_limit(self, starter_session, mongo, starter_uid):
        # Clean any previous test products
        mongo.products.delete_many({"user_id": starter_uid, "url": {"$regex": "^TEST_"}})
        # Pre-existing? Ensure exactly 0 to start counting
        existing_count = mongo.products.count_documents({"user_id": starter_uid})
        # We seed 3 fake products directly to hit the limit deterministically
        seed_ids = []
        for i in range(max(0, 3 - existing_count)):
            pid = f"TEST_seed_{i}_{int(time.time())}"
            mongo.products.insert_one({
                "id": pid, "user_id": starter_uid,
                "url": f"TEST_url_{pid}", "title": f"TEST_prod_{i}",
                "current_price": 10.0, "initial_price": 10.0, "lowest_price": 10.0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            seed_ids.append(pid)
        try:
            count = mongo.products.count_documents({"user_id": starter_uid})
            assert count >= 3, f"expected >=3 products, got {count}"
            # 4th insert should 402
            r = starter_session.post(f"{API}/products/track",
                                     json={"url": "TEST_https://amazon.it/dp/BLOCKED"},
                                     timeout=15)
            assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"
            detail = r.json().get("detail") or {}
            assert detail.get("code") == "tracker_limit", detail
        finally:
            mongo.products.delete_many({"user_id": starter_uid, "url": {"$regex": "^TEST_"}})


# ------------------------------------------------------------
# 5. Health history 7-day limit for starter
# ------------------------------------------------------------
class TestHealthHistoryLimit:
    def test_starter_limited_days_7(self, starter_session, mongo, starter_uid):
        now = datetime.now(timezone.utc)
        old_iso = (now - timedelta(days=30)).isoformat()
        recent_iso = (now - timedelta(days=1)).isoformat()
        # Seed 2 old + 2 recent
        mongo.health_history.delete_many({"user_id": starter_uid, "_test_seed": True})
        docs = [
            {"user_id": starter_uid, "score": 55, "created_at": old_iso, "_test_seed": True},
            {"user_id": starter_uid, "score": 60, "created_at": old_iso, "_test_seed": True},
            {"user_id": starter_uid, "score": 75, "created_at": recent_iso, "_test_seed": True},
            {"user_id": starter_uid, "score": 80, "created_at": recent_iso, "_test_seed": True},
        ]
        mongo.health_history.insert_many(docs)
        try:
            r = starter_session.get(f"{API}/health-history", timeout=10)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("limited_days") == 7, data
            # Ensure no seeded point older than 7 days appears
            for p in data.get("points", []):
                ca = str(p.get("created_at") or "")
                assert ca >= (now - timedelta(days=7)).isoformat() or not p.get("_test_seed"), ca
        finally:
            mongo.health_history.delete_many({"user_id": starter_uid, "_test_seed": True})

    def test_admin_no_limited_days(self, admin_session):
        r = admin_session.get(f"{API}/health-history", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "limited_days" not in data, data


# ------------------------------------------------------------
# 6. Temporary Pro promotion opens gated endpoints
# ------------------------------------------------------------
class TestProPromotion:
    def test_starter_promoted_to_pro(self, starter_session, mongo):
        mongo.users.update_one({"email": STARTER_EMAIL}, {"$set": {"plan": "pro"}})
        try:
            r_bench = starter_session.get(f"{API}/pc-benchmark/full", timeout=10)
            r_booster = starter_session.get(f"{API}/booster", timeout=10)
            r_net = starter_session.get(f"{API}/net-result", timeout=10)
            r_alerts = starter_session.put(f"{API}/alerts",
                                            json={"cpu_temp": 85, "gpu_temp": 85}, timeout=10)
            assert r_booster.status_code == 200, r_booster.text
            assert r_net.status_code == 200, r_net.text
            # Full bench may 400/500 for missing data but must NOT be 402
            assert r_bench.status_code != 402, r_bench.text
            assert r_alerts.status_code in (200, 204), r_alerts.text
        finally:
            mongo.users.update_one({"email": STARTER_EMAIL}, {"$set": {"plan": "starter"}})


# ------------------------------------------------------------
# 7. Milestones catalog rewards
# ------------------------------------------------------------
class TestMilestonesRewards:
    def test_milestones_catalog_rewards(self, starter_session):
        r = starter_session.get(f"{API}/milestones", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        by_code = {m["code"]: m for m in data["milestones"]}
        assert by_code["tweaks_10"]["reward"]["key"] == "adv_tweaks"
        assert by_code["tweaks_50"]["reward"]["key"] == "pdf_report"
        assert by_code["health_streak_7"]["reward"]["key"] == "history_90d"
        # speed_demon is secret & locked -> masked (reward None). Check that a milestone
        # with reward.key == gpu_reference_full exists somewhere OR the secret is unlocked.
        sd = by_code.get("speed_demon")
        if sd and sd.get("reward"):
            assert sd["reward"]["key"] == "gpu_reference_full"
        else:
            # secret masked: name should be "???"
            assert sd is not None
            assert sd.get("name_it") == "???"


# ------------------------------------------------------------
# 8. Missions available filter
# ------------------------------------------------------------
class TestMissionsFilter:
    def test_starter_missions_no_adv_in_available(self, starter_session, mongo, starter_uid):
        # Ensure adv_tweaks flag off
        mongo.user_progress.update_one({"user_id": starter_uid},
                                       {"$unset": {"features.adv_tweaks": ""}})
        r = starter_session.get(f"{API}/missions", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        available_codes = [m["code"] for m in data.get("available", [])]
        assert "net_check" not in available_codes, available_codes
        assert "boost_match" not in available_codes, available_codes
