"""Discord OAuth2 account linking + status endpoints.

Flow:
- GET /api/discord/connect -> genera state, salva in DB, redirect a Discord authorize
- GET /api/discord/callback?code=&state= -> exchange code, chiama /users/@me, memorizza
  discord_user_id nell'utente, aggiunge al server via guilds.join, assegna ruolo se configurato
- GET /api/discord/status -> stato del collegamento per l'utente corrente
- DELETE /api/discord/disconnect -> rimuove il legame lato DB (non rimuove dal server Discord)
"""
import base64
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from database import db

logger = logging.getLogger("boostpc.discord")

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_ME_URL = "https://discord.com/api/users/@me"
DISCORD_API = "https://discord.com/api/v10"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _redirect_uri_for(request) -> str:
    """Ritorna il redirect_uri da usare nel flow OAuth.
    Priorita': env var esplicita (per test/backend headless) -> host del request (auto-detect).
    Forza https:// perche' dietro proxy Emergent il traffico interno arriva su http.
    """
    env_uri = _env("DISCORD_REDIRECT_URI")
    if env_uri:
        return env_uri
    scheme = request.headers.get("x-forwarded-proto") or "https"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    return f"{scheme}://{host}/api/discord/callback"


def _frontend_url_for(request) -> str:
    env_url = _env("FRONTEND_URL")
    if env_url:
        return env_url.rstrip("/")
    scheme = request.headers.get("x-forwarded-proto") or "https"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    return f"{scheme}://{host}"


def _frontend_url() -> str:
    return _env("FRONTEND_URL", "https://forgefps.dev").rstrip("/")


def _authorize_url(state: str, redirect_uri: str) -> str:
    params = {
        "response_type": "code",
        "client_id": _env("DISCORD_CLIENT_ID"),
        "scope": "identify guilds.join",
        "state": state,
        "redirect_uri": redirect_uri,
        "prompt": "consent",
    }
    return f"{DISCORD_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def _exchange_code(code: str, redirect_uri: str) -> dict:
    cid = _env("DISCORD_CLIENT_ID")
    csecret = _env("DISCORD_CLIENT_SECRET")
    basic = base64.b64encode(f"{cid}:{csecret}".encode()).decode()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
        if r.status_code != 200:
            logger.warning("Discord token exchange failed: %s %s", r.status_code, r.text)
            raise HTTPException(400, detail="Discord token exchange failed")
        return r.json()


async def _fetch_discord_user(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(DISCORD_ME_URL, headers={"Authorization": f"Bearer {access_token}"})
        if r.status_code != 200:
            raise HTTPException(400, detail="Discord user fetch failed")
        return r.json()


async def _add_to_guild(discord_user_id: str, access_token: str, user_plan: str = "free") -> None:
    guild_id = _env("DISCORD_GUILD_ID")
    bot_token = _env("DISCORD_BOT_TOKEN")
    role_id = _env("DISCORD_ROLE_BOOSTED_ID")
    role_pro_id = _env("DISCORD_ROLE_PRO")
    if not (guild_id and bot_token):
        logger.info("Guild add skipped: missing DISCORD_GUILD_ID or DISCORD_BOT_TOKEN")
        return
    # Ruoli da assegnare al join: Boosted PC sempre; Pro se piano compatibile
    roles_to_add = [r for r in [role_id] if r]
    if role_pro_id and (user_plan or "").strip().lower() in ("pro", "creator"):
        roles_to_add.append(role_pro_id)
    payload: dict = {"access_token": access_token}
    if roles_to_add:
        payload["roles"] = roles_to_add
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }
    url = f"{DISCORD_API}/guilds/{guild_id}/members/{discord_user_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.put(url, json=payload, headers=headers)
        # 201 = added, 204 = already in guild, altri = errore ma non blocchiamo il link
        if r.status_code not in (201, 204):
            logger.warning("Discord guild add returned %s: %s", r.status_code, r.text)
            return
        # Idempotente: se era gia' nel guild, assegno singolarmente i ruoli
        if r.status_code == 204:
            for rid in roles_to_add:
                role_url = f"{DISCORD_API}/guilds/{guild_id}/members/{discord_user_id}/roles/{rid}"
                rr = await client.put(role_url, headers={"Authorization": f"Bot {bot_token}"})
                if rr.status_code not in (204, 200):
                    logger.warning("Discord role %s assign returned %s: %s", rid, rr.status_code, rr.text)


def build(get_current_user):
    router = APIRouter(prefix="/api/discord", tags=["discord"])

    # Cache in-memory per ridurre chiamate all'API Discord (5 min)
    _live_cache = {"data": None, "at": 0.0}

    @router.get("/live-stats")
    async def discord_live_stats():
        """Statistiche live del server Discord (endpoint pubblico, no auth).
        Fonte primaria: widget.json (richiede widget abilitato in Discord).
        Ritorna sempre 200: se widget non abilitato/errore, restituisce enabled=false.
        Cache 5 min in-memory.
        """
        import time
        now = time.time()
        if _live_cache["data"] and (now - _live_cache["at"]) < 300:
            return _live_cache["data"]

        guild_id = _env("DISCORD_GUILD_ID")
        invite = _env("DISCORD_INVITE_URL")
        result = {"enabled": False, "presence_count": 0, "invite_url": invite}
        if guild_id:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(f"https://discord.com/api/guilds/{guild_id}/widget.json")
                if r.status_code == 200:
                    data = r.json()
                    result = {
                        "enabled": True,
                        "presence_count": data.get("presence_count", 0),
                        "instant_invite": data.get("instant_invite") or invite,
                        "invite_url": invite or data.get("instant_invite"),
                        "name": data.get("name", ""),
                    }
                else:
                    logger.info("Discord widget.json returned %s (widget likely disabled)", r.status_code)
            except Exception as e:
                logger.warning("Discord live-stats fetch failed: %s", e)

        _live_cache["data"] = result
        _live_cache["at"] = now
        return result



    @router.get("/connect")
    async def connect_discord(request: Request, user: dict = Depends(get_current_user)):
        if not _env("DISCORD_CLIENT_ID"):
            raise HTTPException(503, detail="Discord integration not configured")
        state = secrets.token_urlsafe(32)
        redirect_uri = _redirect_uri_for(request)
        await db.discord_oauth_states.insert_one({
            "_id": state,
            "user_id": str(user["_id"]),
            "redirect_uri": redirect_uri,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        })
        return RedirectResponse(_authorize_url(state, redirect_uri), status_code=307)

    @router.get("/callback")
    async def discord_callback(
        request: Request,
        code: str = Query(...),
        state: str = Query(...),
        user: dict = Depends(get_current_user),
    ):
        try:
            await db.discord_oauth_states.create_index("expires_at", expireAfterSeconds=0)
        except Exception:
            pass
        state_doc = await db.discord_oauth_states.find_one_and_delete(
            {"_id": state, "user_id": str(user["_id"])}
        )
        if not state_doc:
            raise HTTPException(400, detail="Invalid or expired state")

        # Ri-usa lo stesso redirect_uri usato nel /connect (OAuth requirement)
        redirect_uri = state_doc.get("redirect_uri") or _redirect_uri_for(request)
        token = await _exchange_code(code, redirect_uri)
        me = await _fetch_discord_user(token["access_token"])

        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "discord_user_id": me["id"],
                "discord_username": me.get("global_name") or me.get("username") or "",
                "discord_avatar": me.get("avatar") or "",
                "discord_linked_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        try:
            user_plan = (user.get("plan") or "free")
            await _add_to_guild(me["id"], token["access_token"], user_plan=user_plan)
        except Exception as e:
            logger.warning("Guild add failed but link saved: %s", e)

        frontend = _frontend_url_for(request)
        return RedirectResponse(f"{frontend}/app/account?discord=linked", status_code=307)

    @router.get("/status")
    async def discord_status(user: dict = Depends(get_current_user)):
        invite = _env("DISCORD_INVITE_URL")
        doc = await db.users.find_one({"_id": user["_id"]}, {"discord_user_id": 1, "discord_username": 1, "discord_avatar": 1, "discord_linked_at": 1})
        if not doc or not doc.get("discord_user_id"):
            return {"linked": False, "configured": bool(_env("DISCORD_CLIENT_ID")), "invite_url": invite}
        return {
            "linked": True,
            "configured": True,
            "user_id": doc.get("discord_user_id"),
            "username": doc.get("discord_username", ""),
            "avatar": doc.get("discord_avatar", ""),
            "linked_at": doc.get("discord_linked_at", ""),
            "invite_url": invite,
        }

    @router.delete("/disconnect")
    async def discord_disconnect(user: dict = Depends(get_current_user)):
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$unset": {
                "discord_user_id": "", "discord_username": "", "discord_avatar": "", "discord_linked_at": "",
            }},
        )
        return {"ok": True}

    @router.post("/share-score")
    async def share_score(payload: dict, user: dict = Depends(get_current_user)):
        """Posta il proprio Health Score / benchmark su Discord.
        Body: { kind: 'health' | 'benchmark', score: int, metrics?: dict, note?: str }
        """
        from services.discord_webhooks import post_bot_message
        channel_id = _env("DISCORD_CHANNEL_SCORES")
        if not channel_id:
            raise HTTPException(503, detail="Share channel not configured")
        # Serve account Discord collegato
        udoc = await db.users.find_one({"_id": user["_id"]}, {"discord_user_id": 1, "discord_username": 1, "discord_avatar": 1, "name": 1, "email": 1})
        if not udoc or not udoc.get("discord_user_id"):
            raise HTTPException(400, detail="Discord not linked")

        kind = (payload.get("kind") or "health").lower()
        score = int(payload.get("score") or 0)
        note = (payload.get("note") or "").strip()[:200]
        metrics = payload.get("metrics") or {}

        display_name = udoc.get("discord_username") or udoc.get("name") or (udoc.get("email", "").split("@")[0]) or "un gamer"
        avatar_hash = udoc.get("discord_avatar")
        avatar_url = None
        if avatar_hash:
            avatar_url = f"https://cdn.discordapp.com/avatars/{udoc['discord_user_id']}/{avatar_hash}.png?size=128"

        color = 0x00FF66 if score >= 75 else (0xFFAA00 if score >= 50 else 0xFF3355)
        if kind == "benchmark":
            title = f"{display_name}: benchmark {score}/100"
            desc = "e il tuo PC quanto fa?"
            fields = []
            if metrics.get("dpc_us"): fields.append({"name": "DPC latency", "value": f"{metrics['dpc_us']} μs", "inline": True})
            if metrics.get("iops"): fields.append({"name": "Disk IOPS", "value": str(metrics["iops"]), "inline": True})
            if metrics.get("jitter_ms"): fields.append({"name": "Jitter", "value": f"{metrics['jitter_ms']} ms", "inline": True})
        else:
            title = f"{display_name}: Health Score {score}/100"
            desc = "boost fatto con FrameForge - e il tuo PC?"
            fields = []

        embed = {
            "title": title,
            "description": (note + "\n\n" + desc) if note else desc,
            "color": color,
            "url": "https://forgefps.dev",
            "footer": {"text": "forgefps.dev - misuralo anche tu"},
        }
        if fields:
            embed["fields"] = fields
        if avatar_url:
            embed["thumbnail"] = {"url": avatar_url}

        ok = await post_bot_message(channel_id, embed)
        if not ok:
            raise HTTPException(500, detail="Failed to post on Discord")
        return {"ok": True}

    return router
