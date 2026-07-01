"""BOOST PC AI - Backend API tests"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="session")
def user_session():
    """Register a fresh test user session (cookie-based)."""
    s = requests.Session()
    email = f"test_user_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Tester"}, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["email"] == email.lower()
    s.email = email
    s.password = password
    return s


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


# ---------- AUTH ----------
class TestAuth:
    def test_register_login_me_logout(self):
        s = requests.Session()
        email = f"test_flow_{uuid.uuid4().hex[:8]}@example.com"
        pw = "Password123!"
        # register
        r = s.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Flow"}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == email.lower()
        assert "id" in data
        # /me
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == email
        # logout
        r = s.post(f"{API}/auth/logout", timeout=15)
        assert r.status_code == 200
        # after logout, /me should be 401
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401
        # login again
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
        assert r.status_code == 200
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == email

    def test_admin_login(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
        assert r.json()["role"] == "admin"

    def test_login_invalid_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrongpass"}, timeout=15)
        assert r.status_code == 401

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# ---------- Product Tracker ----------
class TestProducts:
    def test_track_amazon_url_creates_product(self, user_session):
        url = "https://www.amazon.it/dp/B0BSHF7WHW"
        r = user_session.post(f"{API}/products/track", json={"url": url, "target_price": 500}, timeout=60)
        assert r.status_code == 200, f"track failed: {r.status_code} {r.text}"
        p = r.json()
        assert "id" in p
        assert p["url"] == url
        # scrape likely blocked - status may be != 'ok', last_error may be set. Both allowed.
        pytest.shared_product_id = p["id"]

    def test_list_products_contains_tracked(self, user_session):
        r = user_session.get(f"{API}/products", timeout=15)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        assert any(p["id"] == pytest.shared_product_id for p in arr)

    def test_get_product_detail(self, user_session):
        pid = pytest.shared_product_id
        r = user_session.get(f"{API}/products/{pid}", timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["id"] == pid
        assert "history" in p and isinstance(p["history"], list)

    def test_set_manual_price(self, user_session):
        pid = pytest.shared_product_id
        r = user_session.put(f"{API}/products/{pid}/price", json={"price": 450.0}, timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["current_price"] == 450.0
        assert p["status"] == "ok"
        # verify persistence + history
        r = user_session.get(f"{API}/products/{pid}", timeout=15)
        assert r.status_code == 200
        det = r.json()
        assert det["current_price"] == 450.0
        assert len(det["history"]) >= 1
        assert any(h["price"] == 450.0 for h in det["history"])

    def test_set_target_price(self, user_session):
        pid = pytest.shared_product_id
        r = user_session.put(f"{API}/products/{pid}/target", json={"target_price": 400.0}, timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["target_price"] == 400.0

    def test_manual_price_lower_updates_lowest_price(self, user_session):
        """Setting a lower manual price should update lowest_price
        AND (new iteration) create a drop notification."""
        pid = pytest.shared_product_id
        r = user_session.put(f"{API}/products/{pid}/price", json={"price": 380.0}, timeout=15)
        assert r.status_code == 200
        assert r.json()["lowest_price"] == 380.0

    def test_products_search_query(self, user_session):
        r = user_session.post(f"{API}/products/search", json={"query": "RTX 4070"}, timeout=60)
        assert r.status_code == 200, f"search failed: {r.status_code} {r.text}"
        body = r.json()
        assert "results" in body
        assert isinstance(body["results"], list)

    def test_delete_product(self, user_session):
        # Create a product and delete
        r = user_session.post(f"{API}/products/track",
                              json={"url": "https://www.amazon.it/dp/TESTDEL"}, timeout=60)
        assert r.status_code == 200
        pid = r.json()["id"]
        r = user_session.delete(f"{API}/products/{pid}", timeout=15)
        assert r.status_code == 200
        r = user_session.get(f"{API}/products/{pid}", timeout=15)
        assert r.status_code == 404


# ---------- Notifications ----------
class TestNotifications:
    def test_list_notifications(self, user_session):
        r = user_session.get(f"{API}/notifications", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_read_all_notifications(self, user_session):
        r = user_session.post(f"{API}/notifications/read-all", timeout=15)
        assert r.status_code == 200
        assert r.json() == {"ok": True}


# ---------- Stats ----------
class TestStats:
    def test_stats_shape(self, user_session):
        r = user_session.get(f"{API}/stats", timeout=15)
        assert r.status_code == 200
        s = r.json()
        for key in ["tracked_products", "builds", "chat_sessions", "unread_notifications", "total_saved"]:
            assert key in s


# ---------- Desktop Agent (now requires auth + injects token) ----------
class TestDesktopAgent:
    def test_download_agent_unauth_401(self):
        r = requests.get(f"{API}/desktop-agent/download", timeout=30)
        assert r.status_code == 401

    def test_download_agent_authed_injects_token(self, user_session):
        r = user_session.get(f"{API}/desktop-agent/download", timeout=30)
        assert r.status_code == 200
        text = r.text
        assert len(text) > 100
        assert "import" in text
        # Placeholders should be replaced
        assert "__AGENT_TOKEN__" not in text
        assert "__BACKEND_URL__" not in text
        # Should contain agent token variable
        assert "AGENT_TOKEN =" in text
        assert "BACKEND_URL =" in text


# ---------- Push Notifications ----------
class TestPush:
    def test_vapid_public_key(self):
        r = requests.get(f"{API}/push/vapid-public-key", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "publicKey" in body
        assert isinstance(body["publicKey"], str)
        assert len(body["publicKey"]) > 20

    def test_subscribe_and_unsubscribe(self, user_session):
        fake_sub = {
            "endpoint": f"https://fcm.googleapis.com/fake/{uuid.uuid4().hex}",
            "keys": {"p256dh": "BFakeP256dhKey123", "auth": "FakeAuthKey"}
        }
        r = user_session.post(f"{API}/push/subscribe",
                              json={"subscription": fake_sub}, timeout=15)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # unsubscribe
        r = user_session.post(f"{API}/push/unsubscribe",
                              json={"subscription": fake_sub}, timeout=15)
        assert r.status_code == 200

    def test_subscribe_requires_auth(self):
        fake_sub = {"endpoint": "https://fcm.googleapis.com/x", "keys": {}}
        r = requests.post(f"{API}/push/subscribe", json={"subscription": fake_sub}, timeout=15)
        assert r.status_code == 401

    def test_push_test_endpoint_graceful(self, user_session):
        # Subscribe fake first so send_push_to_user has a target (will fail delivery but must not crash).
        fake_sub = {
            "endpoint": f"https://fcm.googleapis.com/fake/{uuid.uuid4().hex}",
            "keys": {"p256dh": "BFakeP256dhKey123", "auth": "FakeAuthKey"}
        }
        user_session.post(f"{API}/push/subscribe", json={"subscription": fake_sub}, timeout=15)
        r = user_session.post(f"{API}/push/test", timeout=30)
        assert r.status_code == 200
        assert r.json() == {"ok": True}


# ---------- Agent Token + Specs ----------
class TestAgentSpecs:
    def test_agent_token_returns_token(self, user_session):
        r = user_session.get(f"{API}/agent/token", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "token" in body
        assert isinstance(body["token"], str)
        assert len(body["token"]) > 10
        # idempotent - same token on second call
        r2 = user_session.get(f"{API}/agent/token", timeout=15)
        assert r2.json()["token"] == body["token"]
        user_session.agent_token = body["token"]

    def test_agent_token_requires_auth(self):
        r = requests.get(f"{API}/agent/token", timeout=15)
        assert r.status_code == 401

    def test_report_specs_invalid_token_401(self):
        r = requests.post(f"{API}/agent/report-specs",
                          json={"data": {"cpu": "x"}},
                          headers={"X-Agent-Token": "not-a-real-token-xyz"},
                          timeout=15)
        assert r.status_code == 401

    def test_report_specs_with_valid_token_and_read_back(self, user_session):
        # get token
        tr = user_session.get(f"{API}/agent/token", timeout=15)
        token = tr.json()["token"]
        payload = {"data": {"cpu": "Ryzen 7 5800X", "gpu": "RTX 3070",
                            "ram": "32 GB", "os": "Windows 11"}}
        r = requests.post(f"{API}/agent/report-specs",
                          json=payload, headers={"X-Agent-Token": token}, timeout=15)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # persistence
        r = user_session.get(f"{API}/pc-specs", timeout=15)
        assert r.status_code == 200
        specs = r.json()
        assert specs is not None
        assert specs["data"]["cpu"] == "Ryzen 7 5800X"
        assert specs["data"]["gpu"] == "RTX 3070"

    def test_pc_specs_requires_auth(self):
        r = requests.get(f"{API}/pc-specs", timeout=15)
        assert r.status_code == 401


# ---------- Manual price drop now sends push (graceful) ----------
class TestManualPriceCreatesNotification:
    def test_lower_manual_price_creates_notification(self, admin_session):
        # Create a product for admin
        url = f"https://www.amazon.it/dp/TESTNOTIF{uuid.uuid4().hex[:6]}"
        r = admin_session.post(f"{API}/products/track",
                               json={"url": url, "target_price": 100}, timeout=60)
        assert r.status_code == 200
        pid = r.json()["id"]
        # Set initial price high
        r = admin_session.put(f"{API}/products/{pid}/price", json={"price": 500.0}, timeout=15)
        assert r.status_code == 200
        # Now set a lower price -> should create notification
        before = admin_session.get(f"{API}/notifications", timeout=15).json()
        r = admin_session.put(f"{API}/products/{pid}/price", json={"price": 300.0}, timeout=30)
        assert r.status_code == 200
        after = admin_session.get(f"{API}/notifications", timeout=15).json()
        assert len(after) > len(before), "Manual lower price should create a notification"
        # cleanup
        admin_session.delete(f"{API}/products/{pid}", timeout=15)


# ---------- AI (expected graceful failure due to no balance) ----------
class TestAIGracefulErrors:
    def test_build_generate_graceful_error(self, user_session):
        r = user_session.post(f"{API}/builds/generate",
                              json={"budget": 1500, "use_case": "gaming",
                                    "resolution": "1440p", "notes": "test"},
                              timeout=60)
        # Expected 502 due to Emergent key no-balance; also acceptable 200 if by chance works
        assert r.status_code in (200, 502), f"unexpected {r.status_code}: {r.text[:200]}"
        if r.status_code == 502:
            body = r.json()
            assert "detail" in body

    def test_advisor_chat_graceful_error(self, user_session):
        r = user_session.post(f"{API}/advisor/chat",
                              json={"message": "Hi, quick test"},
                              timeout=60, stream=False)
        # Streaming endpoint should still return 200 with error text inside
        assert r.status_code == 200
        text = r.text
        assert "__SESSION__" in text
        # Should contain either normal content or "Errore AI" gracefully
        # (we don't fail if error present - that's the graceful case)
