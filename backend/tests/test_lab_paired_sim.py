"""Simulazione E2E dello schema APPAIATO del Laboratorio (default dalla v2).

Copre quello che lo schema a blocchi non tocca:
  - sequenza ABBA on/off/off/on/on/off con le commutazioni fra una misura e l'altra
  - decisione su t-test appaiato + intervallo di confidenza
  - istogramma dei frametime -> percentili calcolati dal backend
  - run rifiutato perche' preso in condizioni non confrontabili (PC a batteria)
  - rilevamento del frame cap sulla baseline
  - correzione Holm APPLICATA: i mantenuti che non reggono tornano indietro

Eseguire come script, con un backend vivo e un database usa-e-getta.
"""
import math
import os
import sys

import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@boostpc.io")
PWD = os.environ.get("ADMIN_PASSWORD", "")

s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PWD}, timeout=15)
assert r.status_code == 200, r.text
tk = s.get(f"{BASE}/api/agent/token", timeout=15).json()["token"]
H = {"X-Agent-Token": tk}

# Stessa suddivisione di lab_stats.HIST_BUCKETS, replicata qui perche' la
# simulazione recita la parte dell'agent, che il backend non lo importa.
HIST_BUCKETS = 306


def hist_bucket(ms):
    if ms < 20:
        return int(ms / 0.1)
    if ms < 50:
        return 200 + int((ms - 20) / 0.5)
    if ms < 100:
        return 260 + int((ms - 50) / 2.0)
    if ms < 300:
        return 285 + int((ms - 100) / 10.0)
    return 305


CTX = {"res_w": 2560, "res_h": 1440, "refresh_hz": 165, "on_battery": False,
       "power_plan": "High performance", "obs_running": False,
       "cpu_pct_avg": 55.0, "gpu_pct_avg": 96.0, "temp_gpu_avg": 68.0}


def make_run(fps, frames=12000, game="cs2.exe", slow_factor=1.6, ctx=None, capped=False):
    """Un run come lo manda l'agent: istogramma dei frametime + contesto.

    Senza `capped` i frame hanno la dispersione che hanno in un gioco vero
    (deviazione ~8% attorno alla media): se fossero tutti sullo stesso valore
    il backend li leggerebbe, a ragione, come un frame cap.
    """
    ft = 1000.0 / fps
    hist = [0] * HIST_BUCKETS
    if capped:
        # tutti i frame sullo stesso valore: e' la firma di un V-Sync
        hist[hist_bucket(ft)] += frames
        return {"fps_avg": round(fps, 2), "ft_avg_ms": round(ft, 3), "ft_cv": 0.01,
                "frames": frames, "duration_s": 90, "game": game,
                "hist": hist, "metrics_version": 2, "ctx": dict(ctx or CTX)}
    n_slow = frames // 100
    n_fast = frames - n_slow
    # dispersione deterministica e simmetrica: 21 gradini da -10% a +10%
    steps = 21
    for k in range(steps):
        off = 1.0 + 0.20 * (k / (steps - 1)) - 0.10
        share = n_fast // steps + (1 if k < n_fast % steps else 0)
        hist[hist_bucket(ft * off)] += share
    for k in range(n_slow):
        hist[hist_bucket(ft * slow_factor * (1.0 + 0.3 * (k % 5) / 4))] += 1
    return {"fps_avg": round(fps, 2), "ft_avg_ms": round(ft, 3), "ft_cv": 0.12,
            "frames": frames, "duration_s": 90, "game": game,
            "hist": hist, "metrics_version": 2, "ctx": dict(ctx or CTX)}


_wobble_i = 0


def wobble(scale=0.35):
    """Rumore deterministico ma non costante.

    Serve perche' misure identiche al centesimo sono un caso degenere: senza
    varianza il t-test non ha un errore standard da stimare e ripiega sul test
    dei segni. In un gioco vero la varianza c'e' sempre.
    """
    global _wobble_i
    _wobble_i += 1
    return scale * ((_wobble_i * 7) % 5 - 2) / 2.0


def nxt():
    return requests.get(f"{BASE}/api/agent/lab/next", headers=H, timeout=15).json()


def event(t, data=None):
    return requests.post(f"{BASE}/api/agent/lab/event", json={"type": t, "data": data},
                         headers=H, timeout=15).json()


def post_run(phase, run, tweak_id=None):
    body = {"phase": phase, "run": run}
    if tweak_id:
        body["tweak_id"] = tweak_id
    return requests.post(f"{BASE}/api/agent/lab/run", json=body, headers=H, timeout=20).json()


def cleanup():
    sess = s.get(f"{BASE}/api/lab/session", timeout=15).json()["session"]
    if sess and sess["status"] not in ("completed", "aborted"):
        s.post(f"{BASE}/api/lab/abort", timeout=15)
        event("aborted")


# ==========================================================================
# 1. Frame cap sulla baseline: il Lab deve dirlo, non misurare a vuoto
# ==========================================================================
cleanup()
r = s.post(f"{BASE}/api/lab/start",
           json={"risk_level": "safe", "run_seconds": 90, "include_reboot": False}, timeout=15)
assert r.status_code == 200, r.text
n = nxt()
assert n["action"] == "snapshot", n
event("snapshot_done", {"restore_point": True, "states": {}})
for _ in range(3):
    resp = post_run("baseline", make_run(60.0, capped=True))
assert resp.get("baseline_ok"), resp
assert resp["quality"]["capped"] is True, resp["quality"]
assert 59 <= resp["quality"]["cap_fps"] <= 61, resp["quality"]
print(f"frame cap rilevato a {resp['quality']['cap_fps']} FPS OK")
cleanup()

# ==========================================================================
# 2. Sessione appaiata completa
# ==========================================================================
r = s.post(f"{BASE}/api/lab/start",
           json={"risk_level": "medium", "run_seconds": 90, "include_reboot": False}, timeout=15)
assert r.status_code == 200, r.text
sess = r.json()["session"]
assert sess["paired"] is True, sess.get("paired")
print("sessione appaiata creata, candidati:", len(sess["candidates"]))

n = nxt()
assert n["action"] == "snapshot", n
event("snapshot_done", {"restore_point": True, "states": {c: "Da ottimizzare" for c in n["candidate_ids"]}})

# --- baseline con deriva termica: il PC si scalda run dopo run ---
BASE_FPS = 200.0
for i in range(3):
    resp = post_run("baseline", make_run(BASE_FPS - i * 1.5))
assert resp.get("baseline_ok"), resp
assert resp["stats"]["metrics_version"] == 2, resp["stats"]
assert resp["stats"]["fps_p1"] < resp["stats"]["fps_avg"], resp["stats"]
assert resp["quality"]["capped"] is False, resp["quality"]
print("baseline OK:", resp["stats"]["fps_avg"], "FPS avg | 1% low", resp["stats"]["fps_p1"],
      "| frame", resp["stats"]["frames"])

# --- run rifiutato: stesso identico run ma a batteria ---
n = nxt()
assert n["action"] == "apply_tweak", n
first_tweak = n["tweak_id"]
assert n["paired"] is True, n
event("tweak_applied", {"tweak_id": first_tweak, "requires_reboot": False})
n = nxt()
assert n["action"] == "run_pair" and n["stage"] == "on", n   # dopo apply si e' gia' ON
batt = dict(CTX, on_battery=True)
resp = post_run("pair_on", make_run(150.0, ctx=batt), first_tweak)
assert resp.get("rejected"), resp
assert "batteria" in resp["reason"], resp
print("run a batteria rifiutato OK:", resp["reason"])

# --- sequenza ABBA del primo tweak: effetto reale +6%, su deriva discendente ---
EFFECT = 1.06
drift = [0.0, -1.0, -2.0, -3.0, -4.0, -5.0]   # comune ai due lati di ogni coppia
stages_seen = []
step = 0
while True:
    n = nxt()
    if n["action"] == "pair_toggle":
        assert n["tweak_id"] == first_tweak, n
        event("pair_toggled", {"tweak_id": n["tweak_id"], "stage": n["stage"],
                               "final": bool(n.get("final"))})
        continue
    if n["action"] != "run_pair":
        break
    stage = n["stage"]
    stages_seen.append(stage)
    fps = BASE_FPS + drift[step]
    if stage == "on":
        fps *= EFFECT
    step += 1
    resp = post_run("pair_on" if stage == "on" else "pair_off", make_run(fps), first_tweak)
    assert not resp.get("rejected"), resp
    if resp.get("decision"):
        break

assert stages_seen == ["on", "off", "off", "on", "on", "off"], stages_seen
assert resp["design"] == "paired_abba", resp
assert resp["n_pairs"] == 3, resp
assert resp["decision"] == "kept", resp
assert resp["significance"]["method"] == "paired_t_test", resp
lo, hi = resp["delta"]["fps_ci_pct"]
assert lo > 0, f"l'intervallo deve escludere lo zero: {lo}..{hi}"
assert 5.0 < resp["delta"]["fps_avg_pct"] < 7.0, resp["delta"]
print(f"ABBA OK: {stages_seen} -> {resp['decision']} "
      f"({resp['delta']['fps_avg_pct']}%, IC {lo}..{hi}%) {resp['reason'][:70]}")

# l'ultima misura era OFF: un tweak promosso va riacceso prima di proseguire
n = nxt()
assert n["action"] == "pair_toggle" and n["stage"] == "on" and n["final"], n
event("pair_toggled", {"tweak_id": n["tweak_id"], "stage": "on", "final": True})
print("riaccensione finale del tweak promosso OK")

# ==========================================================================
# 3. Il resto della coda non fa nulla -> auto-stop, poi Holm
# ==========================================================================
kept_before = None
report = None
guard = 0
while report is None and guard < 400:
    guard += 1
    n = nxt()
    act = n["action"]
    if act in ("wait", "transition"):
        continue
    if act == "apply_tweak":
        event("tweak_applied", {"tweak_id": n["tweak_id"], "requires_reboot": False})
    elif act == "pair_toggle":
        event("pair_toggled", {"tweak_id": n["tweak_id"], "stage": n["stage"],
                               "final": bool(n.get("final"))})
    elif act == "run_pair":
        # nessun effetto: ON e OFF si equivalgono, con un filo di rumore
        resp = post_run("pair_on" if n["stage"] == "on" else "pair_off",
                        make_run(BASE_FPS + wobble()), n["tweak_id"])
        if resp.get("decision"):
            assert resp["decision"] == "rolled_back", resp
    elif act == "run_test":
        resp = post_run("test", make_run(BASE_FPS), n["tweak_id"])
    elif act == "run_recheck":
        post_run("recheck", make_run(BASE_FPS))
    elif act == "rollback_tweaks":
        kept_before = list(n["tweak_ids"])
        print("Holm chiede il rollback di:", kept_before, "-", n["reason"])
        event("tweaks_rolled_back", {"tweak_ids": kept_before})
    elif act == "run_synergy":
        post_run("synergy_" + n["stage"], make_run(BASE_FPS * EFFECT))
    elif act == "synergy_toggle":
        event("synergy_toggled", {"stage": n["stage"]})
    elif act == "run_validation":
        resp = post_run("validation", make_run(BASE_FPS * EFFECT, frames=40000))
        assert resp.get("completed"), resp
        report = resp["report"]
    elif act == "complete":
        report = n["report"]
    else:
        print("azione inattesa:", n)
        sys.exit(1)

assert report is not None, "la sessione non si e' chiusa"
assert report["design"] == "paired_abba", report["design"]
assert report["metrics_version"] == 2, report
assert report["quality"]["capped"] is False, report["quality"]
mt = report["multiple_testing"]
assert mt["applied"] is True, mt
assert mt["hypotheses"] >= 2, mt
# il guadagno finale viene dalla misura di validazione, non dalla stima accumulata
assert report["final"]["source"] == "validazione", report["final"]
assert report["final"]["fps_p1"], report["final"]
paired_steps = [st for st in report["steps"] if st["design"] == "paired_abba"]
assert paired_steps and all(st["n_pairs"] == 3 for st in paired_steps), paired_steps
kept_steps = [st for st in report["steps"] if st["decision"] == "kept"]
assert all(st["holm_ok"] for st in kept_steps), kept_steps
print("report:", report["total_gain_pct"], "% |", len(report["steps"]), "tweak testati |",
      "kept:", report["kept"], "| demoti:", mt["demoted"])

# ==========================================================================
# 4. L'aggregato di flotta conserva la dispersione, non solo la media
# ==========================================================================
fv = s.get(f"{BASE}/api/lab/fleet-validation", timeout=15).json()
items = [i for i in fv["items"] if i["tested"] > 0]
assert items, fv
it = items[0]
assert "success_ci_pct" in it and it["success_ci_pct"][0] <= it["success_pct"] <= it["success_ci_pct"][1], it
assert "delta_sd_pct" in it, it
assert it["thin"] in (True, False), it
print("fleet-validation OK:", it["tweak_id"], it["success_pct"], "% IC", it["success_ci_pct"],
      "| sd", it["delta_sd_pct"])


# ==========================================================================
# 5. Holm applicato: un tweak tenuto al limite deve tornare indietro
# ==========================================================================
# Effetto +2% ma con coppie poco concordi: p ~ 0.04, sopra la soglia del
# singolo test, sotto quella corretta per il numero di test fatti. Prima
# Holm compariva solo come annotazione nel report e il tweak restava applicato.
cleanup()
r = s.post(f"{BASE}/api/lab/start",
           json={"risk_level": "medium", "run_seconds": 90, "include_reboot": False}, timeout=15)
assert r.status_code == 200, r.text
n = nxt()
assert n["action"] == "snapshot", n
event("snapshot_done", {"restore_point": True, "states": {}})

B2 = 100.0
for _ in range(3):
    resp = post_run("baseline", make_run(B2))
assert resp.get("baseline_ok"), resp

DIFFS = [1.3, 2.0, 2.7]          # media +2%, coppie discordi -> p ~ 0.04
marginal = None
pair_idx = 0
rolled_back_ids = None
report2 = None
guard = 0
while report2 is None and guard < 400:
    guard += 1
    n = nxt()
    act = n["action"]
    if act in ("wait", "transition"):
        continue
    if act == "apply_tweak":
        if marginal is None:
            marginal = n["tweak_id"]
        event("tweak_applied", {"tweak_id": n["tweak_id"], "requires_reboot": False})
    elif act == "pair_toggle":
        event("pair_toggled", {"tweak_id": n["tweak_id"], "stage": n["stage"],
                               "final": bool(n.get("final"))})
    elif act == "run_pair":
        if n["tweak_id"] == marginal:
            d = DIFFS[min(pair_idx, len(DIFFS) - 1)]
            fps = B2 + (d if n["stage"] == "on" else 0.0) + wobble(0.05)
            if n["stage"] == "off":
                pair_idx += 1
        else:
            fps = B2 + wobble()
        resp = post_run("pair_on" if n["stage"] == "on" else "pair_off",
                        make_run(fps), n["tweak_id"])
        if resp.get("decision") and n["tweak_id"] == marginal:
            assert resp["decision"] == "kept", resp
            assert 0.01 < resp["significance"]["p_value"] < 0.10, resp["significance"]
            print(f"{marginal}: tenuto al singolo test (p={resp['significance']['p_value']})")
    elif act == "run_recheck":
        post_run("recheck", make_run(B2))
    elif act == "rollback_tweaks":
        rolled_back_ids = list(n["tweak_ids"])
        event("tweaks_rolled_back", {"tweak_ids": rolled_back_ids})
    elif act == "synergy_toggle":
        event("synergy_toggled", {"stage": n["stage"]})
    elif act == "run_synergy":
        post_run("synergy_" + n["stage"], make_run(B2))
    elif act == "run_validation":
        resp = post_run("validation", make_run(B2, frames=40000))
        report2 = resp["report"]
    elif act == "complete":
        report2 = n["report"]
    else:
        print("azione inattesa:", n)
        sys.exit(1)

assert rolled_back_ids == [marginal], (rolled_back_ids, marginal)
assert report2["multiple_testing"]["demoted"] == [marginal], report2["multiple_testing"]
assert marginal not in report2["kept"], report2["kept"]
step = next(st for st in report2["steps"] if st["tweak_id"] == marginal)
assert step["decision"] == "rolled_back" and step["demoted"] is True, step
assert step["p_adj"] >= 0.10 > step["p_value"], step
print(f"Holm APPLICATO: {marginal} p={step['p_value']} -> p corretto {step['p_adj']} -> annullato OK")

cleanup()
print("\nTUTTI I TEST DELLO SCHEMA APPAIATO PASSATI")
