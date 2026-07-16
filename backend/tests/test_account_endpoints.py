"""Tests for new /api/auth account endpoints: preferences, profile, change-password, delete-account."""
import os
import time
import uuid
import requests
import pytest

def _read_frontend_env():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()
BASE_URL = BASE_URL.rstrip("/")
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


def _register(session, email, password="pw123456", name="Throwaway"):
    r = session.post(f"{BASE_URL}/api/auth/register",
                     json={"email": email, "password": password, "name": name})
    return r


def _login(session, email, password):
    return session.post(f"{BASE_URL}/api/auth/login",
                        json={"email": email, "password": password})


@pytest.fixture
def throwaway():
    s = requests.Session()
    email = f"TEST_{uuid.uuid4().hex[:10]}@test.io"
    password = "pw123456"
    r = _register(s, email, password)
    assert r.status_code == 200, r.text
    return {"session": s, "email": email, "password": password}


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    return s


# ---------- auth required ----------
class TestAuthRequired:
    def test_preferences_get_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/preferences")
        assert r.status_code == 401

    def test_preferences_put_401(self):
        r = requests.put(f"{BASE_URL}/api/auth/preferences",
                         json={"local_only": True, "email_alerts": False, "language": "it"})
        assert r.status_code == 401

    def test_profile_401(self):
        r = requests.patch(f"{BASE_URL}/api/auth/profile", json={"name": "X"})
        assert r.status_code == 401

    def test_change_pw_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/change-password",
                          json={"current_password": "a", "new_password": "abcdef"})
        assert r.status_code == 401

    def test_delete_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/delete-account", json={"password": "x"})
        assert r.status_code == 401


# ---------- preferences ----------
class TestPreferences:
    def test_default_and_update(self, throwaway):
        s = throwaway["session"]
        r = s.get(f"{BASE_URL}/api/auth/preferences")
        assert r.status_code == 200
        data = r.json()
        assert data == {"local_only": False, "email_alerts": False, "language": "it"}

        r = s.put(f"{BASE_URL}/api/auth/preferences",
                  json={"local_only": True, "email_alerts": True, "language": "en"})
        assert r.status_code == 200
        d = r.json()
        assert d["local_only"] is True and d["email_alerts"] is True and d["language"] == "en"

        r = s.get(f"{BASE_URL}/api/auth/preferences")
        assert r.json() == {"local_only": True, "email_alerts": True, "language": "en"}


# ---------- profile ----------
class TestProfile:
    def test_update_name(self, throwaway):
        s = throwaway["session"]
        r = s.patch(f"{BASE_URL}/api/auth/profile", json={"name": "NewName"})
        assert r.status_code == 200
        assert r.json()["name"] == "NewName"
        # verify via /me
        me = s.get(f"{BASE_URL}/api/auth/me").json()
        assert me["name"] == "NewName"


# ---------- change password ----------
class TestChangePassword:
    def test_wrong_current(self, throwaway):
        s = throwaway["session"]
        r = s.post(f"{BASE_URL}/api/auth/change-password",
                   json={"current_password": "wrongpw", "new_password": "newpw123"})
        assert r.status_code == 400
        assert "Password attuale" in r.json().get("detail", "")

    def test_same_as_current(self, throwaway):
        s = throwaway["session"]
        r = s.post(f"{BASE_URL}/api/auth/change-password",
                   json={"current_password": throwaway["password"],
                         "new_password": throwaway["password"]})
        assert r.status_code == 400

    def test_success_and_relogin(self, throwaway):
        s = throwaway["session"]
        new_pw = "newpw123"
        r = s.post(f"{BASE_URL}/api/auth/change-password",
                   json={"current_password": throwaway["password"], "new_password": new_pw})
        assert r.status_code == 200
        # cookies should still work
        assert s.get(f"{BASE_URL}/api/auth/me").status_code == 200
        # login with old password should fail
        s2 = requests.Session()
        assert _login(s2, throwaway["email"], throwaway["password"]).status_code == 401
        # login with new password should succeed
        s3 = requests.Session()
        assert _login(s3, throwaway["email"], new_pw).status_code == 200


# ---------- delete account ----------
class TestDeleteAccount:
    def test_admin_cannot_delete(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/auth/delete-account",
                               json={"password": ADMIN_PASSWORD})
        assert r.status_code == 400
        # admin still logged in
        assert admin_session.get(f"{BASE_URL}/api/auth/me").status_code == 200

    def test_wrong_password(self, throwaway):
        s = throwaway["session"]
        r = s.post(f"{BASE_URL}/api/auth/delete-account", json={"password": "wrong"})
        assert r.status_code == 400
        assert s.get(f"{BASE_URL}/api/auth/me").status_code == 200

    def test_success(self, throwaway):
        s = throwaway["session"]
        r = s.post(f"{BASE_URL}/api/auth/delete-account", json={"password": throwaway["password"]})
        assert r.status_code == 200
        # cookies cleared -> unauthorized
        assert s.get(f"{BASE_URL}/api/auth/me").status_code == 401
        # cannot log back in
        s2 = requests.Session()
        assert _login(s2, throwaway["email"], throwaway["password"]).status_code == 401


# ---------- regression admin ----------
class TestAdminRegression:
    def test_admin_login_works(self):
        s = requests.Session()
        r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
