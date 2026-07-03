import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse

import ai_engine
import push
from database import db, now_iso
from helpers import specs_to_text, compute_health, get_or_create_agent_token
from desktop_agent import AGENT_SCRIPT
from ps_agent import PS_SCRIPT
from models import SpecsInput, GoalInput, FpsInput, PcSpecsInput, TelemetryInput, AlertInput
from routers.profiles import resolve_tweak_ids


def _iso_age(ts):
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    except Exception:
        return 1e9


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
        if data.startup is not None:
            fields["startup"] = data.startup
        if data.benchmark is not None:
            record = {**data.benchmark, "user_id": uid, "created_at": now_iso()}
            fields["benchmark"] = record
            await db.benchmarks.insert_one({**record})
        await db.pc_specs.update_one({"user_id": uid}, {"$set": fields}, upsert=True)
        return {"ok": True}

    @r.get("/pc-benchmark")
    async def pc_benchmark(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0, "benchmark": 1})
        history = await db.benchmarks.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(10)
        return {"latest": (doc or {}).get("benchmark"), "history": history}

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
             "$push": {"samples": {"$each": [sample], "$slice": -120}}},
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

    @r.get("/pc-health")
    async def pc_health(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        if not doc or not doc.get("health"):
            return {"available": False}
        return {**compute_health(doc["health"]), "available": True}

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
        return PlainTextResponse(script, headers={"Content-Disposition": "attachment; filename=boostpc_agent.py"})

    @r.get("/agent/script")
    async def agent_script(t: str = "", mode: str = "sync", profile: str = ""):
        rec = await db.agent_tokens.find_one({"token": t})
        if not rec:
            return PlainTextResponse("Write-Host '[BOOST PC] Token non valido. Riapri la pagina Desktop Agent.' -ForegroundColor Red",
                                     media_type="text/plain")
        if mode not in ("sync", "optimize", "restore", "benchmark", "monitor"):
            mode = "sync"
        backend = os.environ.get("FRONTEND_URL", "http://localhost:8001")
        ids = await resolve_tweak_ids(db, rec["user_id"], profile) if profile else []
        profile_literal = ",".join("'" + i.replace("'", "") + "'" for i in ids)
        script = (PS_SCRIPT.replace("__BACKEND_URL__", backend)
                  .replace("__AGENT_TOKEN__", t).replace("__MODE__", mode)
                  .replace("__PROFILE_IDS__", profile_literal))
        return PlainTextResponse(script, media_type="text/plain")

    return r
