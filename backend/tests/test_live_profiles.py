"""Backend tests for BoostPC Live telemetry + Game Profiles features (iteration 8)."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE_URL}/api/agent/token")
    assert r.status_code == 200
    tok = r.json().get("token")
    assert tok
    return tok


# --- Telemetry ingest + retrieve ---
class TestTelemetry:
    def test_post_no_token_401(self):
        r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                          json={"sample": {"cpu_util": 10}},
                          headers={"X-Agent-Token": "bogus"})
        assert r.status_code == 401

    def test_post_ok_and_live_true(self, session, agent_token):
        sample = {"cpu_util": 42, "cpu_temp": 55, "gpu_util": 70, "gpu_temp": 62,
                  "gpu_clock": 1800, "ram_used_pct": 55, "vram_used_pct": 40, "gpu_power": 150}
        r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                          json={"sample": sample},
                          headers={"X-Agent-Token": agent_token})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        g = session.get(f"{BASE_URL}/api/pc-telemetry")
        assert g.status_code == 200
        data = g.json()
        assert isinstance(data.get("samples"), list)
        assert data.get("live") is True
        assert len(data["samples"]) >= 1
        last = data["samples"][-1]
        assert last.get("cpu_util") == 42
        assert last.get("gpu_clock") == 1800

    def test_samples_appended(self, session, agent_token):
        # capture current length
        base = session.get(f"{BASE_URL}/api/pc-telemetry").json()
        before = len(base.get("samples", []))
        for i in range(3):
            requests.post(f"{BASE_URL}/api/agent/telemetry",
                          json={"sample": {"cpu_util": i, "gpu_util": i}},
                          headers={"X-Agent-Token": agent_token})
        after = session.get(f"{BASE_URL}/api/pc-telemetry").json()
        # samples endpoint returns last 60, so length should have grown (capped at 60)
        assert len(after.get("samples", [])) >= min(before + 3, 60)
        # last sample cpu_util == 2
        assert after["samples"][-1]["cpu_util"] == 2

    def test_get_returns_max_60(self, session):
        data = session.get(f"{BASE_URL}/api/pc-telemetry").json()
        assert len(data.get("samples", [])) <= 60


# --- Profiles templates + catalog ---
class TestTemplates:
    def test_templates_and_catalog(self, session):
        r = session.get(f"{BASE_URL}/api/profiles/templates")
        assert r.status_code == 200
        data = r.json()
        assert len(data["templates"]) == 5
        assert len(data["catalog"]) == 26
        ids = {t["id"] for t in data["templates"]}
        assert {"tpl_valorant", "tpl_cs2", "tpl_warzone", "tpl_fortnite", "tpl_streaming"} <= ids
        # Each catalog entry has id/name/cat
        for c in data["catalog"]:
            assert set(["id", "name", "cat"]) <= set(c.keys())


# --- Profiles CRUD ---
class TestProfilesCRUD:
    def test_create_filter_invalid_and_get_list(self, session):
        payload = {"game_name": "TEST_apex", "tweak_ids": ["power", "gaming", "xxx"]}
        r = session.post(f"{BASE_URL}/api/profiles", json=payload)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["game_name"] == "TEST_apex"
        assert created["tweak_ids"] == ["power", "gaming"]  # xxx filtered out
        pid = created["id"]

        lst = session.get(f"{BASE_URL}/api/profiles").json()
        assert any(p["id"] == pid for p in lst)

        # Update
        upd = session.put(f"{BASE_URL}/api/profiles/{pid}",
                          json={"game_name": "TEST_apex2", "tweak_ids": ["power", "gaming", "priority", "bogus"]})
        assert upd.status_code == 200
        updated = upd.json()
        assert updated["game_name"] == "TEST_apex2"
        assert updated["tweak_ids"] == ["power", "gaming", "priority"]

        # Script contains profile ids
        tok = session.get(f"{BASE_URL}/api/agent/token").json()["token"]
        s = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": tok, "mode": "optimize", "profile": pid})
        assert s.status_code == 200
        assert "$script:PROFILE = @('power','gaming','priority')" in s.text

        # Delete
        d = session.delete(f"{BASE_URL}/api/profiles/{pid}")
        assert d.status_code == 200
        lst2 = session.get(f"{BASE_URL}/api/profiles").json()
        assert not any(p["id"] == pid for p in lst2)


# --- Agent script with profile / monitor mode ---
class TestAgentScriptProfileMonitor:
    def test_valorant_profile_injected(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": agent_token, "mode": "optimize", "profile": "tpl_valorant"})
        assert r.status_code == 200
        # must contain @('power','gaming',...) - check presence of key ids
        assert "$script:PROFILE = @(" in r.text
        for tid in ("'power'", "'gaming'", "'priority'", "'stickykeys'"):
            assert tid in r.text
        assert "__PROFILE_IDS__" not in r.text

    def test_empty_profile(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": agent_token, "mode": "optimize"})
        assert r.status_code == 200
        assert "$script:PROFILE = @()" in r.text

    def test_monitor_mode(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": agent_token, "mode": "monitor"})
        assert r.status_code == 200
        assert "$MODE    = 'monitor'" in r.text
        assert "Get-TelemetrySample" in r.text
        assert "Send-Telemetry" in r.text
