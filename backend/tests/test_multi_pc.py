"""Multi-PC (Fase 1) backend tests.
Covers: devices CRUD/activate, X-Device agent registration, plan limits,
overlay cross-PC source, legacy agent (no X-Device) fallback.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gaming-nexus-199.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASS = "4zWK4o_xSw5prU-2b7w9dQ"
STARTER_EMAIL = "credits_test@frameforge.dev"
STARTER_PASS = "Cr3d1ts!Test99"


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def starter_session():
    return _login(STARTER_EMAIL, STARTER_PASS)


@pytest.fixture(scope="module")
def admin_agent_token(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agent/token", timeout=15)
    assert r.status_code == 200
    return r.json()["token"]


@pytest.fixture(scope="module")
def starter_agent_token(starter_session):
    r = starter_session.get(f"{BASE_URL}/api/agent/token", timeout=15)
    assert r.status_code == 200
    return r.json()["token"]


# ----- GET /api/devices ------------------------------------------------------

def test_admin_list_devices(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/devices", timeout=15)
    assert r.status_code == 200
    data = r.json()
    ids = [d["device_id"] for d in data["devices"]]
    assert "gaming-rig" in ids
    assert "stream-box" in ids
    assert data["limit"] == 99, f"streamer limit expected 99, got {data['limit']}"
    assert data["active"] == "gaming-rig"
    for d in data["devices"]:
        for k in ("device_id", "name", "role", "online", "is_active"):
            assert k in d, f"missing key {k} in device row"


def test_starter_list_devices_limit_1(starter_session):
    r = starter_session.get(f"{BASE_URL}/api/devices", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["limit"] == 1
    assert len(data["devices"]) == 1
    assert data["devices"][0]["device_id"] == "casa-pc"


# ----- Agent report-specs with X-Device --------------------------------------

def _minimal_specs():
    return {"data": {"cpu": "TEST CPU", "gpu": "TEST GPU"}, "health": None}


def test_admin_agent_report_creates_new_device(admin_session, admin_agent_token):
    # Register a brand-new PC-TEST-A for admin (streamer -> plenty of headroom)
    r = requests.post(
        f"{BASE_URL}/api/agent/report-specs",
        headers={"X-Agent-Token": admin_agent_token, "X-Device": "PC-TEST-A"},
        json=_minimal_specs(),
        timeout=20,
    )
    assert r.status_code == 200, r.text[:300]
    # Verify it shows up in /api/devices
    r2 = admin_session.get(f"{BASE_URL}/api/devices", timeout=15)
    ids = [d["device_id"] for d in r2.json()["devices"]]
    assert "pc-test-a" in ids, f"pc-test-a not registered. Got {ids}"
    # Cleanup
    admin_session.delete(f"{BASE_URL}/api/devices/pc-test-a", timeout=15)


def test_starter_second_device_returns_402_device_limit(starter_agent_token):
    r = requests.post(
        f"{BASE_URL}/api/agent/report-specs",
        headers={"X-Agent-Token": starter_agent_token, "X-Device": "PC-TEST-B"},
        json=_minimal_specs(),
        timeout=20,
    )
    assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text[:200]}"
    body = r.json()
    detail = body.get("detail", body)
    assert detail.get("code") == "device_limit", f"expected code=device_limit, got {detail}"


def test_legacy_agent_no_x_device_hits_primary(admin_session, admin_agent_token):
    # Sends without X-Device -> should be routed to admin's primary device (gaming-rig)
    # and should NOT create a new device row
    before = admin_session.get(f"{BASE_URL}/api/devices", timeout=15).json()
    before_ids = sorted([d["device_id"] for d in before["devices"]])
    r = requests.post(
        f"{BASE_URL}/api/agent/report-specs",
        headers={"X-Agent-Token": admin_agent_token},
        json={"data": {"cpu": "legacy-cpu"}},
        timeout=20,
    )
    assert r.status_code == 200, r.text[:200]
    after = admin_session.get(f"{BASE_URL}/api/devices", timeout=15).json()
    after_ids = sorted([d["device_id"] for d in after["devices"]])
    assert before_ids == after_ids, f"legacy agent should NOT create new device. before={before_ids} after={after_ids}"


# ----- Activate + PUT + DELETE ----------------------------------------------

def test_activate_changes_active_and_pc_specs(admin_session):
    # Activate stream-box
    r = admin_session.post(f"{BASE_URL}/api/devices/stream-box/activate", timeout=15)
    assert r.status_code == 200
    assert r.json().get("active") == "stream-box"
    # /api/devices reflects active
    d = admin_session.get(f"{BASE_URL}/api/devices", timeout=15).json()
    assert d["active"] == "stream-box"
    # pc-specs returns the streaming PC's specs (should have RTX 3060 per seed)
    specs = admin_session.get(f"{BASE_URL}/api/pc-specs", timeout=15)
    assert specs.status_code == 200
    stream_specs_str = str(specs.json()).lower()
    # Now switch back to gaming-rig
    r2 = admin_session.post(f"{BASE_URL}/api/devices/gaming-rig/activate", timeout=15)
    assert r2.status_code == 200
    specs2 = admin_session.get(f"{BASE_URL}/api/pc-specs", timeout=15)
    gaming_specs_str = str(specs2.json()).lower()
    # They should differ (different GPU seeded)
    assert stream_specs_str != gaming_specs_str, "pc-specs identical across devices - device_filter not applied?"


def test_put_rename_and_role(admin_session):
    # Rename stream-box then restore
    orig_name = "PC Streaming"
    r = admin_session.put(f"{BASE_URL}/api/devices/stream-box", json={"name": "PC Streaming X"}, timeout=15)
    assert r.status_code == 200
    d = admin_session.get(f"{BASE_URL}/api/devices", timeout=15).json()
    sb = [x for x in d["devices"] if x["device_id"] == "stream-box"][0]
    assert sb["name"] == "PC Streaming X"
    # restore
    admin_session.put(f"{BASE_URL}/api/devices/stream-box", json={"name": orig_name}, timeout=15)
    # role change ok
    r2 = admin_session.put(f"{BASE_URL}/api/devices/stream-box", json={"role": "laptop"}, timeout=15)
    assert r2.status_code == 200
    # restore role
    admin_session.put(f"{BASE_URL}/api/devices/stream-box", json={"role": "streaming"}, timeout=15)
    # invalid role -> 400
    r3 = admin_session.put(f"{BASE_URL}/api/devices/stream-box", json={"role": "server"}, timeout=15)
    assert r3.status_code == 400


def test_delete_test_device_and_active_fallback(admin_session, admin_agent_token):
    # Create PC-TEST-DEL for admin
    r = requests.post(
        f"{BASE_URL}/api/agent/report-specs",
        headers={"X-Agent-Token": admin_agent_token, "X-Device": "PC-TEST-DEL"},
        json=_minimal_specs(),
        timeout=20,
    )
    assert r.status_code == 200
    # Activate it
    ar = admin_session.post(f"{BASE_URL}/api/devices/pc-test-del/activate", timeout=15)
    assert ar.status_code == 200
    # Delete
    dr = admin_session.delete(f"{BASE_URL}/api/devices/pc-test-del", timeout=15)
    assert dr.status_code == 200
    # Should fall back to primary (gaming-rig)
    d = admin_session.get(f"{BASE_URL}/api/devices", timeout=15).json()
    assert d["active"] == "gaming-rig", f"active fallback broken. got {d['active']}"
    # Cleanup: make sure gaming-rig is active
    admin_session.post(f"{BASE_URL}/api/devices/gaming-rig/activate", timeout=15)


# ----- Overlay cross-PC ------------------------------------------------------

def test_overlay_source_device_cross_pc(admin_session):
    # Get token
    cfg = admin_session.get(f"{BASE_URL}/api/overlay/config", timeout=15).json()
    token = cfg["token"]
    # Set source_device=stream-box
    r = admin_session.put(f"{BASE_URL}/api/overlay/config", json={"source_device": "stream-box"}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("source_device") == "stream-box"
    # Data fetch works
    r2 = requests.get(f"{BASE_URL}/api/overlay/{token}/data", timeout=15)
    assert r2.status_code == 200
    # Invalid device -> 400
    r3 = admin_session.put(f"{BASE_URL}/api/overlay/config", json={"source_device": "does-not-exist"}, timeout=15)
    assert r3.status_code == 400
    # Reset to empty (active)
    r4 = admin_session.put(f"{BASE_URL}/api/overlay/config", json={"source_device": ""}, timeout=15)
    assert r4.status_code == 200
    assert r4.json().get("source_device") in (None, "")


# ----- Pro telemetry gated ---------------------------------------------------

def test_pc_telemetry_admin(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/pc-telemetry", timeout=15)
    # Should be 200 for streamer (pro-tier)
    assert r.status_code == 200


# ----- Regression: missions/subscriptions -----------------------------------

def test_missions_endpoint(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/missions", timeout=15)
    assert r.status_code == 200


def test_subscriptions_status(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/subscriptions/status", timeout=15)
    assert r.status_code == 200
