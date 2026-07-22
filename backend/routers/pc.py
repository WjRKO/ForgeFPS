import io
import os
import hmac
import time
import hashlib
import zipfile
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse

import ai_engine
import push
from database import db, now_iso
from helpers import specs_to_text, compute_health, get_or_create_agent_token, grade_bufferbloat
from desktop_agent import AGENT_SCRIPT
from ps_agent import PS_SCRIPT
from models import SpecsInput, GoalInput, FpsInput, PcSpecsInput, TelemetryInput, AlertInput, PrematchInput, NetResultInput, ReportPhaseInput, BoosterInput, BenchExplainInput
from routers.profiles import resolve_tweak_ids, TWEAK_CATALOG, TEMPLATES
from routers.advisor import _check_ai_rate_limit

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


# GitHub Release del ZIP generico dell'agent. Aggiornare a ogni bump di versione.
AGENT_ZIP_UPSTREAM = os.environ.get(
    "AGENT_ZIP_UPSTREAM",
    "https://github.com/WjRKO/ForgeFPS/releases/download/v0.7.1/forgefps-agent.zip",
)
_AGENT_ZIP_CACHE_PATH = f"/tmp/forgefps-agent-cache-{hashlib.sha256(AGENT_ZIP_UPSTREAM.encode()).hexdigest()[:10]}.zip"


def _render_launcher_bat(token: str, backend: str, standalone: bool) -> bytes:
    """Genera il contenuto di un launcher Windows .bat con token pre-compilato.

    standalone=True: file esterno da posizionare accanto al ZIP estratto (cerca
        'forgefps-agent\\forgefps-agent.exe' relativo alla propria directory).
    standalone=False: file DENTRO la cartella 'forgefps-agent/' del ZIP
        (lancia 'forgefps-agent.exe' dalla stessa directory).
    """
    if standalone:
        pre = [
            "cd /d \"%~dp0\"",
            "if not exist \"forgefps-agent\\forgefps-agent.exe\" (",
            "  echo.",
            "  echo [ERRORE] Cartella 'forgefps-agent' non trovata.",
            "  echo Estrai prima forgefps-agent.zip in questa stessa cartella,",
            "  echo poi rilancia questo file.",
            "  echo.",
            "  pause",
            "  exit /b 1",
            ")",
            "cd forgefps-agent",
        ]
    else:
        pre = ["cd /d \"%~dp0\""]
    lines = [
        "@echo off",
        "REM FrameForge - Launcher personale (contiene il tuo token privato)",
        "REM Doppio click qui: la GUI sicura parte automaticamente.",
        "setlocal",
        *pre,
        f'forgefps-agent.exe --backend "{backend}" --token {token} --mode securegui',
        "if errorlevel 1 (",
        "  echo.",
        "  echo L'agent si e' chiuso con errore. Premi INVIO per uscire.",
        "  pause",
        ")",
        "endlocal",
        "",
    ]
    return "\r\n".join(lines).encode("utf-8")


async def _ensure_agent_zip_cached() -> bytes:
    """Fetch (una sola volta) il ZIP dell'agent da GitHub e caching su disco.
    Le chiamate successive lo servono dal filesystem. Se il file cache manca o
    e' inconsistente, viene ri-scaricato."""
    if os.path.exists(_AGENT_ZIP_CACHE_PATH):
        try:
            with open(_AGENT_ZIP_CACHE_PATH, "rb") as fh:
                data = fh.read()
            zipfile.ZipFile(io.BytesIO(data)).close()  # sanity
            return data
        except Exception:
            try: os.unlink(_AGENT_ZIP_CACHE_PATH)
            except Exception: pass
    import httpx as _httpx
    async with _httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.get(AGENT_ZIP_UPSTREAM)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Upstream ZIP fetch failed ({resp.status_code})")
        data = resp.content
    with open(_AGENT_ZIP_CACHE_PATH, "wb") as fh:
        fh.write(data)
    return data


async def _build_agent_script(user_id: str, profile: str = "") -> str:
    backend = os.environ.get("FRONTEND_URL", "http://localhost:8001")
    ids = await resolve_tweak_ids(db, user_id, profile) if profile else []
    profile_literal = ",".join("'" + i.replace("'", "") + "'" for i in ids)
    pm = await db.prematch_settings.find_one({"user_id": user_id}) or {}
    pm_apps = pm.get("close_apps", DEFAULT_PREMATCH_APPS)
    pm_apps_literal = ",".join("'" + a.replace("'", "") + "'" for a in pm_apps)
    pm_power = "$true" if pm.get("set_power", True) else "$false"
    bs = await db.booster_settings.find_one({"user_id": user_id}) or {}
    b_apps_literal = ",".join("'" + a.replace("'", "") + "'" for a in bs.get("close_apps", []))
    def _psb(v):
        return "$true" if v else "$false"
    return (PS_SCRIPT.replace("__BACKEND_URL__", backend)
            .replace("__PROFILE_IDS__", profile_literal)
            .replace("__PREMATCH_APPS__", pm_apps_literal)
            .replace("__PREMATCH_POWER__", pm_power)
            .replace("__BOOSTER_APPS__", b_apps_literal)
            .replace("__BOOSTER_POWER__", _psb(bs.get("set_power", True)))
            .replace("__BOOSTER_PRIORITY__", _psb(bs.get("boost_priority", True)))
            .replace("__BOOSTER_PURGE__", _psb(bs.get("purge_ram", True))))


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["pc"])

    @r.get("/agent/token")
    async def agent_token(user: dict = Depends(get_current_user)):
        return {"token": await get_or_create_agent_token(str(user["_id"]))}

    @r.get("/agent/launcher-bat")
    async def agent_launcher_bat(user: dict = Depends(get_current_user)):
        """Genera un launcher Windows .bat per-utente con token pre-compilato.
        L'utente lo scarica una volta e lo mette accanto al ZIP estratto:
        doppio click -> la GUI parte senza dover incollare il token ogni volta."""
        from fastapi.responses import Response as _Resp
        token = await get_or_create_agent_token(str(user["_id"]))
        backend = os.environ.get("FRONTEND_URL", "https://forgefps.dev").rstrip("/")
        body = _render_launcher_bat(token, backend, standalone=True)
        return _Resp(
            content=body,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": 'attachment; filename="forgefps-launcher.bat"',
                "Cache-Control": "no-store",
            },
        )

    @r.get("/agent/download-zip")
    async def agent_download_zip(user: dict = Depends(get_current_user)):
        """Scarica il ZIP dell'agent con dentro un launcher personalizzato.
        Il ZIP base viene fetchato UNA volta da GitHub e messo in cache locale.
        Ad ogni richiesta iniettiamo `forgefps-agent/Avvia-FrameForge.bat` con
        il token dell'utente autenticato: un solo download, un solo doppio click."""
        from fastapi.responses import Response as _Resp
        token = await get_or_create_agent_token(str(user["_id"]))
        backend = os.environ.get("FRONTEND_URL", "https://forgefps.dev").rstrip("/")
        base_zip = await _ensure_agent_zip_cached()
        bat_bytes = _render_launcher_bat(token, backend, standalone=False)
        buf = io.BytesIO(base_zip)
        with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("forgefps-agent/Avvia-FrameForge.bat", bat_bytes)
        payload = buf.getvalue()
        # IMPORTANTE: usa Response (non StreamingResponse) per settare
        # Content-Length automaticamente. StreamingResponse con BytesIO senza
        # length header viene troncata da Cloudflare/ingress (bug segnalato dagli
        # utenti: ZIP arrivava a ~30% e 7-Zip rilevava "Fine dei dati inattesa").
        return _Resp(
            content=payload,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="forgefps-agent.zip"',
                "Content-Length": str(len(payload)),
                "Cache-Control": "no-store",
            },
        )

    @r.get("/agent/profiles")
    async def agent_list_profiles(x_agent_token: str = Header(default="")):
        """Ritorna i profili dell'utente + catalog per la GUI desktop.
        Autenticata via X-Agent-Token (stesso pattern di /api/agent/report-specs)."""
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        uid = rec["user_id"]
        profiles = await db.game_profiles.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1).to_list(100)
        return {"profiles": profiles, "templates": TEMPLATES, "catalog": TWEAK_CATALOG}

    @r.post("/agent/magic-link")
    async def agent_magic_link(x_agent_token: str = Header(default="")):
        """Genera un magic link mono-uso (5min) per la GUI desktop.
        Autenticato via X-Agent-Token: la GUI locale non ha cookie utente."""
        import secrets as _secrets
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        uid = rec["user_id"]
        now = datetime.now(timezone.utc)
        # Rate limit: 5/hour per user (stesso limite dell'endpoint web).
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        recent_count = await db.magic_tokens.count_documents({
            "user_id": uid, "created_at": {"$gte": one_hour_ago},
        })
        if recent_count >= 5:
            raise HTTPException(status_code=429, detail="Troppi magic link. Riprova tra un'ora.")
        token = _secrets.token_urlsafe(32)
        ttl_seconds = 300
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        await db.magic_tokens.insert_one({
            "token": token, "user_id": uid,
            "expires_at": expires_at, "created_at": now.isoformat(),
            "used": False, "source": "desktop_gui",
        })
        frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
        mobile_url = f"{frontend}/auth/mobile?t={token}"
        return {
            "token": token,
            "expires_in_seconds": ttl_seconds,
            "mobile_url": mobile_url,
        }

    @r.get("/agent/magic-qr")
    async def agent_magic_qr(token: str, x_agent_token: str = Header(default="")):
        """Genera QR SVG per il magic link (per la GUI desktop che non ha JS libraries).
        Autenticato via X-Agent-Token; il token DEV corrispondere allo stesso user."""
        import qrcode as _qr
        import qrcode.image.svg as _qrsvg
        from fastapi.responses import Response as _Resp
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        magic = await db.magic_tokens.find_one({"token": token, "user_id": rec["user_id"]})
        if not magic:
            raise HTTPException(status_code=404, detail="Magic token non trovato")
        frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
        url = f"{frontend}/auth/mobile?t={token}"
        img = _qr.make(url, image_factory=_qrsvg.SvgPathImage, box_size=8, border=1)
        buf = __import__("io").BytesIO()
        img.save(buf)
        return _Resp(content=buf.getvalue(), media_type="image/svg+xml",
                     headers={"Cache-Control": "no-store"})

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
        if data.boost_session is not None:
            await db.boost_sessions.insert_one({**data.boost_session, "user_id": uid, "created_at": now_iso()})
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

    def _bench_score(bench: dict) -> int | None:
        if not bench:
            return None
        s = bench.get("score")
        if s is None:
            s = (bench.get("after") or {}).get("score")
        try:
            return int(s) if s is not None else None
        except Exception:
            return None

    def _bench_overall(bench: dict) -> int | None:
        if not bench:
            return None
        v = bench.get("overall") or (bench.get("after") or {}).get("overall")
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    def _cpu_family(cpu_str: str | None) -> str | None:
        s = (cpu_str or "").lower()
        if not s:
            return None
        if "ultra" in s:
            for t in ("9", "7", "5", "3"):
                if f"ultra {t}" in s or f"ultra{t}" in s:
                    return f"intel-ultra-{t}"
        if "ryzen" in s or "amd" in s:
            for t in ("9", "7", "5", "3"):
                if f"ryzen {t}" in s or f"ryzen{t}" in s:
                    return f"ryzen-{t}"
        for t in ("i9", "i7", "i5", "i3"):
            if t in s:
                return f"intel-{t}"
        return None

    def _gpu_family(gpu_str: str | None) -> str | None:
        s = (gpu_str or "").lower()
        if not s:
            return None
        if "rtx" in s:
            for gen in ("50", "40", "30", "20"):
                if f"rtx {gen}" in s or f"rtx{gen}" in s:
                    return f"rtx-{gen}"
            return "rtx"
        if "gtx" in s:
            return "gtx"
        if "arc" in s and "intel" in s:
            return "intel-arc"
        if "rx" in s:
            for gen in ("9", "8", "7", "6", "5"):
                if f"rx {gen}" in s or f"rx{gen}" in s:
                    return f"radeon-rx-{gen}000"
            return "radeon-rx"
        return None

    def _percentile_rank(scores: list[int], my_score: int) -> int:
        """Return integer percentile 0..100. 90 => faster than 90% of the fleet."""
        if not scores:
            return 0
        below = sum(1 for s in scores if s < my_score)
        return int(round(100 * below / len(scores)))

    @r.get("/benchmarks/fleet-percentile")
    async def benchmarks_fleet_percentile(user: dict = Depends(get_current_user)):
        """Ranks the user's latest benchmark score against the fleet and against
        users with similar CPU/GPU family. Returns null percentiles if not enough
        data is available (fleet<3 or similar<3)."""
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0, "benchmark": 1, "data": 1})
        if not doc:
            return {"available": False}
        my_score = _bench_score(doc.get("benchmark"))
        if my_score is None:
            return {"available": False}
        data = doc.get("data") or {}
        cpu_fam = _cpu_family(data.get("cpu"))
        gpu_fam = _gpu_family(data.get("gpu"))

        cursor = db.pc_specs.find(
            {"benchmark": {"$exists": True}, "user_id": {"$ne": uid}},
            {"_id": 0, "benchmark": 1, "data": 1})
        fleet: list[dict] = []
        async for row in cursor:
            s = _bench_score(row.get("benchmark"))
            if s is None:
                continue
            fleet.append({"score": s, "data": row.get("data") or {}})

        fleet_scores = [x["score"] for x in fleet]
        fleet_percentile = _percentile_rank(fleet_scores, my_score) if len(fleet_scores) >= 3 else None

        similar_scores: list[int] = []
        if cpu_fam or gpu_fam:
            for x in fleet:
                d = x["data"]
                if cpu_fam and _cpu_family(d.get("cpu")) == cpu_fam:
                    similar_scores.append(x["score"])
                elif gpu_fam and _gpu_family(d.get("gpu")) == gpu_fam:
                    similar_scores.append(x["score"])
        similar_percentile = _percentile_rank(similar_scores, my_score) if len(similar_scores) >= 3 else None

        # Delta before/after: compare last two benchmarks in db.benchmarks
        last_two = await db.benchmarks.find(
            {"user_id": uid}, {"_id": 0}
        ).sort("created_at", -1).to_list(2)
        delta = None
        if len(last_two) == 2:
            cur_s = _bench_score(last_two[0])
            prev_s = _bench_score(last_two[1])
            if cur_s is not None and prev_s not in (None, 0):
                pct = round(((cur_s - prev_s) / prev_s) * 100, 1)
                delta = {"current": cur_s, "previous": prev_s, "delta_pct": pct,
                         "improved": cur_s >= prev_s,
                         "previous_ts": last_two[1].get("ts") or last_two[1].get("created_at")}

        return {
            "available": True,
            "my_score": my_score,
            "my_overall": _bench_overall(doc.get("benchmark")),
            "fleet_percentile": fleet_percentile,
            "fleet_count": len(fleet_scores),
            "similar_percentile": similar_percentile,
            "similar_count": len(similar_scores),
            "cpu_family": cpu_fam,
            "gpu_family": gpu_fam,
            "delta": delta,
        }

    # Guardrails: server-side check on the last synced running_apps.
    # Prevents users from starting a benchmark while a game or a stream is running.
    _GAME_KEYWORDS = (
        "fortnite", "valorant", "riotclientservices", "leagueoflegends", "league of legends",
        "cs2", "csgo", "counter-strike", "dota2", "overwatch", "apex", "gta5", "gta v",
        "rocketleague", "warthunder", "warzone", "modernwarfare", "call of duty",
        "battlefield", "rainbowsix", "r6", "eldenring", "witcher", "minecraft",
        "starfield", "cyberpunk", "baldursgate", "pubg", "genshin", "roblox",
    )
    _STREAM_KEYWORDS = ("obs64", "obs32", "obs.exe", "streamlabs", "xsplit",
                        "twitchstudio", "vmix", "wirecast")
    _RECORDER_KEYWORDS = ("nvidia broadcast", "shadowplay", "gamebar", "bandicam",
                          "fraps", "geforce experience")

    @r.get("/benchmarks/guardrails")
    async def benchmarks_guardrails(user: dict = Depends(get_current_user)):
        """Server-side guardrails based on the last known running_apps snapshot.
        Returns warnings but never blocks: the frontend decides whether to nudge
        the user before starting a benchmark."""
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one({"user_id": uid},
                                         {"_id": 0, "running_apps": 1, "running_at": 1})
        running = [str(a).lower() for a in (doc or {}).get("running_apps") or []]
        warnings: list[dict] = []

        def _match(keywords):
            for a in running:
                for k in keywords:
                    if k in a:
                        return a
            return None

        game = _match(_GAME_KEYWORDS)
        stream = _match(_STREAM_KEYWORDS)
        recorder = _match(_RECORDER_KEYWORDS)
        if game:
            warnings.append({"key": "game_running", "detail": game, "severity": "high"})
        if stream:
            warnings.append({"key": "stream_running", "detail": stream, "severity": "high"})
        if recorder:
            warnings.append({"key": "recorder_running", "detail": recorder, "severity": "medium"})

        running_at = (doc or {}).get("running_at")
        age = None
        if running_at:
            age = int(_iso_age(running_at))
            if age > 600:
                warnings.append({"key": "stale_snapshot", "detail": age, "severity": "info"})
        elif not running:
            warnings.append({"key": "no_snapshot", "detail": None, "severity": "info"})

        blocking = any(w["severity"] == "high" for w in warnings)
        return {
            "ok": not blocking,
            "blocking": blocking,
            "warnings": warnings,
            "running_at": running_at,
            "running_age_s": age,
        }

    @r.get("/benchmarks/history")
    async def benchmarks_history(days: int = 30, user: dict = Depends(get_current_user)):
        """Time series of the user's benchmark score/overall over the past N days.
        Used by the Benchmark page sparkline. Capped at 90 days, 500 points."""
        uid = str(user["_id"])
        days = max(1, min(90, int(days or 30)))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.benchmarks.find(
            {"user_id": uid, "created_at": {"$gte": cutoff}},
            {"_id": 0, "user_id": 0}
        ).sort("created_at", 1).to_list(500)
        points = []
        for row in rows:
            after = row.get("after") or row
            points.append({
                "ts": row.get("created_at") or row.get("ts"),
                "score": _bench_score(row),
                "overall": _bench_overall(row),
                "cpu_score": after.get("cpu_score"),
            })
        # Compute simple stats for the header
        vals = [p["score"] for p in points if p["score"] is not None]
        stats = None
        if vals:
            stats = {
                "count": len(vals),
                "min": min(vals),
                "max": max(vals),
                "avg": int(round(sum(vals) / len(vals))),
                "latest": vals[-1],
            }
        return {"points": points, "days": days, "stats": stats}

    @r.get("/pc/sync-history")
    async def pc_sync_history(days: int = 7, user: dict = Depends(get_current_user)):
        """Timeline of the user's recent syncs, sourced from health_history since
        each hardware sync produces a health record. Used by the MyPc dashboard."""
        uid = str(user["_id"])
        days = max(1, min(30, int(days or 7)))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.health_history.find(
            {"user_id": uid, "created_at": {"$gte": cutoff}},
            {"_id": 0, "user_id": 0}
        ).sort("created_at", 1).to_list(200)
        events = [{
            "ts": r.get("created_at"),
            "score": r.get("score"),
            "grade": r.get("grade"),
        } for r in rows if r.get("created_at")]
        # Bucket by day for a mini heatmap in the frontend
        buckets: dict[str, int] = {}
        for e in events:
            day = e["ts"][:10]
            buckets[day] = buckets.get(day, 0) + 1
        return {"events": events, "days": days,
                "by_day": [{"day": d, "count": c} for d, c in sorted(buckets.items())]}

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
        # Return stop signal: the agent's monitor loop reads this and exits cleanly
        # when the user clicks "Stop" on the web dashboard.
        ctrl = await db.monitor_control.find_one({"user_id": rec["user_id"]}, {"_id": 0}) or {}
        return {"ok": True, "stop": bool(ctrl.get("stop_requested"))}

    @r.post("/monitor/stop")
    async def monitor_stop(user: dict = Depends(get_current_user)):
        """Web dashboard: request the local monitor loop to exit cleanly.
        The agent polls /api/agent/telemetry every second and reads the `stop`
        field in the response. Requires agent script from the current backend
        (delivered fresh on every launch via /api/agent/script, so no .exe
        rebuild is needed)."""
        uid = str(user["_id"])
        await db.monitor_control.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, "stop_requested": True, "requested_at": now_iso()}},
            upsert=True)
        return {"ok": True}

    @r.post("/monitor/reset")
    async def monitor_reset(user: dict = Depends(get_current_user)):
        """Clears the stop flag before starting a new monitor session so the
        agent doesn't exit immediately if the previous stop was never acked."""
        uid = str(user["_id"])
        await db.monitor_control.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, "stop_requested": False, "reset_at": now_iso()}},
            upsert=True)
        return {"ok": True}

    @r.get("/monitor/state")
    async def monitor_state(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.monitor_control.find_one({"user_id": uid},
                                                {"_id": 0, "user_id": 0}) or {}
        return {"stop_requested": bool(doc.get("stop_requested")),
                "requested_at": doc.get("requested_at"),
                "reset_at": doc.get("reset_at")}

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

    @r.get("/booster")
    async def get_booster(user: dict = Depends(get_current_user)):
        doc = await db.booster_settings.find_one({"user_id": str(user["_id"])}, {"_id": 0}) or {}
        return {"close_apps": doc.get("close_apps", []), "set_power": doc.get("set_power", True),
                "boost_priority": doc.get("boost_priority", True), "purge_ram": doc.get("purge_ram", True)}

    @r.put("/booster")
    async def set_booster(payload: BoosterInput, user: dict = Depends(get_current_user)):
        await db.booster_settings.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"user_id": str(user["_id"]), "close_apps": payload.close_apps,
                      "set_power": payload.set_power, "boost_priority": payload.boost_priority,
                      "purge_ram": payload.purge_ram, "updated_at": now_iso()}},
            upsert=True)
        return {"ok": True}

    @r.get("/booster/sessions")
    async def booster_sessions(user: dict = Depends(get_current_user)):
        rows = await db.boost_sessions.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(10)
        return {"sessions": rows}

    @r.post("/benchmark/explain")
    async def benchmark_explain(payload: BenchExplainInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0, "benchmark": 1, "data": 1})
        bench = (doc or {}).get("benchmark")
        if not bench:
            raise HTTPException(status_code=404, detail="Nessun benchmark disponibile. Esegui prima un benchmark dal FrameForge Agent.")
        lang = (payload.lang or "it")[:2]
        bench_ts = bench.get("ts") or bench.get("created_at") or ""
        cached = await db.benchmark_explanations.find_one(
            {"user_id": uid, "bench_ts": bench_ts, "lang": lang}, {"_id": 0})
        if cached:
            return {"explanation": cached["text"], "cached": True}
        await _check_ai_rate_limit(uid)
        specs_text = specs_to_text((doc or {}).get("data") or {})
        try:
            text = await ai_engine.explain_benchmark(specs_text, bench.get("before"), bench.get("after") or bench, lang)
        except Exception:
            raise HTTPException(status_code=502, detail="Analisi AI non disponibile al momento. Riprova tra poco.")
        await db.benchmark_explanations.insert_one(
            {"user_id": uid, "bench_ts": bench_ts, "lang": lang, "text": text, "created_at": now_iso()})
        return {"explanation": text, "cached": False}

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
                                detail="Nessun hardware rilevato. Usa il FrameForge Agent per inviare le specifiche.")
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
            msg = str(e)
            if "Budget" in msg and "exceeded" in msg:
                raise HTTPException(status_code=402,
                    detail="Credito LLM esaurito. Ricarica da Profilo -> Universal Key -> Add Balance.")
            raise HTTPException(status_code=502, detail=msg)

    @r.post("/startup/analyze")
    async def startup_analyze(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        startup = (doc or {}).get("startup") or []
        if not startup:
            raise HTTPException(status_code=400, detail="Nessun dato di avvio. Usa il FrameForge Agent.")
        try:
            return await ai_engine.analyze_startup(startup)
        except Exception as e:
            msg = str(e)
            if "Budget" in msg and "exceeded" in msg:
                raise HTTPException(status_code=402,
                    detail="Credito LLM esaurito. Ricarica da Profilo -> Universal Key -> Add Balance.")
            raise HTTPException(status_code=502, detail=msg)

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
                "Write-Host '[ERR ] Token non valido. Riapri la pagina FrameForge Agent.' -ForegroundColor Red",
                media_type="text/plain")
        script = await _build_agent_script(rec["user_id"], profile)
        # Prepend UTF-8 BOM: Windows PowerShell 5.1 legge i .ps1 senza BOM in ANSI (Windows-1252),
        # causando caratteri glitchati per emoji/UTF-8 (es. · … 📚 👤). Il BOM forza UTF-8.
        return PlainTextResponse("\ufeff" + script, media_type="text/plain; charset=utf-8",
                                 headers={"Content-Disposition": "attachment; filename=forgefps.ps1"})

    @r.get("/agent/script-info")
    async def agent_script_info(t: str = "", profile: str = "", user: dict = Depends(get_current_user)):
        rec = await db.agent_tokens.find_one({"token": t})
        user_id = rec["user_id"] if rec else str(user["_id"])
        script = await _build_agent_script(user_id, profile)
        # Include UTF-8 BOM per allinearsi al byte stream servito da /agent/script
        data = ("\ufeff" + script).encode("utf-8")
        return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "filename": "forgefps.ps1"}

    # Modalita' accettate dal FrameForge Agent quando aperto via protocollo frameforge://
    _ALLOWED_URI_MODES = {"optimize", "sync", "benchmark", "monitor", "prematch", "booster", "restore", "gui"}

    @r.get("/agent/launch-uri")
    async def agent_launch_uri(mode: str = "optimize", silent: int = 0, user: dict = Depends(get_current_user)):
        """Genera un URI custom-protocol firmato con HMAC del token dell'utente.
        Il FrameForge Agent (v0.7.0+) registra il protocollo 'frameforge://' su Windows;
        quando l'utente clicca un bottone nella dashboard il browser passa questo URI
        all'exe locale, che verifica la firma con il proprio token e apre la GUI.

        silent=1 (richiede agent v0.7.1+): l'agent esegue PowerShell -WindowStyle
        Hidden senza aprire la GUI. Utile per sync/benchmark 'ambientali'
        triggerati dal web. Il param 'silent' NON e' incluso nell'HMAC per
        retrocompat con v0.7.0 (che verifica 'mode|ts'). Manipolare silent puo'
        solo cambiare UX (GUI vs hidden), non e' un vettore di sicurezza.
        """
        if mode not in _ALLOWED_URI_MODES:
            raise HTTPException(status_code=400, detail=f"mode non valido. Ammessi: {sorted(_ALLOWED_URI_MODES)}")
        silent_flag = 1 if silent else 0
        token = await get_or_create_agent_token(str(user["_id"]))
        ts = int(time.time())
        # HMAC su "mode|ts" (retrocompat v0.7.0). silent viaggia solo come hint.
        msg = f"{mode}|{ts}".encode("utf-8")
        sig = hmac.new(token.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        uri = f"frameforge://launch?mode={mode}&silent={silent_flag}&ts={ts}&sig={sig}"
        return {"uri": uri, "mode": mode, "silent": bool(silent_flag), "ts": ts, "expires_in": 60}

    return r
