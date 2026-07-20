"""Magic-link ('Continue on mobile') sub-routes extracted from auth.py.
Provides: /magic-link (create), /consume-magic, /magic-status/{token}.
Contract identical to previous inline definitions (same paths, payloads, responses,
cookies, rate-limiting).
"""
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response


def register_magic_routes(router: APIRouter, db, get_current_user, set_auth_cookies,
                          create_access_token, create_refresh_token,
                          public_user, parse_device_label):
    """Attach magic-link endpoints to the given router."""

    @router.post("/magic-link")
    async def create_magic_link(user: dict = Depends(get_current_user)):
        """Generate a one-time 5-minute token for 'Continue on mobile' QR flow.
        Rate-limited to 5 per user per hour."""
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        recent_count = await db.magic_tokens.count_documents({
            "user_id": str(user["_id"]),
            "created_at": {"$gte": one_hour_ago},
        })
        if recent_count >= 5:
            raise HTTPException(status_code=429, detail="Too many magic links. Try again in an hour.")
        token = secrets.token_urlsafe(32)
        ttl_seconds = 300  # 5 minutes
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        await db.magic_tokens.insert_one({
            "token": token,
            "user_id": str(user["_id"]),
            "expires_at": expires_at,
            "created_at": now.isoformat(),
            "used": False,
        })
        return {"token": token, "expires_in_seconds": ttl_seconds}

    @router.post("/consume-magic")
    async def consume_magic_link(data: dict, request: Request, response: Response):
        """Consume a magic link token, set auth cookies, return user profile.
        Single-use, 5-minute TTL enforced. Records device info for cross-device notification."""
        token = (data or {}).get("token", "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="Missing token")
        ua = request.headers.get("user-agent", "")
        device_label = parse_device_label(ua)
        rec = await db.magic_tokens.find_one_and_update(
            {"token": token, "used": False},
            {"$set": {
                "used": True,
                "used_at": datetime.now(timezone.utc).isoformat(),
                "device_ua": ua[:300],
                "device_label": device_label,
            }},
        )
        if not rec:
            raise HTTPException(status_code=401, detail="Link expired or already used")
        try:
            expires_at = datetime.fromisoformat(rec["expires_at"].replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Link expired")
        user = await db.users.find_one({"_id": ObjectId(rec["user_id"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        uid = str(user["_id"])
        set_auth_cookies(response,
                         create_access_token(uid, user["email"]),
                         create_refresh_token(uid))
        return public_user(user)

    @router.get("/magic-status/{token}")
    async def magic_status(token: str):
        """Public: check if a magic token has been consumed. Used by desktop GUI and
        web modal to detect cross-device handoff and notify the originating device.
        Returns only status + device label, never user identity."""
        token = (token or "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="Missing token")
        rec = await db.magic_tokens.find_one(
            {"token": token},
            {"used": 1, "used_at": 1, "device_label": 1, "expires_at": 1},
        )
        if not rec:
            raise HTTPException(status_code=404, detail="Token not found")
        expired = False
        try:
            expired = datetime.fromisoformat(rec["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc)
        except Exception:
            expired = True
        return {
            "used": bool(rec.get("used")),
            "used_at": rec.get("used_at"),
            "device_label": rec.get("device_label") or "",
            "expired": expired,
        }
