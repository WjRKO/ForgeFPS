import os
import logging

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import db, client
from auth import build_auth_router, seed_admin
from helpers import refresh_product_price
import watchdog
from settings import get_cors_origins, get_cors_origin_regex
from routers import advisor, builds, products, pc, push_routes, admin, profiles, discord as discord_router, subscriptions, payments, overlay, community, milestones, lab, missions, devices as devices_router, autopilot as autopilot_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("boostpc")

app = FastAPI(title="FrameForge")
auth_router, get_current_user = build_auth_router(db)
scheduler = AsyncIOScheduler()

app.include_router(auth_router)
for module in (advisor, builds, products, pc, push_routes, admin, profiles, discord_router, subscriptions, payments, overlay, community, milestones, lab, missions, devices_router, autopilot_router):
    app.include_router(module.build(get_current_user))


@app.get("/api/")
async def root():
    return {"message": "FrameForge online"}


@app.get("/health")
async def health():
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=get_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Overlay HTML pages need permissive CSP + iframe embed (per OBS Browser Source
    # in ambienti di preview con iframe). Skippiamo l'X-Frame-Options e usiamo un
    # CSP piu' permissivo per queste route.
    path = request.url.path
    is_overlay_html = (
        path.startswith("/api/overlay/") and not (path.endswith("/data") or path.endswith("/config") or path.endswith("/token"))
    ) or (
        # v0.7.7: Milestone OBS overlay
        path.startswith("/api/milestones/overlay/") and not path.endswith("/poll")
    )
    if is_overlay_html:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "frame-ancestors *;"
        )
        # NO X-Frame-Options: gli overlay devono poter essere embeddati (OBS/iframe preview)
    else:
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response

PRICE_CHECK_BATCH = 100


async def scheduled_price_check():
    logger.info("Running scheduled price check...")
    cursor = db.products.find({"url": {"$ne": ""}}).sort("updated_at", 1).limit(PRICE_CHECK_BATCH)
    async for product in cursor:
        try:
            await refresh_product_price(product)
        except Exception as e:
            logger.warning(f"Price check failed for {product.get('id')}: {e}")


async def scheduled_trial_reminders():
    """Ogni giorno alle 09:00 UTC: manda email di reminder ai trial in scadenza T-3 e T-1.

    Idempotent via campo `trial_reminder_sent_at` sul doc user.
    """
    from datetime import datetime, timezone, timedelta
    from email_service import send_trial_ending
    now = datetime.now(timezone.utc)
    logger.info("Running scheduled trial reminders...")

    cursor = db.users.find({
        "plan": {"$in": ["pro_trial", "streamer_trial"]},
        "trial_expires_at": {"$ne": None},
    })
    sent = 0
    async for user in cursor:
        try:
            exp_str = user.get("trial_expires_at")
            if not exp_str:
                continue
            exp = datetime.fromisoformat(exp_str.replace("Z", "+00:00")) if isinstance(exp_str, str) else exp_str
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            delta = exp - now
            days_left = delta.days + (1 if delta.seconds > 0 else 0)
            if days_left not in (1, 3):
                continue
            # Idempotency: non rimandare se gia' inviato per questa soglia
            already = (user.get("trial_reminder_sent") or {}).get(f"t_{days_left}")
            if already:
                continue
            await send_trial_ending(user["email"], user.get("name", ""), user.get("plan", "pro_trial"), days_left)
            await db.users.update_one({"_id": user["_id"]}, {"$set": {
                f"trial_reminder_sent.t_{days_left}": now.isoformat(),
            }})
            sent += 1
        except Exception as e:
            logger.warning("trial reminder failed for %s: %s", user.get("email"), e)
    logger.info("Trial reminders sent: %d", sent)


async def _ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    await db.products.create_index("user_id")
    await db.price_history.create_index("product_id")
    await db.agent_tokens.create_index("token")
    await db.agent_tokens.create_index("user_id")
    await db.push_subscriptions.create_index("user_id")
    await db.pc_specs.create_index("user_id")

    # Collezioni per-utente che prima non avevano indici: ogni lettura era una
    # scansione completa. Le forme sono ricavate dalle query esistenti, non
    # ipotizzate: dove c'e' un ordinamento, l'indice e' composto e lo include,
    # cosi' Mongo copre filtro e sort con la stessa struttura.
    await db.user_progress.create_index("user_id")
    await db.user_missions.create_index("user_id")
    # usato dal job delle streak, che filtra sui due campi annidati
    await db.user_missions.create_index([("daily.streak", 1), ("daily.streak_day", 1)])
    await db.devices.create_index([("user_id", 1), ("device_id", 1)])
    await db.devices.create_index([("user_id", 1), ("first_seen", 1)])
    # due indici e non uno composto: device_filter() a volte filtra per solo
    # user_id, e in quel caso un indice (user_id, device_id, created_at) non
    # riuscirebbe a servire l'ordinamento.
    await db.health_history.create_index([("user_id", 1), ("created_at", -1)])
    await db.health_history.create_index([("user_id", 1), ("device_id", 1), ("created_at", -1)])
    await db.system_changes.create_index([("user_id", 1), ("created_at", -1)])
    await db.system_changes.create_index([("user_id", 1), ("device_id", 1), ("created_at", -1)])
    await db.perf_watchdogs.create_index([("source", 1), ("ref_id", 1)], unique=True)
    await db.perf_watchdogs.create_index([("status", 1), ("due_at", 1)])
    await db.perf_watchdogs.create_index([("user_id", 1), ("created_at", -1)])
    await db.benchmarks.create_index([("user_id", 1), ("created_at", -1)])
    await db.pc_telemetry.create_index([("user_id", 1), ("device_id", 1)])
    await db.net_results.create_index([("user_id", 1), ("created_at", -1)])
    await db.boost_sessions.create_index("user_id")
    await db.notifications.create_index([("user_id", 1), ("read", 1)])
    await db.chat_messages.create_index([("user_id", 1), ("created_at", -1)])
    await db.chat_messages.create_index("session_id")
    await db.lab_sessions.create_index([("user_id", 1), ("status", 1)])
    await db.lab_sessions.create_index("session_id")
    await db.overlay_tokens.create_index("token")
    await db.overlay_tokens.create_index("user_id")
    await db.autopilot_runs.create_index([("user_id", 1), ("created_at", -1)])


#: giorni di storico salute conservati. Va tenuto sopra ai limiti che l'app
#: espone davvero: /api/health-history restituisce al massimo gli ultimi 90
#: record e la timeline arriva a 30 giorni, quindi 180 e' abbondante.
HEALTH_HISTORY_RETENTION_DAYS = int(os.environ.get("HEALTH_HISTORY_RETENTION_DAYS", "180"))


async def scheduled_prune_health_history():
    """Cancella i record di health_history piu' vecchi della finestra di retention.

    E' l'unica collezione storica senza tetto: `price_history` viene ripulita
    alla rimozione del prodotto e la telemetria e' limitata da uno $slice, ma
    qui ogni scansione dell'agent inseriva un documento che restava per sempre.
    Non si puo' usare un indice TTL perche' `created_at` e' una stringa ISO e
    non una data BSON; il confronto lessicografico su ISO-8601 in UTC pero'
    coincide con quello cronologico, quindi il filtro e' corretto.
    """
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=HEALTH_HISTORY_RETENTION_DAYS)).isoformat()
    try:
        res = await db.health_history.delete_many({"created_at": {"$lt": cutoff}})
        if res.deleted_count:
            logging.info("prune health_history: rimossi %s record antecedenti a %s",
                         res.deleted_count, cutoff)
    except Exception as exc:
        logging.warning("prune health_history fallito: %s", exc)


async def scheduled_streak_reminders():
    """~19:00 IT (17:00 UTC): push a chi ha una streak attiva ma nessuna daily completata oggi."""
    from missions import _day_id, _yesterday_id
    import push
    today, yday = _day_id(), _yesterday_id()
    cur = db.user_missions.find({"daily.streak": {"$gte": 1}, "daily.streak_day": yday,
                                 "daily.reminder_day": {"$ne": today}})
    async for doc in cur:
        uid = doc["user_id"]
        streak = int((doc.get("daily") or {}).get("streak") or 0)
        try:
            await push.send_push_to_user(db, uid, {
                "title": "🔥 Streak a rischio!",
                "body": f"La tua streak di {streak} giorni scade a mezzanotte. Completa una missione giornaliera per salvarla.",
                "url": "/app/milestones"})
        except Exception:
            logger.warning("Streak reminder push failed for %s", uid)
        await db.user_missions.update_one(
            {"user_id": uid}, {"$set": {"daily.reminder_day": today}})


async def _watchdog_baseline(uid: str, device_id, at_iso: str):
    """Health score piu' recente al momento dell'intervento (entro 3 giorni prima)."""
    from datetime import timedelta
    ts = watchdog.parse_ts(at_iso)
    if not ts:
        return None, None
    floor = (ts - timedelta(days=3)).isoformat()
    q = {"user_id": uid, "created_at": {"$lte": at_iso, "$gte": floor}}
    if device_id:
        q["device_id"] = device_id
    row = await db.health_history.find_one(q, {"_id": 0, "score": 1, "created_at": 1},
                                           sort=[("created_at", -1)])
    if row and isinstance(row.get("score"), (int, float)):
        return float(row["score"]), row["created_at"]
    return None, None


async def _watchdog_create_missing(now):
    """Crea un watchdog per ogni intervento recente che non ne ha ancora uno.

    Riconciliazione invece di hook dentro autopilot.py / lab.py: un solo punto da
    mantenere, e gli interventi conclusi mentre il servizio era giu' non si perdono.
    """
    from datetime import timedelta
    cutoff = (now - timedelta(days=watchdog.GIVE_UP_AFTER_DAYS)).isoformat()
    created = 0

    async def _add(uid, device_id, source, ref_id, at_iso, baseline, baseline_at):
        nonlocal created
        try:
            await db.perf_watchdogs.insert_one({
                "user_id": uid, **({"device_id": device_id} if device_id else {}),
                "source": source, "ref_id": str(ref_id),
                "baseline": baseline, "baseline_at": baseline_at,
                "created_at": at_iso,
                "due_at": watchdog.due_at(at_iso), "expires_at": watchdog.expired_at(at_iso),
                "status": "pending", "notified": False,
            })
            created += 1
        except Exception:
            pass  # indice unico su (source, ref_id): esiste gia', nulla da fare

    async for run in db.autopilot_runs.find(
            {"status": "done", "completed_at": {"$gte": cutoff}}, {"_id": 1, "user_id": 1,
                                                                   "device_id": 1, "after": 1,
                                                                   "completed_at": 1}):
        ref = str(run["_id"])
        if await db.perf_watchdogs.find_one({"source": "autopilot", "ref_id": ref}, {"_id": 1}):
            continue
        # Auto-Pilot misura gia' l'health subito dopo l'intervento: e' la baseline giusta.
        score = (run.get("after") or {}).get("score")
        at = run["completed_at"]
        if not isinstance(score, (int, float)):
            score, at2 = await _watchdog_baseline(run["user_id"], run.get("device_id"), at)
            at = at2 or at
        if score:
            await _add(run["user_id"], run.get("device_id"), "autopilot", ref,
                       run["completed_at"], float(score), at)

    async for sess in db.lab_sessions.find(
            {"status": "completed", "finished_at": {"$gte": cutoff}},
            {"_id": 0, "session_id": 1, "user_id": 1, "device_id": 1, "finished_at": 1}):
        ref = sess.get("session_id")
        if not ref or await db.perf_watchdogs.find_one({"source": "lab", "ref_id": ref}, {"_id": 1}):
            continue
        score, at = await _watchdog_baseline(sess["user_id"], sess.get("device_id"), sess["finished_at"])
        if score:
            await _add(sess["user_id"], sess.get("device_id"), "lab", ref,
                       sess["finished_at"], score, at)
    return created


async def scheduled_perf_watchdog():
    """Verifica differita degli interventi: il boost ha tenuto, o il PC sta peggio?

    Auto-Pilot e Laboratorio misurano l'effetto nell'istante in cui applicano i
    tweak. Questo job torna a guardare 48h dopo, quando l'effetto e' quello vero.
    """
    import push
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    now_iso_str = now.isoformat()
    try:
        created = await _watchdog_create_missing(now)
    except Exception as exc:
        logger.warning("creazione watchdog fallita: %s", exc)
        created = 0

    evaluated = regressed = 0
    cur = db.perf_watchdogs.find({"status": "pending", "due_at": {"$lte": now_iso_str}})
    async for wd in cur:
        try:
            q = {"user_id": wd["user_id"], "created_at": {"$gt": wd["created_at"]}}
            if wd.get("device_id"):
                q["device_id"] = wd["device_id"]
            rows = await db.health_history.find(q, {"_id": 0, "score": 1}).to_list(50)
            verdict = watchdog.evaluate(wd.get("baseline"), [r.get("score") for r in rows])

            if verdict["status"] == "waiting":
                if (wd.get("expires_at") or "") <= now_iso_str:
                    await db.perf_watchdogs.update_one(
                        {"_id": wd["_id"]},
                        {"$set": {"status": "expired", "evaluated_at": now_iso_str}})
                continue

            await db.perf_watchdogs.update_one({"_id": wd["_id"]}, {"$set": {
                "status": verdict["status"], "delta_pct": verdict["delta_pct"],
                "observed": verdict["observed"], "samples": verdict["samples"],
                "evaluated_at": now_iso_str,
            }})
            evaluated += 1

            note = watchdog.notification_for(verdict, wd.get("source", ""), wd["baseline"])
            if note:
                regressed += 1
                await db.notifications.insert_one({
                    "user_id": wd["user_id"], "type": "regression",
                    "title": note["title"], "body": note["body"], "link": note["link"],
                    "created_at": now_iso_str, "read": False})
                try:
                    await push.send_push_to_user(db, wd["user_id"], {
                        "title": note["title"], "body": note["body"], "url": note["link"]})
                except Exception as exc:
                    logger.debug("push di regressione non inviata: %s", exc)
                await db.perf_watchdogs.update_one({"_id": wd["_id"]}, {"$set": {"notified": True}})
        except Exception as exc:
            logger.warning("valutazione watchdog fallita: %s", exc)
    if created or evaluated:
        logger.info("watchdog prestazioni: %s creati, %s valutati, %s regressioni", created, evaluated, regressed)


@app.on_event("startup")
async def startup():
    await _ensure_indexes()
    await seed_admin(db)
    scheduler.add_job(scheduled_price_check, "interval", minutes=45, id="price_check", replace_existing=True)
    scheduler.add_job(scheduled_trial_reminders, "cron", hour=9, minute=0, id="trial_reminders", replace_existing=True)
    scheduler.add_job(scheduled_streak_reminders, "cron", hour=17, minute=0, id="streak_reminders", replace_existing=True)
    scheduler.add_job(scheduled_prune_health_history, "cron", hour=4, minute=30, id="prune_health_history", replace_existing=True)
    scheduler.add_job(scheduled_perf_watchdog, "cron", hour=6, minute=15, id="perf_watchdog", replace_existing=True)
    scheduler.start()
    # Discord: annuncia release nuove (non-blocking se webhook non configurato)
    try:
        from services.release_announcer import announce_new_releases
        posted = await announce_new_releases()
        if posted:
            logger.info("Discord: announced %d new release(s)", posted)
    except Exception as e:
        logger.warning("Release announcer failed: %s", e)
    logger.info("FrameForge started")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)
    client.close()
