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
    # Auto-detect preview: la pod di preview su Emergent ha HOSTNAME che inizia
    # con "agent-env-" (es. agent-env-7dc8dffb-...). In produzione il pattern
    # e' diverso, quindi l'announcer parte solo li'. Override manuale:
    # - RELEASE_ANNOUNCER_ENABLED=true  -> forza ON (utile per test in preview)
    # - RELEASE_ANNOUNCER_ENABLED=false -> forza OFF ovunque
    manual = os.environ.get("RELEASE_ANNOUNCER_ENABLED", "").strip().lower()
    if manual in ("0", "false", "no", "off"):
        logger.info("Release announcer forzato OFF via RELEASE_ANNOUNCER_ENABLED, skip")
        return 0
    if manual not in ("1", "true", "yes", "on"):
        # Nessun override esplicito: usa auto-detect
        hostname = os.environ.get("HOSTNAME", "")
        if hostname.startswith("agent-env-"):
            logger.info("Release announcer disabilitato in preview (HOSTNAME=%s), skip", hostname)
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



async def announce_release_by_version(version: str, force: bool = False) -> tuple[bool, str]:
    """Annuncia una release specifica dal manifest. Se force=True bypassa il check
    'gia annunciata' (utile per ri-annunci manuali). Ritorna (ok, message)."""
    if not MANIFEST.exists():
        return False, "Manifest releases.json non trovato"
    try:
        releases = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Manifest non parsabile: {e}"
    r = next((x for x in releases if x.get("version") == version), None)
    if not r:
        available = ", ".join(x.get("version", "?") for x in releases)
        return False, f"Versione {version} non nel manifest. Disponibili: {available}"
    already = await db.announced_releases.find_one({"_id": version})
    if already and not force:
        return False, f"Versione {version} gia annunciata in passato. Usa force=true per ri-annunciare"
    title = r.get("title") or f"FrameForge {version}"
    notes_md = f"**{title}**\n\n{r.get('notes_md', '')}"
    url = r.get("url") or "https://forgefps.dev/changelog"
    ok = await post_release(version=version, notes_md=notes_md, url=url)
    if not ok:
        return False, "Post su Discord fallito (webhook non configurato o errore Discord)"
    if not already:
        await db.announced_releases.insert_one({
            "_id": version,
            "announced_at": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "date": r.get("date", ""),
        })
    return True, f"Release {version} annunciata correttamente"
