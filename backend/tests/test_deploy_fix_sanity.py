"""
Sanity tests post deployment fix (iteration 28).
- Ensures backend still responds
- Auth core (login/me/logout, mfa/status, magic-link)
- Agent endpoints (download-zip, launcher-bat)
- Codebase-level checks: .gitignore no longer blocks env files,
  frontend build compiled with window.location.origin for /api/discord/connect,
  /app/backend/.env and /app/frontend/.env exist with required keys.
"""
import io
import os
import re
import glob
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- SANITY: backend up ----------
def test_backend_public_endpoint_reachable():
    # magic-status is public and returns 404 for unknown token
    r = requests.get(f"{BASE_URL}/api/auth/magic-status/dummy", timeout=15)
    # 404 (not found) OR 400 acceptable — key is: backend is reachable, not 5xx
    assert r.status_code in (200, 400, 404), f"unexpected {r.status_code}: {r.text[:200]}"


# ---------- SANITY: login ----------
def test_admin_login_returns_user_and_cookie():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert "user" in data or "email" in data
    # cookie set
    cookie_names = {c.name for c in s.cookies}
    assert any("token" in n.lower() or "session" in n.lower() or "access" in n.lower() for n in cookie_names), \
        f"no auth cookie found: {cookie_names}"


def test_auth_me_with_cookie(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert data.get("email") == ADMIN_EMAIL


def test_mfa_status(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/auth/mfa/status", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert isinstance(data["enabled"], bool)


def test_magic_link_creation(admin_session):
    # cleanup magic_tokens for admin first to avoid rate limit collisions
    try:
        from pymongo import MongoClient
        mongo_url = open("/app/backend/.env").read()
        m = re.search(r"MONGO_URL=(.+)", mongo_url)
        dbn = re.search(r"DB_NAME=(.+)", mongo_url)
        if m and dbn:
            cli = MongoClient(m.group(1).strip(), serverSelectionTimeoutMS=3000)
            cli[dbn.group(1).strip()].magic_tokens.delete_many({"email": ADMIN_EMAIL})
    except Exception:
        pass

    r = admin_session.post(f"{BASE_URL}/api/auth/magic-link", timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "token" in data
    assert "expires_in_seconds" in data
    assert isinstance(data["expires_in_seconds"], int)
    assert data["expires_in_seconds"] > 0


# ---------- SANITY: agent endpoints ----------
def test_agent_download_zip(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agent/download-zip", timeout=60)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    content = r.content
    size_mb = len(content) / (1024 * 1024)
    assert size_mb > 8, f"zip too small: {size_mb:.2f} MB"
    zf = zipfile.ZipFile(io.BytesIO(content))
    names = zf.namelist()
    # find forgefps-agent/Avvia-FrameForge.bat (path may include prefix)
    matches = [n for n in names if n.endswith("Avvia-FrameForge.bat") and "forgefps-agent" in n]
    assert matches, f"Avvia-FrameForge.bat missing. sample: {names[:20]}"


def test_agent_launcher_bat(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agent/launcher-bat", timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    body = r.text
    # must contain a token (long alnum string) — check heuristically
    assert re.search(r"[A-Za-z0-9_\-]{20,}", body), "no token embedded in .bat"
    assert ".bat" in (r.headers.get("content-disposition") or "").lower() or \
        "octet-stream" in (r.headers.get("content-type") or "").lower() or \
        "text" in (r.headers.get("content-type") or "").lower()


# ---------- FIX-SPECIFIC: codebase checks ----------
def test_gitignore_does_not_block_env_files():
    with open("/app/.gitignore") as f:
        lines = [ln.strip() for ln in f.readlines()]
    forbidden = {".env", ".env.*", "*.env"}
    hits = [ln for ln in lines if ln in forbidden]
    assert not hits, f".gitignore still contains env-blocking lines: {hits}"


def test_env_files_present_with_required_keys():
    with open("/app/backend/.env") as f:
        be = f.read()
    assert re.search(r"^MONGO_URL=", be, re.M), "backend .env missing MONGO_URL"
    assert re.search(r"^DB_NAME=", be, re.M), "backend .env missing DB_NAME"
    with open("/app/frontend/.env") as f:
        fe = f.read()
    assert re.search(r"^REACT_APP_BACKEND_URL=", fe, re.M), "frontend .env missing REACT_APP_BACKEND_URL"


def test_frontend_build_uses_window_origin_for_discord_connect():
    build_files = glob.glob("/app/frontend/build/static/js/*.js")
    assert build_files, "no frontend build files found"
    bad_pattern = re.compile(r'process\.env\.REACT_APP_BACKEND_URL\s*\|\|\s*""[^\n]{0,100}/api/discord/connect')
    good_pattern = re.compile(r'window\.location\.origin[^\n]{0,50}/api/discord/connect')
    found_bad = []
    found_good = False
    for fp in build_files:
        try:
            with open(fp, "r", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue
        if bad_pattern.search(content):
            found_bad.append(os.path.basename(fp))
        if good_pattern.search(content):
            found_good = True
    assert not found_bad, f"old pattern still present in: {found_bad}"
    assert found_good, "window.location.origin + /api/discord/connect pattern not found in build"
