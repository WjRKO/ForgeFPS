"""Tests for monitor lifecycle endpoints (Phase A+E)."""
import os
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(sess):
    r = sess.get(f"{BASE_URL}/api/agent/token")
    assert r.status_code == 200, f"agent token: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


# --- unauth ---
def test_monitor_stop_unauth():
    r = requests.post(f"{BASE_URL}/api/monitor/stop")
    assert r.status_code == 401


def test_monitor_reset_unauth():
    r = requests.post(f"{BASE_URL}/api/monitor/reset")
    assert r.status_code == 401


def test_monitor_state_unauth():
    r = requests.get(f"{BASE_URL}/api/monitor/state")
    assert r.status_code == 401


# --- happy path lifecycle ---
def test_reset_initial(sess):
    r = sess.post(f"{BASE_URL}/api/monitor/reset")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_state_after_reset(sess):
    r = sess.get(f"{BASE_URL}/api/monitor/state")
    assert r.status_code == 200
    data = r.json()
    assert data.get("stop_requested") is False
    assert "requested_at" in data
    assert "reset_at" in data


def test_telemetry_returns_stop_false(sess, agent_token):
    sample = {"ts": datetime.now(timezone.utc).isoformat(), "cpu_util": 42, "gpu_util": 55}
    r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                      json={"sample": sample},
                      headers={"X-Agent-Token": agent_token})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("stop") is False


def test_stop_and_telemetry_returns_stop_true(sess, agent_token):
    r = sess.post(f"{BASE_URL}/api/monitor/stop")
    assert r.status_code == 200
    assert r.json().get("ok") is True

    # Verify state
    st = sess.get(f"{BASE_URL}/api/monitor/state").json()
    assert st["stop_requested"] is True
    assert st.get("requested_at")

    # Now telemetry should return stop:true
    sample = {"ts": datetime.now(timezone.utc).isoformat(), "cpu_util": 42}
    r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                      json={"sample": sample},
                      headers={"X-Agent-Token": agent_token})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("stop") is True


def test_reset_clears_stop(sess, agent_token):
    r = sess.post(f"{BASE_URL}/api/monitor/reset")
    assert r.status_code == 200

    st = sess.get(f"{BASE_URL}/api/monitor/state").json()
    assert st["stop_requested"] is False

    sample = {"ts": datetime.now(timezone.utc).isoformat(), "cpu_util": 10}
    r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                      json={"sample": sample},
                      headers={"X-Agent-Token": agent_token})
    assert r.status_code == 200
    assert r.json().get("stop") is False


def test_telemetry_invalid_token():
    sample = {"ts": datetime.now(timezone.utc).isoformat()}
    r = requests.post(f"{BASE_URL}/api/agent/telemetry",
                      json={"sample": sample},
                      headers={"X-Agent-Token": "invalid-xxx"})
    assert r.status_code == 401
