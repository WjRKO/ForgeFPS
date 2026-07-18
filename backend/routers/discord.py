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
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from database import db

logger = logging.getLogger("boostpc.discord")

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_ME_URL = "https://discord.com/api/users/@me"
DISCORD_API = "https://discord.com/api/v10"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _frontend_url() -> str:
    return _env("FRONTEND_URL", "https://forgefps.dev").rstrip("/")


def _authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": _env("DISCORD_CLIENT_ID"),
        "scope": "identify guilds.join",
        "state": state,
        "redirect_uri": _env("DISCORD_REDIRECT_URI"),
        "prompt": "consent",
    }
    return f"{DISCORD_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def _exchange_code(code: str) -> dict:
    cid = _env("DISCORD_CLIENT_ID")
    csecret = _env("DISCORD_CLIENT_SECRET")
    basic = base64.b64encode(f"{cid}:{csecret}".encode()).decode()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _env("DISCORD_REDIRECT_URI"),
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


async def _add_to_guild(discord_user_id: str, access_token: str) -> None:
    guild_id = _env("DISCORD_GUILD_ID")
    bot_token = _env("DISCORD_BOT_TOKEN")
    role_id = _env("DISCORD_ROLE_BOOSTED_ID")
    if not (guild_id and bot_token):
        logger.info("Guild add skipped: missing DISCORD_GUILD_ID or DISCORD_BOT_TOKEN")
        return
    payload = {"access_token": access_token}
    if role_id:
        payload["roles"] = [role_id]
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
        # Idempotente: se gia' era nel guild, assegno il ruolo
        if role_id and r.status_code == 204:
            role_url = f"{DISCORD_API}/guilds/{guild_id}/members/{discord_user_id}/roles/{role_id}"
            rr = await client.put(role_url, headers={"Authorization": f"Bot {bot_token}"})
            if rr.status_code not in (204, 200):
                logger.warning("Discord role assign returned %s: %s", rr.status_code, rr.text)


def build(get_current_user):
    router = APIRouter(prefix="/api/discord", tags=["discord"])

    @router.get("/connect")
    async def connect_discord(user: dict = Depends(get_current_user)):
        if not _env("DISCORD_CLIENT_ID"):
            raise HTTPException(503, detail="Discord integration not configured")
        state = secrets.token_urlsafe(32)
        await db.discord_oauth_states.insert_one({
            "_id": state,
            "user_id": str(user["_id"]),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        })
        return RedirectResponse(_authorize_url(state), status_code=307)

    @router.get("/callback")
    async def discord_callback(
        code: str = Query(...),
        state: str = Query(...),
        user: dict = Depends(get_current_user),
    ):
        # Ensure TTL index (idempotente, no-op se gia' presente)
        try:
            await db.discord_oauth_states.create_index("expires_at", expireAfterSeconds=0)
        except Exception:
            pass
        state_doc = await db.discord_oauth_states.find_one_and_delete(
            {"_id": state, "user_id": str(user["_id"])}
        )
        if not state_doc:
            raise HTTPException(400, detail="Invalid or expired state")

        token = await _exchange_code(code)
        me = await _fetch_discord_user(token["access_token"])

        # Salva legame nel documento utente
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "discord_user_id": me["id"],
                "discord_username": me.get("global_name") or me.get("username") or "",
                "discord_avatar": me.get("avatar") or "",
                "discord_linked_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        # Aggiungi al guild + eventuale ruolo (best-effort)
        try:
            await _add_to_guild(me["id"], token["access_token"])
        except Exception as e:
            logger.warning("Guild add failed but link saved: %s", e)

        # Redirect al frontend con banner successo
        return RedirectResponse(f"{_frontend_url()}/app/account?discord=linked", status_code=307)

    @router.get("/status")
    async def discord_status(user: dict = Depends(get_current_user)):
        doc = await db.users.find_one({"_id": user["_id"]}, {"discord_user_id": 1, "discord_username": 1, "discord_avatar": 1, "discord_linked_at": 1})
        if not doc or not doc.get("discord_user_id"):
            return {"linked": False, "configured": bool(_env("DISCORD_CLIENT_ID"))}
        return {
            "linked": True,
            "configured": True,
            "user_id": doc.get("discord_user_id"),
            "username": doc.get("discord_username", ""),
            "avatar": doc.get("discord_avatar", ""),
            "linked_at": doc.get("discord_linked_at", ""),
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

    return router
