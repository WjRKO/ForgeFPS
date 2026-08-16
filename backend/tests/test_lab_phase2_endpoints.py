"""Lab Phase 2 endpoint tests - registry filters, start with reboot toggle, agent script markers"""
from pathlib import Path as _P
# Radice del repository calcolata dal file: i percorsi "/app/..." erano il
# layout di un vecchio container e non esistono ne' in locale ne' nell'immagine
# attuale, che monta il codice in /srv/app.
_BACKEND_DIR = _P(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
import os, requests, pytest
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN = {"email": os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"), "password": os.environ.get("ADMIN_PASSWORD", "")}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    # cleanup any prior lab session
    try:
        s.post(f"{BASE}/api/lab/abort", timeout=10)
    except Exception:
        pass
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE}/api/agent/token", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _cleanup_sessions(sess):
    # abort any running lab session (idempotent)
    for _ in range(2):
        try:
            sess.post(f"{BASE}/api/lab/abort", timeout=10)
        except Exception:
            pass


def test_registry_with_reboot(session):
    r = session.get(f"{BASE}/api/lab/registry", params={"risk_level": "medium", "include_reboot": "true"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    ids = [c["tweak_id"] for c in data["candidates"]]
    assert len(data["candidates"]) == 14, f"expected 14 got {len(ids)}: {ids}"
    # Check mpo, gpu_msi, timer at tail (requires_reboot)
    reboot_ids = [c["tweak_id"] for c in data["candidates"] if c.get("requires_reboot")]
    assert set(reboot_ids) >= {"mpo", "gpu_msi", "timer"}, reboot_ids
    tail = ids[-3:]
    assert set(tail) == {"mpo", "gpu_msi", "timer"}, f"reboot not in tail: {tail}"


def test_registry_without_reboot(session):
    r = session.get(f"{BASE}/api/lab/registry", params={"risk_level": "medium", "include_reboot": "false"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    ids = [c["tweak_id"] for c in data["candidates"]]
    assert len(ids) == 11, f"expected 11 got {len(ids)}: {ids}"
    for x in ("mpo", "gpu_msi", "timer"):
        assert x not in ids


def test_start_with_include_reboot_false(session):
    _cleanup_sessions(session)
    r = session.post(f"{BASE}/api/lab/start", json={"risk_level": "medium", "window_days": 90, "include_reboot": False}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json().get("session") or r.json()
    cand = data.get("candidates") or []
    assert len(cand) == 11, len(cand)
    session.post(f"{BASE}/api/lab/abort", timeout=10)


def test_start_with_include_reboot_true(session):
    _cleanup_sessions(session)
    r = session.post(f"{BASE}/api/lab/start", json={"risk_level": "medium", "window_days": 90, "include_reboot": True}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json().get("session") or r.json()
    cand = data.get("candidates") or []
    assert len(cand) == 14
    assert any(c.get("requires_reboot") for c in cand)
    session.post(f"{BASE}/api/lab/abort", timeout=10)


def test_agent_script_phase2_markers(session, agent_token):
    r = session.get(f"{BASE}/api/agent/script", params={"t": agent_token, "mode": "lab"}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.text
    for marker in ["reboot_required", "Register-LabResume", "run_synergy", "run_validation", "RunOnce"]:
        assert marker in body, f"marker missing: {marker}"


def test_agent_fake_token_401(session):
    r = requests.get(f"{BASE}/api/agent/lab/next", headers={"X-Agent-Token": "fake_invalid_token_xyz"}, timeout=15)
    assert r.status_code in (401, 403), r.status_code


def test_abort_awaiting_reboot(session, agent_token):
    """Note: full reboot->abort flow is validated in test_lab_phase2_sim.py.
    Here we just validate that abort works while a session with reboot tweaks is active."""
    _cleanup_sessions(session)
    r = session.post(f"{BASE}/api/lab/start", json={"risk_level": "medium", "window_days": 90, "include_reboot": True}, timeout=15)
    assert r.status_code == 200
    ab = session.post(f"{BASE}/api/lab/abort", timeout=15)
    assert ab.status_code == 200, ab.text
    body = ab.json()
    assert "rollback_ids" in body or "session" in body, body


def test_cleanup_final(session):
    _cleanup_sessions(session)
    # purge lab_sessions collection via direct mongo
    async def _clean():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        res = await db.lab_sessions.delete_many({})
        print("purged lab_sessions:", res.deleted_count)
        cli.close()
    # load .env
    if not os.environ.get("MONGO_URL"):
        from dotenv import load_dotenv
        load_dotenv(str(_BACKEND_DIR / ".env"))
    asyncio.run(_clean())
