"""Regression tests — Missions engine (/api/missions/*).

Flow: nuovo utente -> 3 starter auto-attivate -> slots_full -> abandon/activate
-> completamento automatico svc_purge tramite services_done (2 servizi rimossi
dall'audit tra due scan) -> +XP nel pool tier.
"""
import os
import random
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get(
    "BACKEND_URL", "http://localhost:8001")

_FILLER = [{"name": f"Svc{i}", "display": f"Filler {i}", "state": "Running",
            "start_mode": "Auto", "shared": True, "ram_mb": None,
            "dependents": 0, "ms": True} for i in range(10)]


@pytest.fixture(scope="module")
def ctx():
    s = requests.Session()
    email = f"missions_test_{random.randint(10000, 99999)}@test.io"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "name": "MTest", "password": "Test_Pass_123!"}, timeout=15)
    assert r.status_code == 200, r.text
    tok = s.get(f"{BASE_URL}/api/agent/token", timeout=10).json()["token"]
    return {"s": s, "agent_token": tok}


def _scan(ctx, audit):
    r = requests.post(f"{BASE_URL}/api/agent/report-specs",
                      headers={"X-Agent-Token": ctx["agent_token"]},
                      json={"services_audit": audit}, timeout=15)
    assert r.status_code == 200, r.text


def test_starter_missions_auto_activated(ctx):
    d = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()
    codes = {m["code"] for m in d["active"]}
    assert codes == {"svc_purge", "bench_first", "advisor_consult"}
    assert d["slots"] == {"used": 3, "max": 3}
    assert all(m["progress"] == 0 for m in d["active"])


def test_activate_fails_when_slots_full(ctx):
    r = ctx["s"].post(f"{BASE_URL}/api/missions/activate/net_check", timeout=10)
    assert r.status_code == 400
    assert r.json()["detail"] == "slots_full"


def test_abandon_and_activate(ctx):
    assert ctx["s"].post(f"{BASE_URL}/api/missions/abandon/advisor_consult", timeout=10).json()["ok"]
    assert ctx["s"].post(f"{BASE_URL}/api/missions/activate/health_80", timeout=10).json()["ok"]
    d = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()
    codes = {m["code"] for m in d["active"]}
    assert "health_80" in codes and "advisor_consult" not in codes


def test_unknown_mission_rejected(ctx):
    assert ctx["s"].post(f"{BASE_URL}/api/missions/activate/nope", timeout=10).status_code == 400


def test_chain_and_weekly_initial(ctx):
    d = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()
    steps = d["chain"]["steps"]
    assert [s["code"] for s in steps] == ["recruit_scan", "recruit_optimize", "recruit_benchmark"]
    assert steps[0]["status"] == "active"      # nessuno scan ancora
    assert steps[1]["status"] == "locked"
    assert d["chain"]["done"] is False
    wk = d["weekly"]
    assert wk["week_id"] and wk["expires_at"]
    # utente senza specs.cpu -> fallback deterministico (niente chiamata AI)
    assert {m["template"] for m in wk["missions"]} == {"w_bench", "w_net"}
    assert all(m["progress"] == 0 and not m["completed_at"] for m in wk["missions"])


def test_svc_purge_completes_and_awards_xp(ctx):
    xp_before = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()["xp"]
    tracked = [
        {"name": "DiagTrack", "display": "Connected User Experiences", "state": "Running",
         "start_mode": "Auto", "shared": True, "ram_mb": 45, "dependents": 0, "ms": True},
        {"name": "dmwappushservice", "display": "WAP Push", "state": "Running",
         "start_mode": "Auto", "shared": True, "ram_mb": 12, "dependents": 0, "ms": True},
    ]
    _scan(ctx, tracked + _FILLER)   # servizi consigliati presenti
    _scan(ctx, list(_FILLER))       # spariti -> services_done x2
    d = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()
    assert "svc_purge" in [m["code"] for m in d["completed"]]
    assert "svc_purge" in [m["code"] for m in d["just_completed"]]
    # >= : gli scan possono sbloccare anche milestone concorrenti (es. first_scan +10)
    assert d["xp"] >= xp_before + 60
    # just_completed e' one-shot: seconda GET non lo ripete
    d2 = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()
    assert d2["just_completed"] == []


def test_chain_advances_with_activity(ctx):
    # dopo gli scan del test precedente: pc_scans>=1 e services_done>=1
    d = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()
    st = {s["code"]: s["status"] for s in d["chain"]["steps"]}
    assert st["recruit_scan"] == "completed"
    assert st["recruit_optimize"] == "completed"
    assert st["recruit_benchmark"] == "active"
    assert d["chain"]["done"] is False


def test_benchmark_completes_chain_and_weekly(ctx):
    r = requests.post(f"{BASE_URL}/api/agent/report-specs",
                      headers={"X-Agent-Token": ctx["agent_token"]},
                      json={"benchmark": {"overall": 75, "duration_s": 30}}, timeout=15)
    assert r.status_code == 200
    d = ctx["s"].get(f"{BASE_URL}/api/missions", timeout=10).json()
    just = [m["code"] for m in d["just_completed"]]
    assert "recruit_benchmark" in just
    assert d["chain"]["done"] is True
    wk = {m["template"]: bool(m["completed_at"]) for m in d["weekly"]["missions"]}
    assert wk["w_bench"] is True
