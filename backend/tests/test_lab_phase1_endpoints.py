"""Endpoint-level tests for Lab Phase 1 (iteration 44)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASS = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def agent_token(sess):
    r = sess.get(f"{BASE_URL}/api/agent/token", timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


def _cleanup(sess):
    # abort any active session so subsequent tests don't hit 409
    try:
        sess.post(f"{BASE_URL}/api/lab/abort", timeout=10)
    except Exception:
        pass


# ---------------- lab/registry ----------------
def test_registry_safe(sess):
    r = sess.get(f"{BASE_URL}/api/lab/registry?risk_level=safe", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert "candidates" in j and "skipped" in j
    cands = j["candidates"]
    assert len(cands) >= 1
    # ordered by prior desc
    priors = [c["prior"] for c in cands]
    assert priors == sorted(priors, reverse=True)
    # visual tweak should be in skipped for safe
    skipped_ids = {s.get("tweak_id") for s in j["skipped"]}
    assert "visual" in skipped_ids


def test_registry_medium(sess):
    r = sess.get(f"{BASE_URL}/api/lab/registry?risk_level=medium", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert len(j["candidates"]) >= 1


# ---------------- lab/start ----------------
def test_start_invalid_risk_422(sess):
    _cleanup(sess)
    r = sess.post(f"{BASE_URL}/api/lab/start", json={"risk_level": "bogus", "target_window_s": 90}, timeout=10)
    assert r.status_code == 422


def test_start_ok_then_double_409(sess):
    _cleanup(sess)
    r = sess.post(f"{BASE_URL}/api/lab/start", json={"risk_level": "safe", "target_window_s": 90}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    sess_obj = j.get("session", j)
    assert sess_obj.get("status") == "waiting_agent"
    assert sess_obj.get("session_id")
    # doppio start
    r2 = sess.post(f"{BASE_URL}/api/lab/start", json={"risk_level": "safe", "target_window_s": 90}, timeout=10)
    assert r2.status_code == 409
    _cleanup(sess)


# ---------------- /api/agent/lab/next auth ----------------
def test_agent_lab_next_fake_token_401():
    r = requests.get(f"{BASE_URL}/api/agent/lab/next", headers={"X-Agent-Token": "not-a-real-token"}, timeout=10)
    assert r.status_code == 401


# ---------------- /api/agent/script mode=lab markers ----------------
def test_agent_script_lab_markers(agent_token):
    r = requests.get(f"{BASE_URL}/api/agent/script?t={agent_token}&mode=lab", timeout=15)
    assert r.status_code == 200, r.text[:300]
    body = r.text
    for marker in ["Invoke-LabRun", "Get-LabTick", "agent/lab/next"]:
        assert marker in body, f"missing marker {marker!r}"


# ---------------- /api/agent/launch-uri?mode=lab ----------------
def test_agent_launch_uri_lab(sess):
    r = sess.get(f"{BASE_URL}/api/agent/launch-uri?mode=lab", timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    uri = j.get("uri") or j.get("launch_uri") or ""
    assert uri.startswith("frameforge://"), f"unexpected: {uri}"
    assert "mode=lab" in uri or "lab" in uri
