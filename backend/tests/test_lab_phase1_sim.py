"""Simulazione E2E agent del Laboratorio (Fase 1) via HTTP."""
import os
import random
import sys
import requests

BASE = "https://gaming-nexus-199.preview.emergentagent.com"
EMAIL = "admin@boostpc.io"
PWD = "4zWK4o_xSw5prU-2b7w9dQ"

s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PWD}, timeout=15)
assert r.status_code == 200, r.text
tk = s.get(f"{BASE}/api/agent/token", timeout=15).json()["token"]
H = {"X-Agent-Token": tk}

# pulizia sessioni precedenti
sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
if sess and sess["status"] not in ("completed", "aborted"):
    s.post(f"{BASE}/api/lab/abort", timeout=15)
    requests.post(f"{BASE}/api/agent/lab/event", json={"type": "aborted"}, headers=H, timeout=15)

# registry
reg = s.get(f"{BASE}/api/lab/registry?risk_level=medium", timeout=15).json()
print("registry:", len(reg["candidates"]), "candidati |", [c["tweak_id"] for c in reg["candidates"]][:4], "... skipped:", [x["tweak_id"] for x in reg["skipped"]])

# start invalido
r = s.post(f"{BASE}/api/lab/start", json={"risk_level": "hardware"}, timeout=15)
assert r.status_code == 422, f"expected 422 got {r.status_code}"
print("start rischio invalido -> 422 OK")

r = s.post(f"{BASE}/api/lab/start", json={"risk_level": "medium", "run_seconds": 90, "include_reboot": False}, timeout=15)
assert r.status_code == 200, r.text
sess = r.json()["session"]
print("sessione creata:", sess["session_id"][:8], "status", sess["status"], "| candidati:", len(sess["candidates"]))

# doppio start -> 409
r = s.post(f"{BASE}/api/lab/start", json={"risk_level": "safe"}, timeout=15)
assert r.status_code == 409, r.status_code
print("doppio start -> 409 OK")

def nxt():
    return requests.get(f"{BASE}/api/agent/lab/next", headers=H, timeout=15).json()

def event(t, data=None):
    return requests.post(f"{BASE}/api/agent/lab/event", json={"type": t, "data": data}, headers=H, timeout=15).json()

def post_run(phase, tweak_id, fps):
    run = {"fps_avg": round(fps, 2), "fps_p1": round(fps * 0.82, 2), "fps_p01": round(fps * 0.7, 2),
           "ft_avg_ms": round(1000 / fps, 3), "ft_var": 1.5, "frames": 15000, "duration_s": 90,
           "game": "cs2.exe", "cpu_pct": 55, "gpu_pct": 96, "temp_gpu": 70}
    body = {"phase": phase, "run": run}
    if tweak_id:
        body["tweak_id"] = tweak_id
    return requests.post(f"{BASE}/api/agent/lab/run", json=body, headers=H, timeout=15).json()

# 1. snapshot
n = nxt()
assert n["action"] == "snapshot", n
print("next -> snapshot, candidati:", len(n["candidate_ids"]))
event("snapshot_done", {"restore_point": True, "states": {c: "Da ottimizzare" for c in n["candidate_ids"]}})

# 2. baseline: primo giro con CV alto per testare il 4o run + outlier
n = nxt()
assert n["action"] == "run_baseline", n
base = 200.0
noisy = [200, 230, 195]  # CV > 5%
for f in noisy:
    resp = post_run("baseline", None, f)
print("baseline dopo 3 run rumorosi:", resp)
assert resp.get("extra_run"), "atteso extra_run per CV>5%"
resp = post_run("baseline", None, 201)
assert resp.get("baseline_ok"), resp
print("baseline OK (outlier scartato):", resp["stats"])

# 3. test loop: primo tweak -> miglioramento reale (kept), secondo -> nullo (rollback), poi 3 nulli -> auto-stop
random.seed(7)
tested = []
while True:
    n = nxt()
    if n["action"] in ("wait", "transition"):
        continue
    if n["action"] == "run_validation":
        resp = post_run("validation", None, 217, )
        assert resp.get("completed"), resp
        report = resp["report"]
        print("COMPLETE via validazione. gain:", report["total_gain_pct"], "% | kept:", report["kept"])
        break
    if n["action"] == "complete":
        print("COMPLETE. report gain:", n["report"]["total_gain_pct"], "% | kept:", n["report"]["kept"])
        report = n["report"]
        break
    if n["action"] == "apply_tweak":
        event("tweak_applied", {"tweak_id": n["tweak_id"], "requires_reboot": n.get("requires_reboot", False)})
        tested.append(n["tweak_id"])
        continue
    if n["action"] == "run_test":
        tid = n["tweak_id"]
        cur_base = 201.0 if len(tested) == 1 else None
        # primo tweak: +8%; gli altri: rumore attorno alla baseline corrente
        if len(tested) == 1:
            f = 217 + random.uniform(-0.8, 0.8)
        else:
            f = 217 + random.uniform(-1.0, 1.0) if tested and tested[0] in ("power",) else 201 + random.uniform(-1, 1)
        resp = post_run("test", tid, f)
        if resp.get("decision"):
            print(f"  {tid}: {resp['decision']} ({resp['reason']}) p={resp['significance']['p_value']}")
            if resp["decision"] == "rolled_back":
                event("rolled_back", {"tweak_id": tid})
        continue
    if n["action"] == "run_recheck":
        f = 217 + random.uniform(-0.5, 0.5) if tested and tested[0] in ("power",) else 201 + random.uniform(-0.5, 0.5)
        post_run("recheck", None, f)
        continue
    print("azione inattesa:", n)
    sys.exit(1)

assert report["baseline"]["fps_avg"], report
assert len(report["steps"]) >= 4
assert report.get("auto_stop_reason"), "atteso auto-stop"
kept_steps = [st for st in report["steps"] if st["decision"] == "kept"]
assert len(kept_steps) >= 1
print("steps:", [(st["tweak_id"], st["decision"], st["delta_pct"]) for st in report["steps"]])
print("performance_index:", report["performance_index"], "| durata:", report["total_duration_min"], "min")

# 4. sessione utente vede report
sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
assert sess["status"] == "completed" and sess["report"]
print("GET /lab/session -> completed con report OK")

# 5. test abort su nuova sessione
r = s.post(f"{BASE}/api/lab/start", json={"risk_level": "safe", "run_seconds": 90}, timeout=15)
assert r.status_code == 200
n = nxt(); assert n["action"] == "snapshot"
s.post(f"{BASE}/api/lab/abort", timeout=15)
n = nxt()
assert n["action"] == "abort", n
print("abort -> action abort, rollback_ids:", n["rollback_ids"])
event("aborted")
sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
assert sess["status"] == "aborted"
print("sessione aborted OK")

# auth check
r = requests.get(f"{BASE}/api/agent/lab/next", headers={"X-Agent-Token": "fake"}, timeout=15)
assert r.status_code == 401, r.status_code
print("token agent invalido -> 401 OK")
print("\nTUTTI I TEST E2E PASSATI")
