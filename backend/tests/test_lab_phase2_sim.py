"""Simulazione E2E agent del Laboratorio FASE 2: reboot-resume, warmup, synergy pass, validazione."""
import os
import random
import sys
import requests

BASE = "http://localhost:8001"
EMAIL = os.environ.get("ADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"))
PWD = os.environ.get("ADMIN_PASSWORD", "")

s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PWD}, timeout=15)
assert r.status_code == 200, r.text
tk = s.get(f"{BASE}/api/agent/token", timeout=15).json()["token"]
H = {"X-Agent-Token": tk}

sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
if sess and sess["status"] not in ("completed", "aborted"):
    s.post(f"{BASE}/api/lab/abort", timeout=15)
    requests.post(f"{BASE}/api/agent/lab/event", json={"type": "aborted"}, headers=H, timeout=15)

# registry: con e senza reboot
reg = s.get(f"{BASE}/api/lab/registry?risk_level=medium&include_reboot=true", timeout=15).json()
ids = [c["tweak_id"] for c in reg["candidates"]]
reboot_ids = [c["tweak_id"] for c in reg["candidates"] if c.get("requires_reboot")]
assert "mpo" in ids and "gpu_msi" in ids and "timer" in ids, ids
assert ids[-3:] == reboot_ids, f"i reboot devono stare in coda: {ids}"
reg2 = s.get(f"{BASE}/api/lab/registry?risk_level=medium&include_reboot=false", timeout=15).json()
assert not any(c.get("requires_reboot") for c in reg2["candidates"])
print(f"registry OK: {len(ids)} candidati, reboot in coda {reboot_ids}; senza reboot: {len(reg2['candidates'])}")

r = s.post(f"{BASE}/api/lab/start", json={"risk_level": "medium", "run_seconds": 90, "include_reboot": True}, timeout=15)
assert r.status_code == 200, r.text
print("sessione creata, candidati:", len(r.json()["session"]["candidates"]))

def nxt():
    return requests.get(f"{BASE}/api/agent/lab/next", headers=H, timeout=15).json()

def event(t, data=None):
    return requests.post(f"{BASE}/api/agent/lab/event", json={"type": t, "data": data}, headers=H, timeout=15).json()

def post_run(phase, tweak_id, fps, dur=90):
    run = {"fps_avg": round(fps, 2), "fps_p1": round(fps * 0.82, 2), "fps_p01": round(fps * 0.7, 2),
           "ft_avg_ms": round(1000 / fps, 3), "ft_var": 1.5, "frames": 15000, "duration_s": dur, "game": "cs2.exe"}
    body = {"phase": phase, "run": run}
    if tweak_id:
        body["tweak_id"] = tweak_id
    return requests.post(f"{BASE}/api/agent/lab/run", json=body, headers=H, timeout=15).json()

# snapshot + baseline pulita (CV basso)
n = nxt(); assert n["action"] == "snapshot", n
event("snapshot_done", {"restore_point": True, "states": {}})
random.seed(3)
cur_fps = 200.0
for _ in range(3):
    resp = post_run("baseline", None, cur_fps + random.uniform(-0.6, 0.6))
assert resp.get("baseline_ok"), resp
print("baseline OK:", resp["stats"])

# piano: power kept (+8%), priority kept (+4%), tutti gli altri no-reboot nulli;
# mpo (reboot) kept (+3%) per testare reboot-resume + warmup
KEPT_GAIN = {"power": 1.08, "priority": 1.04, "mpo": 1.03}
tested, rebooted, warmups = [], [], 0
seen_reboot_required = False
guard = 0
while True:
    guard += 1
    assert guard < 300, "loop infinito"
    n = nxt()
    a = n["action"]
    if a == "complete":
        report = n["report"]
        print("COMPLETE (via next)")
        break
    if a in ("wait", "transition"):
        # transizione interna (es. verso synergy) — ripolla
        continue
    if a == "apply_tweak":
        tested.append(n["tweak_id"])
        event("tweak_applied", {"tweak_id": n["tweak_id"], "requires_reboot": n.get("requires_reboot", False)})
        continue
    if a == "reboot_required":
        seen_reboot_required = True
        assert n["applied_at"], n
        rebooted.append(n["tweak_id"])
        event("reboot_done", {"tweak_id": n["tweak_id"]})
        print(f"  reboot-resume simulato per {n['tweak_id']}")
        continue
    if a == "run_warmup":
        warmups += 1
        resp = post_run("warmup", n["tweak_id"], cur_fps * 1.01, dur=45)
        assert resp.get("warmup_done"), resp
        continue
    if a == "run_test":
        tid = n["tweak_id"]
        mult = KEPT_GAIN.get(tid)
        f = cur_fps * mult + random.uniform(-0.5, 0.5) if mult else cur_fps + random.uniform(-0.5, 0.5)
        resp = post_run("test", tid, f)
        if resp.get("decision"):
            print(f"  {tid}: {resp['decision']} ({resp['reason']}) -> next_status={resp.get('next_status')}")
            if resp["decision"] == "kept":
                cur_fps = cur_fps * mult
            else:
                event("rolled_back", {"tweak_id": tid})
        continue
    if a == "synergy_toggle":
        event("synergy_toggled", {"stage": n["stage"]})
        continue
    if a == "run_synergy":
        pair = n["pair"]
        # off: togli i gain della coppia; on: fps corrente (leggera sinergia extra su power+priority)
        base_wo = cur_fps
        for t in pair:
            base_wo /= KEPT_GAIN.get(t, 1.0)
        f = base_wo if n["stage"] == "off" else cur_fps * 1.02
        resp = post_run(f"synergy_{n['stage']}", None, f + random.uniform(-0.4, 0.4))
        if resp.get("pair_done"):
            print(f"  synergy {pair}: combined={resp['synergy']['combined_delta_pct']}% sum={resp['synergy']['individual_sum_pct']}% is_synergy={resp['synergy']['is_synergy']} -> {resp['next_status']}")
        continue
    if a == "run_validation":
        assert n["run_seconds"] == 300
        resp = post_run("validation", None, cur_fps * 0.99, dur=300)
        assert resp.get("completed"), resp
        report = resp["report"]
        print("VALIDAZIONE ok:", resp["validation"])
        break
    if a == "run_recheck":
        post_run("recheck", None, cur_fps + random.uniform(-0.5, 0.5))
        continue
    print("azione inattesa:", n)
    sys.exit(1)

assert seen_reboot_required, "reboot_required mai visto"
assert warmups >= 1, "warmup mai eseguito"
assert report["reboots_required"] >= 1, report["reboots_required"]
assert report["validation"] and report["validation"]["real_gain_pct"] is not None
assert isinstance(report["synergies_found"], list) and len(report["synergies_found"]) >= 1
print("\nreport: gain", report["total_gain_pct"], "% | kept", report["kept"], "| reboots", report["reboots_required"])
print("synergies:", [(x["pair"], x["is_synergy"]) for x in report["synergies_found"]])
print("validation:", report["validation"]["real_gain_pct"], "% vs", report["validation"]["predicted_gain_pct"], "% | discrepancy:", report["validation"]["discrepancy"])

# next dopo il complete: l'agent deve ricevere il report una volta sola? gia' ack via run -> wait
n = nxt()
assert n["action"] == "wait", n
print("post-complete next -> wait OK (agent_ack)")
print("\nTUTTI I TEST FASE 2 PASSATI")
