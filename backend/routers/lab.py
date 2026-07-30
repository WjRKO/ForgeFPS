"""Laboratorio Automatico delle Prestazioni - Fase 1.

Backend orchestrator: il PS agent (mode=lab) fa polling di /api/agent/lab/next
ed esegue le azioni; il backend persiste lo stato, calcola CV/delta/Welch e
decide kept/rolled_back, auto-stop e report finale.
Pipeline Fase 1: SNAPSHOT -> BASELINE (3 run, CV check) -> TEST_LOOP -> REPORT.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header

from database import db, now_iso
from models import LabStartInput, LabRunInput, LabEventInput, LabCheckInput
from lab_registry import REGISTRY_VERSION, TWEAKS, select_candidates, bios_suggestions
from lab_stats import mean, cv, significance, welch_ci, cohens_d, holm_adjust

FLEET_MIN_SAMPLES = 3

BASELINE_RUNS = 3
TEST_RUNS = 3
CV_MAX = 0.05
MIN_EFFECT_PCT = 1.0
AUTO_STOP_WINDOW = 3
MARGINAL_GAIN_RATIO = 0.03
SYNERGY_RUNS = 2
SYNERGY_MAX_PAIRS = 2
SYNERGY_FACTOR = 1.15
VALIDATION_SECONDS = 300
VALIDATION_MIN_RATIO = 0.5
WARMUP_SECONDS = 45
CHECK_RUNS = 2
REGRESSION_PCT = -5.0
STUTTER_KEEP_PCT = 3.0
STUTTER_GUARD_PCT = -5.0
FPS_NEUTRAL_PCT = -0.5

ACTIVE_STATUSES = ("waiting_agent", "snapshot", "baseline", "testing", "awaiting_reboot", "synergy", "validation", "aborting")


def _hw_class(specs_data):
    import re as _re
    gpu = (specs_data or {}).get("gpu") or ""
    cpu = (specs_data or {}).get("cpu") or ""
    gv = "nvidia" if _re.search(r"nvidia|geforce|rtx|gtx", gpu, _re.I) else ("amd" if _re.search(r"amd|radeon|\brx\b", gpu, _re.I) else "other")
    cv_ = "intel" if "intel" in cpu.lower() else ("amd" if _re.search(r"amd|ryzen", cpu, _re.I) else "other")
    return f"{gv}_{cv_}"


async def _fleet_blend(candidates, hw):
    """Fase 3: fonde il prior statico con lo storico aggregato anonimo della fleet (hardware simile)."""
    fleet = {}
    async for d in db.lab_fleet_stats.find({"hw_class": hw}):
        fleet[d["tweak_id"]] = d
    used = 0
    for c in candidates:
        f = fleet.get(c["tweak_id"])
        if f and f.get("tested", 0) >= FLEET_MIN_SAMPLES:
            rate = max(0.05, min(0.9, f["kept"] / f["tested"]))
            w = min(0.7, f["tested"] / (f["tested"] + 10))
            c["prior"] = round((1 - w) * c["prior"] + w * rate, 3)
            c["fleet"] = {"tested": f["tested"], "kept": f["kept"],
                          "avg_delta_pct": round((f.get("delta_sum") or 0) / f["tested"], 2)}
            used += 1
    candidates.sort(key=lambda c: (bool(c.get("requires_reboot")), -c["prior"]))
    return used


def _log(sess, msg, level="info"):
    sess.setdefault("logs", []).append({"ts": now_iso(), "msg": msg, "level": level})
    sess["logs"] = sess["logs"][-120:]


def _fps_list(runs, key="fps_avg"):
    return [r.get(key) for r in runs if isinstance(r.get(key), (int, float))]


def _run_stats(runs):
    fps = _fps_list(runs)
    p1 = _fps_list(runs, "fps_p1")
    lat = _fps_list(runs, "latency_ms")
    return {
        "fps_avg": round(mean(fps), 2) if fps else None,
        "fps_p1": round(mean(p1), 2) if p1 else None,
        "latency_ms": round(mean(lat), 2) if lat else None,
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


def _result_delta(sess, tweak_id):
    for r in sess.get("results", []):
        if r["tweak_id"] == tweak_id and r["decision"] == "kept":
            return r["delta"].get("fps_avg_pct") or 0
    return 0


def _advance_after_testing(sess, stop_reason=None):
    """Fine test loop -> synergy pass (coppie greedy tra i kept no-reboot) -> validazione -> report."""
    if stop_reason:
        sess["auto_stop_reason"] = stop_reason
        _log(sess, stop_reason, "warn")
    kept = sess.get("kept", [])
    meta = {c["tweak_id"]: c for c in sess.get("candidates", [])}
    eligible = [t for t in kept if not meta.get(t, {}).get("requires_reboot")]
    pairs = []
    from itertools import combinations
    for a, b in combinations(eligible, 2):
        ma, mb = meta.get(a, {}), meta.get(b, {})
        if b in (ma.get("conflicts_with") or []) or a in (mb.get("conflicts_with") or []):
            continue
        if ma.get("family") and ma.get("family") == mb.get("family"):
            continue  # coppie complementari: famiglie diverse
        pairs.append({"a": a, "b": b, "sum_delta": round(_result_delta(sess, a) + _result_delta(sess, b), 2)})
    pairs.sort(key=lambda p: -p["sum_delta"])
    pairs = pairs[:SYNERGY_MAX_PAIRS]
    if pairs:
        sess["status"] = "synergy"
        sess["synergy"] = {"pairs": pairs, "idx": 0, "stage": "off", "toggled": False,
                           "off_runs": [], "on_runs": [], "results": []}
        _log(sess, f"SYNERGY PASS: {len(pairs)} coppie di tweak mantenuti da verificare ({SYNERGY_RUNS} run off + {SYNERGY_RUNS} run on per coppia)")
    elif kept:
        sess["status"] = "validation"
        _log(sess, f"VALIDAZIONE: sessione di gioco reale da {VALIDATION_SECONDS // 60} minuti con la configurazione finale")
    else:
        _complete(sess)


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
        pv = r["significance"].get("p_value")
        if r.get("decision_basis") == "fluidity" and r.get("significance_p1"):
            pv = r["significance_p1"].get("p_value")
        steps.append({
            "tweak_id": r["tweak_id"],
            "tweak": names.get(r["tweak_id"], r["tweak_id"]),
            "before": r.get("before_fps"),
            "after": r.get("after_fps"),
            "delta_pct": r["delta"].get("fps_avg_pct"),
            "p1_delta_pct": r["delta"].get("fps_p1_pct"),
            "latency_delta_ms": r["delta"].get("latency_ms"),
            "ci_pct": r["delta"].get("fps_ci_pct"),
            "effect_d": r["delta"].get("effect_d"),
            "basis": r.get("decision_basis"),
            "decision": r["decision"],
            "reason": r.get("reason"),
            "p_value": pv,
        })
    pvals = [s["p_value"] for s in steps if s.get("p_value") is not None]
    if pvals:
        adj = holm_adjust(pvals)
        k = 0
        for s in steps:
            if s.get("p_value") is not None:
                s["p_adj"] = adj[k]
                s["holm_ok"] = bool(adj[k] < 0.10)
                k += 1
    kept_steps = [s for s in steps if s["decision"] == "kept"]
    multiple_testing = {"method": "holm_bonferroni", "alpha": 0.10,
                        "kept_total": len(kept_steps),
                        "kept_confirmed": sum(1 for s in kept_steps if s.get("holm_ok"))}
    n_rb = sum(1 for s in steps if s["decision"] == "rolled_back")
    meta = {c["tweak_id"]: c for c in sess.get("candidates", [])}
    reboots = sum(1 for r in sess.get("results", []) if meta.get(r["tweak_id"], {}).get("requires_reboot"))
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
    lat0, latf = base0.get("latency_ms"), final.get("latency_ms")
    lat_delta = round(latf - lat0, 2) if (lat0 is not None and latf is not None) else None
    return {
        "lab_session_id": sess["session_id"],
        "game": final.get("game") or base0.get("game"),
        "baseline": {"fps_avg": base0.get("fps_avg"), "fps_p1": base0.get("fps_p1")},
        "final": {"fps_avg": final.get("fps_avg"), "fps_p1": final.get("fps_p1")},
        "total_gain_pct": gain,
        "total_p1_gain_pct": gain_p1,
        "total_latency_delta_ms": lat_delta,
        "multiple_testing": multiple_testing,
        "drift_events": sess.get("drift_events") or [],
        "steps": steps,
        "kept": sess.get("kept", []),
        "synergies_found": (sess.get("synergy") or {}).get("results", []),
        "validation": sess.get("validation"),
        "bios_suggestions": sess.get("bios_suggestions") or [],
        "hw_class": sess.get("hw_class"),
        "reboots_required": reboots,
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
        candidates, skipped = select_candidates(specs.get("data") or {}, payload.risk_level, payload.include_reboot)
        if not candidates:
            raise HTTPException(status_code=400, detail="Nessun tweak candidato per questo livello di rischio/hardware.")
        hw = _hw_class(specs.get("data") or {})
        fleet_used = await _fleet_blend(candidates, hw)
        sd = specs.get("data") or {}
        sess = {
            "session_id": str(uuid.uuid4()),
            "user_id": uid,
            "kind": "full",
            "risk_level": payload.risk_level,
            "run_seconds": payload.run_seconds,
            "include_reboot": payload.include_reboot,
            "hw_class": hw,
            "specs_at": {"ram_speed_mhz": sd.get("ram_speed_mhz"), "ram_modules": sd.get("ram_modules"),
                         "gpu_driver": sd.get("gpu_driver_version") or sd.get("gpu_driver")},
            "bios_suggestions": bios_suggestions(specs.get("data") or {}),
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
        if fleet_used:
            _log(sess, f"Prior arricchiti con i dati fleet: {fleet_used} tweak hanno statistiche da PC simili ({hw.replace('_', ' GPU + ')} CPU)")
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
    async def lab_registry(risk_level: str = "medium", include_reboot: bool = True, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}) or {}
        candidates, skipped = select_candidates(specs.get("data") or {}, risk_level, include_reboot)
        hw = _hw_class(specs.get("data") or {})
        await _fleet_blend(candidates, hw)
        return {"registry_version": REGISTRY_VERSION, "candidates": candidates, "skipped": skipped,
                "hw_class": hw, "bios_suggestions": bios_suggestions(specs.get("data") or {})}

    @r.post("/lab/check")
    async def lab_check(payload: LabCheckInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        if await _active(uid):
            raise HTTPException(status_code=409, detail="Hai gia' una sessione Lab attiva.")
        last = await db.lab_sessions.find_one(
            {"user_id": uid, "status": "completed", "kind": {"$ne": "check"}, "report": {"$ne": None}},
            sort=[("started_at", -1)])
        if not last or not ((last.get("report") or {}).get("final") or {}).get("fps_avg"):
            raise HTTPException(status_code=400, detail="Serve prima un Lab completo come riferimento.")
        rep = last["report"]
        ref = {"fps_avg": rep["final"]["fps_avg"], "fps_p1": rep["final"].get("fps_p1"),
               "game": rep.get("game"), "session_id": last["session_id"], "at": last.get("finished_at")}
        sess = {
            "session_id": str(uuid.uuid4()), "user_id": uid, "kind": "check",
            "check_reason": payload.reason, "check_ref": ref,
            "run_seconds": last.get("run_seconds", 90), "status": "waiting_agent",
            "candidates": [], "queue": [], "baseline": {"runs": [], "stats": None},
            "results": [], "kept": [], "logs": [], "report": None,
            "started_at": now_iso(), "finished_at": None,
        }
        _log(sess, f"Mini-lab di verifica ({payload.reason}): {CHECK_RUNS} run vs riferimento {ref['fps_avg']} FPS ({ref.get('game') or 'n/d'})")
        _log(sess, "In attesa dell'agent: esegui il comando Lab in PowerShell come Amministratore")
        await _save(sess)
        return {"session": _public(sess)}

    @r.get("/lab/history")
    async def lab_history(user: dict = Depends(get_current_user)):
        out = []
        cur = db.lab_sessions.find({"user_id": str(user["_id"]), "status": "completed"},
                                   sort=[("started_at", -1)]).limit(15)
        async for s in cur:
            rep = s.get("report") or {}
            out.append({
                "session_id": s["session_id"], "kind": s.get("kind", "full"),
                "started_at": s.get("started_at"), "game": rep.get("game"),
                "total_gain_pct": rep.get("total_gain_pct"),
                "kept": len(rep.get("kept") or []), "tweaks_tested": rep.get("tweaks_tested"),
                "baseline_fps": (rep.get("baseline") or {}).get("fps_avg"),
                "final_fps": (rep.get("final") or {}).get("fps_avg"),
                "check_reason": s.get("check_reason"), "regression": rep.get("regression"),
            })
        return {"sessions": out}

    @r.get("/lab/insights")
    async def lab_insights(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        last = await db.lab_sessions.find_one(
            {"user_id": uid, "status": "completed", "kind": {"$ne": "check"}, "report": {"$ne": None}},
            sort=[("started_at", -1)])
        if not last:
            return {"items": [], "has_ref": False}

        def _num(v):
            try:
                return float(str(v).strip())
            except Exception:
                return None

        specs = await db.pc_specs.find_one({"user_id": uid}) or {}
        data = specs.get("data") or {}
        at = last.get("specs_at") or {}
        bios_ids = {b["id"] for b in (last.get("bios_suggestions") or [])}
        items = []
        cur_speed, at_speed = _num(data.get("ram_speed_mhz")), _num(at.get("ram_speed_mhz"))
        if "xmp" in bios_ids and cur_speed and at_speed and cur_speed > at_speed * 1.1:
            items.append({"id": "bios_xmp", "kind": "confirm", "detail": f"RAM: {int(at_speed)} -> {int(cur_speed)} MHz"})
        if "dual_channel" in bios_ids and (_num(data.get("ram_modules")) or 0) >= 2:
            items.append({"id": "bios_dual", "kind": "confirm", "detail": "dual channel rilevato"})
        if "rebar" in bios_ids:
            if str(data.get("rebar_status") or "").lower() == "on":
                items.append({"id": "bios_rebar", "kind": "confirm", "detail": "ReBAR attivo rilevato"})
            else:
                items.append({"id": "bios_rebar", "kind": "manual", "detail": None})
        cur_drv = data.get("gpu_driver_version") or data.get("gpu_driver")
        at_drv = at.get("gpu_driver")
        if cur_drv and at_drv and str(cur_drv) != str(at_drv):
            items.append({"id": "driver_update", "kind": "check", "detail": f"{at_drv} -> {cur_drv}"})
        rep = last.get("report") or {}
        return {"items": items, "has_ref": bool((rep.get("final") or {}).get("fps_avg")),
                "ref": {"fps_avg": (rep.get("final") or {}).get("fps_avg"), "game": rep.get("game"),
                        "at": last.get("finished_at")}}

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
            if sess.get("kind") == "check":
                sess["status"] = "baseline"
                _log(sess, f"Agent collegato: mini-lab di verifica, {CHECK_RUNS} run")
                await _save(sess)
                st = "baseline"
            else:
                sess["status"] = "snapshot"
                _log(sess, "Agent collegato: avvio fase SNAPSHOT")
                await _save(sess)
                st = "snapshot"
        if st == "snapshot":
            return {"action": "snapshot", "session_id": sess["session_id"],
                    "candidate_ids": [c["tweak_id"] for c in sess["candidates"]]}
        if st == "baseline":
            done = len(sess["baseline"]["runs"])
            if sess.get("kind") == "check":
                target = CHECK_RUNS
            else:
                target = BASELINE_RUNS if done < BASELINE_RUNS else BASELINE_RUNS + 1
            return {"action": "run_baseline", "run_seconds": rs, "runs_done": done, "runs_target": target}
        if st == "aborting":
            ids = list(sess.get("kept", []))
            cur = sess.get("current")
            if cur and cur.get("applied") and cur["tweak_id"] not in ids:
                ids.append(cur["tweak_id"])
            return {"action": "abort", "rollback_ids": ids}
        if st == "awaiting_reboot":
            cur = sess.get("current") or {}
            return {"action": "reboot_required", "tweak_id": cur.get("tweak_id"),
                    "applied_at": cur.get("applied_at"), "session_id": sess["session_id"]}
        if st == "synergy":
            syn = sess.get("synergy") or {}
            pairs = syn.get("pairs", [])
            idx = syn.get("idx", 0)
            if idx >= len(pairs):
                sess["status"] = "validation"
                _log(sess, f"VALIDAZIONE: sessione di gioco reale da {VALIDATION_SECONDS // 60} minuti")
                await _save(sess)
                return {"action": "run_validation", "run_seconds": VALIDATION_SECONDS}
            pair = pairs[idx]
            stage = syn.get("stage", "off")
            if not syn.get("toggled"):
                return {"action": "synergy_toggle", "stage": stage, "pair": [pair["a"], pair["b"]],
                        "pair_num": idx + 1, "pairs_total": len(pairs)}
            runs_done = len(syn.get("off_runs" if stage == "off" else "on_runs", []))
            return {"action": "run_synergy", "stage": stage, "pair": [pair["a"], pair["b"]],
                    "runs_done": runs_done, "runs_target": SYNERGY_RUNS, "run_seconds": rs,
                    "pair_num": idx + 1, "pairs_total": len(pairs)}
        if st == "validation":
            return {"action": "run_validation", "run_seconds": VALIDATION_SECONDS}
        if st == "testing":
            cur = sess.get("current")
            rc = sess.get("recheck")
            if rc:
                return {"action": "run_recheck", "run_seconds": rs,
                        "runs_done": len(rc["runs"]), "runs_target": rc["target"]}
            total = len(sess["candidates"])
            step = len(sess.get("results", [])) + len(sess.get("skipped_runtime", [])) + 1
            if not cur:
                queue = sess.get("queue", [])
                if queue and len(sess.get("results", [])) >= sess.get("recheck_after", 0) + 3:
                    sess["recheck"] = {"runs": [], "target": 1}
                    sess["recheck_after"] = len(sess.get("results", []))
                    _log(sess, "Controllo drift baseline (schema A/B/A): 1 run di verifica")
                    await _save(sess)
                    return {"action": "run_recheck", "run_seconds": rs, "runs_done": 0, "runs_target": 1}
                if not queue:
                    _advance_after_testing(sess)
                    await _save(sess)
                    if sess["status"] == "completed":
                        sess["agent_ack"] = True
                        await _save(sess)
                        return {"action": "complete", "report": sess["report"]}
                    return {"action": "transition", "status": sess["status"]}
                tid = queue.pop(0)
                sess["queue"] = queue
                sess["current"] = {"tweak_id": tid, "applied": False, "runs": []}
                await _save(sess)
                cur = sess["current"]
            tweak = next((c for c in sess["candidates"] if c["tweak_id"] == cur["tweak_id"]), {"tweak_id": cur["tweak_id"]})
            if not cur.get("applied"):
                return {"action": "apply_tweak", "tweak_id": cur["tweak_id"], "tweak": tweak,
                        "requires_reboot": bool(tweak.get("requires_reboot")),
                        "step": step, "total": total}
            if cur.get("warmup_needed"):
                return {"action": "run_warmup", "tweak_id": cur["tweak_id"], "run_seconds": WARMUP_SECONDS}
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
                cur["applied_at"] = now_iso()
                if data.get("requires_reboot"):
                    sess["status"] = "awaiting_reboot"
                    _log(sess, f"Tweak applicato: {data.get('tweak_id')} — RIAVVIO RICHIESTO. Il Lab riprende automaticamente dopo il riavvio.", "warn")
                else:
                    _log(sess, f"Tweak applicato: {data.get('tweak_id')} (backup creato)")
            else:
                _log(sess, f"Tweak applicato: {data.get('tweak_id')} (backup creato)")
        elif t == "reboot_done":
            cur = sess.get("current")
            if sess["status"] == "awaiting_reboot" and cur:
                sess["status"] = "testing"
                cur["warmup_needed"] = True
                _log(sess, f"Riavvio completato: riprendo il test di {cur['tweak_id']} (1 run di warm-up + {TEST_RUNS} run misurati)", "ok")
        elif t == "synergy_toggled":
            syn = sess.get("synergy")
            if syn:
                syn["toggled"] = True
                stage = data.get("stage", syn.get("stage"))
                _log(sess, f"Synergy: coppia {'disattivata' if stage == 'off' else 'riattivata'} per la misura {stage.upper()}")
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

        if payload.phase == "warmup":
            cur = sess.get("current")
            if cur:
                cur["warmup_needed"] = False
            _log(sess, f"Warm-up post-riavvio completato ({run.get('fps_avg')} FPS, scartato dalle statistiche)")
            await _save(sess)
            return {"ok": True, "warmup_done": True}

        if payload.phase in ("synergy_off", "synergy_on"):
            syn = sess.get("synergy")
            if sess["status"] != "synergy" or not syn:
                return {"ok": False, "reason": "nessun synergy pass attivo"}
            stage = "off" if payload.phase == "synergy_off" else "on"
            key = f"{stage}_runs"
            syn[key].append(run)
            pair = syn["pairs"][syn["idx"]]
            _log(sess, f"Synergy {pair['a']}+{pair['b']} [{stage.upper()}] run {len(syn[key])}: {run.get('fps_avg')} FPS avg")
            if len(syn[key]) < SYNERGY_RUNS:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": len(syn[key])}
            if stage == "off":
                syn["stage"] = "on"
                syn["toggled"] = False
                await _save(sess)
                return {"ok": True, "stage_done": "off"}
            # coppia completata: calcola la sinergia
            off_fps = _fps_list(syn["off_runs"])
            on_fps = _fps_list(syn["on_runs"])
            combined = _delta_pct(mean(on_fps), mean(off_fps)) if off_fps and on_fps else None
            is_syn = bool(combined is not None and pair["sum_delta"] > 0 and combined > pair["sum_delta"] * SYNERGY_FACTOR)
            res = {"pair": [pair["a"], pair["b"]], "combined_delta_pct": combined,
                   "individual_sum_pct": pair["sum_delta"], "is_synergy": is_syn,
                   "off_fps_avg": round(mean(off_fps), 2) if off_fps else None,
                   "on_fps_avg": round(mean(on_fps), 2) if on_fps else None}
            syn["results"].append(res)
            if is_syn:
                _log(sess, f"SINERGIA trovata: {pair['a']}+{pair['b']} insieme valgono {combined}% (somma singoli {pair['sum_delta']}%)", "ok")
            else:
                _log(sess, f"Nessuna sinergia extra: {pair['a']}+{pair['b']} = {combined}% (somma singoli {pair['sum_delta']}%)")
            syn["idx"] += 1
            syn["stage"] = "off"
            syn["toggled"] = False
            syn["off_runs"], syn["on_runs"] = [], []
            if syn["idx"] >= len(syn["pairs"]):
                sess["status"] = "validation"
                _log(sess, f"VALIDAZIONE: sessione di gioco reale da {VALIDATION_SECONDS // 60} minuti con la configurazione finale")
            await _save(sess)
            return {"ok": True, "pair_done": True, "synergy": res, "next_status": sess["status"]}

        if payload.phase == "validation":
            if sess["status"] != "validation":
                return {"ok": False, "reason": f"stato {sess['status']}"}
            base0 = sess.get("baseline0") or {}
            predicted = _delta_pct(sess["baseline"]["stats"].get("fps_avg") if sess["baseline"].get("stats") else None,
                                   base0.get("fps_avg")) or 0
            real = _delta_pct(run.get("fps_avg"), base0.get("fps_avg"))
            discrepancy = bool(predicted >= 2.0 and real is not None and real < predicted * VALIDATION_MIN_RATIO)
            sess["validation"] = {"run": run, "real_gain_pct": real, "predicted_gain_pct": round(predicted, 2),
                                  "duration_s": run.get("duration_s"), "discrepancy": discrepancy}
            if discrepancy:
                _log(sess, f"DISCREPANZA: guadagno reale {real}% < 50% del previsto ({round(predicted, 2)}%) — segnalato nel report", "warn")
            else:
                _log(sess, f"Validazione in gioco reale: {run.get('fps_avg')} FPS avg ({'+' if (real or 0) >= 0 else ''}{real}% vs baseline)", "ok")
            _complete(sess)
            sess["agent_ack"] = True
            await _save(sess)
            return {"ok": True, "validation": sess["validation"], "completed": True, "report": sess["report"]}

        if payload.phase == "recheck":
            rc = sess.get("recheck")
            if sess["status"] != "testing" or not rc:
                return {"ok": False, "reason": "nessun recheck attivo"}
            rc["runs"].append(run)
            base = sess["baseline"]["stats"] or {}
            drift = _delta_pct(run.get("fps_avg"), base.get("fps_avg")) or 0
            if rc["target"] == 1 and len(rc["runs"]) == 1:
                if abs(drift) <= 3.0:
                    sess["recheck"] = None
                    _log(sess, f"Baseline stabile: drift {drift}% (entro +/-3%)", "ok")
                    await _save(sess)
                    return {"ok": True, "drift_pct": drift, "stable": True}
                rc["target"] = 3
                sess.setdefault("drift_events", []).append({"at": now_iso(), "drift_pct": drift})
                _log(sess, f"DRIFT rilevato: {drift}% — ri-misuro la baseline (3 run)", "warn")
                await _save(sess)
                return {"ok": True, "drift_pct": drift, "stable": False, "need_more": True}
            if len(rc["runs"]) < rc["target"]:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": len(rc["runs"])}
            stats = _run_stats(rc["runs"])
            sess["baseline"]["runs"] = rc["runs"]
            sess["baseline"]["stats"] = stats
            sess["recheck"] = None
            _log(sess, f"RE-BASELINE: nuova baseline {stats['fps_avg']} FPS (drift compensato)", "warn")
            await _save(sess)
            return {"ok": True, "rebaselined": True, "stats": stats}

        if payload.phase == "baseline":
            if sess["status"] != "baseline":
                return {"ok": False, "reason": f"stato {sess['status']}"}
            if sess.get("kind") == "check":
                sess["baseline"]["runs"].append(run)
                runs = sess["baseline"]["runs"]
                _log(sess, f"Verifica run {len(runs)}: {run.get('fps_avg')} FPS avg")
                if len(runs) < CHECK_RUNS:
                    await _save(sess)
                    return {"ok": True, "need_more": True, "runs_done": len(runs)}
                stats = _run_stats(runs)
                ref = sess.get("check_ref") or {}
                delta = _delta_pct(stats.get("fps_avg"), ref.get("fps_avg"))
                d1 = _delta_pct(stats.get("fps_p1"), ref.get("fps_p1"))
                regression = bool(delta is not None and delta <= REGRESSION_PCT)
                if stats.get("game") and ref.get("game") and stats["game"] != ref["game"]:
                    _log(sess, f"ATTENZIONE: gioco diverso dal riferimento ({stats['game']} vs {ref['game']}), confronto indicativo", "warn")
                sess["report"] = {
                    "kind": "check", "check_reason": sess.get("check_reason"),
                    "game": stats.get("game") or ref.get("game"),
                    "baseline": {"fps_avg": ref.get("fps_avg"), "fps_p1": ref.get("fps_p1")},
                    "final": {"fps_avg": stats.get("fps_avg"), "fps_p1": stats.get("fps_p1")},
                    "total_gain_pct": delta, "total_p1_gain_pct": d1,
                    "regression": regression, "ref_at": ref.get("at"),
                    "kept": [], "tweaks_tested": 0, "steps": [],
                }
                sess["baseline"]["stats"] = stats
                sess["status"] = "completed"
                sess["finished_at"] = now_iso()
                if regression:
                    _log(sess, f"REGRESSIONE: {delta}% vs riferimento ({ref.get('fps_avg')} FPS) — consigliato un nuovo Lab completo", "warn")
                else:
                    _log(sess, f"Verifica completata: {stats.get('fps_avg')} FPS ({'+' if (delta or 0) >= 0 else ''}{delta}% vs riferimento)", "ok")
                await _save(sess)
                return {"ok": True, "baseline_ok": True, "stats": stats, "completed": True, "check": sess["report"]}
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
        base_p1 = _fps_list(sess["baseline"]["runs"], "fps_p1")
        test_p1 = _fps_list(cur["runs"], "fps_p1")
        sig_p1 = significance(test_p1, base_p1) if len(base_p1) >= 2 and len(test_p1) >= 2 else None
        delta = {
            "fps_avg_pct": _delta_pct(test_stats["fps_avg"], base_runs["fps_avg"]),
            "fps_p1_pct": _delta_pct(test_stats["fps_p1"], base_runs["fps_p1"]),
        }
        ci = welch_ci(test_fps, base_fps)
        if ci and base_runs.get("fps_avg"):
            bm = base_runs["fps_avg"]
            delta["fps_ci_pct"] = [round(ci[1] / bm * 100, 2), round(ci[2] / bm * 100, 2)]
        eff = cohens_d(test_fps, base_fps)
        if eff is not None:
            delta["effect_d"] = eff
        if test_stats.get("latency_ms") is not None and base_runs.get("latency_ms") is not None:
            delta["latency_ms"] = round(test_stats["latency_ms"] - base_runs["latency_ms"], 2)
        d = delta["fps_avg_pct"] or 0
        d1 = delta["fps_p1_pct"]
        improvement = d >= MIN_EFFECT_PCT
        kept = bool(sig["significant"] and improvement)
        basis = "fps"
        if kept and d1 is not None and d1 <= STUTTER_GUARD_PCT:
            kept = False
            basis = "stutter_guard"
            reason = f"FPS +{d}% ma fluidita' peggiorata (1% low {d1}%)"
        elif kept:
            reason = f"significativo (p={sig['p_value']}), +{d}% FPS"
        elif sig_p1 and sig_p1["significant"] and d1 is not None and d1 >= STUTTER_KEEP_PCT and d >= FPS_NEUTRAL_PCT:
            kept = True
            basis = "fluidity"
            reason = f"fluidita': 1% low +{d1}% (p={sig_p1['p_value']}), FPS stabili ({d}%)"
        elif not sig["significant"]:
            reason = f"non significativo (p={sig['p_value']})"
        elif d < 0:
            reason = f"peggioramento ({d}%)"
        else:
            reason = f"delta trascurabile (+{d}% < {MIN_EFFECT_PCT}%)"
        if kept and delta.get("latency_ms") is not None and delta["latency_ms"] <= -1:
            reason += f", input lag {delta['latency_ms']}ms"
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
            "significance_p1": ({"p_value": sig_p1["p_value"], "significant": sig_p1["significant"]} if sig_p1 else None),
            "decision": "kept" if kept else "rolled_back",
            "decision_basis": basis,
            "reason": reason,
            "at": now_iso(),
        }
        sess["results"].append(result)
        await db.lab_fleet_stats.update_one(
            {"tweak_id": cur["tweak_id"], "hw_class": sess.get("hw_class", "other_other")},
            {"$inc": {"tested": 1, "kept": 1 if kept else 0, "delta_sum": d}},
            upsert=True)
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
            _advance_after_testing(sess, stop_reason)
            completed = sess["status"] == "completed"
            if completed:
                sess["agent_ack"] = True
        await _save(sess)
        return {"ok": True, "decision": result["decision"], "reason": reason,
                "delta": delta, "significance": result["significance"],
                "completed": completed, "next_status": sess["status"],
                "remaining": len(sess.get("queue", []))}

    return r

