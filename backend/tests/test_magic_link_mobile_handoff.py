"""Tests for the 'Continue on Mobile' magic-link cross-device handoff feature.

Covers:
- Agent-side magic link creation (POST /api/agent/magic-link)
- Agent-side QR generation (GET /api/agent/magic-qr)
- Rate limiting (5/hour per user)
- Web magic-link + consume-magic with device label parsing
- Public /api/auth/magic-status
"""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://stream-gear-monitor.preview.emergentagent.com"
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


def _clean_magic_tokens():
    """Reset magic_tokens collection so rate-limits don't leak between tests."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def m():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        await db.magic_tokens.delete_many({})
    asyncio.run(m())


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE_URL}/api/agent/token", timeout=15)
    assert r.status_code == 200
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(autouse=True)
def clean_between():
    _clean_magic_tokens()
    yield


# ---------- Agent magic-link endpoint ----------

class TestAgentMagicLink:
    def test_magic_link_ok(self, agent_token):
        r = requests.post(f"{BASE_URL}/api/agent/magic-link",
                          headers={"X-Agent-Token": agent_token}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
        assert data["expires_in_seconds"] == 300
        assert "mobile_url" in data and "/auth/mobile?t=" in data["mobile_url"]

    def test_magic_link_no_token(self):
        r = requests.post(f"{BASE_URL}/api/agent/magic-link", timeout=15)
        assert r.status_code == 401

    def test_magic_link_invalid_token(self):
        r = requests.post(f"{BASE_URL}/api/agent/magic-link",
                          headers={"X-Agent-Token": "bogus_token_xyz"}, timeout=15)
        assert r.status_code == 401

    def test_magic_link_rate_limited(self, agent_token):
        # Create 5 successfully, 6th must return 429
        for i in range(5):
            r = requests.post(f"{BASE_URL}/api/agent/magic-link",
                              headers={"X-Agent-Token": agent_token}, timeout=15)
            assert r.status_code == 200, f"iteration {i}: {r.status_code} {r.text}"
        r = requests.post(f"{BASE_URL}/api/agent/magic-link",
                          headers={"X-Agent-Token": agent_token}, timeout=15)
        assert r.status_code == 429


# ---------- Agent magic-QR endpoint ----------

class TestAgentMagicQR:
    def test_qr_ok_svg(self, agent_token):
        r = requests.post(f"{BASE_URL}/api/agent/magic-link",
                          headers={"X-Agent-Token": agent_token}, timeout=15)
        assert r.status_code == 200
        tok = r.json()["token"]
        qr = requests.get(f"{BASE_URL}/api/agent/magic-qr",
                          params={"token": tok},
                          headers={"X-Agent-Token": agent_token}, timeout=15)
        assert qr.status_code == 200
        assert qr.headers.get("content-type", "").startswith("image/svg+xml")
        assert len(qr.content) > 500
        assert b"<svg" in qr.content

    def test_qr_unknown_token_404(self, agent_token):
        qr = requests.get(f"{BASE_URL}/api/agent/magic-qr",
                          params={"token": "does_not_exist_zzz"},
                          headers={"X-Agent-Token": agent_token}, timeout=15)
        assert qr.status_code == 404

    def test_qr_no_agent_token_401(self):
        qr = requests.get(f"{BASE_URL}/api/agent/magic-qr",
                          params={"token": "anything"}, timeout=15)
        assert qr.status_code == 401


# ---------- Web magic-status (public) ----------

class TestMagicStatus:
    def test_magic_status_unknown_404(self):
        r = requests.get(f"{BASE_URL}/api/auth/magic-status/no_such_token", timeout=15)
        assert r.status_code == 404

    def test_magic_status_unused(self, session):
        r = session.post(f"{BASE_URL}/api/auth/magic-link", timeout=15)
        assert r.status_code == 200
        tok = r.json()["token"]
        s = requests.get(f"{BASE_URL}/api/auth/magic-status/{tok}", timeout=15)  # public
        assert s.status_code == 200
        d = s.json()
        assert d["used"] is False
        assert d["expired"] is False
        assert d["device_label"] == ""


# ---------- Consume-magic device label parsing ----------

def _create_web_token(session):
    r = session.post(f"{BASE_URL}/api/auth/magic-link", timeout=15)
    assert r.status_code == 200
    return r.json()["token"]


@pytest.mark.parametrize("ua,expected", [
    ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36", "Android"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "iPhone"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Windows"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Mac"),
    ("", "Dispositivo sconosciuto"),
])
def test_consume_magic_device_label(session, ua, expected):
    token = _create_web_token(session)
    # Use fresh session so the consume doesn't clobber the module-level cookies.
    r = requests.post(f"{BASE_URL}/api/auth/consume-magic",
                      json={"token": token},
                      headers={"User-Agent": ua} if ua else {"User-Agent": ""}, timeout=15)
    assert r.status_code == 200, f"consume failed: {r.status_code} {r.text}"
    # status must reflect used + label
    s = requests.get(f"{BASE_URL}/api/auth/magic-status/{token}", timeout=15)
    assert s.status_code == 200
    d = s.json()
    assert d["used"] is True
    assert d["device_label"] == expected, f"UA={ua!r} -> {d['device_label']!r}, expected {expected!r}"


def test_consume_magic_single_use(session):
    token = _create_web_token(session)
    r1 = requests.post(f"{BASE_URL}/api/auth/consume-magic",
                       json={"token": token},
                       headers={"User-Agent": "Test"}, timeout=15)
    assert r1.status_code == 200
    r2 = requests.post(f"{BASE_URL}/api/auth/consume-magic",
                       json={"token": token},
                       headers={"User-Agent": "Test"}, timeout=15)
    assert r2.status_code == 401


# ---------- Regression: web magic-link + cookies ----------

def test_web_magic_link_still_works(session):
    r = session.post(f"{BASE_URL}/api/auth/magic-link", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "token" in d
    assert d.get("expires_in_seconds") == 300


def test_consume_magic_sets_cookies_and_returns_user(session):
    token = _create_web_token(session)
    fresh = requests.Session()
    r = fresh.post(f"{BASE_URL}/api/auth/consume-magic",
                   json={"token": token},
                   headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13)"}, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("email") == ADMIN_EMAIL
    assert "id" in body
    # cookies present
    assert "access_token" in fresh.cookies
    assert "refresh_token" in fresh.cookies
    # can call /me
    me = fresh.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me.status_code == 200
    assert me.json().get("email") == ADMIN_EMAIL
