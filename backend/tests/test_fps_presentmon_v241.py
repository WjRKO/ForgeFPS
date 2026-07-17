"""Iteration 10: Verify PresentMon v2.4.1 fix in monitor PS script + regression on
telemetry/alerts/profiles/other modes."""
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
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agent/token", timeout=10)
    assert r.status_code == 200
    return r.json()["token"]


# ---- Monitor PS script: PresentMon v2.4.1 + fixes ----
class TestMonitorScriptPresentMonV241:
    @pytest.fixture(scope="class")
    def script_body(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": agent_token, "mode": "monitor"}, timeout=15)
        assert r.status_code == 200
        assert len(r.text) > 1000
        return r.text

    def test_presentmon_v241_url(self, script_body):
        assert "v2.4.1/PresentMon-2.4.1-x64.exe" in script_body

    def test_no_v1_10_0(self, script_body):
        assert "v1.10.0" not in script_body
        assert "PresentMon-1.10.0" not in script_body

    def test_double_dash_v1_metrics_flag(self, script_body):
        assert "--v1_metrics" in script_body

    def test_no_single_dash_output_file(self, script_body):
        # Ensure single-dash form is not present (double-dash '--output_file' is fine)
        # single dash '-output_file' would appear as space + dash + word
        assert " -output_file" not in script_body

    def test_read_shared_function(self, script_body):
        assert "function Read-Shared" in script_body
        assert "FileShare]::ReadWrite" in script_body

    def test_case_insensitive_column_detect(self, script_body):
        assert "*betweenpresents*" in script_body
        # case-insensitive: uses .ToLower()
        assert ".ToLower()" in script_body

    def test_fps_functions_present(self, script_body):
        for fn in ("function Start-Fps", "function Get-Fps", "function Stop-Fps"):
            assert fn in script_body

    def test_monitor_branch_try_finally(self, script_body):
        assert "$MODE -eq 'monitor'" in script_body
        assert "try {" in script_body
        assert "finally {" in script_body

    def test_no_placeholders(self, script_body):
        for ph in ("__BACKEND_URL__", "__AGENT_TOKEN__", "__MODE__", "__PROFILE_IDS__"):
            assert ph not in script_body


# ---- Regression: telemetry with FPS=240 game='cs2' ----
class TestTelemetryFpsCs2:
    def test_telemetry_fps240_cs2(self, admin_session, agent_token):
        sample = {"cpu_util": 30, "cpu_temp": 58, "gpu_util": 70, "gpu_temp": 65,
                  "ram_used_pct": 40, "fps": 240, "game": "cs2"}
        r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                          json={"sample": sample},
                          headers={"X-Agent-Token": agent_token}, timeout=10)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        time.sleep(0.5)
        d = admin_session.get(f"{BASE_URL}/api/pc-telemetry", timeout=10).json()
        assert d["samples"], "no samples returned"
        last = d["samples"][-1]
        assert last.get("fps") == 240
        assert last.get("game") == "cs2"


# ---- Regression: other modes + profile injection ----
class TestOtherModes:
    @pytest.mark.parametrize("mode", ["sync", "benchmark", "restore", "optimize"])
    def test_mode_ok(self, agent_token, mode):
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": agent_token, "mode": mode}, timeout=15)
        assert r.status_code == 200
        assert len(r.text) > 500
        assert "$MODE    = $Mode" in r.text

    def test_optimize_with_profile(self, admin_session, agent_token):
        # find a template id
        tpl = admin_session.get(f"{BASE_URL}/api/profiles/templates", timeout=10).json()
        assert tpl["templates"], "no templates"
        # Prefer tpl_valorant if present
        tid = "tpl_valorant"
        if not any(t.get("id") == tid for t in tpl["templates"]):
            tid = tpl["templates"][0]["id"]
        r = requests.get(f"{BASE_URL}/api/agent/script",
                         params={"t": agent_token, "mode": "optimize", "profile": tid}, timeout=15)
        assert r.status_code == 200
        # PROFILE_IDS injected -> $script:PROFILE line must contain at least one quoted id
        assert "$script:PROFILE = @(" in r.text
        # Extract the profile line
        for line in r.text.splitlines():
            if line.startswith("$script:PROFILE = @("):
                # should not be empty parens
                assert line.strip() != "$script:PROFILE = @()", "profile ids not injected"
                assert "'" in line, "profile ids not quoted"
                break


# ---- Regression: /api/alerts GET/PUT ----
class TestAlertsRegression:
    def test_get_defaults_or_saved(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/alerts", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert {"enabled", "cpu_max", "gpu_max"}.issubset(d.keys())

    def test_put_persists(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/alerts",
                              json={"enabled": True, "cpu_max": 90, "gpu_max": 85}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        g = admin_session.get(f"{BASE_URL}/api/alerts", timeout=10).json()
        assert g["enabled"] is True
        assert g["cpu_max"] == 90
        assert g["gpu_max"] == 85
