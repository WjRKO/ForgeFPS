"""Sim E2E Lab fase 4: stutter score, latenza input, mini-lab di verifica (check), history/insights.
Eseguire come script: python tests/test_lab_phase4_sim.py (NON via pytest)."""
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

sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
if sess and sess["status"] not in ("completed", "aborted"):
    s.post(f"{BASE}/api/lab/abort", timeout=15)
    requests.post(f"{BASE}/api/agent/lab/event", json={"type": "aborted"}, headers=H, timeout=15)


def nxt():
    return requests.get(f"{BASE}/api/agent/lab/next", headers=H, timeout=15).json()


def event(t, data=None):
    return requests.post(f"{BASE}/api/agent/lab/event", json={"type": t, "data": data}, headers=H, timeout=15).json()


def post_run(phase, run, tweak_id=None):
    body = {"phase": phase, "run": run}
    if tweak_id:
        body["tweak_id"] = tweak_id
    rr = requests.post(f"{BASE}/api/agent/lab/run", json=body, headers=H, timeout=15)
    assert rr.status_code == 200, rr.text
    return rr.json()


def mk(fps, p1, lat=None, game="cs2.exe", dur=90):
    run = {"fps_avg": fps, "fps_p1": p1, "fps_p01": round(p1 * 0.9, 2), "ft_avg_ms": round(1000 / fps, 3),
           "ft_var": 1.2, "frames": 9000, "duration_s": dur, "game": game}
    if lat is not None:
        run["latency_ms"] = lat
    return run


# ---------- FULL LAB con profili di decisione controllati ----------
r = s.post(f"{BASE}/api/lab/start", json={"risk_level": "medium", "run_seconds": 90, "include_reboot": False}, timeout=15)
assert r.status_code == 200, r.text
print("full lab avviato, candidati:", len(r.json()["session"]["candidates"]))

# fps di base per fase (aggiornati man mano che i tweak vengono mantenuti)
base_fps, base_p1, base_lat = 200.0, 160.0, 25.0
test_n = 0
run_i = 0
profile_reasons = {}

for _ in range(400):
    nx = nxt()
    act = nx.get("action")
    if act == "wait":
        break
    if act == "transition":
        continue
    if act == "snapshot":
        event("snapshot_done", {"restore_point": True, "states": {}})
    elif act == "run_baseline":
        jit = [-0.5, 0.0, 0.5, 0.2][len(str(run_i)) % 4]
        i = nx.get("runs_done", 0)
        resp = post_run("baseline", mk(base_fps + [-0.5, 0.0, 0.5][i % 3], base_p1 + [-0.4, 0.0, 0.4][i % 3], base_lat))
        if resp.get("baseline_ok"):
            print("baseline ok:", resp["stats"]["fps_avg"], "lat", resp["stats"].get("latency_ms"))
    elif act == "apply_tweak":
        event("tweak_applied", {"tweak_id": nx["tweak_id"], "requires_reboot": False})
    elif act == "run_test":
        test_n_cur = len(profile_reasons) + 1
        i = nx.get("runs_done", 0)
        j3 = [-0.2, 0.0, 0.2][i % 3]
        jp = [-0.15, 0.0, 0.15][i % 3]
        if test_n_cur == 1:   # FLUIDITY: fps neutri, 1% low +6%
            run = mk(base_fps + j3 * 0.5, round(base_p1 * 1.06, 1) + jp, base_lat)
        elif test_n_cur == 2:  # STUTTER GUARD: fps +4%, 1% low -13%
            run = mk(round(base_fps * 1.04, 1) + j3, round(base_p1 * 0.87, 1) + jp, base_lat)
        elif test_n_cur == 3:  # GOOD: fps +5%, p1 +5%, latenza -4ms
            run = mk(round(base_fps * 1.05, 1) + j3, round(base_p1 * 1.05, 1) + jp, base_lat - 4)
        else:                  # NEUTRO: non significativo
            run = mk(base_fps + j3, base_p1 + jp, base_lat)
        resp = post_run("test", run, nx["tweak_id"])
        run_i += 1
        if resp.get("decision"):
            profile_reasons[nx["tweak_id"]] = (test_n_cur, resp["decision"], resp["reason"])
            print(f"  test#{test_n_cur} {nx['tweak_id']}: {resp['decision']} ({resp['reason']})")
            if resp["decision"] == "kept":
                st = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]["baseline"]["stats"]
                base_fps, base_p1 = st["fps_avg"], st["fps_p1"]
                if st.get("latency_ms") is not None:
                    base_lat = st["latency_ms"]
                event("log", {"message": "sim: nuova baseline"})
            else:
                event("rolled_back", {"tweak_id": nx["tweak_id"]})
            if resp.get("completed"):
                break
    elif act == "synergy_toggle":
        event("synergy_toggled", {"stage": nx["stage"]})
    elif act == "run_synergy":
        ph = "synergy_" + nx["stage"]
        f = base_fps * (0.94 if nx["stage"] == "off" else 1.0)
        post_run(ph, mk(round(f, 1) + [-0.2, 0.2][nx.get("runs_done", 0) % 2], base_p1, base_lat))
    elif act == "run_validation":
        resp = post_run("validation", mk(base_fps, base_p1, base_lat, dur=300))
        if resp.get("completed"):
            break
    elif act == "complete":
        break

sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
assert sess["status"] == "completed", sess["status"]
rep = sess["report"]

# verifica decisioni
kinds = {n: dec for tid, (n, dec, _) in profile_reasons.items()}
assert kinds.get(1) == "kept", f"test1 (fluidity) doveva essere kept: {profile_reasons}"
assert kinds.get(2) == "rolled_back", f"test2 (stutter guard) doveva essere rollback: {profile_reasons}"
assert kinds.get(3) == "kept", f"test3 (good) doveva essere kept: {profile_reasons}"
r1 = [v for v in profile_reasons.values() if v[0] == 1][0][2]
r2 = [v for v in profile_reasons.values() if v[0] == 2][0][2]
r3 = [v for v in profile_reasons.values() if v[0] == 3][0][2]
assert "fluidita" in r1, r1
assert "peggiorata" in r2, r2
assert "input lag" in r3, r3
print("DECISIONI OK: fluidity kept | stutter guard rollback | good kept con input lag")

# verifica report: nuovi campi
steps = rep["steps"]
assert any(st.get("p1_delta_pct") is not None for st in steps), steps[0]
assert any(st.get("latency_delta_ms") is not None for st in steps), steps[0]
assert any(st.get("basis") == "fluidity" for st in steps)
assert any(st.get("basis") == "stutter_guard" for st in steps)
assert rep.get("total_latency_delta_ms") is not None and rep["total_latency_delta_ms"] < 0, rep.get("total_latency_delta_ms")
print(f"REPORT OK: gain {rep['total_gain_pct']}% | latency {rep['total_latency_delta_ms']}ms | steps con p1/lat/basis")

# ---------- INSIGHTS ----------
ins = s.get(f"{BASE}/api/lab/insights", timeout=15).json()
assert ins["has_ref"], ins
ids = [i["id"] for i in ins["items"]]
assert "bios_rebar" in ids, ids  # admin ha GPU RTX -> suggerimento rebar
print("INSIGHTS OK:", ids)

# ---------- MINI-LAB CHECK (guadagno confermato) ----------
r = s.post(f"{BASE}/api/lab/check", json={"reason": "bios_rebar"}, timeout=15)
assert r.status_code == 200, r.text
ref_fps = r.json()["session"]["check_ref"]["fps_avg"]
print("check avviato, ref:", ref_fps)
new_fps = round(ref_fps * 1.03, 1)
for _ in range(10):
    nx = nxt()
    if nx["action"] == "run_baseline":
        assert nx["runs_target"] == 2, nx
        resp = post_run("baseline", mk(new_fps + [-0.2, 0.2][nx.get("runs_done", 0) % 2], base_p1, base_lat))
        if resp.get("completed"):
            assert resp["check"]["kind"] == "check"
            assert not resp["check"]["regression"]
            break
    elif nx["action"] in ("wait", "complete"):
        break
sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
assert sess["kind"] == "check" and sess["status"] == "completed"
assert sess["report"]["total_gain_pct"] > 0
print(f"CHECK OK: {ref_fps} -> {sess['report']['final']['fps_avg']} FPS (+{sess['report']['total_gain_pct']}%), regression={sess['report']['regression']}")
# l'agent riceve il report una volta
nx = nxt()
assert nx["action"] == "complete" and nx["report"]["kind"] == "check", nx
assert nxt()["action"] == "wait"

# ---------- MINI-LAB CHECK (regressione) ----------
r = s.post(f"{BASE}/api/lab/check", json={"reason": "driver_update"}, timeout=15)
assert r.status_code == 200, r.text
low_fps = round(ref_fps * 0.90, 1)
for _ in range(10):
    nx = nxt()
    if nx["action"] == "run_baseline":
        resp = post_run("baseline", mk(low_fps + [-0.2, 0.2][nx.get("runs_done", 0) % 2], base_p1, base_lat))
        if resp.get("completed"):
            assert resp["check"]["regression"] is True, resp["check"]
            break
sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
assert sess["report"]["regression"] is True
print(f"REGRESSIONE OK: {ref_fps} -> {low_fps} FPS ({sess['report']['total_gain_pct']}%) segnalata")
nxt()  # consegna report all'agent

# ---------- HISTORY ----------
hist = s.get(f"{BASE}/api/lab/history", timeout=15).json()["sessions"]
assert len(hist) >= 3, len(hist)
assert hist[0]["kind"] == "check" and hist[0]["regression"] is True
assert hist[1]["kind"] == "check" and hist[1]["check_reason"] == "bios_rebar"
assert any(h["kind"] == "full" for h in hist)
print(f"HISTORY OK: {len(hist)} sessioni (check regressione, check rebar, full...)")

# check senza ref bloccato per utenti nuovi: reason invalida -> 422
r = s.post(f"{BASE}/api/lab/check", json={"reason": "hack"}, timeout=15)
assert r.status_code == 422, r.status_code
print("validazione reason OK (422)")

print("\nTUTTI I TEST FASE 4 PASSATI")
