"""Release announcer: al boot legge /app/data/releases.json e posta sul canale
Discord #changelog-automatico ogni release non ancora annunciata.

Marca ogni release come "annunciata" in `announced_releases` (idempotente).
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from database import db
from services.discord_webhooks import post_release

logger = logging.getLogger("boostpc.release_announcer")

MANIFEST = Path("/app/data/releases.json")


async def announce_new_releases() -> int:
    """Ritorna il numero di release annunciate in questo run."""
    # Ambiente-safe: nel preview lasciamo l'announcer disabilitato per evitare
    # duplicati (prod e preview userebbero lo stesso webhook con DB Mongo distinti).
    if os.environ.get("RELEASE_ANNOUNCER_ENABLED", "true").strip().lower() in ("0", "false", "no", "off"):
        logger.info("Release announcer disabled via RELEASE_ANNOUNCER_ENABLED, skip")
        return 0
    if not MANIFEST.exists():
        logger.info("Release manifest not found at %s, skip", MANIFEST)
        return 0
    try:
        releases = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to parse release manifest: %s", e)
        return 0

    if not isinstance(releases, list):
        return 0

    posted = 0
    for r in releases:
        version = r.get("version")
        if not version:
            continue
        already = await db.announced_releases.find_one({"_id": version})
        if already:
            continue
        title = r.get("title") or f"FrameForge {version}"
        notes_md = f"**{title}**\n\n{r.get('notes_md', '')}"
        url = r.get("url") or "https://forgefps.dev/changelog"
        ok = await post_release(version=version, notes_md=notes_md, url=url)
        if ok:
            await db.announced_releases.insert_one({
                "_id": version,
                "announced_at": datetime.now(timezone.utc).isoformat(),
                "title": title,
                "date": r.get("date", ""),
            })
            posted += 1
            logger.info("Announced release %s on Discord", version)
        else:
            logger.warning("Failed to announce release %s (webhook not configured or Discord error)", version)
    return posted
