"""Tests for FPS telemetry + alert settings + monitor PS script (iteration 9)."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASS = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agent/token", timeout=10)
    assert r.status_code == 200
    return r.json()["token"]


# ---- /api/alerts GET/PUT ----
class TestAlerts:
    def test_get_alerts_defaults_or_saved(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/alerts", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert set(["enabled", "cpu_max", "gpu_max"]).issubset(d.keys())
        assert isinstance(d["enabled"], bool)
        assert isinstance(d["cpu_max"], int)
        assert isinstance(d["gpu_max"], int)

    def test_put_alerts_persists(self, admin_session):
        payload = {"enabled": True, "cpu_max": 88, "gpu_max": 82}
        r = admin_session.put(f"{BASE_URL}/api/alerts", json=payload, timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        g = admin_session.get(f"{BASE_URL}/api/alerts", timeout=10).json()
        assert g["enabled"] is True
        assert g["cpu_max"] == 88
        assert g["gpu_max"] == 82

    def test_put_alerts_disable(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/alerts",
                              json={"enabled": False, "cpu_max": 70, "gpu_max": 70}, timeout=10)
        assert r.status_code == 200
        g = admin_session.get(f"{BASE_URL}/api/alerts", timeout=10).json()
        assert g["enabled"] is False
        assert g["cpu_max"] == 70


# ---- Telemetry with FPS/game ----
class TestFpsTelemetry:
    def test_telemetry_with_fps_game(self, admin_session, agent_token):
        sample = {"cpu_util": 20, "cpu_temp": 55, "gpu_util": 40, "gpu_temp": 60,
                  "ram_used_pct": 44, "vram_used_pct": 30, "gpu_power": 120,
                  "fps": 144, "game": "valorant"}
        r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                          json={"sample": sample},
                          headers={"X-Agent-Token": agent_token}, timeout=10)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        time.sleep(0.5)
        d = admin_session.get(f"{BASE_URL}/api/pc-telemetry", timeout=10).json()
        assert d["samples"], "no samples returned"
        last = d["samples"][-1]
        assert last.get("fps") == 144
        assert last.get("game") == "valorant"
        assert d.get("live") is True


# ---- Alert temperature branch (should not crash even if no push sub) ----
class TestTempAlertNoCrash:
    def test_high_gpu_triggers_no_error(self, admin_session, agent_token):
        # set low gpu threshold to force alert path
        admin_session.put(f"{BASE_URL}/api/alerts",
                          json={"enabled": True, "cpu_max": 90, "gpu_max": 80}, timeout=10)
        r1 = requests.post(f"{BASE_URL}/api/agent/telemetry",
                           json={"sample": {"cpu_util": 10, "gpu_temp": 95, "cpu_temp": 60}},
                           headers={"X-Agent-Token": agent_token}, timeout=10)
        assert r1.status_code == 200
        assert r1.json() == {"ok": True}
        # 2nd immediate call -> cooldown, still 200
        r2 = requests.post(f"{BASE_URL}/api/agent/telemetry",
                           json={"sample": {"cpu_util": 10, "gpu_temp": 96, "cpu_temp": 61}},
                           headers={"X-Agent-Token": agent_token}, timeout=10)
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}

    def test_telemetry_bad_token(self):
        r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                          json={"sample": {"cpu_util": 1}},
                          headers={"X-Agent-Token": "invalid"}, timeout=10)
        assert r.status_code == 401


# ---- PS monitor script contains FPS/PresentMon + try/finally ----
class TestAgentScriptMonitor:
    def test_monitor_script_contains_fps(self, admin_session, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": agent_token, "mode": "monitor"}, timeout=15)
        assert r.status_code == 200
        body = r.text
        # PresentMon FPS functions
        assert "function Start-Fps" in body
        assert "function Get-Fps" in body
        assert "function Stop-Fps" in body
        # v1.10.0 URL
        assert "PresentMon-2.4.1-x64.exe" in body
        # monitor branch with try/finally
        assert "$MODE -eq 'monitor'" in body
        assert "try {" in body
        assert "} finally {" in body or "finally {" in body
        # backend/token injected
        assert "'invalid'" not in body[:200]

    def test_invalid_token_script(self):
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": "nope", "mode": "monitor"}, timeout=10)
        assert r.status_code == 200
        assert "Token non valido" in r.text


# ---- Regression: profiles + nav routes still exist ----
class TestProfilesRegression:
    def test_profiles_templates(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/profiles/templates", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "templates" in d and len(d["templates"]) >= 5
        assert "catalog" in d and len(d["catalog"]) >= 10

    def test_profiles_list(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/profiles", timeout=10)
        assert r.status_code == 200
