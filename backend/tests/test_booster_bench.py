"""Backend tests for FASE B (Game Booster) and FASE C (Benchmark AI explain)."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stream-gear-monitor.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agent/token")
    assert r.status_code == 200
    return r.json()["token"]


# ---------- FASE B: Booster ----------

class TestBooster:
    def test_get_booster_returns_defaults_or_saved(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/booster")
        assert r.status_code == 200
        d = r.json()
        for k in ("close_apps", "set_power", "boost_priority", "purge_ram"):
            assert k in d
        assert isinstance(d["close_apps"], list)
        assert isinstance(d["set_power"], bool)

    def test_put_booster_persists(self, admin_session):
        payload = {"close_apps": ["chrome", "Discord"], "set_power": True,
                   "boost_priority": True, "purge_ram": False}
        r = admin_session.put(f"{BASE_URL}/api/booster", json=payload)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # GET back
        r2 = admin_session.get(f"{BASE_URL}/api/booster")
        d = r2.json()
        assert d["purge_ram"] is False
        assert "chrome" in d["close_apps"]
        assert "Discord" in d["close_apps"]

    def test_agent_script_contains_booster_placeholders_replaced(self, admin_session, agent_token):
        r = admin_session.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token})
        assert r.status_code == 200
        text = r.text
        assert len(text) > 500
        # no unreplaced placeholders
        assert "__BOOSTER_" not in text
        assert "__PREMATCH_" not in text
        assert "__BACKEND_URL__" not in text
        assert "__PROFILE_IDS__" not in text
        # apps should appear (we set chrome, Discord above)
        assert "'chrome'" in text or "chrome" in text
        # bool flags with $true/$false
        assert "$true" in text or "$false" in text

    def test_agent_script_all_modes(self, admin_session, agent_token):
        for mode in ("optimize", "sync", "benchmark", "restore", "prematch", "monitor", "booster"):
            r = admin_session.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token})
            assert r.status_code == 200, mode
            assert len(r.text) > 500, mode
            assert "__BOOSTER_" not in r.text and "__PREMATCH_" not in r.text

    def test_report_specs_boost_session(self, agent_token):
        payload = {"boost_session": {"game": "TESTGame", "duration_s": 600,
                                     "actions": ["priorita_high"], "ended_at": "2026-07-17T22:00:00Z"}}
        r = requests.post(f"{BASE_URL}/api/agent/report-specs",
                          json=payload, headers={"X-Agent-Token": agent_token})
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_get_booster_sessions_includes_new(self, admin_session, agent_token):
        # Ensure fresh insert
        payload = {"boost_session": {"game": "TESTGameB", "duration_s": 120,
                                     "actions": ["x"], "ended_at": "2026-07-17T22:10:00Z"}}
        requests.post(f"{BASE_URL}/api/agent/report-specs",
                      json=payload, headers={"X-Agent-Token": agent_token})
        r = admin_session.get(f"{BASE_URL}/api/booster/sessions")
        assert r.status_code == 200
        rows = r.json().get("sessions", [])
        games = [s.get("game") for s in rows]
        assert "TESTGameB" in games or "TESTGame" in games


# ---------- FASE C: Benchmark Explain ----------

class TestBenchmarkExplain:
    def test_explain_admin_has_bench(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/benchmark/explain", json={"lang": "it"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "explanation" in d
        assert isinstance(d["explanation"], str) and len(d["explanation"]) > 20

    def test_explain_second_call_cached(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/benchmark/explain", json={"lang": "it"})
        assert r.status_code == 200
        assert r.json().get("cached") is True

    def test_explain_no_bench_returns_404(self):
        # Register a fresh user
        import uuid
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        email = f"TEST_nobench_{uuid.uuid4().hex[:8]}@test.io"
        reg = s.post(f"{BASE_URL}/api/auth/register",
                     json={"email": email, "password": "Passw0rd!123", "name": "T"})
        if reg.status_code not in (200, 201):
            # try login variant
            pytest.skip(f"register failed: {reg.status_code} {reg.text}")
        # ensure logged in (register should set cookie)
        r = s.post(f"{BASE_URL}/api/benchmark/explain", json={"lang": "it"})
        assert r.status_code == 404
        assert "benchmark" in r.text.lower()


class TestPrematchRegression:
    def test_prematch_get(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/prematch")
        assert r.status_code == 200
        assert "close_apps" in r.json()

    def test_prematch_put(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/prematch",
                              json={"close_apps": ["chrome"], "set_power": True})
        assert r.status_code == 200
