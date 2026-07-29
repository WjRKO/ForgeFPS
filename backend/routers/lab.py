"""Laboratorio Automatico delle Prestazioni - Fase 1.

Backend orchestrator: il PS agent (mode=lab) fa polling di /api/agent/lab/next
ed esegue le azioni; il backend persiste lo stato, calcola CV/delta/Welch e
decide kept/rolled_back, auto-stop e report finale.
Pipeline Fase 1: SNAPSHOT -> BASELINE (3 run, CV check) -> TEST_LOOP -> REPORT.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header

from database import db, now_iso
from models import LabStartInput, LabRunInput, LabEventInput
from lab_registry import REGISTRY_VERSION, TWEAKS, select_candidates
from lab_stats import mean, cv, significance

BASELINE_RUNS = 3
TEST_RUNS = 3
CV_MAX = 0.05
MIN_EFFECT_PCT = 1.0
AUTO_STOP_WINDOW = 3
MARGINAL_GAIN_RATIO = 0.03

ACTIVE_STATUSES = ("waiting_agent", "snapshot", "baseline", "testing", "aborting")


def _log(sess, msg, level="info"):
    sess.setdefault("logs", []).append({"ts": now_iso(), "msg": msg, "level": level})
    sess["logs"] = sess["logs"][-120:]


def _fps_list(runs, key="fps_avg"):
    return [r.get(key) for r in runs if isinstance(r.get(key), (int, float))]


def _run_stats(runs):
    fps = _fps_list(runs)
    p1 = _fps_list(runs, "fps_p1")
    return {
        "fps_avg": round(mean(fps), 2) if fps else None,
        "fps_p1": round(mean(p1), 2) if p1 else None,
        "cv_pct": round(cv(fps) * 100, 2) if fps else None,
        "runs": len(runs),
        "game": (runs[-1].get("game") if runs else None),
    }


def _delta_pct(a, b):
    if not a or not b or b == 0:
        return None
    return round((a - b) / b * 100, 2)


def _adapt_priors(sess, family, kept):
    """Se un tweak di una famiglia funziona, alza il prior dei fratelli in coda; se fallisce, abbassalo."""
    bump = 0.08 if kept else -0.05
    queued = set(sess.get("queue", []))
    for c in sess.get("candidates", []):
        if c["tweak_id"] in queued and c.get("family") == family:
            c["prior"] = round(max(0.01, c["prior"] + bump), 3)
    order = {c["tweak_id"]: c["prior"] for c in sess.get("candidates", [])}
    sess["queue"] = sorted(sess.get("queue", []), key=lambda tid: -order.get(tid, 0))


def _auto_stop(sess):
    results = sess.get("results", [])
    if len(results) < AUTO_STOP_WINDOW:
        return None
    recent = results[-AUTO_STOP_WINDOW:]
    if all(not r["significance"]["significant"] for r in recent):
        return f"auto-stop: ultimi {AUTO_STOP_WINDOW} test non significativi"
    total_gain = sum(r["delta"].get("fps_avg_pct") or 0 for r in results if r["decision"] == "kept")
    recent_gain = sum(r["delta"].get("fps_avg_pct") or 0 for r in recent if r["decision"] == "kept")
    if total_gain > 0 and recent_gain / total_gain < MARGINAL_GAIN_RATIO:
        return "auto-stop: rendimenti marginali (<3% del guadagno totale)"
    return None


def _clamp(v, lo=0.0, hi=10.0):
    return round(max(lo, min(hi, v)), 1)


def _build_report(sess):
    base0 = sess.get("baseline0") or {}
    final = sess.get("baseline", {}).get("stats") or base0
    gain = _delta_pct(final.get("fps_avg"), base0.get("fps_avg"))
    gain_p1 = _delta_pct(final.get("fps_p1"), base0.get("fps_p1"))
    steps = []
    names = {t["tweak_id"]: t["name"] for t in TWEAKS}
    for r in sess.get("results", []):
        steps.append({
            "tweak_id": r["tweak_id"],
            "tweak": names.get(r["tweak_id"], r["tweak_id"]),
            "before": r.get("before_fps"),
            "after": r.get("after_fps"),
            "delta_pct": r["delta"].get("fps_avg_pct"),
            "decision": r["decision"],
            "reason": r.get("reason"),
            "p_value": r["significance"].get("p_value"),
        })
    n_rb = sum(1 for s in steps if s["decision"] == "rolled_back")
    try:
        from datetime import datetime
        t0 = datetime.fromisoformat(sess["started_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(now_iso().replace("Z", "+00:00"))
        dur = round((t1 - t0).total_seconds() / 60, 1)
    except Exception:
        dur = None
    perf = _clamp(5 + (gain or 0) / 2)
    fluid = _clamp(5 + (gain_p1 or 0) / 2)
    stab = _clamp(10 - (base0.get("cv_pct") or 0))
    return {
        "lab_session_id": sess["session_id"],
        "game": final.get("game") or base0.get("game"),
        "baseline": {"fps_avg": base0.get("fps_avg"), "fps_p1": base0.get("fps_p1")},
        "final": {"fps_avg": final.get("fps_avg"), "fps_p1": final.get("fps_p1")},
        "total_gain_pct": gain,
        "total_p1_gain_pct": gain_p1,
        "steps": steps,
        "kept": sess.get("kept", []),
        "synergies_found": [],
        "reboots_required": 0,
        "manual_steps_required": [],
        "total_duration_min": dur,
        "performance_index": {
            "prestazioni": perf, "fluidita": fluid, "stabilita": stab,
            "voto_finale": _clamp((perf + fluid + stab) / 3),
        },
        "tweaks_tested": len(steps),
        "auto_stop_reason": sess.get("auto_stop_reason"),
    }


def _complete(sess, reason=None):
    if reason:
        sess["auto_stop_reason"] = reason
        _log(sess, reason, "warn")
    sess["status"] = "completed"
    sess["finished_at"] = now_iso()
    sess["report"] = _build_report(sess)
    _log(sess, "Laboratorio completato: report generato", "ok")


async def _save(sess):
    sess["updated_at"] = now_iso()
    await db.lab_sessions.replace_one({"session_id": sess["session_id"]}, sess, upsert=True)


def _public(sess):
    if not sess:
        return None
    out = {k: v for k, v in sess.items() if k != "_id"}
    return out


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["lab"])

    async def _agent_uid(x_agent_token: str) -> str:
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="token agent non valido")
        return rec["user_id"]

    async def _active(uid: str):
        return await db.lab_sessions.find_one(
            {"user_id": uid, "status": {"$in": list(ACTIVE_STATUSES)}}, sort=[("started_at", -1)])

    # ---------- user endpoints ----------
    @r.post("/lab/start")
    async def lab_start(payload: LabStartInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        if await _active(uid):
            raise HTTPException(status_code=409, detail="Hai gia' una sessione Lab attiva. Interrompila prima di avviarne una nuova.")
        specs = await db.pc_specs.find_one({"user_id": uid}) or {}
        candidates, skipped = select_candidates(specs.get("data") or {}, payload.risk_level)
        if not candidates:
            raise HTTPException(status_code=400, detail="Nessun tweak candidato per questo livello di rischio/hardware.")
        sess = {
            "session_id": str(uuid.uuid4()),
            "user_id": uid,
            "risk_level": payload.risk_level,
            "run_seconds": payload.run_seconds,
            "registry_version": REGISTRY_VERSION,
            "status": "waiting_agent",
            "candidates": candidates,
            "queue": [c["tweak_id"] for c in candidates],
            "skipped": skipped,
            "current": None,
            "baseline": {"runs": [], "stats": None},
            "baseline0": None,
            "results": [],
            "kept": [],
            "snapshot": None,
            "logs": [],
            "report": None,
            "started_at": now_iso(),
            "finished_at": None,
        }
        _log(sess, f"Sessione creata: {len(candidates)} tweak candidati (rischio {payload.risk_level}, finestre {payload.run_seconds}s)")
        _log(sess, "In attesa dell'agent: esegui il comando Lab in PowerShell come Amministratore")
        await _save(sess)
        return {"session": _public(sess)}

    @r.get("/lab/session")
    async def lab_session(user: dict = Depends(get_current_user)):
        sess = await db.lab_sessions.find_one({"user_id": str(user["_id"])}, sort=[("started_at", -1)])
        return {"session": _public(sess)}

    @r.post("/lab/abort")
    async def lab_abort(user: dict = Depends(get_current_user)):
        sess = await _active(str(user["_id"]))
        if not sess:
            raise HTTPException(status_code=404, detail="Nessuna sessione Lab attiva")
        if sess["status"] == "waiting_agent":
            sess["status"] = "aborted"
            sess["finished_at"] = now_iso()
            _log(sess, "Sessione annullata (agent mai collegato)", "warn")
        else:
            sess["status"] = "aborting"
            _log(sess, "Interruzione richiesta: l'agent annullera' tutti i tweak applicati", "warn")
        await _save(sess)
        return {"session": _public(sess)}

    @r.get("/lab/registry")
    async def lab_registry(risk_level: str = "medium", user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}) or {}
        candidates, skipped = select_candidates(specs.get("data") or {}, risk_level)
        return {"registry_version": REGISTRY_VERSION, "candidates": candidates, "skipped": skipped}

    # ---------- agent endpoints ----------
    @r.get("/agent/lab/next")
    async def lab_next(x_agent_token: str = Header(default="")):
        uid = await _agent_uid(x_agent_token)
        sess = await _active(uid)
        if not sess:
            # sessione appena completata: consegna il report all'agent una sola volta
            last = await db.lab_sessions.find_one({"user_id": uid, "status": "completed"}, sort=[("started_at", -1)])
            if last and not last.get("agent_ack"):
                await db.lab_sessions.update_one({"session_id": last["session_id"]}, {"$set": {"agent_ack": True}})
                return {"action": "complete", "report": last.get("report")}
            return {"action": "wait"}
        st = sess["status"]
        rs = sess["run_seconds"]
        if st == "waiting_agent":
            sess["status"] = "snapshot"
            _log(sess, "Agent collegato: avvio fase SNAPSHOT")
            await _save(sess)
            st = "snapshot"
        if st == "snapshot":
            return {"action": "snapshot", "session_id": sess["session_id"],
                    "candidate_ids": [c["tweak_id"] for c in sess["candidates"]]}
        if st == "baseline":
            done = len(sess["baseline"]["runs"])
            target = BASELINE_RUNS if done < BASELINE_RUNS else BASELINE_RUNS + 1
            return {"action": "run_baseline", "run_seconds": rs, "runs_done": done, "runs_target": target}
        if st == "aborting":
            ids = list(sess.get("kept", []))
            cur = sess.get("current")
            if cur and cur.get("applied") and cur["tweak_id"] not in ids:
                ids.append(cur["tweak_id"])
            return {"action": "abort", "rollback_ids": ids}
        if st == "testing":
            cur = sess.get("current")
            total = len(sess["candidates"])
            step = len(sess.get("results", [])) + len(sess.get("skipped_runtime", [])) + 1
            if not cur:
                queue = sess.get("queue", [])
                if not queue:
                    _complete(sess)
                    sess["agent_ack"] = True
                    await _save(sess)
                    return {"action": "complete", "report": sess["report"]}
                tid = queue.pop(0)
                sess["queue"] = queue
                sess["current"] = {"tweak_id": tid, "applied": False, "runs": []}
                await _save(sess)
                cur = sess["current"]
            tweak = next((c for c in sess["candidates"] if c["tweak_id"] == cur["tweak_id"]), {"tweak_id": cur["tweak_id"]})
            if not cur.get("applied"):
                return {"action": "apply_tweak", "tweak_id": cur["tweak_id"], "tweak": tweak,
                        "step": step, "total": total}
            return {"action": "run_test", "tweak_id": cur["tweak_id"], "run_seconds": rs,
                    "runs_done": len(cur["runs"]), "runs_target": TEST_RUNS, "step": step, "total": total}
        return {"action": "wait"}

    @r.post("/agent/lab/event")
    async def lab_event(payload: LabEventInput, x_agent_token: str = Header(default="")):
        uid = await _agent_uid(x_agent_token)
        sess = await _active(uid)
        if not sess:
            return {"ok": False}
        data = payload.data or {}
        t = payload.type
        if t == "snapshot_done":
            sess["snapshot"] = {"restore_point": bool(data.get("restore_point")),
                                "states": data.get("states") or {}, "created_at": now_iso()}
            sess["status"] = "baseline"
            rp = "creato" if data.get("restore_point") else "NON creato (limite Windows 24h) - backup mirato comunque attivo"
            _log(sess, f"Snapshot completato. Punto di ripristino: {rp}", "ok")
            _log(sess, f"Fase BASELINE: {BASELINE_RUNS} run da {sess['run_seconds']}s. Avvia il gioco!")
        elif t == "tweak_applied":
            cur = sess.get("current")
            if cur and cur["tweak_id"] == data.get("tweak_id"):
                cur["applied"] = True
            _log(sess, f"Tweak applicato: {data.get('tweak_id')} (backup creato)")
        elif t == "tweak_skip":
            sess.setdefault("skipped_runtime", []).append(
                {"tweak_id": data.get("tweak_id"), "reason": data.get("reason", "n/d")})
            sess["current"] = None
            _log(sess, f"Tweak saltato: {data.get('tweak_id')} ({data.get('reason', 'n/d')})", "warn")
        elif t == "rolled_back":
            _log(sess, f"Rollback eseguito: {data.get('tweak_id')}", "warn")
        elif t == "aborted":
            sess["status"] = "aborted"
            sess["finished_at"] = now_iso()
            _log(sess, "Sessione interrotta: tutti i tweak del Lab sono stati annullati", "warn")
        elif t == "waiting_game":
            _log(sess, "Agent in attesa del gioco: avvia il gioco e resta in partita")
        elif t == "game_detected":
            _log(sess, f"Gioco rilevato: {data.get('game', 'n/d')}", "ok")
        elif t == "log":
            _log(sess, str(data.get("message", ""))[:300])
        await _save(sess)
        return {"ok": True, "status": sess["status"]}

    @r.post("/agent/lab/run")
    async def lab_run(payload: LabRunInput, x_agent_token: str = Header(default="")):
        uid = await _agent_uid(x_agent_token)
        sess = await _active(uid)
        if not sess:
            raise HTTPException(status_code=404, detail="nessuna sessione attiva")
        run = {k: v for k, v in payload.run.items() if isinstance(v, (int, float, str))}
        run["at"] = now_iso()

        if payload.phase == "baseline":
            if sess["status"] != "baseline":
                return {"ok": False, "reason": f"stato {sess['status']}"}
            sess["baseline"]["runs"].append(run)
            runs = sess["baseline"]["runs"]
            _log(sess, f"Baseline run {len(runs)}: {run.get('fps_avg')} FPS avg | 1% low {run.get('fps_p1')}")
            if len(runs) < BASELINE_RUNS:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": len(runs)}
            fps = _fps_list(runs)
            c = cv(fps)
            if c > CV_MAX and len(runs) == BASELINE_RUNS:
                _log(sess, f"CV baseline {c*100:.1f}% > 5%: richiedo un 4o run e scarto l'outlier", "warn")
                await _save(sess)
                return {"ok": True, "need_more": True, "extra_run": True, "runs_done": len(runs)}
            if len(runs) > BASELINE_RUNS:
                med = sorted(fps)[len(fps) // 2]
                out_i = max(range(len(runs)), key=lambda i: abs((runs[i].get("fps_avg") or med) - med))
                dropped = runs.pop(out_i)
                _log(sess, f"Outlier scartato: run da {dropped.get('fps_avg')} FPS", "warn")
            stats = _run_stats(sess["baseline"]["runs"])
            sess["baseline"]["stats"] = stats
            sess["baseline0"] = dict(stats)
            sess["status"] = "testing"
            _log(sess, f"BASELINE stabile: {stats['fps_avg']} FPS avg | 1% low {stats['fps_p1']} | CV {stats['cv_pct']}%", "ok")
            _log(sess, f"Fase TEST: {len(sess['queue'])} tweak in coda, uno alla volta")
            await _save(sess)
            return {"ok": True, "baseline_ok": True, "stats": stats}

        # phase == test
        cur = sess.get("current")
        if sess["status"] != "testing" or not cur or cur["tweak_id"] != payload.tweak_id:
            return {"ok": False, "reason": "nessun test attivo per questo tweak"}
        cur["runs"].append(run)
        _log(sess, f"Test {cur['tweak_id']} run {len(cur['runs'])}: {run.get('fps_avg')} FPS avg")
        if len(cur["runs"]) < TEST_RUNS:
            await _save(sess)
            return {"ok": True, "need_more": True, "runs_done": len(cur["runs"])}

        base_runs = sess["baseline"]["stats"]
        base_fps = _fps_list(sess["baseline"]["runs"])
        test_fps = _fps_list(cur["runs"])
        test_stats = _run_stats(cur["runs"])
        sig = significance(test_fps, base_fps)
        delta = {
            "fps_avg_pct": _delta_pct(test_stats["fps_avg"], base_runs["fps_avg"]),
            "fps_p1_pct": _delta_pct(test_stats["fps_p1"], base_runs["fps_p1"]),
        }
        d = delta["fps_avg_pct"] or 0
        improvement = d >= MIN_EFFECT_PCT
        kept = bool(sig["significant"] and improvement)
        if kept:
            reason = f"significativo (p={sig['p_value']}), +{d}% FPS"
        elif not sig["significant"]:
            reason = f"non significativo (p={sig['p_value']})"
        elif d < 0:
            reason = f"peggioramento ({d}%)"
        else:
            reason = f"delta trascurabile (+{d}% < {MIN_EFFECT_PCT}%)"
        tweak_meta = next((c for c in sess["candidates"] if c["tweak_id"] == cur["tweak_id"]), {})
        result = {
            "test_id": str(uuid.uuid4()),
            "tweak_id": cur["tweak_id"],
            "family": tweak_meta.get("family"),
            "runs": cur["runs"],
            "before_fps": base_runs["fps_avg"],
            "after_fps": test_stats["fps_avg"],
            "delta": delta,
            "significance": {"method": sig["method"], "p_value": sig["p_value"],
                             "alpha": sig["alpha"], "significant": sig["significant"]},
            "decision": "kept" if kept else "rolled_back",
            "reason": reason,
            "at": now_iso(),
        }
        sess["results"].append(result)
        if kept:
            sess["kept"].append(cur["tweak_id"])
            sess["baseline"]["stats"] = test_stats
            _log(sess, f"MANTENUTO {cur['tweak_id']}: {reason}. Nuova baseline: {test_stats['fps_avg']} FPS", "ok")
        else:
            _log(sess, f"ROLLBACK {cur['tweak_id']}: {reason}", "warn")
        _adapt_priors(sess, tweak_meta.get("family"), kept)
        sess["current"] = None
        stop_reason = _auto_stop(sess)
        completed = False
        if stop_reason or not sess.get("queue"):
            _complete(sess, stop_reason)
            completed = True
        await _save(sess)
        return {"ok": True, "decision": result["decision"], "reason": reason,
                "delta": delta, "significance": result["significance"],
                "completed": completed, "remaining": len(sess.get("queue", []))}

    return r
