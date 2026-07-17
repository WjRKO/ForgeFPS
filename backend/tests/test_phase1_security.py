"""Phase 1 security/UX overhaul backend tests.

Covers:
- Security headers on /api/ (and /health via localhost)
- /health endpoint returns 200 {status: ok} (localhost - not routed externally)
- ChatMessageInput validation (empty / >2000 chars => 422)
- AI rate limit guard wiring on /api/advisor/chat (seed 100 user messages -> 429)
- Admin login + list_users aggregation regression
"""
import os
import time
import requests
import pytest
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
LOCAL_URL = "http://localhost:8001"
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"

SEC_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "geolocation=(), microphone=(), camera=()",
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}


# ---------- Security headers ----------
class TestSecurityHeaders:
    def test_headers_on_api_root_external(self):
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        for k, v in SEC_HEADERS.items():
            assert r.headers.get(k) == v, f"Missing/mismatched {k}: got {r.headers.get(k)}"

    def test_headers_on_health_local(self):
        # /health has no /api prefix so external ingress will NOT hit backend.
        r = requests.get(f"{LOCAL_URL}/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
        for k, v in SEC_HEADERS.items():
            assert r.headers.get(k) == v

    def test_health_external_is_not_backend(self):
        """Documents current infra: external /health returns frontend HTML."""
        r = requests.get(f"{BASE_URL}/health")
        # This SHOULD ideally return {"status":"ok"} but currently frontend HTML.
        ct = r.headers.get("content-type", "")
        assert "text/html" in ct, f"unexpected: {ct}"


# ---------- Admin auth + aggregation regression ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


class TestAdminRegression:
    def test_admin_login(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_admin_users_aggregation(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        u0 = data[0]
        assert "tracked_products" in u0 and "builds" in u0
        assert isinstance(u0["tracked_products"], int)
        assert isinstance(u0["builds"], int)


# ---------- ChatMessageInput validation ----------
class TestChatInputValidation:
    def test_empty_message_rejected(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/advisor/chat", json={"message": ""})
        assert r.status_code == 422

    def test_over_2000_chars_rejected(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/advisor/chat",
                               json={"message": "x" * 2001})
        assert r.status_code == 422

    def test_boundary_2000_chars_accepted(self, admin_session):
        # Should NOT be 422; may be 200 streamed. Just consume a bit.
        r = admin_session.post(f"{BASE_URL}/api/advisor/chat",
                               json={"message": "a" * 2000, "lang": "it"}, stream=True, timeout=15)
        assert r.status_code == 200, r.text[:200]
        # read first small chunk & close
        for chunk in r.iter_content(chunk_size=64):
            if chunk:
                break
        r.close()


# ---------- Advisor chat short message still streams ----------
class TestAdvisorStream:
    def test_short_chat_streams(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/advisor/chat",
                               json={"message": "ciao", "lang": "it"}, stream=True, timeout=20)
        assert r.status_code == 200
        got = b""
        for chunk in r.iter_content(chunk_size=128):
            got += chunk
            if len(got) > 32:
                break
        r.close()
        assert b"__SESSION__" in got


# ---------- AI rate limit guard ----------
class TestAIRateLimit:
    """Verify the guard triggers 429 when >=100 user chat_messages in last hour.

    Strategy: seed 100 fake user messages directly in mongo for admin uid,
    then call /api/advisor/chat -> expect 429. Cleanup after.
    """

    def test_rate_limit_returns_429(self, admin_session):
        # need admin uid
        me = admin_session.get(f"{BASE_URL}/api/auth/me").json()
        uid = me["id"]
        # seed via pymongo directly (backend uses motor async, we use sync driver here)
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        cli = MongoClient(mongo_url)
        try:
            coll = cli[db_name]["chat_messages"]
            now = datetime.now(timezone.utc).isoformat()
            marker = f"__ratelimit_test_{int(time.time())}__"
            docs = [{"id": f"rl-{i}", "session_id": marker, "user_id": uid,
                     "role": "user", "content": "seed", "created_at": now}
                    for i in range(100)]
            coll.insert_many(docs)
            try:
                r = admin_session.post(f"{BASE_URL}/api/advisor/chat",
                                       json={"message": "over-limit", "lang": "it"})
                assert r.status_code == 429, f"expected 429 got {r.status_code}: {r.text[:200]}"
            finally:
                coll.delete_many({"session_id": marker})
                # also remove any assistant/user messages created during a failed attempt
                coll.delete_many({"user_id": uid, "content": "over-limit"})
        finally:
            cli.close()
