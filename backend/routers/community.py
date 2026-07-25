"""
Community router: changelog + feedback rapido.

Endpoints:
  GET  /api/changelog                -> lista release (dal file JSON)
  GET  /api/changelog/status         -> {unseen_count, last_seen_version}
  POST /api/changelog/mark-seen      -> marca l'ultima versione come vista
  POST /api/feedback                 -> registra un feedback e (se configurato) invia su Discord webhook
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import db, now_iso

logger = logging.getLogger("boostpc.community")

_CHANGELOG_PATH = Path(__file__).parent.parent / "data" / "changelog.json"


def _load_changelog() -> list:
    try:
        return json.loads(_CHANGELOG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("changelog.json missing at %s", _CHANGELOG_PATH)
        return []


def _latest_version() -> Optional[str]:
    data = _load_changelog()
    return data[0]["version"] if data else None


class FeedbackInput(BaseModel):
    kind: str = Field(..., pattern=r"^(bug|idea|other)$")
    message: str = Field(..., min_length=5, max_length=4000)
    page: Optional[str] = Field(None, max_length=200)
    screenshot: Optional[str] = Field(None, max_length=2_000_000)  # base64 data URL, ~1.5MB


async def _send_discord_webhook(webhook_url: str, payload: dict, screenshot: Optional[str] = None):
    """Best-effort webhook dispatch. Non-blocking failures logged, not raised."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            files = None
            data = None
            if screenshot and screenshot.startswith("data:image/"):
                # split header/base64 body
                try:
                    header, b64 = screenshot.split(",", 1)
                    mime = header.split(";")[0].replace("data:", "")
                    ext = "png" if "png" in mime else ("jpg" if "jpeg" in mime else "bin")
                    import base64 as _b64
                    binary = _b64.b64decode(b64)
                    files = {"file": (f"screenshot.{ext}", binary, mime)}
                    data = {"payload_json": json.dumps(payload)}
                except Exception:
                    files = None
            if files:
                r = await client.post(webhook_url, data=data, files=files)
            else:
                r = await client.post(webhook_url, json=payload)
            if r.status_code >= 400:
                logger.warning("discord webhook non-2xx: %s %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("discord webhook failed: %s", e)


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["community"])

    @r.get("/changelog")
    async def get_changelog():
        return {"releases": _load_changelog()}

    @r.get("/changelog/status")
    async def changelog_status(user: dict = Depends(get_current_user)):
        latest = _latest_version()
        seen_doc = await db.changelog_seen.find_one({"user_id": str(user["_id"])})
        last_seen = (seen_doc or {}).get("version")
        unseen = 0
        if latest and last_seen != latest:
            releases = _load_changelog()
            # count releases after last_seen (or all if never seen)
            if not last_seen:
                unseen = len(releases)
            else:
                for rel in releases:
                    if rel["version"] == last_seen:
                        break
                    unseen += 1
        return {"latest": latest, "last_seen": last_seen, "unseen": unseen}

    @r.post("/changelog/mark-seen")
    async def mark_seen(user: dict = Depends(get_current_user)):
        latest = _latest_version()
        if not latest:
            return {"ok": True, "version": None}
        await db.changelog_seen.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"version": latest, "updated_at": now_iso()}},
            upsert=True,
        )
        return {"ok": True, "version": latest}

    @r.post("/feedback")
    async def submit_feedback(payload: FeedbackInput, user: dict = Depends(get_current_user)):
        doc = {
            "user_id": str(user["_id"]),
            "user_email": user.get("email"),
            "kind": payload.kind,
            "message": payload.message.strip(),
            "page": payload.page or "",
            "has_screenshot": bool(payload.screenshot),
            "created_at": now_iso(),
        }
        try:
            await db.feedback.insert_one({**doc})
        except Exception as e:
            logger.error("feedback insert failed: %s", e)
            raise HTTPException(500, "Errore salvataggio feedback")

        webhook = os.environ.get("DISCORD_WEBHOOK_FEEDBACK", "").strip()
        if webhook:
            emoji = {"bug": ":bug:", "idea": ":bulb:", "other": ":speech_balloon:"}.get(payload.kind, ":speech_balloon:")
            embed = {
                "title": f"{emoji} Feedback: {payload.kind.upper()}",
                "description": payload.message[:3800],
                "color": 0xE5FF00 if payload.kind == "idea" else (0xFF3B30 if payload.kind == "bug" else 0x00E0FF),
                "fields": [
                    {"name": "User", "value": user.get("email", "?"), "inline": True},
                    {"name": "Plan", "value": user.get("plan", "starter"), "inline": True},
                    {"name": "Page", "value": payload.page or "-", "inline": True},
                ],
                "timestamp": now_iso(),
            }
            await _send_discord_webhook(webhook, {"embeds": [embed]}, payload.screenshot)
        return {"ok": True}

    return r
