"""Admin RBAC tests for BOOST PC AI."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "admin123"


def _register(email=None, password="Password123!"):
    s = requests.Session()
    email = email or f"rbac_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "RBAC User"}, timeout=30)
    assert r.status_code == 200, r.text
    s.email = email
    s.password = password
    s.user_id = r.json()["id"]
    return s


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    me = s.get(f"{API}/auth/me", timeout=15).json()
    assert me["role"] == "admin"
    s.user_id = me["id"]
    return s


@pytest.fixture(scope="module")
def normal_user():
    return _register()


class TestAdminStats:
    def test_stats_ok_for_admin(self, admin):
        r = admin.get(f"{API}/admin/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("total_users", "total_admins", "total_products", "total_builds"):
            assert k in data, f"missing key {k}"
            assert isinstance(data[k], int)
        assert data["total_admins"] >= 1
        assert data["total_users"] >= 1

    def test_stats_forbidden_for_user(self, normal_user):
        r = normal_user.get(f"{API}/admin/stats", timeout=15)
        assert r.status_code == 403

    def test_stats_unauth(self):
        r = requests.get(f"{API}/admin/stats", timeout=15)
        assert r.status_code == 401


class TestAdminUsers:
    def test_list_users_admin(self, admin, normal_user):
        r = admin.get(f"{API}/admin/users", timeout=30)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        assert len(arr) >= 2
        sample = arr[0]
        for k in ("id", "email", "role", "tracked_products", "builds"):
            assert k in sample
        # ensure normal user in list
        emails = {u["email"] for u in arr}
        assert normal_user.email.lower() in emails

    def test_list_users_forbidden(self, normal_user):
        r = normal_user.get(f"{API}/admin/users", timeout=15)
        assert r.status_code == 403

    def test_role_change_and_back(self, admin, normal_user):
        uid = normal_user.user_id
        r = admin.patch(f"{API}/admin/users/{uid}/role", json={"role": "admin"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "admin"
        # verify via list
        arr = admin.get(f"{API}/admin/users", timeout=30).json()
        rec = next(u for u in arr if u["id"] == uid)
        assert rec["role"] == "admin"
        # revert
        r = admin.patch(f"{API}/admin/users/{uid}/role", json={"role": "user"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "user"

    def test_admin_cannot_self_demote(self, admin):
        r = admin.patch(f"{API}/admin/users/{admin.user_id}/role", json={"role": "user"}, timeout=15)
        assert r.status_code == 400

    def test_role_change_forbidden_for_user(self, normal_user, admin):
        r = normal_user.patch(f"{API}/admin/users/{admin.user_id}/role", json={"role": "user"}, timeout=15)
        assert r.status_code == 403

    def test_invalid_role(self, admin, normal_user):
        r = admin.patch(f"{API}/admin/users/{normal_user.user_id}/role", json={"role": "root"}, timeout=15)
        assert r.status_code in (400, 422)

    def test_role_invalid_id(self, admin):
        r = admin.patch(f"{API}/admin/users/notanid/role", json={"role": "user"}, timeout=15)
        assert r.status_code == 400

    def test_admin_cannot_self_delete(self, admin):
        r = admin.delete(f"{API}/admin/users/{admin.user_id}", timeout=15)
        assert r.status_code == 400

    def test_delete_user_forbidden_for_user(self, normal_user, admin):
        r = normal_user.delete(f"{API}/admin/users/{admin.user_id}", timeout=15)
        assert r.status_code == 403

    def test_delete_throwaway_user(self, admin):
        throwaway = _register()
        tid = throwaway.user_id
        # confirm exists in list
        arr = admin.get(f"{API}/admin/users", timeout=30).json()
        assert any(u["id"] == tid for u in arr)
        # delete
        r = admin.delete(f"{API}/admin/users/{tid}", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # verify gone
        arr2 = admin.get(f"{API}/admin/users", timeout=30).json()
        assert not any(u["id"] == tid for u in arr2)
        # second delete -> 404
        r = admin.delete(f"{API}/admin/users/{tid}", timeout=15)
        assert r.status_code == 404


class TestRegression:
    def test_normal_login_and_me(self):
        s = _register()
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "user"

    def test_tracker_add_by_url(self, normal_user):
        # basic tracker flow: post product by URL (mocked source ok)
        payload = {"url": "https://www.amazon.it/dp/B08L5WHFT9", "name": "Test SSD", "current_price": 89.99}
        r = normal_user.post(f"{API}/products/track", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        pid = r.json().get("id")
        assert pid
        # cleanup
        normal_user.delete(f"{API}/products/{pid}", timeout=15)
