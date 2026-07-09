"""BOOST PC AI - Backend API tests"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


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


# ==================================================================
# Iteration 3 - Health / Upgrade / FPS / Startup / Track components
# ==================================================================

# Helper: ensure a user has specs+health+startup stored via agent token
def _seed_specs_health_startup(session, health_overrides=None, startup=None):
    tr = session.get(f"{API}/agent/token", timeout=15)
    assert tr.status_code == 200
    token = tr.json()["token"]
    health = {
        "temp_mb": 3200, "startup_count": 14, "power_plan": "Balanced",
        "game_mode": False, "gpu_scheduling": True, "ram_used_pct": 72,
        "disk_free_pct": 9, "gpu_driver_version": "551.23",
        "gpu_driver_date": "2024-02-01",
    }
    if health_overrides:
        health.update(health_overrides)
    payload = {
        "data": {"cpu": "Ryzen 7 5800X", "gpu": "RTX 3070",
                 "ram": "32 GB", "os": "Windows 11"},
        "health": health,
        "startup": startup if startup is not None else ["Steam", "Discord", "Spotify", "OneDrive"],
    }
    r = requests.post(f"{API}/agent/report-specs", json=payload,
                      headers={"X-Agent-Token": token}, timeout=15)
    assert r.status_code == 200, f"seed failed: {r.status_code} {r.text}"
    return token


# ---------- PC Health ----------
class TestPCHealth:
    def test_pc_health_unavailable_when_no_data(self, user_session):
        # Fresh user - initially no health stored (only specs may have been set earlier)
        # We create a brand-new session for isolation
        s = requests.Session()
        email = f"health_none_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Password123!", "name": "T"}, timeout=30)
        assert r.status_code == 200
        r = s.get(f"{API}/pc-health", timeout=15)
        assert r.status_code == 200
        assert r.json() == {"available": False}

    def test_pc_health_bad_values_lower_score(self, admin_session):
        _seed_specs_health_startup(admin_session)  # bad-ish values
        r = admin_session.get(f"{API}/pc-health", timeout=15)
        assert r.status_code == 200
        h = r.json()
        assert h.get("available") is True
        assert 0 <= h["score"] <= 100
        assert h["score"] < 85, f"bad values should reduce score, got {h['score']}"
        assert h["grade"] in ("Ottimo", "Buono", "Da migliorare", "Critico")
        assert isinstance(h["checks"], list) and len(h["checks"]) >= 5
        statuses = {c["status"] for c in h["checks"]}
        assert statuses & {"ok", "warn", "bad"}
        # driver_version echo
        assert h.get("driver_version") == "551.23"

    def test_pc_health_good_values_high_score(self, admin_session):
        _seed_specs_health_startup(admin_session, health_overrides={
            "temp_mb": 200, "startup_count": 5, "power_plan": "High Performance",
            "game_mode": True, "gpu_scheduling": True, "ram_used_pct": 40,
            "disk_free_pct": 55, "gpu_driver_version": "551.23",
            "gpu_driver_date": (time.strftime("%Y-%m-%d")),
        })
        r = admin_session.get(f"{API}/pc-health", timeout=15)
        assert r.status_code == 200
        h = r.json()
        assert h["score"] >= 85, f"good values should give high score, got {h['score']}"
        assert h["grade"] == "Ottimo"

    def test_pc_health_requires_auth(self):
        r = requests.get(f"{API}/pc-health", timeout=15)
        assert r.status_code == 401


# ---------- Upgrade Analyze (AI) ----------
class TestUpgradeAnalyze:
    def test_upgrade_without_specs_returns_400(self):
        s = requests.Session()
        email = f"upg_nospecs_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Password123!", "name": "T"}, timeout=30)
        assert r.status_code == 200
        r = s.post(f"{API}/upgrade/analyze", json={"budget": 800, "goal": "gaming"}, timeout=30)
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_upgrade_with_specs_returns_ai_json(self, admin_session):
        _seed_specs_health_startup(admin_session)
        r = admin_session.post(f"{API}/upgrade/analyze",
                               json={"budget": 900, "goal": "gaming 1440p"}, timeout=90)
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text[:400]}"
        body = r.json()
        # Real Claude JSON shape
        assert "bottleneck" in body
        assert "recommendations" in body and isinstance(body["recommendations"], list)
        assert len(body["recommendations"]) > 0
        # Save first rec category for track test
        first = body["recommendations"][0]
        assert "suggested" in first or "name" in first
        pytest.shared_upgrade_recs = body["recommendations"]


# ---------- FPS Estimate (AI) ----------
class TestFPSEstimate:
    def test_fps_with_specs(self, admin_session):
        _seed_specs_health_startup(admin_session)
        r = admin_session.post(f"{API}/fps/estimate",
                               json={"game": "Fortnite", "resolution": "1440p"}, timeout=90)
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text[:400]}"
        body = r.json()
        assert body.get("game")
        assert body.get("resolution") == "1440p"
        est = body.get("estimates")
        assert isinstance(est, list) and len(est) >= 3
        for e in est[:4]:
            assert "fps" in e or "avg_fps" in e or "preset" in e

    def test_fps_without_specs_still_works(self):
        s = requests.Session()
        email = f"fps_nospecs_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Password123!", "name": "T"}, timeout=30)
        assert r.status_code == 200
        r = s.post(f"{API}/fps/estimate",
                   json={"game": "Valorant", "resolution": "1080p"}, timeout=90)
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text[:400]}"
        body = r.json()
        assert "estimates" in body


# ---------- Startup Analyze (AI) ----------
class TestStartupAnalyze:
    def test_startup_without_data_400(self):
        s = requests.Session()
        email = f"startup_none_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Password123!", "name": "T"}, timeout=30)
        assert r.status_code == 200
        r = s.post(f"{API}/startup/analyze", timeout=30)
        assert r.status_code == 400

    def test_startup_with_data(self, admin_session):
        _seed_specs_health_startup(admin_session)
        r = admin_session.post(f"{API}/startup/analyze", timeout=90)
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text[:400]}"
        body = r.json()
        assert "items" in body and isinstance(body["items"], list)
        assert len(body["items"]) >= 1
        it = body["items"][0]
        assert "name" in it
        assert "recommendation" in it or "reason" in it


# ---------- Track Build Components / Track Upgrade ----------
class TestTrackComponents:
    def test_track_build_creates_products(self, admin_session):
        # First generate & save a build (or use existing). Use generate then simulate saving? 
        # Save uses different flow. Instead, insert a build directly via generate + save endpoints if any.
        # Check builds list
        r = admin_session.get(f"{API}/builds", timeout=15)
        assert r.status_code == 200
        builds = r.json()
        if not builds:
            # Generate one via AI (may return 502 if no balance). If unavailable, skip.
            gen = admin_session.post(f"{API}/builds/generate",
                                     json={"budget": 1000, "use_case": "gaming",
                                           "resolution": "1080p", "notes": "test"}, timeout=90)
            if gen.status_code != 200:
                pytest.skip(f"cannot obtain saved build (generate={gen.status_code})")
            # Save if endpoint exists
            build_data = gen.json()
            save = admin_session.post(f"{API}/builds", json=build_data, timeout=15)
            if save.status_code != 200:
                pytest.skip(f"no /builds save endpoint success ({save.status_code})")
            r = admin_session.get(f"{API}/builds", timeout=15)
            builds = r.json()
        if not builds:
            pytest.skip("no saved builds to test track")
        build_id = builds[0]["id"]
        r = admin_session.post(f"{API}/builds/{build_id}/track", timeout=30)
        assert r.status_code == 200, f"track build failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert "tracked" in body
        assert "group" in body and isinstance(body["group"], str) and len(body["group"]) > 0
        pytest.shared_build_group = body["group"]

        # Verify products list has 'group' field for those items
        rp = admin_session.get(f"{API}/products", timeout=15)
        assert rp.status_code == 200
        grouped = [p for p in rp.json() if p.get("group") == body["group"]]
        assert len(grouped) >= 1
        assert grouped[0].get("platform") == "build-component"

    def test_track_upgrade_creates_products(self, admin_session):
        _seed_specs_health_startup(admin_session)
        # Ensure we have upgrade recs
        recs = getattr(pytest, "shared_upgrade_recs", None)
        if not recs:
            u = admin_session.post(f"{API}/upgrade/analyze",
                                   json={"budget": 700, "goal": "gaming"}, timeout=90)
            if u.status_code != 200:
                pytest.skip(f"upgrade/analyze failed: {u.status_code}")
            recs = u.json().get("recommendations") or []
        if not recs:
            pytest.skip("no upgrade recommendations available")
        group_name = f"Upgrade Test {uuid.uuid4().hex[:6]}"
        # Ensure each rec has suggested key (may be name)
        norm = []
        for r in recs[:3]:
            norm.append({
                "category": r.get("category", "GPU"),
                "suggested": r.get("suggested") or r.get("name") or "Componente",
                "price": r.get("price", 300),
            })
        resp = admin_session.post(f"{API}/upgrade/track",
                                  json={"group": group_name, "components": norm}, timeout=30)
        assert resp.status_code == 200, f"track upgrade failed: {resp.status_code} {resp.text}"
        body = resp.json()
        assert body.get("group") == group_name
        assert body.get("tracked", 0) >= 1
        # Verify in /products
        rp = admin_session.get(f"{API}/products", timeout=15)
        assert rp.status_code == 200
        matched = [p for p in rp.json() if p.get("group") == group_name]
        assert len(matched) >= 1


# ---------- report-specs accepts health+startup ----------
class TestReportSpecsHealthStartup:
    def test_report_specs_accepts_health_and_startup(self, admin_session):
        token = _seed_specs_health_startup(admin_session)
        # Read back via pc-specs
        r = admin_session.get(f"{API}/pc-specs", timeout=15)
        assert r.status_code == 200
        doc = r.json()
        assert doc.get("health") is not None
        assert doc["health"]["gpu_driver_version"] == "551.23"
        assert isinstance(doc.get("startup"), list)
        assert "Steam" in doc["startup"]
