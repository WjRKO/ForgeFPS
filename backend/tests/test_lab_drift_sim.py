"""Mini-sim: path drift -> re-baseline del recheck A/B/A. Eseguire come script.

Avvia con `paired: false`: qui si verifica lo schema a BLOCCHI, che resta la
strada per i tweak con riavvio e per chi sceglie la sessione breve. I run non
portano l'istogramma, quindi copre anche il percorso di ricaduta per gli agent
vecchi. Lo schema appaiato ha la sua simulazione in test_lab_paired_sim.py.
"""
import os

import requests

# L'indirizzo del backend arriva SEMPRE dall'ambiente: quando era fisso su
# localhost:8001 la suite colpiva l'istanza di lavoro anche lanciandola
# contro un'altra porta, sporcando il database reale e bloccando l'admin.
BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
s = requests.Session()
s.post(f"{BASE}/api/auth/login",
       json={"email": os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"),
             "password": os.environ.get("ADMIN_PASSWORD", "")}, timeout=15)
tk = s.get(f"{BASE}/api/agent/token", timeout=15).json()["token"]
H = {"X-Agent-Token": tk}
nxt = lambda: requests.get(f"{BASE}/api/agent/lab/next", headers=H, timeout=15).json()
ev = lambda t, d=None: requests.post(f"{BASE}/api/agent/lab/event", json={"type": t, "data": d}, headers=H, timeout=15).json()


def post_run(phase, fps, tweak_id=None):
    body = {"phase": phase, "run": {"fps_avg": fps, "fps_p1": round(fps * 0.8, 1), "ft_avg_ms": round(1000 / fps, 3),
            "ft_var": 1.0, "frames": 9000, "duration_s": 90, "game": "cs2.exe"}}
    if tweak_id:
        body["tweak_id"] = tweak_id
    return requests.post(f"{BASE}/api/agent/lab/run", json=body, headers=H, timeout=15).json()


sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
if sess and sess["status"] not in ("completed", "aborted"):
    s.post(f"{BASE}/api/lab/abort", timeout=15)
    ev("aborted")
s.post(f"{BASE}/api/lab/start", json={"risk_level": "medium", "run_seconds": 90, "include_reboot": False, "paired": False}, timeout=15)
base = 200.0
n_res, i, done = 0, 0, False
for _ in range(200):
    nx = nxt()
    a = nx.get("action")
    if a == "snapshot":
        ev("snapshot_done", {"restore_point": True, "states": {}})
    elif a == "run_baseline":
        post_run("baseline", base + [-0.5, 0, 0.5][nx.get("runs_done", 0) % 3])
    elif a == "apply_tweak":
        ev("tweak_applied", {"tweak_id": nx["tweak_id"], "requires_reboot": False})
    elif a == "run_test":
        r = post_run("test", round(base * 1.05, 1) + [-0.2, 0, 0.2][nx.get("runs_done", 0) % 3], nx["tweak_id"])
        if r.get("decision"):
            n_res += 1
            if r["decision"] == "kept":
                base = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]["baseline"]["stats"]["fps_avg"]
            else:
                ev("rolled_back", {"tweak_id": nx["tweak_id"]})
    elif a == "run_recheck":
        i += 1
        if i == 1:
            r = post_run("recheck", round(base * 0.94, 1))  # drift -6%
            assert r.get("stable") is False and r.get("need_more"), r
            print("drift rilevato:", r["drift_pct"], "% -> chiede 3 run")
        else:
            r = post_run("recheck", round(base * 0.94, 1) + [0, -0.3, 0.3][i % 3])
            if r.get("rebaselined"):
                assert abs(r["stats"]["fps_avg"] - base * 0.94) < 2.0, r["stats"]
                print("RE-BASELINE OK:", r["stats"]["fps_avg"], "FPS")
                done = True
                break
    elif a in ("wait", "complete", "transition"):
        if a == "complete":
            break
assert done, "re-baseline non raggiunto"
sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
assert (sess.get("drift_events") or []), "drift_events mancante"
s.post(f"{BASE}/api/lab/abort", timeout=15)
ev("aborted")
print("drift_events registrati:", sess["drift_events"])
print("TEST DRIFT/RE-BASELINE PASSATO (sessione abortita per pulizia)")
