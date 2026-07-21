"""Phase 3 & 4: benchmark fleet-percentile, guardrails, benchmarks history,
pc sync-history endpoints. Cookie-based auth."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert any(c.name in ("access_token", "session", "auth_token") or "token" in c.name.lower()
               for c in s.cookies), f"no auth cookie set; cookies={s.cookies}"
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE_URL}/api/agent/token", timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


# ---- Auth guard: all endpoints must be 401 without cookies ----
class TestAuthGuard:
    def test_fleet_percentile_401(self):
        r = requests.get(f"{BASE_URL}/api/benchmarks/fleet-percentile", timeout=10)
        assert r.status_code == 401

    def test_guardrails_401(self):
        r = requests.get(f"{BASE_URL}/api/benchmarks/guardrails", timeout=10)
        assert r.status_code == 401

    def test_history_401(self):
        r = requests.get(f"{BASE_URL}/api/benchmarks/history", timeout=10)
        assert r.status_code == 401

    def test_sync_history_401(self):
        r = requests.get(f"{BASE_URL}/api/pc/sync-history", timeout=10)
        assert r.status_code == 401


# ---- fleet-percentile ----
class TestFleetPercentile:
    def test_response_shape(self, session):
        r = session.get(f"{BASE_URL}/api/benchmarks/fleet-percentile", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "available" in j
        if j["available"]:
            for k in ("my_score", "fleet_percentile", "fleet_count",
                      "similar_percentile", "similar_count",
                      "cpu_family", "gpu_family", "delta"):
                assert k in j, f"missing key {k}"


# ---- benchmarks history ----
class TestBenchmarksHistory:
    def test_default_days(self, session):
        r = session.get(f"{BASE_URL}/api/benchmarks/history", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "points" in j and "days" in j and "stats" in j
        assert isinstance(j["points"], list)
        assert j["days"] == 30

    def test_days_cap(self, session):
        r = session.get(f"{BASE_URL}/api/benchmarks/history?days=500", timeout=15)
        assert r.status_code == 200
        assert r.json()["days"] == 90

    def test_days_floor(self, session):
        # days=0 falls back to default 30 due to `int(days or 30)` in server
        r = session.get(f"{BASE_URL}/api/benchmarks/history?days=1", timeout=15)
        assert r.status_code == 200
        assert r.json()["days"] == 1


# ---- sync-history ----
class TestSyncHistory:
    def test_default(self, session):
        r = session.get(f"{BASE_URL}/api/pc/sync-history", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "events" in j and "by_day" in j and "days" in j
        assert isinstance(j["events"], list)
        assert isinstance(j["by_day"], list)
        assert j["days"] == 7

    def test_days_cap(self, session):
        r = session.get(f"{BASE_URL}/api/pc/sync-history?days=999", timeout=15)
        assert r.status_code == 200
        assert r.json()["days"] == 30


# ---- guardrails ----
class TestGuardrails:
    def test_baseline_no_game(self, session, agent_token):
        # Clear any running apps first
        r = session.post(f"{BASE_URL}/api/agent/report-specs",
                         headers={"X-Agent-Token": agent_token},
                         json={"running_apps": []}, timeout=15)
        assert r.status_code == 200, r.text
        g = session.get(f"{BASE_URL}/api/benchmarks/guardrails", timeout=15)
        assert g.status_code == 200
        j = g.json()
        for k in ("ok", "blocking", "warnings", "running_at", "running_age_s"):
            assert k in j
        assert j["blocking"] is False
        # No high severity warnings
        assert not any(w.get("severity") == "high" for w in j["warnings"])

    def test_game_running_blocks(self, session, agent_token):
        r = session.post(f"{BASE_URL}/api/agent/report-specs",
                         headers={"X-Agent-Token": agent_token},
                         json={"running_apps": ["valorant.exe"]}, timeout=15)
        assert r.status_code == 200
        g = session.get(f"{BASE_URL}/api/benchmarks/guardrails", timeout=15)
        assert g.status_code == 200
        j = g.json()
        assert j["blocking"] is True
        assert j["ok"] is False
        keys = [w["key"] for w in j["warnings"]]
        assert "game_running" in keys
        # verify severity and detail structure
        game_w = next(w for w in j["warnings"] if w["key"] == "game_running")
        assert game_w["severity"] == "high"
        assert "valorant" in game_w["detail"]

    def test_stream_running_blocks(self, session, agent_token):
        r = session.post(f"{BASE_URL}/api/agent/report-specs",
                         headers={"X-Agent-Token": agent_token},
                         json={"running_apps": ["obs64.exe"]}, timeout=15)
        assert r.status_code == 200
        g = session.get(f"{BASE_URL}/api/benchmarks/guardrails", timeout=15)
        j = g.json()
        assert j["blocking"] is True
        keys = [w["key"] for w in j["warnings"]]
        assert "stream_running" in keys

    def test_cleanup_running_apps(self, session, agent_token):
        # cleanup so we don't leave the admin in "blocked" state
        r = session.post(f"{BASE_URL}/api/agent/report-specs",
                         headers={"X-Agent-Token": agent_token},
                         json={"running_apps": []}, timeout=15)
        assert r.status_code == 200
