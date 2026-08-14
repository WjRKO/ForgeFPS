"""Tests for Gameplay Doctor endpoints and diagnose regression.
Feature: POST/GET /api/advisor/gameplay-doctor (Pro-gated).
"""
import os
import time
import uuid
import requests
import pytest
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"))
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def free_user(mongo):
    """Register a fresh starter (free) user."""
    email = f"TEST_gd_free_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "Testpwd123!", "name": "TestFree"}, timeout=15)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:200]}"
    yield {"session": s, "email": email}
    # cleanup
    try:
        mongo.users.delete_many({"email": email.lower()})
    except Exception:
        pass


@pytest.fixture(scope="module")
def pro_user_no_telemetry(mongo):
    """Register a fresh user, promote to pro via DB, no telemetry seeded."""
    email = f"TEST_gd_pro_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "Testpwd123!", "name": "TestPro"}, timeout=15)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:200]}"
    uid_doc = mongo.users.find_one({"email": email.lower()})
    assert uid_doc is not None
    # promote to pro (mimic streamer effective plan)
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    mongo.users.update_one(
        {"_id": uid_doc["_id"]},
        {"$set": {"plan": "streamer", "subscription_status": "active",
                  "subscription_expires_at": expires}},
    )
    # ensure NO telemetry for this user
    mongo.pc_telemetry.delete_many({"user_id": str(uid_doc["_id"])})
    yield {"session": s, "email": email, "uid": str(uid_doc["_id"])}
    try:
        mongo.users.delete_many({"email": email.lower()})
    except Exception:
        pass


# ---------- REGRESSION: /diagnose still works ----------
def test_diagnose_regression_admin(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/advisor/diagnose", json={"lang": "it"}, timeout=120)
    assert r.status_code == 200, f"diagnose failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert "summary" in data and "actions" in data
    assert isinstance(data["actions"], list) and len(data["actions"]) >= 1
    a0 = data["actions"][0]
    for k in ("title", "description", "verify", "impact", "difficulty", "priority"):
        assert k in a0, f"missing key {k} in action: {a0}"


# ---------- Gameplay Doctor: GET latest (works even before generating) ----------
def test_gameplay_doctor_latest_admin_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/advisor/gameplay-doctor/latest", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "report" in d  # may be null or a document
    if d["report"]:
        assert "report" in d["report"] or "stats" in d["report"]


# ---------- Gameplay Doctor: POST admin (seeded telemetry) ----------
def test_gameplay_doctor_post_admin(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/advisor/gameplay-doctor",
                           json={"lang": "it"}, timeout=120)
    assert r.status_code == 200, f"POST gd failed: {r.status_code} {r.text[:500]}"
    d = r.json()
    assert "id" in d and "report" in d and "stats" in d
    rep = d["report"]
    assert "verdict" in rep and isinstance(rep["verdict"], str) and rep["verdict"]
    assert rep.get("health") in ("good", "minor", "bad"), f"invalid health: {rep.get('health')}"
    assert isinstance(rep.get("score"), (int, float))
    assert 0 <= rep["score"] <= 100
    assert "issues" in rep and isinstance(rep["issues"], list)
    # Sample the fields on issues (if present)
    if rep["issues"]:
        it = rep["issues"][0]
        for k in ("type", "severity", "title", "evidence", "cause", "fix"):
            assert k in it, f"missing key {k} in issue: {it}"
        # gui_tweak: present but may be null
        assert "gui_tweak" in it


# ---------- GET latest after POST ----------
def test_gameplay_doctor_latest_after_post(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/advisor/gameplay-doctor/latest", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("report") is not None, "no persisted report after POST"
    doc = d["report"]
    assert "report" in doc and "stats" in doc
    assert doc["report"].get("verdict")


# ---------- Gating: free user -> 402 ----------
def test_gameplay_doctor_free_user_gated(free_user):
    r = free_user["session"].post(f"{BASE_URL}/api/advisor/gameplay-doctor",
                                  json={"lang": "it"}, timeout=30)
    assert r.status_code in (402, 403), f"expected 402/403, got {r.status_code}: {r.text[:300]}"


def test_diagnose_free_user_gated(free_user):
    """Verify diagnose has consistent gating."""
    r = free_user["session"].post(f"{BASE_URL}/api/advisor/diagnose",
                                  json={"lang": "it"}, timeout=30)
    assert r.status_code in (402, 403), f"expected 402/403, got {r.status_code}: {r.text[:300]}"


# ---------- Edge: pro user with no telemetry -> 400 ----------
def test_gameplay_doctor_no_telemetry_400(pro_user_no_telemetry):
    r = pro_user_no_telemetry["session"].post(
        f"{BASE_URL}/api/advisor/gameplay-doctor",
        json={"lang": "it"}, timeout=30)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    assert isinstance(detail, str) and detail, "detail missing/empty"
    lo = detail.lower()
    assert any(k in lo for k in ("session", "sessione", "60", "monitor")), \
        f"unexpected 400 detail: {detail}"
