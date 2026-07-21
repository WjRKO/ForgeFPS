"""Tests for POST /api/admin/releases/mark-announced (iteration 32).

Covers:
- AUTH: 401 senza cookie, 403 con utente non-admin
- SUCCESS: admin marca versioni pulite
- IDEMPOTENZA: seconda chiamata ritorna already_announced
- VALIDATION: body vuoto, versions vuoto, entries invalide filtrate
- DB SIDE EFFECT: entry con source='admin_skip' e title contenente 'marked by admin'
- INTEGRATION: announce_new_releases() skippa versioni gia' marcate e posta solo 0.6.14
"""
import os
import sys
import uuid
import asyncio
import pytest
import requests
from pathlib import Path
from dotenv import dotenv_values

# Load backend .env for MONGO_URL/DB_NAME/REACT_APP_BACKEND_URL fallback
_backend_env = dotenv_values("/app/backend/.env")
_frontend_env = dotenv_values("/app/frontend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or _frontend_env.get("REACT_APP_BACKEND_URL")
assert BACKEND_URL, "REACT_APP_BACKEND_URL missing"
BASE_URL = BACKEND_URL.rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = _backend_env.get("MONGO_URL") or os.environ.get("MONGO_URL")
DB_NAME = _backend_env.get("DB_NAME") or os.environ.get("DB_NAME")

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"

CLEANUP_IDS = ["test-a", "test-b", "0.6.6", "0.6.7", "0.6.8", "0.6.10", "0.6.13", "0.6.14"]

# Sync pymongo client for DB checks / cleanup (avoids motor event-loop clashes).
from pymongo import MongoClient
_mc = MongoClient(MONGO_URL)
_sdb = _mc[DB_NAME]


def _cleanup_db():
    _sdb.announced_releases.delete_many({"_id": {"$in": CLEANUP_IDS}})
    _sdb.announced_releases.delete_many({"source": "test_setup"})


@pytest.fixture(autouse=True)
def pre_cleanup():
    _cleanup_db()
    yield
    _cleanup_db()


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture
def user_session():
    s = requests.Session()
    email = f"nonadmin_{uuid.uuid4().hex[:8]}@test.io"
    pw = "Password123!"
    r = s.post(f"{API}/auth/register",
               json={"email": email, "password": pw, "name": "NonAdmin"}, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    r2 = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r2.status_code == 200
    return s


# ---------- AUTH ----------
def test_no_auth_returns_401():
    r = requests.post(f"{API}/admin/releases/mark-announced",
                      json={"versions": ["test-a"]}, timeout=15)
    assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"


def test_non_admin_returns_403(user_session):
    r = user_session.post(f"{API}/admin/releases/mark-announced",
                          json={"versions": ["test-a"]}, timeout=15)
    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"


# ---------- SUCCESS + DB SIDE EFFECT ----------
def test_admin_marks_versions_clean(admin_session):
    r = admin_session.post(f"{API}/admin/releases/mark-announced",
                           json={"versions": ["test-a", "test-b"]}, timeout=15)
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert set(data.get("marked_as_announced", [])) == {"test-a", "test-b"}
    assert data.get("already_announced") == []

    entry = _sdb.announced_releases.find_one({"_id": "test-a"})
    assert entry is not None
    assert entry.get("source") == "admin_skip"
    assert "marked by admin" in (entry.get("title") or "")


# ---------- IDEMPOTENZA ----------
def test_idempotent_second_call(admin_session):
    r1 = admin_session.post(f"{API}/admin/releases/mark-announced",
                            json={"versions": ["test-a", "test-b"]}, timeout=15)
    assert r1.status_code == 200
    r2 = admin_session.post(f"{API}/admin/releases/mark-announced",
                            json={"versions": ["test-a", "test-b"]}, timeout=15)
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("marked_as_announced") == []
    assert set(data.get("already_announced", [])) == {"test-a", "test-b"}


# ---------- VALIDATION ----------
def test_empty_body_returns_400(admin_session):
    r = admin_session.post(f"{API}/admin/releases/mark-announced", json={}, timeout=15)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"


def test_empty_versions_list_returns_400(admin_session):
    r = admin_session.post(f"{API}/admin/releases/mark-announced",
                           json={"versions": []}, timeout=15)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"


def test_invalid_entries_are_filtered(admin_session):
    # Impl: str(v).strip() - empty strings skipped. 123->"123", None->"None" (str)
    r = admin_session.post(f"{API}/admin/releases/mark-announced",
                           json={"versions": [123, None, "", "test-a"]}, timeout=15)
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    marked = data.get("marked_as_announced", [])
    assert "" not in marked
    assert "test-a" in marked


# ---------- INTEGRATION: announce_new_releases skippa marcate ----------
def test_integration_announcer_skips_marked(admin_session, monkeypatch):
    # Mark the 5 releases via the new admin endpoint (source=admin_skip).
    to_mark = ["0.6.6", "0.6.7", "0.6.8", "0.6.10", "0.6.13"]
    r = admin_session.post(f"{API}/admin/releases/mark-announced",
                           json={"versions": to_mark}, timeout=15)
    assert r.status_code == 200

    # Ensure older versions 0.6.0-0.6.5 are also marked (test_setup source, cleaned up).
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    for v in ["0.6.0", "0.6.1", "0.6.2", "0.6.3", "0.6.4", "0.6.5"]:
        if not _sdb.announced_releases.find_one({"_id": v}):
            _sdb.announced_releases.insert_one({
                "_id": v, "announced_at": now,
                "title": "pre-existing (test setup)", "date": "", "source": "test_setup",
            })

    # Monkeypatch post_release and RUN in the module's own event loop
    posted_versions = []

    async def fake_post_release(*, version, notes_md, url):
        posted_versions.append(version)
        return True

    sys.path.insert(0, "/app/backend")
    from services import release_announcer as ra
    monkeypatch.setattr(ra, "post_release", fake_post_release)
    monkeypatch.setenv("RELEASE_ANNOUNCER_ENABLED", "true")

    # Use a fresh loop and reinitialize motor client on that loop to avoid loop mismatch.
    # Simpler: call from a sync-run new loop; motor lazy-connects on first await.
    async def _run():
        return await ra.announce_new_releases()

    # Motor client from `database` is bound to whatever loop first used it.
    # Since the server is a separate process, in this test process motor is unused
    # until this point. Create a new loop, set as current, and run.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        count = loop.run_until_complete(_run())
    finally:
        loop.close()

    assert posted_versions == ["0.6.14"], f"expected only 0.6.14, got {posted_versions}"
    assert count == 1
