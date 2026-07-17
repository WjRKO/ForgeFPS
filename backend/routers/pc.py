import os
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse

import ai_engine
import push
from database import db, now_iso
from helpers import specs_to_text, compute_health, get_or_create_agent_token, grade_bufferbloat
from desktop_agent import AGENT_SCRIPT
from ps_agent import PS_SCRIPT
from models import SpecsInput, GoalInput, FpsInput, PcSpecsInput, TelemetryInput, AlertInput, PrematchInput, NetResultInput, ReportPhaseInput
from routers.profiles import resolve_tweak_ids

# Default background processes closed by "Prima del match" (must stay in sync with frontend groups)
DEFAULT_PREMATCH_APPS = [
    "chrome", "msedge", "firefox", "opera", "brave",
    "Discord", "Slack", "Teams", "Telegram", "WhatsApp", "Skype", "SkypeApp",
    "Spotify", "Music.UI",
    "OneDrive", "GoogleDriveFS", "Dropbox",
    "EpicGamesLauncher",
    "CCleaner", "Cortana", "YourPhone", "PhoneExperienceHost",
]


def _iso_age(ts):
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    except Exception:
        return 1e9


async def _build_agent_script(user_id: str, profile: str = "") -> str:
    backend = os.environ.get("FRONTEND_URL", "http://localhost:8001")
    ids = await resolve_tweak_ids(db, user_id, profile) if profile else []
    profile_literal = ",".join("'" + i.replace("'", "") + "'" for i in ids)
    pm = await db.prematch_settings.find_one({"user_id": user_id}) or {}
    pm_apps = pm.get("close_apps", DEFAULT_PREMATCH_APPS)
    pm_apps_literal = ",".join("'" + a.replace("'", "") + "'" for a in pm_apps)
    pm_power = "$true" if pm.get("set_power", True) else "$false"
    return (PS_SCRIPT.replace("__BACKEND_URL__", backend)
            .replace("__PROFILE_IDS__", profile_literal)
            .replace("__PREMATCH_APPS__", pm_apps_literal)
            .replace("__PREMATCH_POWER__", pm_power))


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["pc"])

    @r.get("/agent/token")
    async def agent_token(user: dict = Depends(get_current_user)):
        return {"token": await get_or_create_agent_token(str(user["_id"]))}

    @r.post("/agent/report-specs")
    async def report_specs(data: SpecsInput, x_agent_token: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        uid = rec["user_id"]
        fields = {"user_id": uid, "updated_at": now_iso()}
        if data.data:
            fields["data"] = data.data
        if data.health is not None:
            fields["health"] = data.health
            _h = compute_health(data.health)
            await db.health_history.insert_one({
                "user_id": uid, "score": _h.get("score"), "grade": _h.get("grade"),
                "cpu_temp": _h.get("cpu_temp"), "gpu_temp": _h.get("gpu_temp"),
                "created_at": now_iso()})
        if data.startup is not None:
            fields["startup"] = data.startup
        if data.games is not None:
            fields["games"] = data.games
        if data.running_apps is not None:
            fields["running_apps"] = data.running_apps
            fields["running_at"] = now_iso()
        if data.benchmark is not None:
            record = {**data.benchmark, "user_id": uid, "created_at": now_iso()}
            fields["benchmark"] = record
            await db.benchmarks.insert_one({**record})
        await db.pc_specs.update_one({"user_id": uid}, {"$set": fields}, upsert=True)
        return {"ok": True}

    @r.post("/agent/netresult")
    async def agent_netresult(payload: NetResultInput, x_agent_token: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        graded = grade_bufferbloat(payload.result)
        await db.net_results.update_one(
            {"user_id": rec["user_id"]},
            {"$set": {"user_id": rec["user_id"], "result": graded, "updated_at": now_iso()}},
            upsert=True)
        return {"ok": True, "grade": graded.get("grade")}

    @r.get("/net-result")
    async def net_result(user: dict = Depends(get_current_user)):
        doc = await db.net_results.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        if not doc:
            return {"available": False}
        return {"available": True, **doc}

    @r.get("/pc-benchmark")
    async def pc_benchmark(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0, "benchmark": 1})
        history = await db.benchmarks.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(10)
        return {"latest": (doc or {}).get("benchmark"), "history": history}

    async def _gather_snapshot(uid: str) -> dict:
        """Snapshot the current key performance metrics for a Before/After report."""
        snap = {"captured_at": now_iso(), "health_score": None, "health_grade": None,
                "bufferbloat_ms": None, "bufferbloat_grade": None,
                "fps_avg": None, "bench_overall": None}
        specs = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0, "health": 1, "benchmark": 1})
        if specs:
            if specs.get("health"):
                h = compute_health(specs["health"])
                snap["health_score"] = h.get("score")
                snap["health_grade"] = h.get("grade")
            bench = specs.get("benchmark") or {}
            snap["bench_overall"] = bench.get("overall") or (bench.get("after") or {}).get("overall")
        net = await db.net_results.find_one({"user_id": uid}, {"_id": 0, "result": 1})
        if net and net.get("result"):
            snap["bufferbloat_ms"] = net["result"].get("bufferbloat_ms")
            snap["bufferbloat_grade"] = net["result"].get("grade")
        tel = await db.pc_telemetry.find_one({"user_id": uid}, {"_id": 0, "samples": 1})
        if tel and tel.get("samples"):
            fps_vals = [s.get("fps") for s in tel["samples"] if isinstance(s.get("fps"), (int, float)) and s.get("fps") > 0]
            if fps_vals:
                snap["fps_avg"] = round(sum(fps_vals) / len(fps_vals))
        return snap

    def _report_deltas(before: dict, after: dict) -> dict:
        d = {}
        if before and after:
            for k in ("health_score", "fps_avg", "bench_overall"):
                if before.get(k) is not None and after.get(k) is not None:
                    d[k] = after[k] - before[k]
            if before.get("bufferbloat_ms") is not None and after.get("bufferbloat_ms") is not None:
                d["bufferbloat_ms"] = after["bufferbloat_ms"] - before["bufferbloat_ms"]  # negative = better
        return d

    @r.post("/report/snapshot")
    async def report_snapshot(payload: ReportPhaseInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        snap = await _gather_snapshot(uid)
        await db.boost_reports.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, payload.phase: snap, "updated_at": now_iso()}},
            upsert=True)
        return {"ok": True, "phase": payload.phase, "snapshot": snap}

    @r.get("/report")
    async def get_report(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.boost_reports.find_one({"user_id": uid}, {"_id": 0})
        if not doc:
            return {"before": None, "after": None, "deltas": {}, "updated_at": None}
        before = doc.get("before"); after = doc.get("after")
        return {"before": before, "after": after,
                "deltas": _report_deltas(before, after), "updated_at": doc.get("updated_at")}

    @r.delete("/report")
    async def reset_report(user: dict = Depends(get_current_user)):
        await db.boost_reports.delete_one({"user_id": str(user["_id"])})
        return {"ok": True}

    @r.post("/agent/telemetry")
    async def agent_telemetry(payload: TelemetryInput, x_agent_token: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        sample = {**payload.sample}
        sample.setdefault("ts", now_iso())
        await db.pc_telemetry.update_one(
            {"user_id": rec["user_id"]},
            {"$set": {"user_id": rec["user_id"], "updated_at": now_iso()},
             "$push": {"samples": {"$each": [sample], "$slice": -300}}},
            upsert=True)
        await _check_temp_alerts(rec["user_id"], sample)
        return {"ok": True}

    @r.get("/pc-telemetry")
    async def pc_telemetry(user: dict = Depends(get_current_user)):
        doc = await db.pc_telemetry.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        if not doc:
            return {"samples": [], "updated_at": None, "live": False}
        live = False
        try:
            from datetime import datetime, timezone
            live = (datetime.now(timezone.utc) - datetime.fromisoformat(doc["updated_at"])).total_seconds() < 12
        except Exception:
            live = False
        return {"samples": doc.get("samples", [])[-60:], "updated_at": doc.get("updated_at"), "live": live}

    async def _check_temp_alerts(uid, sample):
        cfg = await db.alert_settings.find_one({"user_id": uid}) or {}
        if not cfg.get("enabled", True):
            return
        cpu_max = cfg.get("cpu_max", 90)
        gpu_max = cfg.get("gpu_max", 85)
        to_send = []
        ct, gt = sample.get("cpu_temp"), sample.get("gpu_temp")
        if ct and ct >= cpu_max and _iso_age(cfg.get("last_cpu_alert", "")) > 300:
            to_send.append(("cpu", f"CPU a {ct}°C (soglia {cpu_max}°C). Riduci il carico o controlla il raffreddamento."))
        if gt and gt >= gpu_max and _iso_age(cfg.get("last_gpu_alert", "")) > 300:
            to_send.append(("gpu", f"GPU a {gt}°C (soglia {gpu_max}°C). Riduci il carico o controlla il raffreddamento."))
        for metric, body in to_send:
            try:
                await push.send_push_to_user(db, uid, {"title": "🔥 Temperatura critica!", "body": body, "url": "/app/live"})
            except Exception:
                pass
            await db.alert_settings.update_one({"user_id": uid}, {"$set": {"user_id": uid, f"last_{metric}_alert": now_iso()}}, upsert=True)

    @r.get("/alerts")
    async def get_alerts(user: dict = Depends(get_current_user)):
        cfg = await db.alert_settings.find_one({"user_id": str(user["_id"])}, {"_id": 0}) or {}
        return {"enabled": cfg.get("enabled", True), "cpu_max": cfg.get("cpu_max", 90), "gpu_max": cfg.get("gpu_max", 85)}

    @r.put("/alerts")
    async def set_alerts(payload: AlertInput, user: dict = Depends(get_current_user)):
        await db.alert_settings.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"user_id": str(user["_id"]), "enabled": payload.enabled,
                      "cpu_max": payload.cpu_max, "gpu_max": payload.gpu_max}},
            upsert=True)
        return {"ok": True}

    @r.get("/pc-specs")
    async def get_specs(user: dict = Depends(get_current_user)):
        return await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})

    @r.post("/pc-specs")
    async def save_specs(payload: PcSpecsInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        existing = await db.pc_specs.find_one({"user_id": uid})
        base = (existing or {}).get("data", {}) if existing else {}
        merged = {**base, **{k: v for k, v in payload.data.items() if v not in (None, "")}}
        await db.pc_specs.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, "data": merged, "source": payload.source, "updated_at": now_iso()}},
            upsert=True)
        return await db.pc_specs.find_one({"user_id": uid}, {"_id": 0})

    @r.get("/prematch")
    async def get_prematch(user: dict = Depends(get_current_user)):
        doc = await db.prematch_settings.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0, "running_apps": 1, "running_at": 1})
        running = {"running_apps": (specs or {}).get("running_apps", []), "running_at": (specs or {}).get("running_at")}
        if not doc:
            return {"close_apps": DEFAULT_PREMATCH_APPS, "set_power": True, **running}
        return {"close_apps": doc.get("close_apps", DEFAULT_PREMATCH_APPS), "set_power": doc.get("set_power", True), **running}

    @r.put("/prematch")
    async def set_prematch(payload: PrematchInput, user: dict = Depends(get_current_user)):
        await db.prematch_settings.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"user_id": str(user["_id"]), "close_apps": payload.close_apps, "set_power": payload.set_power}},
            upsert=True)
        return {"ok": True}

    @r.get("/games")
    async def get_games(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0, "games": 1, "updated_at": 1})
        return {"games": (doc or {}).get("games", []), "updated_at": (doc or {}).get("updated_at")}

    @r.get("/pc-health")
    async def pc_health(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        if not doc or not doc.get("health"):
            return {"available": False}
        return {**compute_health(doc["health"]), "available": True}

    @r.get("/health-history")
    async def health_history(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        rows = await db.health_history.find({"user_id": uid}, {"_id": 0, "user_id": 0}) \
            .sort("created_at", -1).limit(90).to_list(90)
        rows.reverse()
        return {"points": rows}

    @r.post("/upgrade/analyze")
    async def upgrade_analyze(data: GoalInput, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        if not specs or not specs.get("data"):
            raise HTTPException(status_code=400,
                                detail="Nessun hardware rilevato. Usa il Desktop Agent (opzione 7) per inviare le specifiche.")
        try:
            return await ai_engine.generate_upgrade(specs_to_text(specs), data.budget, data.goal)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    @r.post("/fps/estimate")
    async def fps_estimate(data: FpsInput, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        try:
            return await ai_engine.estimate_fps(specs_to_text(specs) if specs else "", data.game, data.resolution)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    @r.post("/startup/analyze")
    async def startup_analyze(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        startup = (doc or {}).get("startup") or []
        if not startup:
            raise HTTPException(status_code=400, detail="Nessun dato di avvio. Usa il Desktop Agent (opzione 7).")
        try:
            return await ai_engine.analyze_startup(startup)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    @r.get("/desktop-agent/download")
    async def download_agent(user: dict = Depends(get_current_user)):
        token = await get_or_create_agent_token(str(user["_id"]))
        backend = os.environ.get("FRONTEND_URL", "http://localhost:8001")
        script = AGENT_SCRIPT.replace("__BACKEND_URL__", backend).replace("__AGENT_TOKEN__", token)
        return PlainTextResponse(script, headers={"Content-Disposition": "attachment; filename=forgefps_agent.py"})

    @r.get("/agent/script")
    async def agent_script(t: str = "", profile: str = ""):
        rec = await db.agent_tokens.find_one({"token": t})
        if not rec:
            return PlainTextResponse(
                "Write-Host '[FrameForge] Token non valido. Riapri la pagina Collega il PC.' -ForegroundColor Red",
                media_type="text/plain")
        script = await _build_agent_script(rec["user_id"], profile)
        return PlainTextResponse(script, media_type="text/plain",
                                 headers={"Content-Disposition": "attachment; filename=forgefps.ps1"})

    @r.get("/agent/script-info")
    async def agent_script_info(t: str = "", profile: str = "", user: dict = Depends(get_current_user)):
        rec = await db.agent_tokens.find_one({"token": t})
        user_id = rec["user_id"] if rec else str(user["_id"])
        script = await _build_agent_script(user_id, profile)
        data = script.encode("utf-8")
        return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "filename": "forgefps.ps1"}

    return r
