"""Iteration 54: Auto-Pilot, Device Compare, Streak Reminder tests."""
from pathlib import Path as _P
# Radice del repository calcolata dal file: i percorsi "/app/..." erano il
# layout di un vecchio container e non esistono ne' in locale ne' nell'immagine
# attuale, che monta il codice in /srv/app.
_BACKEND_DIR = _P(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
import os
import sys
import asyncio
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            for line in open("../frontend/.env"):
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
        except Exception:
            pass
    return (v or "").rstrip("/")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
STARTER_EMAIL = os.environ.get("STARTER_EMAIL", os.environ.get("STARTER_EMAIL", "credits_test@frameforge.dev"))
STARTER_PASSWORD = os.environ.get("STARTER_PASSWORD", "")

sys.path.insert(0, str(_BACKEND_DIR))


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def starter_session():
    return _login(STARTER_EMAIL, STARTER_PASSWORD)


@pytest.fixture(scope="module")
def admin_agent_token(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/agent/token")
    assert r.status_code == 200
    return r.json()["token"]


# ------------------- Auto-Pilot -------------------

class TestAutopilotAdmin:
    def test_status_admin_unlimited(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/autopilot/status")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] is None, f"admin should have unlimited: {data}"
        assert data.get("remaining") is None

    def test_start_then_result_flow(self, admin_session, admin_agent_token):
        # Start
        r = admin_session.post(f"{BASE_URL}/api/autopilot/start")
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        run_id = r.json().get("run_id")
        assert run_id

        # Agent result
        payload = {
            "applied": ["power", "gaming_mode"],
            "before": {"cpu_temp": 65, "gpu_temp": 70, "ram_used_pct": 75},
            "after": {"cpu_temp": 60, "gpu_temp": 64, "ram_used_pct": 60},
        }
        r2 = requests.post(
            f"{BASE_URL}/api/autopilot/agent/result",
            json=payload,
            headers={"X-Agent-Token": admin_agent_token, "X-Device": "gaming-rig"},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["applied"] == 2

        # Status latest should be done
        r3 = admin_session.get(f"{BASE_URL}/api/autopilot/status")
        assert r3.status_code == 200
        latest = r3.json().get("latest")
        assert latest is not None
        assert latest["status"] == "done"
        assert len(latest["applied"]) == 2
        assert latest["before"].get("score") is not None
        assert latest["after"].get("score") is not None
        assert isinstance(latest.get("delta_score"), int)

    def test_tweaks_applied_counter_bumped(self, admin_session, admin_agent_token):
        # Read counter before
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")

        async def get_state():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            u = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 1})
            uid = str(u["_id"])
            up = await db.user_progress.find_one({"user_id": uid}, {"counters": 1})
            client.close()
            return (up or {}).get("counters", {}).get("tweaks_applied", 0)

        before = asyncio.run(get_state())

        # Start + result
        admin_session.post(f"{BASE_URL}/api/autopilot/start")
        payload = {
            "applied": ["power", "gaming_mode"],
            "before": {"cpu_temp": 65, "gpu_temp": 70, "ram_used_pct": 75},
            "after": {"cpu_temp": 60, "gpu_temp": 64, "ram_used_pct": 60},
        }
        r = requests.post(
            f"{BASE_URL}/api/autopilot/agent/result",
            json=payload,
            headers={"X-Agent-Token": admin_agent_token, "X-Device": "gaming-rig"},
        )
        assert r.status_code == 200

        after = asyncio.run(get_state())
        assert after - before >= 2, f"counter did not bump: {before} -> {after}"


class TestAutopilotStarter:
    def test_starter_status_limit_1(self, starter_session):
        r = starter_session.get(f"{BASE_URL}/api/autopilot/status")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 1

    def test_starter_402_when_used(self, starter_session):
        # first attempt: check status
        r = starter_session.get(f"{BASE_URL}/api/autopilot/status")
        used = r.json().get("used", 0)
        if used < 1:
            r2 = starter_session.post(f"{BASE_URL}/api/autopilot/start")
            assert r2.status_code == 200
        # now exceeded
        r3 = starter_session.post(f"{BASE_URL}/api/autopilot/start")
        assert r3.status_code == 402
        detail = r3.json().get("detail", {})
        assert detail.get("code") == "autopilot_limit"


# ------------------- Device Compare -------------------

class TestDeviceCompare:
    def test_compare_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/devices/compare")
        assert r.status_code == 401

    def test_compare_admin_two_devices(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/devices/compare")
        assert r.status_code == 200
        devs = r.json().get("devices", [])
        assert len(devs) == 2, f"expected 2 devices, got {len(devs)}"
        for d in devs:
            assert "health" in d and set(["score", "grade", "cpu_temp", "gpu_temp"]).issubset(d["health"].keys())
            assert "live" in d and "cpu_util" in d["live"]
            assert "specs" in d


# ------------------- URI Modes -------------------

class TestUriModes:
    def test_autopilot_mode_allowed(self):
        # inspect module directly
        import importlib
        pc_mod = importlib.import_module("routers.pc")
        src = open(pc_mod.__file__).read()
        # Both _ALLOWED_URI_MODES sets must include 'autopilot'
        # Rough check: count occurrences
        assert src.count("'autopilot'") + src.count('"autopilot"') >= 2


# ------------------- Streak Reminder -------------------

class TestStreakReminder:
    def test_scheduler_job_registered(self):
        # Ensure server.py has cron hour=17 for streak_reminders
        src = open(str(_BACKEND_DIR / "server.py")).read()
        assert "streak_reminders" in src
        assert "hour=17" in src

    def test_reminder_idempotent(self):
        """Set streak_day=yday, unset reminder_day, run reminder → sets today; second run no-op. Restore."""
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")

        async def run():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            u = await db.users.find_one({"email": STARTER_EMAIL}, {"_id": 1})
            uid = str(u["_id"])

            # Save original
            orig = await db.user_missions.find_one({"user_id": uid}, {"daily": 1}) or {}
            orig_daily = orig.get("daily", {}).copy()

            # Import helpers
            sys.path.insert(0, str(_BACKEND_DIR))
            from missions import _yesterday_id, _day_id
            yday = _yesterday_id()
            today = _day_id()

            # Setup: streak>=1, streak_day=yesterday, unset reminder_day
            await db.user_missions.update_one(
                {"user_id": uid},
                {"$set": {"daily.streak": 3, "daily.streak_day": yday},
                 "$unset": {"daily.reminder_day": ""}},
                upsert=True,
            )

            # Call function (must patch db in server module to point at same client)
            import server
            server.db = db  # ensure using our db
            await server.scheduled_streak_reminders()

            after1 = await db.user_missions.find_one({"user_id": uid}, {"daily": 1})
            reminder1 = (after1 or {}).get("daily", {}).get("reminder_day")

            # Second run
            await server.scheduled_streak_reminders()
            after2 = await db.user_missions.find_one({"user_id": uid}, {"daily": 1})
            reminder2 = (after2 or {}).get("daily", {}).get("reminder_day")

            # Restore original
            restore_set = {}
            restore_unset = {}
            for k in ["streak", "streak_day", "reminder_day"]:
                v = orig_daily.get(k)
                if v is None:
                    restore_unset[f"daily.{k}"] = ""
                else:
                    restore_set[f"daily.{k}"] = v
            update = {}
            if restore_set:
                update["$set"] = restore_set
            if restore_unset:
                update["$unset"] = restore_unset
            if update:
                await db.user_missions.update_one({"user_id": uid}, update)

            client.close()
            return reminder1, reminder2, today

        reminder1, reminder2, today = asyncio.run(run())
        assert reminder1 == today, f"first run did not set reminder_day (got {reminder1})"
        assert reminder2 == today, f"second run changed reminder_day ({reminder2})"


# ------------------- Regression -------------------

class TestRegression:
    def test_missions_ok(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/missions")
        assert r.status_code == 200

    def test_devices_ok(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/devices")
        assert r.status_code == 200
        assert len(r.json().get("devices", [])) == 2
