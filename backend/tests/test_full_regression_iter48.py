"""Full regression smoke test - iteration 48.
Tests all backend endpoints requested by user for FrameForge SaaS full regression."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gaming-nexus-199.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASS = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"Login failed {r.status_code} {r.text[:200]}"
    return s


# -----------------------------
# Auth
# -----------------------------
class TestAuth:
    def test_login_success(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json().get("email") == ADMIN_EMAIL

    def test_login_wrong_password(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=10)
        assert r.status_code in (400, 401, 403)

    def test_protected_without_cookie(self):
        r = requests.get(f"{BASE_URL}/api/stats", timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}"


# -----------------------------
# Core GET endpoints (must be 200 with cookie)
# -----------------------------
CORE_GET_ENDPOINTS = [
    "/api/stats",
    "/api/products",
    "/api/pc-specs",
    "/api/pc-health",
    "/api/games",
    "/api/profiles",
    "/api/lab/history",
    "/api/lab/insights",
    "/api/milestones",
    "/api/notifications",
    "/api/alerts",
    "/api/report",
]

@pytest.mark.parametrize("endpoint", CORE_GET_ENDPOINTS)
def test_core_get_endpoint(admin_session, endpoint):
    r = admin_session.get(f"{BASE_URL}{endpoint}", timeout=20)
    assert r.status_code == 200, f"{endpoint} returned {r.status_code} body={r.text[:200]}"
    # ensure JSON-parseable
    try:
        data = r.json()
    except Exception as e:
        pytest.fail(f"{endpoint} not JSON: {e}")
    assert data is not None


# -----------------------------
# Advisor rate/validation
# -----------------------------
def test_advisor_chat_empty_body_422(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/advisor/chat", json={}, timeout=10)
    assert r.status_code in (400, 422), f"Expected 422/400 got {r.status_code} {r.text[:200]}"


# -----------------------------
# Security headers
# -----------------------------
def test_security_headers_present():
    r = requests.get(f"{BASE_URL}/api/health" if False else f"{BASE_URL}/", timeout=10)
    # Check via backend endpoint too
    r2 = requests.get(f"{BASE_URL}/api/stats", timeout=10)
    headers = {k.lower(): v for k, v in r2.headers.items()}
    # CSP, X-Frame-Options
    assert "x-frame-options" in headers or "content-security-policy" in headers, f"No security headers: {list(headers.keys())}"


# -----------------------------
# Public pages
# -----------------------------
@pytest.mark.parametrize("path", ["/", "/security", "/privacy-telemetry", "/changelog", "/pricing", "/demo", "/login", "/register"])
def test_public_pages_load(path):
    r = requests.get(f"{BASE_URL}{path}", timeout=15)
    assert r.status_code == 200, f"{path} => {r.status_code}"
    assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()
