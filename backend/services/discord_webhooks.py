"""Outbound Discord webhooks (channel-specific POST endpoints).

Uso:
    from services.discord_webhooks import post_release, post_price_drop
    await post_release("v0.6.2", "Nuova GUI Edge + tour interattivo")

Le URL webhook sono in .env e non vanno mai esposte al frontend.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("boostpc.discord_webhooks")

COLOR_ACCENT = 0xE5FF00
COLOR_INFO = 0x00E0FF
COLOR_OK = 0x00FF66
COLOR_WARN = 0xFFAA00


async def post_bot_message(channel_id: str, embed: dict, content: str = "") -> bool:
    """Posta un messaggio nel canale specificato usando il bot token.
    Piu' pulito dei webhook perche' appare come messaggio del bot ufficiale (con avatar/username).
    """
    bot_token = _env("DISCORD_BOT_TOKEN")
    if not (channel_id and bot_token):
        return False
    payload = {"embeds": [embed]}
    if content:
        payload["content"] = content[:2000]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                json=payload,
                headers={"Authorization": f"Bot {bot_token}"},
            )
            if r.status_code >= 400:
                logger.warning("post_bot_message %s -> %s: %s", channel_id, r.status_code, r.text[:200])
                return False
            return True
    except Exception as e:
        logger.warning("post_bot_message failed: %s", e)
        return False


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


async def _post(url: str, payload: dict) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            if r.status_code >= 400:
                logger.warning("Discord webhook %s -> %s: %s", url[:60], r.status_code, r.text[:200])
                return False
            return True
    except Exception as e:
        logger.warning("Discord webhook failed: %s", e)
        return False


async def post_release(version: str, notes_md: str, url: Optional[str] = None) -> bool:
    """Nuova release pubblicata: manda embed nel canale changelog."""
    hook = _env("DISCORD_WEBHOOK_CHANGELOG")
    if not hook:
        return False
    lines = notes_md.strip().splitlines()
    desc = "\n".join(lines[:20])  # cap
    payload = {
        "username": "FrameForge Releases",
        "embeds": [{
            "title": f"FrameForge {version} rilasciato",
            "description": desc[:3800],
            "color": COLOR_ACCENT,
            "url": url or "https://forgefps.dev/changelog",
            "footer": {"text": "forgefps.dev/changelog"},
        }],
    }
    return await _post(hook, payload)


async def post_price_drop(product_name: str, old_price: float, new_price: float, product_url: Optional[str] = None) -> bool:
    """Alert calo prezzo su un prodotto seguito."""
    hook = _env("DISCORD_WEBHOOK_PRICES")
    if not hook:
        return False
    delta = old_price - new_price
    pct = (delta / old_price * 100) if old_price else 0
    payload = {
        "username": "FrameForge Prices",
        "embeds": [{
            "title": f"Calo prezzo: {product_name}",
            "description": f"**{new_price:.2f} EUR** (prima {old_price:.2f} EUR, -{pct:.1f}%)",
            "color": COLOR_OK,
            "url": product_url or "",
        }],
    }
    return await _post(hook, payload)


async def post_milestone(text: str, subtitle: str = "") -> bool:
    """Milestone community (100 utenti, 1000 boost, ecc.)."""
    hook = _env("DISCORD_WEBHOOK_CHANGELOG")
    if not hook:
        return False
    payload = {
        "username": "FrameForge",
        "embeds": [{
            "title": text,
            "description": subtitle or "",
            "color": COLOR_INFO,
        }],
    }
    return await _post(hook, payload)


async def post_raw(webhook_env_name: str, content: str) -> bool:
    """Fallback: manda un messaggio grezzo al webhook indicato."""
    hook = _env(webhook_env_name)
    return await _post(hook, {"content": content[:2000]})
