"""Backend tests for BoostPC agent script + benchmark endpoints."""
import os
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stream-gear-monitor.preview.emergentagent.com').rstrip('/')
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
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


# --- PS script content tests (optimize mode - main bug fix verification) ---
class TestOptimizeScript:
    def test_optimize_script_200(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": "optimize"})
        assert r.status_code == 200
        assert len(r.text) > 1000

    def test_no_getnewclosure(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": "optimize"})
        assert "GetNewClosure" not in r.text, "GetNewClosure must be removed (bug fix)"

    def test_uses_this_tag(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": "optimize"})
        assert "$this.Tag" in r.text, "New-Preset handler must use $this.Tag"

    def test_tabcontrol_and_presets(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": "optimize"})
        txt = r.text
        assert "TabControl" in txt
        assert "script:PRESETS" in txt
        assert "'competitivo'" in txt
        assert "'streaming'" in txt
        # 'completo' handled as a special case in the Click handler
        assert "'completo'" in txt

    def test_no_placeholders(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": "optimize"})
        for ph in ("__BACKEND_URL__", "__AGENT_TOKEN__", "__MODE__"):
            assert ph not in r.text, f"Placeholder {ph} not substituted"

    def test_token_and_mode_substituted(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": "optimize"})
        assert f"'{agent_token}'" in r.text
        assert "$MODE    = 'optimize'" in r.text


# --- Regression: other modes ---
class TestOtherModes:
    @pytest.mark.parametrize("mode", ["sync", "benchmark", "restore"])
    def test_mode_returns_script(self, agent_token, mode):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": mode})
        assert r.status_code == 200
        assert len(r.text) > 500
        assert f"$MODE    = '{mode}'" in r.text
        assert "__MODE__" not in r.text

    def test_invalid_token(self):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": "badtoken", "mode": "sync"})
        assert r.status_code == 200
        assert "Token non valido" in r.text


# --- Benchmark reporting flow ---
class TestBenchmarkFlow:
    def test_report_and_get_benchmark(self, session, agent_token):
        payload = {
            "benchmark": {
                "before": {"cpu_score": 100, "ram_mbps": 5000, "overall": 500},
                "after": {"cpu_score": 130, "ram_mbps": 6000, "overall": 650},
                "ts": "2026-01-15T10:00:00Z",
            }
        }
        r = requests.post(
            f"{BASE_URL}/api/agent/report-specs",
            json=payload,
            headers={"X-Agent-Token": agent_token},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Verify via authenticated endpoint
        g = session.get(f"{BASE_URL}/api/pc-benchmark")
        assert g.status_code == 200
        data = g.json()
        assert data.get("latest") is not None
        latest = data["latest"]
        assert latest.get("before", {}).get("overall") == 500
        assert latest.get("after", {}).get("overall") == 650
        assert isinstance(data.get("history"), list)
        assert len(data["history"]) >= 1

    def test_report_invalid_token(self):
        r = requests.post(
            f"{BASE_URL}/api/agent/report-specs",
            json={"benchmark": {"after": {"overall": 1}, "ts": "2026-01-15T10:00:00Z"}},
            headers={"X-Agent-Token": "invalid"},
        )
        assert r.status_code == 401
