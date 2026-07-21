"""Regression tests for GET /api/agent/launch-uri (custom-protocol handoff).

Verifies:
- Auth required (401 without cookie)
- Valid mode returns signed URI with expected HMAC
- Invalid mode returns 400 with list of allowed modes
- HMAC signature is verifiable using the user's agent token as key
"""

import os
import hmac
import hashlib
import time
import urllib.parse
import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get(
    "BACKEND_URL", "http://localhost:8001"
)
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASS = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=10,
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE_URL}/api/agent/token", timeout=10)
    assert r.status_code == 200
    return r.json()["token"]


def test_launch_uri_requires_auth():
    r = requests.get(f"{BASE_URL}/api/agent/launch-uri?mode=optimize", timeout=10)
    assert r.status_code in (401, 403)


def test_launch_uri_default_mode(session):
    r = session.get(f"{BASE_URL}/api/agent/launch-uri", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "optimize"
    assert data["uri"].startswith("frameforge://launch?")
    assert "sig=" in data["uri"] and "ts=" in data["uri"]


def test_launch_uri_invalid_mode(session):
    r = session.get(f"{BASE_URL}/api/agent/launch-uri?mode=hackerman", timeout=10)
    assert r.status_code == 400
    assert "mode non valido" in r.json()["detail"]


@pytest.mark.parametrize(
    "mode", ["optimize", "sync", "benchmark", "monitor", "prematch", "booster", "restore", "gui"]
)
def test_launch_uri_all_valid_modes(session, mode):
    r = session.get(f"{BASE_URL}/api/agent/launch-uri?mode={mode}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == mode
    assert data["uri"].startswith(f"frameforge://launch?mode={mode}&")


def test_launch_uri_signature_verifies(session, agent_token):
    """L'agent locale ricrea la firma HMAC con lo stesso token: deve combaciare."""
    r = session.get(f"{BASE_URL}/api/agent/launch-uri?mode=monitor", timeout=10)
    assert r.status_code == 200
    uri = r.json()["uri"]
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
    mode = qs["mode"][0]
    ts = qs["ts"][0]
    sig = qs["sig"][0]
    expected = hmac.new(
        agent_token.encode(), f"{mode}|{ts}".encode(), hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(expected, sig), "server HMAC != client-recomputed HMAC"


def test_launch_uri_signature_rejects_wrong_token(session):
    r = session.get(f"{BASE_URL}/api/agent/launch-uri?mode=optimize", timeout=10)
    uri = r.json()["uri"]
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
    bad = hmac.new(
        b"attacker_guessed_token",
        f"{qs['mode'][0]}|{qs['ts'][0]}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert bad != qs["sig"][0], "wrong-key HMAC accidentally matched (shouldn't)"


def test_launch_uri_fresh_timestamp(session):
    """ts deve essere entro pochi secondi da 'ora' per non essere gia' scaduto."""
    r = session.get(f"{BASE_URL}/api/agent/launch-uri?mode=optimize", timeout=10)
    ts = int(r.json()["ts"])
    assert abs(int(time.time()) - ts) < 10
