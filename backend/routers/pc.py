import logging
import uuid
import io
import os
import re
import hmac
import time
import hashlib
import tempfile
import zipfile
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse

import ai_engine
import push
from database import db, now_iso
from helpers import specs_to_text, compute_health, compute_hw_insights, get_or_create_agent_token, grade_bufferbloat
from desktop_agent import AGENT_SCRIPT
from ps_agent import PS_SCRIPT
from services.gpu_catalog_service import find_gpu_reference, compute_health_vs_reference
from models import SpecsInput, GoalInput, FpsInput, FpsUpgradeInput, PcSpecsInput, TelemetryInput, AlertInput, PrematchInput, NetResultInput, ReportPhaseInput, BoosterInput, BenchExplainInput, AgentDiagInput
from routers.profiles import resolve_tweak_ids, TWEAK_CATALOG, TEMPLATES
from routers.advisor import _check_ai_rate_limit
from plan_gate import require_pro, require_streamer, get_entitlements, plan_402
from devices import resolve_device, device_filter
from hardware import cpu_family as _cpu_family, gpu_family as _gpu_family
from system_changes import build_change_events, analyze_trend, correlate

logger = logging.getLogger("boostpc.pc")

# GPU vs Reference: modelli disponibili nel piano Free (i piu' diffusi). Pro/trofeo = catalogo completo.
FREE_GPU_MODELS = (
    "rtx 3050", "rtx 3060", "rtx 3070", "rtx 3080", "rtx 4060", "rtx 4070",
    "rtx 2060", "rtx 2070", "gtx 1660", "gtx 1650", "gtx 1060",
    "rx 580", "rx 6600", "rx 6700 xt", "rx 7600", "rx 7800 xt", "arc a750", "arc a770",
)


def _is_free_gpu(model: str) -> bool:
    m = (model or "").lower()
    return any(k in m for k in FREE_GPU_MODELS)

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
    "https://github.com/WjRKO/ForgeFPS/releases/download/v0.9.0/forgefps-agent.zip",
)
# SHA256 del ZIP a cui punta AGENT_ZIP_UPSTREAM. Non e' documentazione: viene
# servito al self-updater dell'agent, che rifiuta di aggiornarsi se il file
# scaricato non corrisponde. Finche' l'eseguibile non e' firmato, questo e'
# l'unico controllo di integrita' che sta fra una release e le macchine degli
# utenti — quindi va aggiornato INSIEME all'URL, mai dopo.
AGENT_ZIP_SHA256 = os.environ.get(
    "AGENT_ZIP_SHA256",
    "b88679a9e27e6420bee9f1b59c1b5d2acdaad9cc5100fd3570eefb69a104df7e",
).lower()
# La directory temporanea va chiesta al sistema: con "/tmp" scritto a mano il
# download dell'agent falliva con FileNotFoundError fuori da un container Linux.
_AGENT_ZIP_CACHE_PATH = os.path.join(
    tempfile.gettempdir(),
    f"forgefps-agent-cache-{hashlib.sha256(AGENT_ZIP_UPSTREAM.encode()).hexdigest()[:10]}.zip",
)


def _extract_latest_version() -> str:
    """Estrae la versione dall'URL upstream (unico source of truth).
    Es. '.../releases/download/v0.7.5/...' -> '0.7.5'. Fallback: '0.7.5'.
    Supporta anche tag con typo tipo 'v.0.7.8' (v + punto invece che senza).
    """
    import re as _re
    m = _re.search(r"/download/v\.?(\d+\.\d+\.\d+)/", AGENT_ZIP_UPSTREAM)
    return m.group(1) if m else "0.7.5"


LATEST_AGENT_VERSION = _extract_latest_version()


def _agent_backend_url() -> str:
    """URL che l'agent desktop usa per chiamare le API (ci appende '/api/...').

    In produzione front-end e API stanno sullo stesso dominio, quindi
    FRONTEND_URL va bene ed e' il default storico. In locale invece sono due
    porte diverse e il dev server non inoltra '/api': senza AGENT_BACKEND_URL
    il launcher punterebbe alla porta del front-end e l'agent riceverebbe
    l'HTML della SPA al posto del JSON.
    """
    from settings import get_api_base
    return get_api_base(os.environ.get("FRONTEND_URL", "https://forgefps.dev"))


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


def _zip_digest_ok(data: bytes) -> bool:
    """Il ZIP e' quello che ci aspettiamo? Se non abbiamo un hash configurato
    non blocchiamo nulla: sarebbe un downtime di distribuzione per una
    configurazione mancante."""
    if not AGENT_ZIP_SHA256:
        return True
    return hashlib.sha256(data).hexdigest() == AGENT_ZIP_SHA256


async def _ensure_agent_zip_cached() -> bytes:
    """Fetch (una sola volta) il ZIP dell'agent da GitHub e caching su disco.
    Le chiamate successive lo servono dal filesystem. Se il file cache manca,
    e' inconsistente o non corrisponde all'hash atteso, viene ri-scaricato.

    La verifica dell'hash vale sia in scrittura sia in lettura: un ZIP alterato
    nella cartella temporanea del server verrebbe altrimenti servito a ogni
    utente che scarica l'agent dalla dashboard.
    """
    if os.path.exists(_AGENT_ZIP_CACHE_PATH):
        try:
            with open(_AGENT_ZIP_CACHE_PATH, "rb") as fh:
                data = fh.read()
            zipfile.ZipFile(io.BytesIO(data)).close()  # sanity
            if not _zip_digest_ok(data):
                raise ValueError("hash della cache diverso da AGENT_ZIP_SHA256")
            return data
        except Exception as exc:
            logger.warning("cache ZIP agent scartata (%s): riscarico da upstream", exc)
            try: os.unlink(_AGENT_ZIP_CACHE_PATH)
            except Exception: pass
    import httpx as _httpx
    async with _httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.get(AGENT_ZIP_UPSTREAM)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Upstream ZIP fetch failed ({resp.status_code})")
        data = resp.content
    if not _zip_digest_ok(data):
        # Meglio non distribuire nulla che distribuire un pacchetto che non
        # corrisponde a quello dichiarato agli utenti sulla pagina di download.
        logger.error("ZIP agent da %s non corrisponde a AGENT_ZIP_SHA256: distribuzione bloccata",
                     AGENT_ZIP_UPSTREAM)
        raise HTTPException(status_code=502,
                            detail="Il pacchetto dell'agent non corrisponde all'hash atteso.")
    with open(_AGENT_ZIP_CACHE_PATH, "wb") as fh:
        fh.write(data)
    return data


async def _build_agent_script(user_id: str, profile: str = "", agent_version: str = "") -> str:
    backend = _agent_backend_url()
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
    if not agent_version:
        _specs = await db.pc_specs.find_one(await device_filter(db, user_id), {"agent_version": 1})
        agent_version = (_specs or {}).get("agent_version") or ""
    return (PS_SCRIPT.replace("__BACKEND_URL__", backend)
            .replace("__PROFILE_IDS__", profile_literal)
            .replace("__INSTALLED_AGENT_VER__", (agent_version or "")[:20].replace("'", ""))
            .replace("__LATEST_AGENT_VER__", LATEST_AGENT_VERSION)
            .replace("__AGENT_DL_URL__", AGENT_ZIP_UPSTREAM.replace("'", ""))
            .replace("__PREMATCH_APPS__", pm_apps_literal)
            .replace("__PREMATCH_POWER__", pm_power)
            .replace("__BOOSTER_APPS__", b_apps_literal)
            .replace("__BOOSTER_POWER__", _psb(bs.get("set_power", True)))
            .replace("__BOOSTER_PRIORITY__", _psb(bs.get("boost_priority", True)))
            .replace("__BOOSTER_PURGE__", _psb(bs.get("purge_ram", True))))


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["pc"])
    require_pro_dep = require_pro(get_current_user)
    require_streamer_dep = require_streamer(get_current_user)

    async def require_adv_tweaks(user: dict = Depends(get_current_user)):
        info = await get_entitlements(db, user)
        if not info["entitlements"]["adv_tweaks"]:
            raise plan_402("pro", info["plan_effective"],
                           "I tweak avanzati (BufferBloat, PreMatch, Booster) richiedono il piano Pro — oppure sbloccali con il trofeo 'Tuning Solido' (10 tweak applicati).",
                           code="adv_tweaks_required")
        return user

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
        backend = _agent_backend_url()
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
        backend = _agent_backend_url()
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
        buf = io.BytesIO()
        img.save(buf)
        return _Resp(content=buf.getvalue(), media_type="image/svg+xml",
                     headers={"Cache-Control": "no-store"})

    @r.get("/pc-specs-agent")
    async def get_specs_agent(x_agent_token: str = Header(default=""), x_device: str = Header(default="")):
        """Ritorna pc-specs autenticato via X-Agent-Token (lato PowerShell/exe locale).
        Serve al ps_agent.py optimize block per capire se un primo scan e' necessario:
        se updated_at e' recente (< 15 min) la GUI salta il primo scan.
        """
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        _did = await resolve_device(db, rec["user_id"], x_device)
        doc = await db.pc_specs.find_one(
            {"user_id": rec["user_id"], **({"device_id": _did} if _did else {})}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="No specs yet")
        return doc

    @r.post("/agent/report-specs")
    async def report_specs(data: SpecsInput, x_agent_token: str = Header(default=""), x_device: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        uid = rec["user_id"]
        did = await resolve_device(db, uid, x_device)
        dflt = {"user_id": uid, **({"device_id": did} if did else {})}
        fields = {"user_id": uid, "updated_at": now_iso()}
        if did:
            fields["device_id"] = did
        prev = None
        if data.data is not None or data.startup is not None or data.services_audit is not None:
            # `data` serve al diff di system_changes: pc_specs viene sovrascritto,
            # quindi questo e' l'unico punto in cui esistono insieme vecchio e nuovo.
            prev = await db.pc_specs.find_one(
                dflt,
                {"_id": 0, "data": 1, "startup": 1, "services_audit": 1, "startup_done": 1, "services_done": 1})
        if data.data:
            fields["data"] = data.data
        if data.health is not None:
            fields["health"] = data.health
            _h = compute_health(data.health)
            await db.health_history.insert_one({
                "user_id": uid, **({"device_id": did} if did else {}),
                "score": _h.get("score"), "grade": _h.get("grade"),
                "cpu_temp": _h.get("cpu_temp"), "gpu_temp": _h.get("gpu_temp"),
                "created_at": now_iso()})
        if data.startup is not None:
            # v0.7.4: agenti PowerShell legacy inviavano list[str] (nomi startup),
            # nuovi client possono inviare list[dict] con name/command/user/location.
            # Normalizza tutto a list[dict] con almeno {name} per compatibilita' DB.
            _norm = []
            for item in (data.startup or []):
                if isinstance(item, str):
                    _norm.append({"name": item})
                elif isinstance(item, dict):
                    _norm.append(item)
                # else: skip elementi malformati (nessun errore, invio non blocca)
            fields["startup"] = _norm
            # Tracking 'fatto': voci prima attive che ora risultano disattivate o rimosse
            if prev and _norm:
                from services_kb import is_startup_noise
                _newby = {str(i.get("name") or "").lower(): i for i in _norm if isinstance(i, dict)}
                _done = {str(d.get("name") or "").lower(): d for d in (prev.get("startup_done") or []) if isinstance(d, dict)}
                for _it in (prev.get("startup") or []):
                    if not isinstance(_it, dict) or _it.get("enabled") is False:
                        continue
                    if is_startup_noise(_it.get("name"), _it.get("publisher")):
                        continue
                    _k = str(_it.get("name") or "").lower()
                    _cur = _newby.get(_k)
                    if _k and (_cur is None or _cur.get("enabled") is False):
                        _done.setdefault(_k, {"name": _it.get("name"), "ram_mb": _it.get("ram_mb"), "done_at": now_iso()})
                for _k in list(_done):
                    _cur = _newby.get(_k)
                    if _cur is not None and _cur.get("enabled") is not False:
                        _done.pop(_k)
                fields["startup_done"] = list(_done.values())[:50]
        if data.services_audit is not None:
            _audit = [i for i in data.services_audit if isinstance(i, dict)][:220]
            fields["services_audit"] = _audit
            fields["services_audit_at"] = now_iso()
            # Tracking 'fatto': servizi consigliati (disattiva/valuta) spariti dall'audit
            # = passati a Disabled o disinstallati (l'agent invia solo Auto+Manual).
            # Guard len>=10: evita falsi positivi su scan parziali.
            if prev and len(_audit) >= 10 and prev.get("services_audit"):
                from services_kb import analyze_services
                _prev_items = analyze_services(prev["services_audit"]).get("items", [])
                _new_names = {str(i.get("name") or "").lower() for i in _audit}
                _done = {str(d.get("name") or "").lower(): d for d in (prev.get("services_done") or []) if isinstance(d, dict)}
                for _it in _prev_items:
                    _k = str(_it.get("name") or "").lower()
                    if _it.get("recommendation") in ("disattiva", "valuta") and _k and _k not in _new_names:
                        _done.setdefault(_k, {"name": _it.get("name"), "display": _it.get("display"), "ram_mb": _it.get("ram_mb"), "done_at": now_iso()})
                for _k in list(_done):
                    if _k in _new_names:
                        _done.pop(_k)
                fields["services_done"] = list(_done.values())[:50]
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
            _bs = {**data.boost_session, "user_id": uid, "created_at": now_iso()}
            await db.boost_sessions.insert_one(dict(_bs))
            # Recap post-partita -> notifica dashboard con confronto vs sessione precedente
            _rec = _bs.get("recap") or {}
            if isinstance(_rec, dict) and _rec.get("fps_avg"):
                try:
                    _prev = await db.boost_sessions.find_one(
                        {"user_id": uid, "game": _bs.get("game"),
                         "recap.fps_avg": {"$gt": 0}, "created_at": {"$lt": _bs["created_at"]}},
                        sort=[("created_at", -1)])
                    _mins = round((_bs.get("duration_s") or 0) / 60)
                    _body = f"{_rec['fps_avg']} FPS medi"
                    if _rec.get("fps_low"):
                        _body += f" · 1% low {_rec['fps_low']}"
                    if _rec.get("gpu_temp_max"):
                        _body += f" · GPU max {_rec['gpu_temp_max']}°C"
                    if _prev and (_prev.get("recap") or {}).get("fps_avg"):
                        _d = int(_rec["fps_avg"]) - int(_prev["recap"]["fps_avg"])
                        _body += f" · {'+' if _d >= 0 else ''}{_d} FPS vs sessione precedente"
                    await db.notifications.insert_one({
                        "id": str(uuid.uuid4()),
                        "user_id": uid, "type": "recap",
                        "title": f"Recap {_bs.get('game')} · {_mins} min",
                        "body": _body, "link": "/app/gaming",
                        "created_at": now_iso(), "read": False})
                except Exception as exc:
                    logger.warning("notifica non creata: %s", exc)
        # Diff di sistema: solo se c'era gia' uno snapshot precedente (al primo sync
        # non c'e' nulla da confrontare e ogni campo risulterebbe "cambiato").
        if prev:
            try:
                events = build_change_events(prev, fields.get("data"), fields.get("startup"))
                if events:
                    ts = now_iso()
                    await db.system_changes.insert_many([
                        {**ev, "user_id": uid, **({"device_id": did} if did else {}), "created_at": ts}
                        for ev in events
                    ])
            except Exception as exc:
                logger.warning("system_changes non registrati per %s: %s", uid, exc)
        await db.pc_specs.update_one(dflt, {"$set": fields}, upsert=True)
        # v0.7.7 Milestones: track scan + health + daily active
        try:
            from milestones import bump_counter, track_health_score, track_daily_active, set_flag
            await bump_counter(db, uid, "pc_scans", 1)
            await track_daily_active(db, uid)
            if data.health is not None:
                _score = compute_health(data.health).get("score")
                if _score is not None:
                    await track_health_score(db, uid, int(_score))
            # v0.8.2 Trofei segreti
            _h = datetime.now(timezone.utc).hour
            if _h >= 22 or _h < 4:
                await set_flag(db, uid, "night_owl_earned", True)
            if data.benchmark is not None and (data.benchmark.get("overall") or 0) >= 90:
                await set_flag(db, uid, "speed_demon_earned", True)
            if data.startup is not None or data.services_audit is not None:
                _d = await db.pc_specs.find_one(dflt, {"services_done": 1, "startup_done": 1})
                if len((_d or {}).get("services_done") or []) + len((_d or {}).get("startup_done") or []) >= 10:
                    await set_flag(db, uid, "surgeon_earned", True)
        except Exception as exc:
            logger.debug("flag surgeon_earned non impostato: %s", exc)
        return {"ok": True}

    @r.post("/agent/netresult")
    async def agent_netresult(payload: NetResultInput, x_agent_token: str = Header(default=""), x_device: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        graded = grade_bufferbloat(payload.result)
        _did = await resolve_device(db, rec["user_id"], x_device)
        dflt = {"user_id": rec["user_id"], **({"device_id": _did} if _did else {})}
        await db.net_results.update_one(
            dflt,
            {"$set": {**dflt, "result": graded, "updated_at": now_iso()}},
            upsert=True)
        return {"ok": True, "grade": graded.get("grade")}

    @r.get("/net-result")
    async def net_result(user: dict = Depends(require_adv_tweaks)):
        doc = await db.net_results.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        if not doc:
            return {"available": False}
        return {"available": True, **doc}

    @r.get("/pc-benchmark")
    async def pc_benchmark(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one(await device_filter(db, uid), {"_id": 0, "benchmark": 1})
        history = await db.benchmarks.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(10)
        return {"latest": (doc or {}).get("benchmark"), "history": history}

    @r.get("/pc-benchmark/full")
    async def pc_benchmark_full(user: dict = Depends(require_pro_dep)):
        """Ultimo Full Benchmark (~2-4min run) + storico ultimi 5.

        FEATURE-GATED: piano Pro o superiore (incl. trial attivi).

        Ritorna solo record che contengono il payload `full` (i.e. Full Benchmark,
        non Quick). Se nessun Full Benchmark e' mai stato eseguito -> latest=None.
        """
        uid = str(user["_id"])
        # Ultimo Full Benchmark (record che ha campo `full`)
        latest = await db.benchmarks.find_one(
            {"user_id": uid, "full": {"$exists": True, "$ne": None}},
            {"_id": 0}, sort=[("created_at", -1)],
        )
        # Storico ultimi 5 (per delta e trend)
        history = await db.benchmarks.find(
            {"user_id": uid, "full": {"$exists": True, "$ne": None}},
            {"_id": 0, "user_id": 0},
        ).sort("created_at", -1).to_list(5)
        return {"latest": latest, "history": history}

    @r.get("/gpu-reference")
    async def gpu_reference(user: dict = Depends(get_current_user)):
        """Lookup GPU dell'utente nel catalogo reference + health check contro il suo
        ultimo benchmark. Ritorna None se la GPU non e' nel catalogo (~50 modelli oggi)
        o se non c'e' ancora un benchmark salvato.

        Response:
          {
            "gpu_string": "NVIDIA GeForce RTX 4070 SUPER",
            "reference": { gpu_model, vendor, g3d, timespy, vram_gb, tdp_w, class },
            "health": { status, expected_perf, expected_perf_min/max, delta, ... },
            "measured_perf": 71  # dall'ultimo benchmark
          }
        """
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one(await device_filter(db, uid), {"_id": 0, "data": 1, "benchmark": 1})
        if not doc:
            return {"reference": None, "reason": "no_specs"}
        gpu_str = (doc.get("data") or {}).get("gpu") or ""
        reference = find_gpu_reference(gpu_str)
        if not reference:
            return {"gpu_string": gpu_str, "reference": None, "reason": "not_in_catalog"}
        ent = (await get_entitlements(db, user))["entitlements"]
        if not ent["gpu_reference_full"] and not _is_free_gpu(reference.get("gpu_model")):
            return {"gpu_string": gpu_str, "reference": None, "reason": "plan_required", "locked": True}
        # Measured perf: prende il quick-bench overall/score piu' recente.
        bench = doc.get("benchmark") or {}
        measured = _bench_overall(bench) or _bench_score(bench) or 0
        health = compute_health_vs_reference(reference, measured) if measured else None
        return {
            "gpu_string": gpu_str,
            "reference": reference,
            "health": health,
            "measured_perf": measured,
        }

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
        doc = await db.pc_specs.find_one(await device_filter(db, uid), {"_id": 0, "benchmark": 1, "data": 1})
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
        doc = await db.pc_specs.find_one(await device_filter(db, uid),
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
            {**(await device_filter(db, uid)), "created_at": {"$gte": cutoff}},
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

    # ---------- Watchdog: il boost ha tenuto? ----------

    @r.get("/pc/watchdog")
    async def pc_watchdog(user: dict = Depends(get_current_user)):
        """Esito della verifica differita dell'ultimo intervento (Auto-Pilot / Lab).

        La valutazione la fa il job schedulato `scheduled_perf_watchdog`: qui si
        legge soltanto, cosi' la pagina non dipende dal momento in cui viene aperta.
        """
        uid = str(user["_id"])
        doc = await db.perf_watchdogs.find_one(
            {**(await device_filter(db, uid))}, {"_id": 0, "user_id": 0},
            sort=[("created_at", -1)])
        if not doc:
            return {"available": False}
        return {"available": True, "watchdog": doc}

    # ---------- Cos'e' cambiato nel PC (system_changes) ----------

    _CHANGES_MAX_DAYS = 180

    @r.get("/pc/changes")
    async def pc_changes(days: int = 30, user: dict = Depends(get_current_user)):
        """Timeline dei cambiamenti di configurazione rilevati dai sync dell'agent."""
        uid = str(user["_id"])
        days = max(1, min(_CHANGES_MAX_DAYS, int(days or 30)))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.system_changes.find(
            {**(await device_filter(db, uid)), "created_at": {"$gte": cutoff}},
            {"_id": 0, "user_id": 0},
        ).sort("created_at", -1).to_list(200)
        return {"changes": rows, "days": days, "count": len(rows)}

    async def _perf_series(uid: str, cutoff: str) -> tuple[list[dict], str]:
        """Serie di performance da correlare, in ordine di preferenza.

        Il benchmark e' la misura piu' affidabile ma sporadica; l'health score
        viene registrato a ogni sync, quindi copre le finestre in cui l'utente non
        ha rifatto un benchmark.
        """
        bench = await db.benchmarks.find(
            {"user_id": uid, "created_at": {"$gte": cutoff}}, {"_id": 0},
        ).sort("created_at", 1).to_list(200)
        pts = [{"at": b.get("created_at"), "value": _bench_overall(b) or _bench_score(b)} for b in bench]
        pts = [p for p in pts if p["at"] and p["value"]]
        if len(pts) >= 3:
            return pts, "benchmark"
        rows = await db.health_history.find(
            {**(await device_filter(db, uid)), "created_at": {"$gte": cutoff}}, {"_id": 0},
        ).sort("created_at", 1).to_list(500)
        pts = [{"at": r.get("created_at"), "value": r.get("score")} for r in rows]
        pts = [p for p in pts if p["at"] and p["value"]]
        return pts, "health"

    @r.get("/pc/what-changed")
    async def pc_what_changed(days: int = 30, user: dict = Depends(get_current_user)):
        """Incrocia l'andamento delle performance con i cambiamenti di configurazione.

        Risponde alla domanda che oggi l'utente non puo' porre a nessuna schermata:
        "il PC va peggio di due settimane fa, cosa e' cambiato?".
        Non afferma causalita': elenca i sospetti nella finestra temporale giusta.
        """
        uid = str(user["_id"])
        days = max(7, min(_CHANGES_MAX_DAYS, int(days or 30)))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        series, metric = await _perf_series(uid, cutoff)
        trend = analyze_trend(series)
        changes = await db.system_changes.find(
            {**(await device_filter(db, uid)), "created_at": {"$gte": cutoff}},
            {"_id": 0, "user_id": 0},
        ).sort("created_at", -1).to_list(200)

        if not trend:
            # Senza abbastanza misure non si parla di trend, ma la timeline dei
            # cambiamenti resta utile da mostrare.
            return {"available": False, "reason": "not_enough_samples", "metric": metric,
                    "samples": len(series), "days": days, "changes": changes[:20]}

        suspects = correlate(trend, changes)
        return {
            "available": True,
            "metric": metric,
            "days": days,
            "trend": trend,
            "suspects": suspects[:10],
            "changes": changes[:20],
        }

    async def _gather_snapshot(uid: str) -> dict:
        """Snapshot the current key performance metrics for a Before/After report."""
        snap = {"captured_at": now_iso(), "health_score": None, "health_grade": None,
                "bufferbloat_ms": None, "bufferbloat_grade": None,
                "fps_avg": None, "bench_overall": None}
        specs = await db.pc_specs.find_one(await device_filter(db, uid), {"_id": 0, "health": 1, "benchmark": 1})
        if specs:
            if specs.get("health"):
                h = compute_health(specs["health"])
                snap["health_score"] = h.get("score")
                snap["health_grade"] = h.get("grade")
            bench = specs.get("benchmark") or {}
            snap["bench_overall"] = bench.get("overall") or (bench.get("after") or {}).get("overall")
        net = await db.net_results.find_one(await device_filter(db, uid), {"_id": 0, "result": 1})
        if net and net.get("result"):
            snap["bufferbloat_ms"] = net["result"].get("bufferbloat_ms")
            snap["bufferbloat_grade"] = net["result"].get("grade")
        tel = await db.pc_telemetry.find_one(await device_filter(db, uid), {"_id": 0, "samples": 1})
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
    async def agent_telemetry(payload: TelemetryInput, x_agent_token: str = Header(default=""), x_device: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="Token agent non valido")
        _did = await resolve_device(db, rec["user_id"], x_device)
        dflt = {"user_id": rec["user_id"], **({"device_id": _did} if _did else {})}
        sample = {**payload.sample}
        sample.setdefault("ts", now_iso())
        await db.pc_telemetry.update_one(
            dflt,
            {"$set": {**dflt, "updated_at": now_iso()},
             "$push": {"samples": {"$each": [sample], "$slice": -1800}}},
            upsert=True)
        await _check_temp_alerts(rec["user_id"], sample, _did)
        # v0.7.7 Milestones: track distinct games (Universal Game Detector)
        try:
            _game_key = sample.get("steam_appid") or sample.get("game_name")
            if _game_key:
                from milestones import add_unique
                await add_unique(db, rec["user_id"], "games_detected", str(_game_key))
        except Exception as exc:
            logger.debug("gioco rilevato non registrato: %s", exc)
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
    async def pc_telemetry(user: dict = Depends(require_pro_dep)):
        doc = await db.pc_telemetry.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        if not doc:
            return {"samples": [], "updated_at": None, "live": False}
        live = False
        try:
            from datetime import datetime, timezone
            live = (datetime.now(timezone.utc) - datetime.fromisoformat(doc["updated_at"])).total_seconds() < 12
        except Exception:
            live = False
        return {"samples": doc.get("samples", [])[-60:], "updated_at": doc.get("updated_at"), "live": live}

    async def _check_temp_alerts(uid, sample, did=None):
        cfg = await db.alert_settings.find_one({"user_id": uid}) or {}
        if not cfg.get("enabled", True):
            return
        dev_label = ""
        if did:
            _dev = await db.devices.find_one({"user_id": uid, "device_id": did}, {"name": 1})
            if _dev and _dev.get("name"):
                dev_label = f"[{_dev['name']}] "
        suffix = f"_{did}" if did else ""
        cpu_max = cfg.get("cpu_max", 90)
        gpu_max = cfg.get("gpu_max", 85)
        to_send = []
        ct, gt = sample.get("cpu_temp"), sample.get("gpu_temp")
        if ct and ct >= cpu_max and _iso_age(cfg.get(f"last_cpu_alert{suffix}", "")) > 300:
            to_send.append(("cpu", f"{dev_label}CPU a {ct}°C (soglia {cpu_max}°C). Riduci il carico o controlla il raffreddamento."))
        if gt and gt >= gpu_max and _iso_age(cfg.get(f"last_gpu_alert{suffix}", "")) > 300:
            to_send.append(("gpu", f"{dev_label}GPU a {gt}°C (soglia {gpu_max}°C). Riduci il carico o controlla il raffreddamento."))
        for metric, body in to_send:
            try:
                await push.send_push_to_user(db, uid, {"title": "🔥 Temperatura critica!", "body": body, "url": "/app/live"})
            except Exception as exc:
                logger.warning("push di temperatura critica non inviata a %s: %s", uid, exc)
            await db.alert_settings.update_one({"user_id": uid}, {"$set": {"user_id": uid, f"last_{metric}_alert{suffix}": now_iso()}}, upsert=True)

    @r.get("/alerts")
    async def get_alerts(user: dict = Depends(get_current_user)):
        cfg = await db.alert_settings.find_one({"user_id": str(user["_id"])}, {"_id": 0}) or {}
        return {"enabled": cfg.get("enabled", True), "cpu_max": cfg.get("cpu_max", 90), "gpu_max": cfg.get("gpu_max", 85)}

    @r.put("/alerts")
    async def set_alerts(payload: AlertInput, user: dict = Depends(get_current_user)):
        info = await get_entitlements(db, user)
        if not info["is_pro"]:
            raise plan_402("pro", info["plan_effective"], "Gli alert termici automatici richiedono il piano Pro.")
        await db.alert_settings.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"user_id": str(user["_id"]), "enabled": payload.enabled,
                      "cpu_max": payload.cpu_max, "gpu_max": payload.gpu_max}},
            upsert=True)
        return {"ok": True}

    @r.get("/pc-specs")
    async def get_specs(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        # Flag 'noise' a read-time: voci di sistema/driver non azionabili (KB aggiornabile)
        if doc and isinstance(doc.get("startup"), list):
            from services_kb import is_startup_noise
            for s in doc["startup"]:
                if isinstance(s, dict) and is_startup_noise(s.get("name"), s.get("publisher")):
                    s["noise"] = True
        return doc

    @r.post("/pc-specs")
    async def save_specs(payload: PcSpecsInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        existing = await db.pc_specs.find_one(await device_filter(db, uid))
        base = (existing or {}).get("data", {}) if existing else {}
        merged = {**base, **{k: v for k, v in payload.data.items() if v not in (None, "")}}
        await db.pc_specs.update_one(
            await device_filter(db, uid),
            {"$set": {"user_id": uid, "data": merged, "source": payload.source, "updated_at": now_iso()}},
            upsert=True)
        return await db.pc_specs.find_one(await device_filter(db, uid), {"_id": 0})

    @r.get("/prematch")
    async def get_prematch(user: dict = Depends(require_adv_tweaks)):
        doc = await db.prematch_settings.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        specs = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0, "running_apps": 1, "running_at": 1})
        running = {"running_apps": (specs or {}).get("running_apps", []), "running_at": (specs or {}).get("running_at")}
        if not doc:
            return {"close_apps": DEFAULT_PREMATCH_APPS, "set_power": True, **running}
        return {"close_apps": doc.get("close_apps", DEFAULT_PREMATCH_APPS), "set_power": doc.get("set_power", True), **running}

    @r.get("/booster")
    async def get_booster(user: dict = Depends(require_adv_tweaks)):
        doc = await db.booster_settings.find_one({"user_id": str(user["_id"])}, {"_id": 0}) or {}
        return {"close_apps": doc.get("close_apps", []), "set_power": doc.get("set_power", True),
                "boost_priority": doc.get("boost_priority", True), "purge_ram": doc.get("purge_ram", True)}

    @r.put("/booster")
    async def set_booster(payload: BoosterInput, user: dict = Depends(require_adv_tweaks)):
        await db.booster_settings.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"user_id": str(user["_id"]), "close_apps": payload.close_apps,
                      "set_power": payload.set_power, "boost_priority": payload.boost_priority,
                      "purge_ram": payload.purge_ram, "updated_at": now_iso()}},
            upsert=True)
        return {"ok": True}

    @r.get("/booster/sessions")
    async def booster_sessions(user: dict = Depends(require_adv_tweaks)):
        rows = await db.boost_sessions.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).to_list(10)
        return {"sessions": rows}

    @r.post("/benchmark/explain")
    async def benchmark_explain(payload: BenchExplainInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.pc_specs.find_one(await device_filter(db, uid), {"_id": 0, "benchmark": 1, "data": 1})
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
    async def set_prematch(payload: PrematchInput, user: dict = Depends(require_adv_tweaks)):
        await db.prematch_settings.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"user_id": str(user["_id"]), "close_apps": payload.close_apps, "set_power": payload.set_power}},
            upsert=True)
        return {"ok": True}

    @r.get("/games")
    async def get_games(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0, "games": 1, "updated_at": 1})
        return {"games": (doc or {}).get("games", []), "updated_at": (doc or {}).get("updated_at")}

    @r.get("/hw-insights")
    async def hw_insights(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0, "data": 1})
        d = (doc or {}).get("data") or {}
        if not d:
            return {"available": False, "insights": []}
        return {"available": True, "insights": compute_hw_insights(d)}

    @r.get("/game/details/{appid}")
    async def game_details(appid: str, user: dict = Depends(get_current_user)):
        """v0.7.7 Universal Game Detector — recupera info Steam Store (cover, genere, dev)
        con cache MongoDB 7 giorni. Riduce chiamate esterne e latenza sul dashboard live."""
        if not appid or not appid.isdigit() or len(appid) > 12:
            raise HTTPException(400, "invalid appid")
        cached = await db.game_cache.find_one({"appid": appid}, {"_id": 0})
        if cached and cached.get("cached_at"):
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["cached_at"])).days
                if age < 7:
                    return cached
            except Exception as exc:
                logger.debug("data della cache gioco non interpretabile: %s", exc)
        import httpx as _httpx
        try:
            async with _httpx.AsyncClient(timeout=8.0, follow_redirects=True) as c:
                resp = await c.get(
                    f"https://store.steampowered.com/api/appdetails",
                    params={"appids": appid, "l": "english", "cc": "us"},
                    headers={"User-Agent": "FrameForge/1.0"},
                )
            j = resp.json() if resp.status_code == 200 else {}
            node = (j or {}).get(appid) or {}
            if not node.get("success"):
                info = {"appid": appid, "found": False, "cached_at": now_iso()}
            else:
                d = node.get("data") or {}
                info = {
                    "appid": appid,
                    "found": True,
                    "name": d.get("name"),
                    "header_image": d.get("header_image"),
                    "capsule_image": d.get("capsule_image"),
                    "developers": (d.get("developers") or [])[:3],
                    "publishers": (d.get("publishers") or [])[:3],
                    "genres": [g.get("description") for g in (d.get("genres") or []) if g.get("description")][:5],
                    "release_date": (d.get("release_date") or {}).get("date"),
                    "cached_at": now_iso(),
                }
        except Exception as e:
            info = {"appid": appid, "found": False, "error": str(e)[:200], "cached_at": now_iso()}
        try:
            await db.game_cache.update_one({"appid": appid}, {"$set": info}, upsert=True)
        except Exception as exc:
            logger.debug("cache del gioco non aggiornata: %s", exc)
        # strip mongo _id from returned dict
        info.pop("_id", None)
        return info

    @r.get("/pc-health")
    async def pc_health(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        if not doc or not doc.get("health"):
            return {"available": False}
        out = {**compute_health(doc["health"]), "available": True}
        try:
            gpu = ((doc.get("data") or {}).get("gpu") or "").lower()
            is_nv = any(k in gpu for k in ("nvidia", "rtx", "gtx", "geforce"))
            is_amd = any(k in gpu for k in ("radeon", "rx ", "amd"))
            vend = "nvidia" if is_nv else ("amd" if is_amd else None)
            scores = []
            async for d in db.pc_specs.find({"health": {"$ne": None}}, {"health": 1, "data.gpu": 1}):
                if vend:
                    g = ((d.get("data") or {}).get("gpu") or "").lower()
                    match = any(k in g for k in ("nvidia", "rtx", "gtx", "geforce")) if vend == "nvidia" \
                        else any(k in g for k in ("radeon", "rx ", "amd"))
                    if not match:
                        continue
                h = compute_health(d["health"])
                if h.get("score") is not None:
                    scores.append(h["score"])
            if len(scores) >= 5:
                me = out.get("score") or 0
                pct = round(sum(1 for s in scores if s <= me) / len(scores) * 100)
                out["fleet"] = {"percentile": pct, "n": len(scores), "vendor": vend or "all"}
        except Exception as exc:
            logger.debug("percentile flotta non calcolato: %s", exc)
        try:
            tel = await db.pc_telemetry.find_one(await device_filter(db, str(user["_id"])), {"samples": {"$slice": -300}})
            samples = (tel or {}).get("samples") or []
            clocks = [s.get("gpu_clock") for s in samples
                      if isinstance(s.get("gpu_clock"), (int, float)) and s.get("gpu_clock") > 0]
            if clocks:
                peak = max(clocks)
                ev = [s for s in samples
                      if isinstance(s.get("gpu_clock"), (int, float)) and s.get("gpu_clock") > 0
                      and (s.get("gpu_util") or 0) >= 90 and s["gpu_clock"] < peak * 0.92
                      and (s.get("gpu_temp") or 0) >= 80]
                out["throttling"] = {"checked": True, "detected": len(ev) >= 5, "events": len(ev),
                                     "peak_clock": peak,
                                     "max_temp": max(((s.get("gpu_temp") or 0) for s in samples), default=0)}
        except Exception as exc:
            logger.debug("analisi throttling non completata: %s", exc)
        return out

    @r.get("/health-history")
    async def health_history(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        rows = await db.health_history.find(await device_filter(db, uid), {"_id": 0, "user_id": 0}) \
            .sort("created_at", -1).limit(90).to_list(90)
        rows.reverse()
        ent = (await get_entitlements(db, user))["entitlements"]
        if not ent["history_90d"]:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            rows = [p for p in rows if str(p.get("created_at") or "") >= cutoff]
            return {"points": rows, "limited_days": 7}
        return {"points": rows}

    @r.post("/upgrade/analyze")
    async def upgrade_analyze(data: GoalInput, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        if not specs or not specs.get("data"):
            raise HTTPException(status_code=400,
                                detail="Nessun hardware rilevato. Usa il FrameForge Agent per inviare le specifiche.")
        try:
            return await ai_engine.generate_upgrade(specs_to_text(specs), data.budget, data.goal)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    async def _fleet_fps(uid: str, game: str):
        specs = await db.pc_specs.find_one(await device_filter(db, uid), {"data.gpu": 1})
        gpu = (((specs or {}).get("data") or {}).get("gpu") or "")
        m = re.search(r"(rtx\s*\d{4}\s*(?:ti|super)?|gtx\s*\d{3,4}\s*(?:ti|super)?|rx\s*\d{4}\s*(?:xtx|xt)?|arc\s*\w?\d{3})", gpu, re.I)
        if not m or not game:
            return None
        token = re.sub(r"\s+", "", m.group(1)).lower()
        gl = re.sub(r"[^a-z0-9]", "", game.lower())[:12]
        if len(gl) < 3:
            return None
        vals, users = [], set()
        async for t in db.pc_telemetry.find({}, {"user_id": 1, "samples": {"$slice": -300}}):
            sp = await db.pc_specs.find_one({"user_id": t["user_id"]}, {"data.gpu": 1})
            g2 = re.sub(r"\s+", "", (((sp or {}).get("data") or {}).get("gpu") or "")).lower()
            if token not in g2:
                continue
            fs = [s["fps"] for s in (t.get("samples") or [])
                  if isinstance(s.get("fps"), (int, float)) and s.get("fps") > 0
                  and gl in re.sub(r"[^a-z0-9]", "", str(s.get("game", "")).lower())]
            if len(fs) >= 30:
                fs.sort()
                vals.append(fs[len(fs) // 2])
                users.add(t["user_id"])
        if len(vals) >= 2 and len(users) >= 2:
            vals.sort()
            return {"fps_median": round(vals[len(vals) // 2]), "sessions": len(vals),
                    "users": len(users), "gpu": token}
        return None

    @r.post("/fps/estimate")
    async def fps_estimate(data: FpsInput, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        try:
            fleet = await _fleet_fps(str(user["_id"]), data.game)
        except Exception:
            fleet = None
        try:
            out = await ai_engine.estimate_fps(specs_to_text(specs) if specs else "", data.game, data.resolution)
            if isinstance(out, dict):
                out["fleet"] = fleet
                out["source"] = "fleet+ai" if fleet else "ai"
            return out
        except Exception as e:
            msg = str(e)
            if "Budget" in msg and "exceeded" in msg:
                raise HTTPException(status_code=402,
                    detail="Credito LLM esaurito. Ricarica da Profilo -> Universal Key -> Add Balance.")
            raise HTTPException(status_code=502, detail=msg)

    @r.post("/fps/upgrade-compare")
    async def fps_upgrade_compare(data: FpsUpgradeInput, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        if not specs or not specs.get("data"):
            raise HTTPException(status_code=400,
                                detail="Nessun hardware rilevato. Usa il FrameForge Agent per inviare le specifiche.")
        try:
            return await ai_engine.estimate_fps_upgrade(specs_to_text(specs), data.game, data.resolution, data.upgrades)
        except Exception as e:
            msg = str(e)
            if "Budget" in msg and "exceeded" in msg:
                raise HTTPException(status_code=402,
                    detail="Credito LLM esaurito. Ricarica da Profilo -> Universal Key -> Add Balance.")
            raise HTTPException(status_code=502, detail=msg)

    @r.get("/services/analyze")
    async def services_analyze(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        audit = (doc or {}).get("services_audit") or []
        if not audit:
            return {"available": False}
        from services_kb import analyze_services
        res = analyze_services(audit, (doc or {}).get("data"), (doc or {}).get("games"))
        return {"available": True, "audited_at": (doc or {}).get("services_audit_at"),
                "done": (doc or {}).get("services_done") or [], **res}

    @r.post("/startup/analyze")
    async def startup_analyze(user: dict = Depends(get_current_user)):
        doc = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"_id": 0})
        startup = (doc or {}).get("startup") or []
        if not startup:
            raise HTTPException(status_code=400, detail="Nessun dato di avvio. Usa il FrameForge Agent.")
        from services_kb import is_startup_noise
        active = [s for s in startup if not (isinstance(s, dict) and (
            s.get("enabled") is False or is_startup_noise(s.get("name"), s.get("publisher"))))]
        if not active:
            return {"items": [], "summary": "Tutti i programmi in avvio risultano già disattivati: nessuna azione necessaria."}
        try:
            return await ai_engine.analyze_startup(active)
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

    @r.post("/agent/diag")
    async def agent_diag(payload: AgentDiagInput, x_agent_token: str = Header(default="")):
        """Eventi diagnostici dell'agent, non telemetria d'uso.

        Esiste per una domanda precisa: il fallback WinForms della GUI vale le
        451 righe che costa? Oggi scatta solo se il server locale non parte, e
        nessuno sa quanto succeda davvero. Con questo, fra un mese lo si sa.
        La collezione e' a sola scrittura dall'agent e si interroga a mano:
            db.agent_diagnostics.aggregate([{$group:{_id:"$event",n:{$sum:1}}}])
        """
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="token agent non valido")
        detail = {}
        for k, v in (payload.detail or {}).items():
            if len(detail) >= 12 or not isinstance(v, (int, float, str, bool)):
                continue
            detail[str(k)[:40]] = v if not isinstance(v, str) else v[:300]
        await db.agent_diagnostics.insert_one({
            "user_id": rec["user_id"], "event": payload.event,
            "detail": detail, "at": now_iso(),
        })
        return {"ok": True}

    @r.get("/agent/latest-version")
    async def agent_latest_version():
        """Endpoint pubblico usato dal self-updater dell'agent (che non ha auth cookie).
        Ritorna versione, URL e SHA256 della release corrente. Nessun dato
        utente. Cachable a livello CDN.

        L'hash e' la parte che conta: l'agent rifiuta di applicare un
        aggiornamento il cui ZIP non corrisponda. Finche' l'eseguibile non e'
        firmato, questo e' l'unico controllo di integrita' sul percorso di
        aggiornamento automatico — quello che avviene senza che l'utente guardi.
        """
        return {
            "version": LATEST_AGENT_VERSION,
            "download_url": AGENT_ZIP_UPSTREAM,
            "sha256": AGENT_ZIP_SHA256,
        }

    @r.get("/agent/script")
    async def agent_script(t: str = "", profile: str = "", x_agent_version: str = Header(default=""), x_device: str = Header(default="")):
        rec = await db.agent_tokens.find_one({"token": t})
        if not rec:
            return PlainTextResponse(
                "Write-Host '[ERR ] Token non valido. Riapri la pagina FrameForge Agent.' -ForegroundColor Red",
                media_type="text/plain")
        # v0.7.6: registra la versione dell'agent locale se dichiarata (solo v0.7.6+
        # invia questo header). Se assente -> agent vecchio, resta "unknown" nel
        # doc utente e il banner di update apparira' finche' non aggiornano.
        if x_agent_version and len(x_agent_version) <= 20:
            try:
                _did = await resolve_device(db, rec["user_id"], x_device)
                await db.pc_specs.update_one(
                    {"user_id": rec["user_id"], **({"device_id": _did} if _did else {})},
                    {"$set": {"agent_version": x_agent_version, "agent_version_at": now_iso()}},
                    upsert=True,
                )
            except Exception as exc:
                logger.debug("versione agent non registrata: %s", exc)
        script = await _build_agent_script(rec["user_id"], profile, x_agent_version)
        # Prepend UTF-8 BOM: Windows PowerShell 5.1 legge i .ps1 senza BOM in ANSI (Windows-1252),
        # causando caratteri glitchati per emoji/UTF-8 (es. · … 📚 👤). Il BOM forza UTF-8.
        return PlainTextResponse("\ufeff" + script, media_type="text/plain; charset=utf-8",
                                 headers={"Content-Disposition": "attachment; filename=forgefps.ps1"})

    @r.get("/agent/status")
    async def agent_status(user: dict = Depends(get_current_user)):
        """Ritorna lo stato dell'agent locale dell'utente: versione installata (se
        rilevata dall'header X-Agent-Version) vs versione ultima disponibile.
        Usato dal banner "Aggiorna l'agent" nella dashboard."""
        latest = LATEST_AGENT_VERSION
        specs = await db.pc_specs.find_one(await device_filter(db, str(user["_id"])), {"agent_version": 1, "updated_at": 1})
        installed = (specs or {}).get("agent_version") or None
        has_ever_run = bool(specs and specs.get("updated_at"))
        # Outdated se:
        #  - l'utente ha usato l'agent almeno una volta (ha pc_specs.updated_at)
        #  - E non ha mai riportato la versione (agent < 0.7.6) OPPURE riportata < latest
        def _lt(a: str, b: str) -> bool:
            try:
                return tuple(int(x) for x in a.split(".")) < tuple(int(x) for x in b.split("."))
            except Exception:
                return False
        is_outdated = bool(has_ever_run and (not installed or _lt(installed, latest)))
        return {
            "installed_version": installed,
            "latest_version": latest,
            "is_outdated": is_outdated,
            "has_ever_run": has_ever_run,
            "download_url": AGENT_ZIP_UPSTREAM,
        }

    # Modalita' accettate dal FrameForge Agent quando aperto via protocollo frameforge://
    _ALLOWED_URI_MODES = {"optimize", "sync", "benchmark", "bufferbloat", "fullbench", "monitor", "prematch", "booster", "restore", "gui", "apply-one", "restore-one", "lab", "autopilot"}

    @r.get("/agent/script-info")
    async def agent_script_info(t: str = "", profile: str = "", user: dict = Depends(get_current_user)):
        rec = await db.agent_tokens.find_one({"token": t})
        user_id = rec["user_id"] if rec else str(user["_id"])
        script = await _build_agent_script(user_id, profile)
        # Include UTF-8 BOM per allinearsi al byte stream servito da /agent/script
        data = ("\ufeff" + script).encode("utf-8")
        return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "filename": "forgefps.ps1"}

    # Modalita' accettate dal FrameForge Agent quando aperto via protocollo frameforge://
    _ALLOWED_URI_MODES = {"optimize", "sync", "benchmark", "bufferbloat", "fullbench", "monitor", "prematch", "booster", "restore", "gui", "lab", "autopilot"}

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
        # Alias retrocompat: l'exe <=0.8.0 ha una whitelist silent hardcoded che NON
        # include 'autopilot' (usciva muto -> timeout "non risponde" sul web).
        # 'cleanup' e' whitelistato nell'exe e libero nello script PS, che lo mappa
        # ad autopilot lato server. Rimuovere quando la fleet sara' su >=0.8.1.
        uri_mode = "cleanup" if mode == "autopilot" else mode
        silent_flag = 1 if silent else 0
        token = await get_or_create_agent_token(str(user["_id"]))
        ts = int(time.time())
        # HMAC su "mode|ts" (retrocompat v0.7.0). silent viaggia solo come hint.
        msg = f"{uri_mode}|{ts}".encode("utf-8")
        sig = hmac.new(token.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        uri = f"frameforge://launch?mode={uri_mode}&silent={silent_flag}&ts={ts}&sig={sig}"
        return {"uri": uri, "mode": mode, "silent": bool(silent_flag), "ts": ts, "expires_in": 60}

    return r
